from __future__ import annotations

from dataclasses import dataclass

import pytest

from pea_app.devonthink_handoff import ImportReceipt, ImportReview
from pea_app.models import (
    ActionItem,
    DailySummary,
    MeetingMinutes,
    TopicSummary,
    WeeklySummary,
    get_model_profile,
)
from pea_app.openai_daily import DailyGenerationResult
from pea_app.openai_minutes import GenerationResult
from pea_app.openai_weekly import WeeklyGenerationResult, WeeklySource
from pea_app.plaud_cli import PlaudRecording, PlaudSummary, PlaudTranscript
from pea_app.workflows import (
    DailySummaryWorkflow,
    DailyWorkflowCheckpoint,
    LatestPlaudCheckpoint,
    LatestPlaudWorkflow,
    WeeklySummaryWorkflow,
    WeeklyWorkflowCheckpoint,
    WorkflowImportService,
)


def minutes_result() -> GenerationResult:
    return GenerationResult(
        minutes=MeetingMinutes(
            title="Weekly training meeting",
            meeting_date="2026-08-06",
            participants=["Alex"],
            topics=[TopicSummary(topic="Capacity", summary=["The plan was reviewed."])],
            decisions=[],
            action_items=[ActionItem(action="Update the plan.", owner="Alex")],
            verification_notes=[],
        ),
        model="gpt-5.6-luna",
        input_tokens=100,
        output_tokens=40,
    )


@dataclass
class FakePlaud:
    list_calls: int = 0
    transcript_calls: int = 0

    def list_recordings(self, limit: int = 20) -> list[PlaudRecording]:
        self.list_calls += 1
        return [PlaudRecording("latest", "Latest meeting", "2026-08-06", "30m")]

    def get_raw_transcript(self, recording: PlaudRecording) -> PlaudTranscript:
        self.transcript_calls += 1
        return PlaudTranscript(recording, "[00:00 - 00:10] Speaker: Test transcript")

    def get_summary(self, recording: PlaudRecording) -> PlaudSummary:
        return PlaudSummary(recording, "Speaker 1 is Alex.")


class FakeMinutesGenerator:
    def __init__(self, fail_once: bool = False) -> None:
        self.calls = 0
        self.fail_once = fail_once

    def generate(self, *_: object, **__: object) -> GenerationResult:
        self.calls += 1
        if self.fail_once and self.calls == 1:
            raise RuntimeError("Temporary generation failure")
        return minutes_result()


class FakeDevonThink:
    def __init__(self, clear: bool = True) -> None:
        self.clear = clear
        self.review_calls = 0
        self.import_calls = 0

    def review(self, handoff):
        self.review_calls += 1
        return ImportReview(
            handoff=handoff,
            database_uuid="database",
            database_name="Inbox",
            source_matches=() if self.clear else ({"uuid": "existing"},),
            title_matches=(),
        )

    def import_record(self, handoff):
        self.import_calls += 1
        return ImportReceipt(
            uuid="created",
            name=handoff.title,
            database_name="Inbox",
            location="/",
            item_url="x-devonthink-item://created",
            content_verified=True,
        )


class FakeArchive:
    def load_minutes(self, start_date, end_date, database="Inbox"):
        from pea_app.devonthink_handoff import DevonThinkMinutesSource

        return [
            DevonThinkMinutesSource(
                "minutes-1",
                "Training review",
                f"{start_date}T10:00:00+02:00",
                "# Training review\n\nApproved Minutes.",
            )
        ]

def test_latest_plaud_workflow_prepares_clear_preview() -> None:
    plaud = FakePlaud()
    generator = FakeMinutesGenerator()
    devonthink = FakeDevonThink()
    checkpoint = LatestPlaudCheckpoint(get_model_profile("economy"), "Inbox")
    progress: list[tuple[int, str, str]] = []

    ready = LatestPlaudWorkflow(plaud, generator, devonthink).run(
        checkpoint, lambda *value: progress.append(value)
    )

    assert ready.can_write
    assert ready.handoff.source_reference == "plaud:latest"
    assert ready.preview.startswith("# Weekly training meeting")
    assert progress[-1][1] == "Ready"
    assert plaud.list_calls == plaud.transcript_calls == generator.calls == 1


