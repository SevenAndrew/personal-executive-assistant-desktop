from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from openai import OpenAI

from .models import DailySummary, ModelProfile
from .openai_weekly import (
    LOW_REASONING_WEEKLY_OUTPUT_TOKENS,
    MAX_WEEKLY_SOURCE_CHARACTERS,
    MEDIUM_REASONING_WEEKLY_OUTPUT_TOKENS,
    WeeklySource,
)
from .secrets import resolve_openai_api_key

DAILY_SYSTEM_INSTRUCTIONS = """Prepare a concise daily management summary in formal British
English. Use only facts in the supplied approved sources. Return a two-column Topic/Summary
structure with one or two concise bullet points per topic. Preserve relevant names, dates,
decisions and commitments. Do not invent owners, decisions, certainty or completion. Consolidate
duplication and identify material ambiguity under a final 'Verification / follow-up' topic.
Exclude unnecessary sensitive personal detail.
"""


@dataclass(frozen=True)
class DailyGenerationResult:
    summary: DailySummary
    model: str
    input_tokens: int | None
    output_tokens: int | None


class OpenAIDailyService:
    def __init__(
        self,
        client_factory: Callable[..., Any] = OpenAI,
        api_key_resolver: Callable[[], str] = resolve_openai_api_key,
    ) -> None:
        self._client_factory = client_factory
        self._api_key_resolver = api_key_resolver

    def generate(
        self, date_id: str, sources: Sequence[WeeklySource], profile: ModelProfile
    ) -> DailyGenerationResult:
        validated = validate_date_id(date_id)
        sections = [f"Requested date: {validated}"]
        for index, source in enumerate(sources, start=1):
            if not all((source.label.strip(), source.source_reference.strip(), source.text.strip())):
                raise ValueError("Every daily source requires a label, reference and text.")
            sections.extend(
                [
                    "",
                    f"--- SOURCE {index} ---",
                    f"Label: {source.label.strip()}",
                    f"Kind: {source.source_kind.strip()}",
                    f"Reference: {source.source_reference.strip()}",
                    "Content:",
                    source.text.strip(),
                ]
            )
        if not sources:
            raise ValueError("No approved source is available for the selected date.")
        material = "\n".join(sections)
        if len(material) > MAX_WEEKLY_SOURCE_CHARACTERS:
            raise ValueError("The selected daily sources exceed the 500,000-character limit.")
        output_tokens = (
            LOW_REASONING_WEEKLY_OUTPUT_TOKENS
            if profile.reasoning_effort == "low"
            else MEDIUM_REASONING_WEEKLY_OUTPUT_TOKENS
        )
        try:
            response = self._client_factory(api_key=self._api_key_resolver()).responses.parse(
                model=profile.model,
                reasoning={"effort": profile.reasoning_effort},
                input=[
                    {"role": "system", "content": DAILY_SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": material},
                ],
                text_format=DailySummary,
                max_output_tokens=output_tokens,
                store=False,
            )
        except Exception as exc:
            raise RuntimeError("The OpenAI daily-summary request failed.") from exc
        parsed = response.output_parsed
        if parsed is None or parsed.date_id != validated:
            raise RuntimeError("OpenAI returned no valid daily summary.")
        usage = getattr(response, "usage", None)
        return DailyGenerationResult(
            parsed,
            profile.model,
            getattr(usage, "input_tokens", None),
            getattr(usage, "output_tokens", None),
        )


def validate_date_id(value: str) -> str:
    cleaned = value.strip()
    try:
        parsed = date.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError("Use a date in YYYY-MM-DD format.") from exc
    if parsed.isoformat() != cleaned:
        raise ValueError("Use a date in YYYY-MM-DD format.")
    return cleaned


def daily_source_reference(date_id: str) -> str:
    return f"daily:{validate_date_id(date_id)}"
