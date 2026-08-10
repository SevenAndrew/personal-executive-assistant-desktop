from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from .devonthink_handoff import (
    DevonThinkHandoff,
    DevonThinkMinutesSource,
    DevonThinkService,
    ImportReceipt,
    ImportReview,
    prepare_handoff,
)
from .models import ModelProfile
from .openai_daily import (
    DailyGenerationResult,
    OpenAIDailyService,
    daily_source_reference,
    validate_date_id,
)
from .openai_minutes import GenerationResult, OpenAIMinutesService
from .openai_weekly import (
    OpenAIWeeklyService,
    WeeklyGenerationResult,
    WeeklySource,
    validate_week_id,
    weekly_source_reference,
)
from .plaud_cli import PlaudCli, PlaudRecording, PlaudSummary, PlaudTranscript

ProgressCallback = Callable[[int, str, str], None]


class PlaudReader(Protocol):
    def list_recordings(self, limit: int = 20) -> list[PlaudRecording]: ...

    def get_raw_transcript(self, recording: PlaudRecording) -> PlaudTranscript: ...

    def get_summary(self, recording: PlaudRecording) -> PlaudSummary: ...


class MinutesGenerator(Protocol):
    def generate(
        self,
        transcript: str,
        profile: ModelProfile,
        meeting_date_hint: str = "",
        plaud_summary: str = "",
        contextual_memory: str = "",
    ) -> GenerationResult: ...


class WeeklyGenerator(Protocol):
    def generate(
        self,
        week_id: str,
        sources: Sequence[WeeklySource],
        profile: ModelProfile,
    ) -> WeeklyGenerationResult: ...


class DevonThinkWriter(Protocol):
    def review(self, handoff: DevonThinkHandoff) -> ImportReview: ...

    def import_record(self, handoff: DevonThinkHandoff) -> ImportReceipt: ...


class MinutesArchive(Protocol):
    def load_minutes(
        self, start_date: str, end_date: str, database: str = "Inbox"
    ) -> list[DevonThinkMinutesSource]: ...


@dataclass
class LatestPlaudCheckpoint:
    profile: ModelProfile
    target_database: str
    destination: str = ""
    recording: PlaudRecording | None = None
    transcript: PlaudTranscript | None = None
    plaud_summary: PlaudSummary | None = None
    contextual_memory: str = ""
    generation: GenerationResult | None = None
    handoff: DevonThinkHandoff | None = None
    review: ImportReview | None = None
    failed_step: int | None = None


@dataclass
class WeeklyWorkflowCheckpoint:
    week_id: str
    sources: list[WeeklySource]
    profile: ModelProfile
    target_database: str
    destination: str = ""
    generation: WeeklyGenerationResult | None = None
    handoff: DevonThinkHandoff | None = None
    review: ImportReview | None = None
    failed_step: int | None = None
    archive_loaded: bool = False


@dataclass
class DailyWorkflowCheckpoint:
    date_id: str
    sources: list[WeeklySource]
    profile: ModelProfile
    target_database: str
    destination: str = ""
    generation: DailyGenerationResult | None = None
    handoff: DevonThinkHandoff | None = None
    review: ImportReview | None = None
    failed_step: int | None = None
    archive_loaded: bool = False


@dataclass(frozen=True)
class WorkflowReady:
    workflow_key: str
    preview: str
    handoff: DevonThinkHandoff
    review: ImportReview
    model: str
    input_tokens: int | None
    output_tokens: int | None

    @property
    def can_write(self) -> bool:
        return self.review.is_clear