def test_latest_workflow_resume_does_not_repeat_completed_reads() -> None:
    plaud = FakePlaud()
    generator = FakeMinutesGenerator(fail_once=True)
    checkpoint = LatestPlaudCheckpoint(get_model_profile("economy"), "Inbox")
    workflow = LatestPlaudWorkflow(plaud, generator, FakeDevonThink())

    with pytest.raises(RuntimeError, match="Temporary"):
        workflow.run(checkpoint, lambda *_: None)

    assert checkpoint.failed_step == 3
    assert checkpoint.recording is not None
    assert checkpoint.transcript is not None

    ready = workflow.run(checkpoint, lambda *_: None)

    assert ready.can_write
    assert plaud.list_calls == 1
    assert plaud.transcript_calls == 1
    assert generator.calls == 2


def test_weekly_workflow_uses_stable_week_reference_and_tag() -> None:
    summary = WeeklySummary(
        week_id="2026-W32",
        topics=[TopicSummary(topic="Planning", summary=["The plan was reviewed."])],
    )

    class FakeWeeklyGenerator:
        def generate(self, *_: object, **__: object) -> WeeklyGenerationResult:
            return WeeklyGenerationResult(summary, "gpt-5.6-luna", 80, 20)

    checkpoint = WeeklyWorkflowCheckpoint(
        week_id="2026-W32",
        sources=[WeeklySource("Minutes", "plaud:latest", "Approved text", "minutes")],
        profile=get_model_profile("economy"),
        target_database="Inbox",
    )

    ready = WeeklySummaryWorkflow(
        FakeWeeklyGenerator(), FakeDevonThink(), FakeArchive()
    ).run(
        checkpoint, lambda *_: None
    )

    assert ready.handoff.source_reference == "weekly:2026-W32"
    assert ready.handoff.record_kind == "weekly-summary"
    assert ready.can_write


def test_daily_workflow_loads_period_minutes_and_uses_daily_reference() -> None:
    summary = DailySummary(
        date_id="2026-08-06",
        topics=[TopicSummary(topic="Planning", summary=["The plan was reviewed."])],
    )

    class FakeDailyGenerator:
        def generate(self, *_: object, **__: object) -> DailyGenerationResult:
            return DailyGenerationResult(summary, "gpt-5.6-luna", 60, 20)

    checkpoint = DailyWorkflowCheckpoint(
        "2026-08-06",
        [WeeklySource("Work chat", "manual-chat:2026-08-06", "Approved chat", "chat")],
        get_model_profile("economy"),
        "Inbox",
    )
    ready = DailySummaryWorkflow(
        FakeDailyGenerator(), FakeDevonThink(), FakeArchive()
    ).run(checkpoint, lambda *_: None)

    assert ready.workflow_key == "daily_summary"
    assert ready.handoff.source_reference == "daily:2026-08-06"
    assert ready.handoff.record_kind == "daily-summary"
    assert checkpoint.sources[0].source_reference == "devonthink:minutes-1"
    assert checkpoint.sources[1].source_reference == "manual-chat:2026-08-06"


def test_workflow_import_rechecks_and_returns_receipt() -> None:
    devonthink = FakeDevonThink()
    checkpoint = LatestPlaudCheckpoint(get_model_profile("economy"), "Inbox")
    ready = LatestPlaudWorkflow(FakePlaud(), FakeMinutesGenerator(), devonthink).run(
        checkpoint, lambda *_: None
    )

    receipt = WorkflowImportService(devonthink).import_ready(ready)

    assert receipt.content_verified
    assert devonthink.import_calls == 1


def test_workflow_import_rejects_duplicate_blocked_result() -> None:
    devonthink = FakeDevonThink(clear=False)
    checkpoint = LatestPlaudCheckpoint(get_model_profile("economy"), "Inbox")
    ready = LatestPlaudWorkflow(FakePlaud(), FakeMinutesGenerator(), devonthink).run(
        checkpoint, lambda *_: None
    )

    with pytest.raises(RuntimeError, match="Duplicate protection"):
        WorkflowImportService(devonthink).import_ready(ready)

    assert devonthink.import_calls == 0
