from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APITimeoutError

from pea_app.devonthink_handoff import (
    DevonThinkDuplicateError,
    DevonThinkError,
    DevonThinkSecurityError,
    DevonThinkService,
    ImportReview,
    format_duplicate_review_message,
    prepare_handoff,
    prepare_remarkable_handoff,
)
from pea_app.models import ActionItem, MeetingMinutes, TopicSummary, get_model_profile
from pea_app.openai_minutes import (
    SYSTEM_INSTRUCTIONS,
    MinutesGenerationError,
    OpenAIMinutesService,
)
from pea_app.secrets import resolve_openai_api_key


def sample_minutes() -> MeetingMinutes:
    return MeetingMinutes(
        title="Training coordination meeting",
        meeting_date="2026-08-06",
        participants=["Alex Morgan", "Sam Patel"],
        topics=[TopicSummary(topic="Course planning", summary=["The draft plan was reviewed."])],
        decisions=["The draft will be retained for the pilot."],
        action_items=[ActionItem(action="Review the source data.", owner="Alex")],
        verification_notes=["Confirm the course date against the source."],
    )


def test_economy_profile_uses_luna_with_low_reasoning() -> None:
    profile = get_model_profile("economy")
    assert profile.model == "gpt-5.6-luna"
    assert profile.reasoning_effort == "low"


def test_prompt_requires_formal_british_english() -> None:
    assert "formal British English" in SYSTEM_INSTRUCTIONS
    assert "British spelling" in SYSTEM_INSTRUCTIONS
    assert "Always provide the meeting" in SYSTEM_INSTRUCTIONS
    assert "Every action item must have an owner" in SYSTEM_INSTRUCTIONS


def test_markdown_includes_date_participants_and_action_owners() -> None:
    markdown = sample_minutes().to_markdown()
    assert "**Date:** 2026-08-06" in markdown
    assert "## Participants\n\n- Alex Morgan\n- Sam Patel" in markdown
    assert "| Topic | Summary |" in markdown
    assert "| Course planning | - The draft plan was reviewed. |" in markdown
    assert "| Action | Owner | Due date |" in markdown
    assert "| Review the source data. | Alex | Not stated |" in markdown


def test_html_preview_renders_complete_structured_minutes() -> None:
    minutes = sample_minutes()
    minutes.topics.append(
        TopicSummary(topic="Licensing <review>", summary=["Check A & B.", "Record outcome."])
    )
    minutes.action_items.append(
        ActionItem(action="Confirm the final plan.", owner="Sam", due_date="2026-08-12")
    )

    rendered = minutes.to_html()

    assert rendered.count("<tr>") == 6
    assert "Licensing &lt;review&gt;" in rendered
    assert "Check A &amp; B." in rendered
    assert "Confirm the final plan." in rendered
    assert "2026-08-12" in rendered


def test_minutes_schema_requires_date_participants_and_action_owner() -> None:
    minutes_required = set(MeetingMinutes.model_json_schema()["required"])
    action_required = set(ActionItem.model_json_schema()["required"])

    assert {"meeting_date", "participants"} <= minutes_required
    assert "owner" in action_required


def test_handoff_requires_source_reference_and_is_stable() -> None:
    markdown = sample_minutes().to_markdown()
    first = prepare_handoff(markdown, "plaud:123")
    second = prepare_handoff(markdown, "plaud:123")
    assert first.status == "awaiting_duplicate_check"
    assert first.title == "Training coordination meeting"
    assert first.source_url == "pea-source://plaud%3A123"
    assert first.content_fingerprint == second.content_fingerprint
    with pytest.raises(ValueError, match="source reference"):
        prepare_handoff(markdown, "")


def test_handoff_blocks_restricted_or_unknown_database() -> None:
    markdown = sample_minutes().to_markdown()
    with pytest.raises(DevonThinkSecurityError, match="Restricted"):
        prepare_handoff(markdown, "plaud:123", "Restricted")
    with pytest.raises(DevonThinkSecurityError, match="not authorised"):
        prepare_handoff(markdown, "plaud:123", "another-database")
    with pytest.raises(DevonThinkSecurityError, match="record type"):
        prepare_handoff(markdown, "plaud:123", record_kind="unknown")


def test_remarkable_handoff_targets_inbox_with_stable_provenance() -> None:
    handoff = prepare_remarkable_handoff(
        "  # Training sketch  ",
        "Reviewed handwritten notes.",
        "remarkdown:document-1",
    )

    assert handoff.title == "Training sketch"
    assert handoff.markdown.startswith("# Training sketch\n\n")
    assert handoff.target_database == "Inbox"
    assert handoff.destination == ""
    assert handoff.record_kind == "remarkable-note"
    assert handoff.source_url == "pea-source://remarkdown%3Adocument-1"