class LatestPlaudWorkflow:
    def __init__(
        self,
        plaud: PlaudReader | None = None,
        generator: MinutesGenerator | None = None,
        devonthink: DevonThinkWriter | None = None,
    ) -> None:
        self._plaud = plaud or PlaudCli()
        self._generator = generator or OpenAIMinutesService()
        self._devonthink = devonthink or DevonThinkService()

    def run(
        self,
        checkpoint: LatestPlaudCheckpoint,
        progress: ProgressCallback,
    ) -> WorkflowReady:
        if checkpoint.recording is None:
            checkpoint.failed_step = 0
            progress(0, "Running", "Retrieving recent PLAUD metadata …")
            recordings = self._plaud.list_recordings(limit=20)
            if not recordings:
                raise RuntimeError("PLAUD returned no recent recording.")
            checkpoint.recording = recordings[0]
            progress(
                0,
                "Complete",
                f"Latest recording selected: {checkpoint.recording.date} · "
                f"{checkpoint.recording.duration}.",
            )

        if checkpoint.transcript is None:
            checkpoint.failed_step = 1
            progress(1, "Running", "Loading the selected raw transcript …")
            checkpoint.transcript = self._plaud.get_raw_transcript(checkpoint.recording)
            progress(1, "Complete", "Raw transcript loaded into memory.")

        if checkpoint.plaud_summary is None:
            checkpoint.failed_step = 2
            progress(2, "Running", "Loading the derived PLAUD summary for speaker context …")
            try:
                checkpoint.plaud_summary = self._plaud.get_summary(checkpoint.recording)
                progress(2, "Complete", "PLAUD speaker context loaded as a secondary source.")
            except RuntimeError:
                progress(2, "Complete", "No PLAUD summary was available; using the raw transcript.")

        if checkpoint.generation is None:
            checkpoint.failed_step = 3
            progress(3, "Running", f"Generating with {checkpoint.profile.model} …")
            checkpoint.generation = self._generator.generate(
                checkpoint.transcript.text,
                checkpoint.profile,
                checkpoint.recording.date,
                checkpoint.plaud_summary.text if checkpoint.plaud_summary else "",
                checkpoint.contextual_memory,
            )
            progress(3, "Complete", _usage_detail(checkpoint.generation))

        if checkpoint.handoff is None:
            checkpoint.failed_step = 4
            progress(4, "Running", "Preparing preview and stable source reference …")
            preview = checkpoint.generation.minutes.to_markdown()
            checkpoint.handoff = prepare_handoff(
                preview,
                checkpoint.recording.source_reference,
                checkpoint.target_database,
                checkpoint.destination,
            )
            progress(4, "Complete", "Reviewable minutes preview prepared.")

        if checkpoint.review is None:
            checkpoint.failed_step = 5
            progress(5, "Running", "Checking DEVONthink target and duplicates …")
            checkpoint.review = self._devonthink.review(checkpoint.handoff)
            detail = (
                "Target and duplicate checks are clear."
                if checkpoint.review.is_clear
                else "Duplicate protection blocked the write."
            )
            progress(5, "Complete" if checkpoint.review.is_clear else "Blocked", detail)

        checkpoint.failed_step = None
        progress(
            6,
            "Ready" if checkpoint.review.is_clear else "Blocked",
            "Awaiting one final write confirmation."
            if checkpoint.review.is_clear
            else "Review the existing DEVONthink record separately.",
        )
        generation = checkpoint.generation
        return WorkflowReady(
            workflow_key="latest_plaud_minutes",
            preview=checkpoint.handoff.markdown,
            handoff=checkpoint.handoff,
            review=checkpoint.review,
            model=generation.model,
            input_tokens=generation.input_tokens,
            output_tokens=generation.output_tokens,
        )


class WeeklySummaryWorkflow:
    def __init__(
        self,
        generator: WeeklyGenerator | None = None,
        devonthink: DevonThinkWriter | None = None,
        archive: MinutesArchive | None = None,
    ) -> None:
        self._generator = generator or OpenAIWeeklyService()
        self._devonthink = devonthink or DevonThinkService()
        self._archive = archive or DevonThinkService()

    def run(
        self,
        checkpoint: WeeklyWorkflowCheckpoint,
        progress: ProgressCallback,
    ) -> WorkflowReady:
        if not checkpoint.archive_loaded:
            checkpoint.failed_step = 0
            progress(0, "Running", "Loading all reviewed Minutes for the selected ISO week …")
            start, end = week_date_range(checkpoint.week_id)
            minutes = minutes_to_weekly_sources(
                self._archive.load_minutes(start, end, checkpoint.target_database)
            )
            checkpoint.sources = minutes + checkpoint.sources
            checkpoint.archive_loaded = True
        if not checkpoint.sources:
            raise ValueError("No reviewed Minutes are available for the selected ISO week.")
        progress(0, "Complete", f"{len(checkpoint.sources)} period source(s) available.")

        if checkpoint.generation is None:
            checkpoint.failed_step = 1
            progress(1, "Running", f"Generating with {checkpoint.profile.model} …")
            checkpoint.generation = self._generator.generate(
                checkpoint.week_id,
                checkpoint.sources,
                checkpoint.profile,
            )
            progress(1, "Complete", _usage_detail(checkpoint.generation))

        if checkpoint.handoff is None:
            checkpoint.failed_step = 2
            progress(2, "Running", "Preparing weekly preview and source reference …")
            checkpoint.handoff = prepare_handoff(
                checkpoint.generation.summary.to_markdown(),
                weekly_source_reference(checkpoint.week_id),
                checkpoint.target_database,
                checkpoint.destination,
                record_kind="weekly-summary",
            )
            progress(2, "Complete", "Two-column weekly preview prepared.")

        if checkpoint.review is None:
            checkpoint.failed_step = 3
            progress(3, "Running", "Checking DEVONthink target and duplicates …")
            checkpoint.review = self._devonthink.review(checkpoint.handoff)
            detail = (
                "Target and duplicate checks are clear."
                if checkpoint.review.is_clear
                else "Duplicate protection blocked the write."
            )
            progress(3, "Complete" if checkpoint.review.is_clear else "Blocked", detail)

        checkpoint.failed_step = None
        progress(
            4,
            "Ready" if checkpoint.review.is_clear else "Blocked",
            "Awaiting one final write confirmation."
            if checkpoint.review.is_clear
            else "Review or merge the existing weekly summary separately.",
        )
        generation = checkpoint.generation
        return WorkflowReady(
            workflow_key="weekly_summary",
            preview=checkpoint.handoff.markdown,
            handoff=checkpoint.handoff,
            review=checkpoint.review,
            model=generation.model,
            input_tokens=generation.input_tokens,
            output_tokens=generation.output_tokens,
        )


