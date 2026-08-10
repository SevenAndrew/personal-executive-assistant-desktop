from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence

import pytest

from pea_app.plaud_cli import (
    PlaudAuthenticationError,
    PlaudCli,
    PlaudError,
    PlaudRecording,
    PlaudSummary,
    parse_recordings,
    parse_summary,
    parse_transcript,
)

FILES_OUTPUT = """
Files on this page: 2

  ID                                  NAME                                  DATE          DURATION
  --------------------------------------------------------------------------------------------------
  abcdefghijklmnopqrstuvwxyz12345678  Weekly coordination                   2026-08-06    42m03s
  1234567890abcdefghijklmnopqrstuvwx  Human insight                         2026-08-05    1h00m

Page 1
"""

TRANSCRIPT_OUTPUT = """
Transcript: Weekly coordination

[00:00 - 00:08] Speaker 1: The draft agenda was reviewed.
[00:08 - 00:14] Speaker 2: The next review will take place on Friday.
"""

SUMMARY_OUTPUT = """
Summary: Weekly coordination

Speaker 1 was identified as Alex Morgan.
"""


def completed(
    command: Sequence[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


def test_parse_recordings_preserves_id_name_and_metadata() -> None:
    recordings = parse_recordings(FILES_OUTPUT)
    assert recordings == [
        PlaudRecording(
            file_id="abcdefghijklmnopqrstuvwxyz12345678",
            name="Weekly coordination",
            date="2026-08-06",
            duration="42m03s",
        ),
        PlaudRecording(
            file_id="1234567890abcdefghijklmnopqrstuvwx",
            name="Human insight",
            date="2026-08-05",
            duration="1h00m",
        ),
    ]
    assert recordings[0].source_reference == "plaud:abcdefghijklmnopqrstuvwxyz12345678"


def test_parse_transcript_keeps_raw_timestamps_and_speakers() -> None:
    transcript = parse_transcript(TRANSCRIPT_OUTPUT)
    assert transcript.startswith("[00:00 - 00:08] Speaker 1:")
    assert "Transcript:" not in transcript
    assert transcript.count("\n") == 1


def test_parse_transcript_rejects_missing_raw_block() -> None:
    with pytest.raises(PlaudError, match="No raw transcript"):
        parse_transcript('No "transaction" transcript for this recording.')


def test_cli_requests_raw_transaction_block() -> None:
    calls: list[tuple[list[str], int]] = []

    def runner(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        calls.append((list(command), timeout))
        return completed(command, stdout=TRANSCRIPT_OUTPUT)

    client = PlaudCli(executable=sys.executable, runner=runner)
    recording = PlaudRecording("file-id", "Meeting", "2026-08-06", "10m00s")
    transcript = client.get_raw_transcript(recording)

    assert calls[0][0][-2:] == ["--block", "transaction"]
    assert transcript.recording == recording
    assert transcript.source_kind == "raw timestamped PLAUD transcript"


def test_cli_requests_and_parses_derived_summary() -> None:
    calls: list[tuple[list[str], int]] = []

    def runner(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        calls.append((list(command), timeout))
        return completed(command, stdout=SUMMARY_OUTPUT)

    client = PlaudCli(executable=sys.executable, runner=runner)
    recording = PlaudRecording("file-id", "Meeting", "2026-08-06", "10m00s")

    assert client.get_summary(recording) == PlaudSummary(
        recording, "Speaker 1 was identified as Alex Morgan."
    )
    assert calls[0][0] == [sys.executable, "summary", "file-id"]
    assert parse_summary(SUMMARY_OUTPUT).startswith("Speaker 1")


def test_cli_maps_authentication_failure() -> None:
    def runner(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return completed(command, returncode=3, stderr="AUTH_FAILED: token invalid")

    client = PlaudCli(executable=sys.executable, runner=runner)
    with pytest.raises(PlaudAuthenticationError, match="sign-in is required"):
        client.list_recordings()
