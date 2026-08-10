from __future__ import annotations

from types import SimpleNamespace

import pytest

from pea_app.devonthink_handoff import prepare_handoff
from pea_app.models import TopicSummary, WeeklySummary, get_model_profile
from pea_app.openai_weekly import (
    WEEKLY_SYSTEM_INSTRUCTIONS,
    OpenAIWeeklyService,
    WeeklySource,
    validate_week_id,
    weekly_source_reference,
)


def sample_summary() -> WeeklySummary:
    return WeeklySummary(
        week_id="2026-W32",
        topics=[
            TopicSummary(
                topic="Training planning",
                summary=["Capacity assumptions were reviewed.", "The revised plan is due Friday."],
            )
        ],
    )


def test_weekly_markdown_is_two_column_table_with_week_in_title() -> None:
    markdown = sample_summary().to_markdown()

    assert markdown.startswith("# Weekly Summary — 2026-W32")
    assert "| Topic | Summary |" in markdown
    assert "| Training planning | - Capacity assumptions were reviewed.<br>" in markdown
    assert "##" not in markdown


def test_weekly_schema_limits_each_topic_to_two_bullets() -> None:
    with pytest.raises(ValueError):
        TopicSummary(topic="Invalid", summary=["One", "Two", "Three"])


def test_week_validation_and_source_reference() -> None:
    assert validate_week_id("2026-W32") == "2026-W32"
    assert weekly_source_reference("2026-W32") == "weekly:2026-W32"
    with pytest.raises(ValueError, match="does not exist"):
        validate_week_id("2026-W54")


def test_weekly_service_uses_selected_sources_and_store_false() -> None:
    calls: list[dict[str, object]] = []

    class FakeResponses:
        def parse(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(
                output_parsed=sample_summary(),
                usage=SimpleNamespace(input_tokens=90, output_tokens=30),
            )

    service = OpenAIWeeklyService(
        client_factory=lambda **_: SimpleNamespace(responses=FakeResponses()),
        api_key_resolver=lambda: "sk-test",
    )
    source = WeeklySource(
        "Approved minutes",
        "plaud:123",
        "# Minutes\n\nA decision was recorded.",
        "approved meeting minutes",
    )

    result = service.generate("2026-W32", [source], get_model_profile("economy"))

    assert result.summary == sample_summary()
    assert calls[0]["model"] == "gpt-5.6-luna"
    assert calls[0]["store"] is False
    assert calls[0]["max_output_tokens"] == 1_800
    assert calls[0]["text_format"] is WeeklySummary
    user_content = calls[0]["input"][1]["content"]
    assert "Requested ISO week: 2026-W32" in user_content
    assert "Reference: plaud:123" in user_content
    assert "A decision was recorded." in user_content


@pytest.mark.parametrize("profile_key", ["standard", "quality"])
def test_weekly_medium_reasoning_profiles_have_larger_bounded_output(
    profile_key: str,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeResponses:
        def parse(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(output_parsed=sample_summary(), usage=None)

    service = OpenAIWeeklyService(
        client_factory=lambda **_: SimpleNamespace(responses=FakeResponses()),
        api_key_resolver=lambda: "sk-test",
    )
    source = WeeklySource("Agenda", "agenda:1", "Approved update.", "Agenda note")

    service.generate("2026-W32", [source], get_model_profile(profile_key))

    assert calls[0]["max_output_tokens"] == 4_000


def test_weekly_prompt_enforces_british_english_and_two_bullets() -> None:
    assert "formal British" in WEEKLY_SYSTEM_INSTRUCTIONS
    assert "one or two concise bullet points" in WEEKLY_SYSTEM_INSTRUCTIONS


def test_weekly_handoff_uses_weekly_summary_record_type() -> None:
    handoff = prepare_handoff(
        sample_summary().to_markdown(),
        weekly_source_reference("2026-W32"),
        record_kind="weekly-summary",
    )

    assert handoff.title == "Weekly Summary — 2026-W32"
    assert handoff.record_kind == "weekly-summary"