class DailySummaryWorkflow:
    def __init__(
        self,
        generator: OpenAIDailyService | None = None,
        devonthink: DevonThinkWriter | None = None,
        archive: MinutesArchive | None = None,
    ) -> None:
        self._generator = generator or OpenAIDailyService()
        self._devonthink = devonthink or DevonThinkService()
        self._archive = archive or DevonThinkService()

    def run(
        self, checkpoint: DailyWorkflowCheckpoint, progress: ProgressCallback
    ) -> WorkflowReady:
        selected_date = validate_date_id(checkpoint.date_id)
        if not checkpoint.archive_loaded:
            checkpoint.failed_step = 0
            progress(0, "Running", "Loading all reviewed Minutes for the selected date …")
            end = (date.fromisoformat(selected_date) + timedelta(days=1)).isoformat()
            minutes = minutes_to_weekly_sources(
                self._archive.load_minutes(selected_date, end, checkpoint.target_database)
            )
            checkpoint.sources = minutes + checkpoint.sources
            checkpoint.archive_loaded = True
        if not checkpoint.sources:
            raise ValueError("No reviewed Minutes are available for the selected date.")
        progress(0, "Complete", f"{len(checkpoint.sources)} period source(s) available.")
        if checkpoint.generation is None:
            checkpoint.failed_step = 1
            progress(1, "Running", f"Generating with {checkpoint.profile.model} …")
            checkpoint.generation = self._generator.generate(
                selected_date, checkpoint.sources, checkpoint.profile
            )
            progress(1, "Complete", _usage_detail(checkpoint.generation))
        if checkpoint.handoff is None:
            checkpoint.failed_step = 2
            progress(2, "Running", "Preparing daily preview and source reference …")
            checkpoint.handoff = prepare_handoff(
                checkpoint.generation.summary.to_markdown(),
                daily_source_reference(selected_date),
                checkpoint.target_database,
                checkpoint.destination,
                record_kind="daily-summary",
            )
            progress(2, "Complete", "Two-column daily preview prepared.")
        if checkpoint.review is None:
            checkpoint.failed_step = 3
            progress(3, "Running", "Checking DEVONthink target and duplicates …")
            checkpoint.review = self._devonthink.review(checkpoint.handoff)
            progress(
                3,
                "Complete" if checkpoint.review.is_clear else "Blocked",
                "Target and duplicate checks are clear."
                if checkpoint.review.is_clear
                else "Duplicate protection blocked the write.",
            )
        checkpoint.failed_step = None
        progress(
            4,
            "Ready" if checkpoint.review.is_clear else "Blocked",
            "Awaiting one final write confirmation."
            if checkpoint.review.is_clear
            else "Review or merge the existing daily summary separately.",
        )
        generation = checkpoint.generation
        return WorkflowReady(
            "daily_summary",
            checkpoint.handoff.markdown,
            checkpoint.handoff,
            checkpoint.review,
            generation.model,
            generation.input_tokens,
            generation.output_tokens,
        )


class WorkflowImportService:
    def __init__(self, devonthink: DevonThinkWriter | None = None) -> None:
        self._devonthink = devonthink or DevonThinkService()

    def import_ready(self, ready: WorkflowReady) -> ImportReceipt:
        if not ready.can_write:
            raise RuntimeError("Duplicate protection has not cleared this workflow output.")
        return self._devonthink.import_record(ready.handoff)


def minutes_to_weekly_sources(
    records: Sequence[DevonThinkMinutesSource],
) -> list[WeeklySource]:
    return [
        WeeklySource(
            record.title,
            record.source_reference,
            record.markdown,
            "reviewed DEVONthink Minutes",
        )
        for record in records
    ]


def week_date_range(week_id: str) -> tuple[str, str]:
    validated = validate_week_id(week_id)
    year, week = validated.split("-W")
    start = date.fromisocalendar(int(year), int(week), 1)
    return start.isoformat(), (start + timedelta(days=7)).isoformat()


def _usage_detail(
    result: GenerationResult | WeeklyGenerationResult | DailyGenerationResult,
) -> str:
    if result.input_tokens is None or result.output_tokens is None:
        return "Preview generated; token usage was not returned."
    return (
        f"Preview generated: {result.input_tokens:,} input and "
        f"{result.output_tokens:,} output tokens."
    )