def test_minutes_archive_filters_metadata_before_reading_matching_text() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeSession:
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
            calls.append((name, arguments))
            if name == "get_databases":
                data: Any = [{"name": "Inbox", "uuid": "database"}]
            elif name == "search_records":
                data = {
                    "results": [
                        {
                            "uuid": "minutes-1",
                            "name": "Training review",
                            "tags": ["minutes", "pea-import"],
                            "additionDate": "2026-08-06T10:00:00+02:00",
                        },
                        {
                            "uuid": "untrusted",
                            "name": "Other document",
                            "tags": ["minutes"],
                            "additionDate": "2026-08-06T11:00:00+02:00",
                        },
                    ]
                }
            elif name == "get_record_text":
                data = {"text": "# Training review\n\nApproved Minutes."}
            return SimpleNamespace(isError=False, structuredContent=data, content=[])

    @asynccontextmanager
    async def factory():
        yield FakeSession()

    records = DevonThinkService(factory).load_minutes(
        "2026-08-03", "2026-08-10", "Inbox"
    )

    assert [record.uuid for record in records] == ["minutes-1"]
    assert records[0].source_reference == "devonthink:minutes-1"
    search = next(arguments for name, arguments in calls if name == "search_records")
    assert search["query"] == "tags:minutes added>=2026-08-03 added<2026-08-10"
    assert [args["uuid"] for name, args in calls if name == "get_record_text"] == [
        "minutes-1"
    ]


def test_duplicate_message_explains_multiple_title_matches() -> None:
    handoff = prepare_handoff(sample_minutes().to_markdown(), "plaud:123")
    review = ImportReview(
        handoff=handoff,
        database_uuid="database-id",
        database_name="Inbox",
        source_matches=(),
        title_matches=({"uuid": "first"}, {"uuid": "second"}),
    )

    message = format_duplicate_review_message(review)

    assert "because DEVONthink already contains 2 documents with the same title" in message
    assert "Title matches: 2" in message
    assert "amend the title to include the meeting date" in message


def test_api_key_prefers_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-environment-value")
    assert resolve_openai_api_key() == "sk-test-environment-value"


