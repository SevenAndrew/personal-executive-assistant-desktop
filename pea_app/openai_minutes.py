from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    LengthFinishReasonError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError

from .models import MeetingMinutes, ModelProfile
from .secrets import resolve_openai_api_key

MAX_TRANSCRIPT_CHARACTERS = 500_000
LOW_REASONING_OUTPUT_TOKENS = 1_800
MEDIUM_REASONING_OUTPUT_TOKENS = 4_000

SYSTEM_INSTRUCTIONS = """Prepare professional meeting minutes in formal British English.
Use the raw transcript as the authoritative event source. A separately supplied PLAUD summary may
be used to resolve speaker identities and transcription ambiguity only where it is consistent with
the transcript. User-approved contextual memory may resolve established names, roles and acronyms,
but must never be treated as evidence of attendance, speech, decisions or commitments. Always provide the meeting
date and a participants list. Use the separately supplied recording date unless the transcript
clearly identifies a different meeting date; record any conflict in verification_notes. Include
only people explicitly identified as participants, not people who are merely mentioned. If no
participant is identifiable, return exactly one participant entry: "Not stated in source".
Every action item must have an owner. Use the explicitly assigned person or role; if none is
assigned, use "Not assigned in source" and add the uncertainty to verification_notes. Do not infer
owners, dates, decisions or commitments. Keep each topic summary to one or two concise bullet
points. Separate decisions from action items. Put unclear names, dates, acronyms, ownership or
commitments in verification_notes. Do not reproduce sensitive personal detail that is not required
for the operational record. Use British spelling and terminology consistently. The output may be
reviewed by senior management, HR, Legal or a regulator.
"""


@dataclass(frozen=True)
class GenerationResult:
    minutes: MeetingMinutes
    model: str
    input_tokens: int | None
    output_tokens: int | None


class MinutesGenerationError(RuntimeError):
    def __init__(self, message: str, *, category: str = "request_failed") -> None:
        super().__init__(message)
        self.category = category


class OpenAIMinutesService:
    def __init__(
        self,
        client_factory: Callable[..., Any] = OpenAI,
        api_key_resolver: Callable[[], str] = resolve_openai_api_key,
    ) -> None:
        self._client_factory = client_factory
        self._api_key_resolver = api_key_resolver

    def generate(
        self,
        transcript: str,
        profile: ModelProfile,
        meeting_date_hint: str = "",
        plaud_summary: str = "",
        contextual_memory: str = "",
    ) -> GenerationResult:
        cleaned_transcript = transcript.strip()
        if not cleaned_transcript:
            raise ValueError("A transcript is required.")
        if len(cleaned_transcript) > MAX_TRANSCRIPT_CHARACTERS:
            raise ValueError(
                f"The transcript exceeds the {MAX_TRANSCRIPT_CHARACTERS:,}-character pilot limit."
            )

        supplied_date = meeting_date_hint.strip() or "Not provided"
        source_material = (
            f"Source metadata\nRecording date: {supplied_date}\n\n"
            f"Raw transcript\n{cleaned_transcript}"
        )
        if plaud_summary.strip():
            source_material += (
                "\n\nSecondary PLAUD summary\n"
                "Use this derived source only to resolve speaker identities, names and obvious "
                "transcription ambiguity when consistent with the raw transcript.\n"
                f"{plaud_summary.strip()}"
            )
        if contextual_memory.strip():
            source_material += (
                "\n\nUser-approved contextual memory\n"
                "Use this only to resolve names, roles, acronyms and established background. "
                "It is not evidence that a person attended, spoke, decided or accepted an action.\n"
                f"{contextual_memory.strip()}"
            )
        client = self._client_factory(api_key=self._api_key_resolver())
        output_tokens = (
            LOW_REASONING_OUTPUT_TOKENS
            if profile.reasoning_effort == "low"
            else MEDIUM_REASONING_OUTPUT_TOKENS
        )
        try:
            response = client.responses.parse(
                model=profile.model,
                reasoning={"effort": profile.reasoning_effort},
                input=[
                    {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                    {"role": "user", "content": source_material},
                ],
                text_format=MeetingMinutes,
                max_output_tokens=output_tokens,
                store=False,
            )
        except Exception as exc:
            raise _describe_openai_failure(exc) from exc

        parsed = response.output_parsed
        if parsed is None:
            raise MinutesGenerationError(
                "OpenAI returned no structured Minutes. The existing preview has been retained. "
                "Retry once or select another model.",
                category="incomplete_output",
            )

        usage = getattr(response, "usage", None)
        return GenerationResult(
            minutes=parsed,
            model=profile.model,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


def _describe_openai_failure(exc: Exception) -> MinutesGenerationError:
    """Map provider errors to useful messages without exposing request content."""
    if isinstance(exc, (LengthFinishReasonError, ValidationError)):
        return MinutesGenerationError(
            "The selected model did not complete the structured Minutes within the available "
            "output allowance. The existing preview has been retained. Please retry once; if the "
            "problem persists, select Standard or Economy.",
            category="incomplete_output",
        )
    if isinstance(exc, AuthenticationError):
        return MinutesGenerationError(
            "OpenAI rejected the API key. Check the saved key under Settings, then run the health "
            "check.",
            category="authentication",
        )
    if isinstance(exc, (PermissionDeniedError, NotFoundError)):
        return MinutesGenerationError(
            "The selected model is not available to this API project. Select another model or "
            "review the project model permissions under Settings.",
            category="model_access",
        )
    if isinstance(exc, RateLimitError):
        return MinutesGenerationError(
            "OpenAI has reached a rate or usage limit. The existing preview has been retained. "
            "Wait briefly and retry, or review API usage under Settings.",
            category="rate_limit",
        )
    if isinstance(exc, APITimeoutError):
        return MinutesGenerationError(
            "The OpenAI request timed out before the Minutes were completed. The existing preview "
            "has been retained. Retry once or select a faster model.",
            category="timeout",
        )
    if isinstance(exc, APIConnectionError):
        return MinutesGenerationError(
            "The app could not reach OpenAI. Check the network connection and run the health check "
            "under Settings.",
            category="connection",
        )
    if isinstance(exc, BadRequestError):
        return MinutesGenerationError(
            "OpenAI rejected the request for the selected model. Select another model and retry; "
            "the existing preview has been retained.",
            category="invalid_request",
        )
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return MinutesGenerationError(
            "OpenAI is temporarily unavailable. The existing preview has been retained. Please "
            "retry later.",
            category="provider_unavailable",
        )
    return MinutesGenerationError(
        "The OpenAI request failed for an unexpected reason. The existing preview has been "
        "retained. Open Settings → Usage and logs for the diagnostic category.",
        category="request_failed",
    )
