from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 90
MAX_RECORDINGS = 50
MAX_TRANSCRIPT_CHARACTERS = 500_000
RECORDING_LINE = re.compile(
    r"^\s{2}(?P<id>\S+)\s{2,}(?P<name>.*?)\s{2,}"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s{2,}(?P<duration>\S+)\s*$"
)
TRANSCRIPT_LINE = re.compile(r"^\[\d{2,}:\d{2}\s+-\s+\d{2,}:\d{2}\]")


class PlaudError(RuntimeError):
    pass


class PlaudNotInstalledError(PlaudError):
    pass


class PlaudAuthenticationError(PlaudError):
    pass


@dataclass(frozen=True)
class PlaudRecording:
    file_id: str
    name: str
    date: str
    duration: str

    @property
    def source_reference(self) -> str:
        return f"plaud:{self.file_id}"


@dataclass(frozen=True)
class PlaudTranscript:
    recording: PlaudRecording
    text: str
    source_kind: str = "raw timestamped PLAUD transcript"


@dataclass(frozen=True)
class PlaudSummary:
    recording: PlaudRecording
    text: str
    source_kind: str = "derived PLAUD summary"


@dataclass(frozen=True)
class PlaudSourceBundle:
    transcript: PlaudTranscript
    summary: PlaudSummary | None


CommandRunner = Callable[[Sequence[str], int], subprocess.CompletedProcess[str]]


class PlaudCli:
    def __init__(
        self,
        executable: str | Path | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        configured = str(executable or os.environ.get("PEA_PLAUD_CLI", "plaud"))
        self._executable = configured
        self._runner = runner or _run_command

    @property
    def executable(self) -> str:
        return self._executable

    def is_installed(self) -> bool:
        return bool(shutil.which(self._executable)) if "/" not in self._executable else Path(
            self._executable
        ).is_file()

    def is_authenticated(self) -> bool:
        if not self.is_installed():
            return False
        result = self._runner([self._executable, "me"], 20)
        return result.returncode == 0

    def login(self) -> None:
        self._require_installed()
        result = self._runner([self._executable, "login"], 300)
        self._raise_for_failure(result, "PLAUD sign-in failed.")

    def list_recordings(self, limit: int = 20) -> list[PlaudRecording]:
        self._require_installed()
        if not 1 <= limit <= MAX_RECORDINGS:
            raise ValueError(f"PLAUD recording limit must be between 1 and {MAX_RECORDINGS}.")
        result = self._runner(
            [self._executable, "files", "--page", "1", "--page-size", str(max(10, limit))],
            DEFAULT_TIMEOUT_SECONDS,
        )
        self._raise_for_failure(result, "PLAUD recordings could not be retrieved.")
        recordings = parse_recordings(result.stdout)
        return recordings[:limit]

    def get_raw_transcript(self, recording: PlaudRecording) -> PlaudTranscript:
        self._require_installed()
        result = self._runner(
            [self._executable, "transcript", recording.file_id, "--block", "transaction"],
            DEFAULT_TIMEOUT_SECONDS,
        )
        self._raise_for_failure(result, "The PLAUD transcript could not be retrieved.")
        text = parse_transcript(result.stdout)
        if len(text) > MAX_TRANSCRIPT_CHARACTERS:
            raise PlaudError(
                f"The transcript exceeds the {MAX_TRANSCRIPT_CHARACTERS:,}-character pilot limit."
            )
        return PlaudTranscript(recording=recording, text=text)

    def get_summary(self, recording: PlaudRecording) -> PlaudSummary:
        self._require_installed()
        result = self._runner(
            [self._executable, "summary", recording.file_id],
            DEFAULT_TIMEOUT_SECONDS,
        )
        self._raise_for_failure(result, "The PLAUD summary could not be retrieved.")
        return PlaudSummary(recording=recording, text=parse_summary(result.stdout))

    def get_source_bundle(self, recording: PlaudRecording) -> PlaudSourceBundle:
        transcript = self.get_raw_transcript(recording)
        try:
            summary = self.get_summary(recording)
        except PlaudError:
            summary = None
        return PlaudSourceBundle(transcript=transcript, summary=summary)

    def _require_installed(self) -> None:
        if not self.is_installed():
            raise PlaudNotInstalledError(
                "The official PLAUD CLI is not installed. Install @plaud-ai/cli first."
            )

    @staticmethod
    def _raise_for_failure(result: subprocess.CompletedProcess[str], fallback: str) -> None:
        combined = f"{result.stdout}\n{result.stderr}"
        if result.returncode == 0:
            return
        if "AUTH_FAILED" in combined or "not logged in" in combined.casefold():
            raise PlaudAuthenticationError("PLAUD sign-in is required.")
        raise PlaudError(fallback)


def parse_recordings(output: str) -> list[PlaudRecording]:
    recordings: list[PlaudRecording] = []
    for line in _without_ansi(output).splitlines():
        if match := RECORDING_LINE.match(line):
            recordings.append(
                PlaudRecording(
                    file_id=match.group("id"),
                    name=match.group("name").strip(),
                    date=match.group("date"),
                    duration=match.group("duration"),
                )
            )
    count_match = re.search(r"Files on this page:\s*(\d+)", output)
    if not recordings and count_match and int(count_match.group(1)) == 0:
        return []
    if not recordings:
        raise PlaudError("The PLAUD recordings response could not be parsed.")
    return recordings


def parse_transcript(output: str) -> str:
    lines = _without_ansi(output).splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if TRANSCRIPT_LINE.match(line))
    except StopIteration as exc:
        if any("No \"transaction\" transcript" in line for line in lines):
            raise PlaudError("No raw transcript is available for this PLAUD recording.") from exc
        raise PlaudError("The PLAUD transcript response could not be parsed.") from exc
    transcript = "\n".join(line.rstrip() for line in lines[start:]).strip()
    if not transcript:
        raise PlaudError("The PLAUD transcript is empty.")
    return transcript


def parse_summary(output: str) -> str:
    lines = [line.rstrip() for line in _without_ansi(output).splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[0].strip().casefold().startswith("summary"):
        lines.pop(0)
    summary = "\n".join(lines).strip()
    if not summary:
        raise PlaudError("The PLAUD summary is empty.")
    return summary


def _run_command(command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update({"NO_COLOR": "1", "FORCE_COLOR": "0"})
    try:
        return subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise PlaudError("The PLAUD request timed out.") from exc
    except OSError as exc:
        raise PlaudError("The PLAUD CLI could not be started.") from exc


def _without_ansi(value: str) -> str:
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", value)