def test_service_uses_selected_model_and_store_false() -> None:
    minutes = sample_minutes()
    calls: list[dict[str, object]] = []

    class FakeResponses:
        def parse(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(
                output_parsed=minutes,
                usage=SimpleNamespace(input_tokens=100, output_tokens=50),
            )

    fake_client = SimpleNamespace(responses=FakeResponses())
    service = OpenAIMinutesService(
        client_factory=lambda **_: fake_client,
        api_key_resolver=lambda: "sk-test",
    )

    result = service.generate(
        "A short test transcript.",
        get_model_profile("economy"),
        "2026-08-06",
        "Speaker 1 is Alex Morgan.",
        "Alex Morgan leads the training planning work.",
    )

    assert result.minutes == minutes
    assert calls[0]["model"] == "gpt-5.6-luna"
    assert calls[0]["reasoning"] == {"effort": "low"}
    assert calls[0]["store"] is False
    assert calls[0]["max_output_tokens"] == 1_800
    user_content = calls[0]["input"][1]["content"]
    assert "Recording date: 2026-08-06" in user_content
    assert "Raw transcript\nA short test transcript." in user_content
    assert "Secondary PLAUD summary" in user_content
    assert "Speaker 1 is Alex Morgan." in user_content
    assert "User-approved contextual memory" in user_content
    assert "not evidence that a person attended" in user_content


@pytest.mark.parametrize("profile_key", ["standard", "quality"])
def test_medium_reasoning_profiles_receive_larger_bounded_output_allowance(
    profile_key: str,
) -> None:
    minutes = sample_minutes()
    calls: list[dict[str, object]] = []

    class FakeResponses:
        def parse(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(output_parsed=minutes, usage=None)

    service = OpenAIMinutesService(
        client_factory=lambda **_: SimpleNamespace(responses=FakeResponses()),
        api_key_resolver=lambda: "sk-test",
    )

    service.generate("A short test transcript.", get_model_profile(profile_key))

    assert calls[0]["max_output_tokens"] == 4_000


def test_timeout_error_is_presented_without_provider_request_content() -> None:
    class FakeResponses:
        def parse(self, **_: object) -> None:
            raise APITimeoutError(
                request=httpx.Request("POST", "https://api.openai.com/v1/responses")
            )

    service = OpenAIMinutesService(
        client_factory=lambda **_: SimpleNamespace(responses=FakeResponses()),
        api_key_resolver=lambda: "sk-test",
    )

    with pytest.raises(MinutesGenerationError, match="timed out") as error:
        service.generate("Private transcript content.", get_model_profile("quality"))

    assert error.value.category == "timeout"
    assert "Private transcript content" not in str(error.value)


class FakeDevonThinkSession:
    def __init__(self, responses: dict[str, list[Any]]) -> None:
        self.responses = {name: list(values) for name, values in responses.items()}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
        self.calls.append((name, arguments))
        value = self.responses[name].pop(0)
        if isinstance(value, SimpleNamespace):
            return value
        return SimpleNamespace(isError=False, structuredContent=value, content=[])


def session_factory(session: FakeDevonThinkSession):
    @asynccontextmanager
    async def factory():
        yield session

    return factory


def database_list(*names: str) -> list[dict[str, str]]:
    return [{"name": name, "uuid": f"uuid-{name}"} for name in names]


def test_devonthink_review_checks_source_and_title() -> None:
    handoff = prepare_handoff(sample_minutes().to_markdown(), "plaud:123")
    session = FakeDevonThinkSession(
        {
            "get_databases": [database_list("Inbox", "private")],
            "lookup_records": [{"count": 0, "results": []}, {"count": 0, "results": []}],
        }
    )

    review = DevonThinkService(session_factory(session)).review(handoff)

    assert review.is_clear
    assert review.database_uuid == "uuid-Inbox"
    assert session.calls[1] == (
        "lookup_records",
        {"database_uuid": "uuid-Inbox", "url": "pea-source://plaud%3A123"},
    )
    assert session.calls[2][1]["name"] == "Training coordination meeting"


def test_devonthink_stops_if_restricted_database_is_visible() -> None:
    handoff = prepare_handoff(sample_minutes().to_markdown(), "plaud:123")
    session = FakeDevonThinkSession(
        {"get_databases": [database_list("Inbox", "Restricted")]}
    )

    with pytest.raises(DevonThinkSecurityError, match="Security check failed"):
        DevonThinkService(session_factory(session)).review(handoff)

    assert [name for name, _ in session.calls] == ["get_databases"]


def test_devonthink_duplicate_blocks_create() -> None:
    handoff = prepare_handoff(sample_minutes().to_markdown(), "plaud:123")
    session = FakeDevonThinkSession(
        {
            "get_databases": [database_list("Inbox")],
            "lookup_records": [
                {"count": 1, "results": [{"uuid": "existing"}]},
                {"count": 0, "results": []},
            ],
        }
    )

    with pytest.raises(DevonThinkDuplicateError, match="source reference"):
        DevonThinkService(session_factory(session)).import_record(handoff)

    assert "create_record" not in [name for name, _ in session.calls]


def test_devonthink_import_rechecks_and_verifies_content() -> None:
    handoff = prepare_handoff(sample_minutes().to_markdown(), "plaud:123")
    session = FakeDevonThinkSession(
        {
            "get_databases": [database_list("Inbox")],
            "lookup_records": [{"count": 0, "results": []}, {"count": 0, "results": []}],
            "create_record": [
                {
                    "uuid": "created-uuid",
                    "name": handoff.title,
                    "location": "/Inbox/Training coordination meeting",
                }
            ],
            "get_record_properties": [
                {
                    "uuid": "created-uuid",
                    "name": handoff.title,
                    "location": "/Inbox/Training coordination meeting",
                }
            ],
            "get_record_text": [
                SimpleNamespace(
                    isError=False,
                    structuredContent=None,
                    content=[SimpleNamespace(text=handoff.markdown)],
                )
            ],
        }
    )

    receipt = DevonThinkService(session_factory(session)).import_record(handoff)

    assert receipt.uuid == "created-uuid"
    assert receipt.content_verified
    assert receipt.item_url == "x-devonthink-item://created-uuid"
    create_arguments = next(args for name, args in session.calls if name == "create_record")
    assert create_arguments["type"] == "markdown"
    assert create_arguments["tags"] == ["minutes", "pea-import"]
    assert create_arguments["url"] == handoff.source_url
    assert handoff.content_fingerprint in create_arguments["comment"]


def test_remarkable_import_uses_database_inbox_without_automatic_tags() -> None:
    handoff = prepare_remarkable_handoff(
        "Training sketch",
        "Reviewed handwritten notes.",
        "remarkdown:document-1",
    )
    session = FakeDevonThinkSession(
        {
            "get_databases": [database_list("Inbox", "private")],
            "lookup_records": [{"results": []}, {"results": []}],
            "create_record": [
                {
                    "uuid": "remarkable-uuid",
                    "name": handoff.title,
                    "location": "/Inbox/Training sketch",
                }
            ],
            "get_record_properties": [
                {
                    "uuid": "remarkable-uuid",
                    "name": handoff.title,
                    "location": "/Inbox/Training sketch",
                }
            ],
            "get_record_text": [{"text": handoff.markdown}],
        }
    )

    receipt = DevonThinkService(session_factory(session)).import_record(handoff)

    assert receipt.database_name == "Inbox"
    create_arguments = next(args for name, args in session.calls if name == "create_record")
    assert create_arguments["database_uuid"] == "uuid-Inbox"
    assert "destination" not in create_arguments
    assert "tags" not in create_arguments


def test_devonthink_import_reports_post_write_mismatch() -> None:
    handoff = prepare_handoff(sample_minutes().to_markdown(), "plaud:123")
    session = FakeDevonThinkSession(
        {
            "get_databases": [database_list("Inbox")],
            "lookup_records": [{"count": 0, "results": []}, {"count": 0, "results": []}],
            "create_record": [{"uuid": "created-uuid", "name": handoff.title}],
            "get_record_properties": [{"uuid": "created-uuid", "name": handoff.title}],
            "get_record_text": [{"text": "Different content"}],
        }
    )

    with pytest.raises(DevonThinkError, match="created, but post-write verification"):
        DevonThinkService(session_factory(session)).import_record(handoff)
