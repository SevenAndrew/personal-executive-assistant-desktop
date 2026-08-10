from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from openai import OpenAI

from .models import ModelProfile, WeeklySummary
from .secrets import resolve_openai_api_key

MAX_WEEKLY_SOURCE_CHARACTERS = 500_000
LOW_REASONING_WEEKLY_OUTPUT_TOKENS = 1_800
MEDIUM_REASONING_WEEKLY_OUTPUT_TOKENS = 4_000
WEEK_ID_PATTERN = re.compile(r"^(?P<year>\d{4})-W(?P<week>\d{2})$")

WEEKLY_SYSTEM_INSTRUCTIONS = """Prepare a concise weekly management summary in formal British
English. Use only facts present in the supplied, explicitly selected sources. Return a two-column
Topic/Summary structure. Every topic must contain one or two concise bullet points; never return a
third bullet. Consolidate duplication across sources, but do not merge distinct facts. Preserve
specific names, dates, decisions and commitments when they are operationally relevant. Do not
invent owners, decisions, certainty or completion. When a source is ambiguous or conflicts with
another source, add a final topic named "Verification / follow-up" with no more than two bullets.
Exclude sensitive personal detail that is not necessary for the management record. Use British
spelling and terminology consistently. The output may be reviewed by senior management, HR,
Legal or a regulator.
"""


@dataclass(frozen=True)
class WeeklySource:
    label: str
    source_reference: str
    text: str
    source_kind: str


@dataclass(frozen=True)
class WeeklyGenerationResult:
    summary: WeeklySummary
    model: str
    input_tokens: int | None
    output_tokens: int | None


class WeeklyGenerationError(RuntimeError):
    pass


class OpenAIWeeklyService:
    def __init__(
        self,
        client_factory: Callable[..., Any] = OpenAI,
        api_key_resolver: Callable[[], str] = resolve_openai_api_key,
    ) -> None:
        self._client_factory = client_factory
        self._api_key_resolver = api_key_resolver

    def generate(
        self,
        week_id: str,
        sources: Sequence[WeeklySource],
        profile: ModelProfile,
    ) -> WeeklyGenerationResult:
        validated_week = validate_week_id(week_id)
        cleaned_sources = _clean_sources(sources)
        source_material = _format_sources(validated_week, cleaned_sources)
        if len(source_material) > MAX_WEEKLY_SOURCE_CHARACTERS:
            raise ValueError(
                f"The selected weekly sources exceed the "
                f"{MAX_WEEKLY_SOURCE_CHARACTERS:,}-character limit."
            )

        client = self._client_factory(api_key=self._api_key_resolver())
        output_tokens = (
            LOW_REASONING_WEEKLY_OUTPUT_TOKENS
            if profile.reasoning_effort == "low"
            else MEDIUM_REASONING_WEEKLY_OUTPUT_TOKENS
        )
        try:
            response = client.responses.parse(
                model=profile.model,
                reasoning={"effort": profile.reasoning_effort},
                input=[
                    {"role": "system", "content": WEEKLY_SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": source_material},
                ],
                text_format=WeeklySummary,
                max_output_tokens=output_tokens,
                store=False,
            )
        except Exception as exc:
            raise WeeklyGenerationError("The OpenAI weekly-summary request failed.") from exc

        parsed = response.output_parsed
        if parsed is None:
            raise WeeklyGenerationError("OpenAI returned no structured weekly summary.")
        if parsed.week_id != validated_week:
            raise WeeklyGenerationError("OpenAI returned a different ISO week than requested.")

        usage = getattr(response, "usage", None)
        return WeeklyGenerationResult(
            summary=parsed,
            model=profile.model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


def validate_week_id(value: str) -> str:
    cleaned = value.strip()
    match = WEEK_ID_PATTERN.fullmatch(cleaned)
    if match is None:
        raise ValueError("Use an ISO week in YYYY-Www format, for example 2026-W32.")
    year = int(match.group("year"))
    week = int(match.group("week"))
    try:
        date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise ValueError("The ISO week does not exist.") from exc
    return cleaned


def weekly_source_reference(week_id: str) -> str:
    return f"weekly:{validate_week_id(week_id)}"


def _clean_sources(sources: Sequence[WeeklySource]) -> list[WeeklySource]:
    cleaned: list[WeeklySource] = []
    for source in sources:
        label = source.label.strip()
        reference = source.source_reference.strip()
        text = source.text.strip()
        kind = source.source_kind.strip()
        if not label or not reference or not text or not kind:
            raise ValueError("Every selected weekly source requires a label, reference and text.")
        cleaned.append(WeeklySource(label, reference, text, kind))
    if not cleaned:
        raise ValueError("Select or enter at least one weekly-summary source.")
    return cleaned


def _format_sources(week_id: str, sources: Sequence[WeeklySource]) -> str:
    sections = [f"Requested ISO week: {week_id}"]
    for index, source in enumerate(sources, start=1):
        sections.extend(
            [
                "",
                f"--- SOURCE {index} ---",
                f"Label: {source.label}",
                f"Kind: {source.source_kind}",
                f"Reference: {source.source_reference}",
                "Content:",
                source.text,
            ]
        )
    return "\n".join(sections)
