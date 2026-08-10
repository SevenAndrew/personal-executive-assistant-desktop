from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REMARKDOWN_MCP_URL = "https://mcp.remarkdown.org/mcp"
AUTH_DIRECTORY = (
    Path.home() / "Library" / "Application Support" / "Personal Executive Assistant" / "mcp-auth"
)
RECENT_WINDOW_DAYS = 30
MAX_DOCUMENTS = 50
MAX_DOCUMENT_CHARACTERS = 300_000
TEXT_READY_STATUSES = frozenset({"typed", "transcribed"})


class RemarkdownError(RuntimeError):
    pass


class RemarkdownNotInstalledError(RemarkdownError):
    pass


class RemarkdownAuthenticationError(RemarkdownError):
    pass


class ToolSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


SessionFactory = Callable[[], Any]


@dataclass(frozen=True)
class RemarkdownIdentity:
    paired: bool
    folder: str
    scope: str
    transcription_window: str
    credit_balance: int
    transcription_paused: bool
    documents_synced: int
    documents_total: int


@dataclass(frozen=True)
class RemarkdownDocumentSummary:
    document_id: str
    name: str
    parent: str
    modified: str
    content_status: str

    @property
    def source_reference(self) -> str:
        return f"remarkdown:{self.document_id}"

    @property
    def text_ready(self) -> bool:
        return self.content_status in TEXT_READY_STATUSES


@dataclass(frozen=True)
class RemarkdownDocument:
    document_id: str
    name: str
    markdown: str
    content_kind: str
    content_status: str
    page_count: int
    ink_pages: tuple[int, ...]

    @property
    def source_reference(self) -> str:
        return f"remarkdown:{self.document_id}"

    @property
    def source_kind(self) -> str:
        if self.content_kind == "typed":
            return "typed reMarkable content"
        return "handwriting transcribed by remarkdown"


class RemarkdownService:
    def __init__(self, session_factory: SessionFactory | None = None) -> None:
        self._session_factory = session_factory or open_remarkdown_session

    @staticmethod
    def is_installed() -> bool:
        return shutil.which("mcp-remote") is not None

    @staticmethod
    def has_local_authorisation(auth_directory: Path = AUTH_DIRECTORY) -> bool:
        for path in auth_directory.rglob("*_tokens.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and isinstance(payload.get("access_token"), str):
                return bool(payload["access_token"])
        return False

    def login(self) -> RemarkdownIdentity:
        self._require_installed()
        return anyio.run(self._whoami)

    def whoami(self) -> RemarkdownIdentity:
        self._require_authorised()
        return anyio.run(self._whoami)

    def list_recent_documents(
        self,
        days: int = RECENT_WINDOW_DAYS,
        limit: int = MAX_DOCUMENTS,
        now: datetime | None = None,
    ) -> list[RemarkdownDocumentSummary]:
        self._require_authorised()
        if not 1 <= days <= RECENT_WINDOW_DAYS:
            raise ValueError(f"The remarkdown window must be between 1 and {RECENT_WINDOW_DAYS} days.")
        if not 1 <= limit <= MAX_DOCUMENTS:
            raise ValueError(f"The remarkdown document limit must be between 1 and {MAX_DOCUMENTS}.")
        documents = anyio.run(self._list_documents)
        threshold = (now or datetime.now(UTC)) - timedelta(days=days)
        recent = [item for item in documents if _is_recent(item.modified, threshold)]
        return sorted(recent, key=lambda item: item.modified, reverse=True)[:limit]

    def fetch_document(self, summary: RemarkdownDocumentSummary) -> RemarkdownDocument:
        self._require_authorised()
        if not summary.text_ready:
            raise RemarkdownError(_content_status_message(summary.content_status))
        return anyio.run(self._fetch_document, summary)

    async def _whoami(self) -> RemarkdownIdentity:
        async with self._session_factory() as session:
            payload = await _call_json(session, "whoami", {})
        reading = payload.get("reading")
        if not isinstance(reading, dict):
            raise RemarkdownError("remarkdown returned no readable account status.")
        credits = reading.get("credits")
        documents = reading.get("documents")
        if not isinstance(credits, dict) or not isinstance(documents, dict):
            raise RemarkdownError("remarkdown returned incomplete reading status.")
        return RemarkdownIdentity(
            paired=bool(payload.get("remarkable_paired", False)),
            folder=str(reading.get("folder") or "Not selected"),
            scope=str(reading.get("scope") or "Not selected"),
            transcription_window=str(reading.get("transcription_window") or "Not stated"),
            credit_balance=_non_negative_int(credits.get("balance")),
            transcription_paused=bool(credits.get("paused", False)),
            documents_synced=_non_negative_int(documents.get("synced")),
            documents_total=_non_negative_int(documents.get("total")),
        )

    async def _list_documents(self) -> list[RemarkdownDocumentSummary]:
        async with self._session_factory() as session:
            payload = await _call_json(session, "list_documents", {})
        items = payload.get("items")
        if not isinstance(items, list):
            raise RemarkdownError("remarkdown returned an invalid document list.")
        documents: list[RemarkdownDocumentSummary] = []
        for item in items:
            if not isinstance(item, dict) or item.get("kind") != "DocumentType":
                continue
            documents.append(
                RemarkdownDocumentSummary(
                    document_id=_required_string(item, "id", "document"),
                    name=_required_string(item, "name", "document"),
                    parent=str(item.get("parent") or ""),
                    modified=str(item.get("modified") or ""),
                    content_status=str(item.get("content_status") or "not_readable"),
                )
            )
        return documents

    async def _fetch_document(
        self,
        summary: RemarkdownDocumentSummary,
    ) -> RemarkdownDocument:
        async with self._session_factory() as session:
            payload = await _call_json(
                session,
                "fetch_document",
                {"id": summary.document_id, "force": False},
            )
        if payload.get("status") != "ok":
            raise RemarkdownError(str(payload.get("note") or "The document is not available."))
        content_status = str(payload.get("content_status") or summary.content_status)
        if content_status not in TEXT_READY_STATUSES:
            raise RemarkdownError(_content_status_message(content_status))
        markdown = payload.get("markdown")
        if not isinstance(markdown, str) or not markdown.strip():
            raise RemarkdownError("remarkdown returned no text for the selected document.")
        if len(markdown) > MAX_DOCUMENT_CHARACTERS:
            raise RemarkdownError(
                f"The document exceeds the {MAX_DOCUMENT_CHARACTERS:,}-character pilot limit."
            )
        ink_pages = payload.get("ink_pages")
        if not isinstance(ink_pages, list):
            ink_pages = []
        return RemarkdownDocument(
            document_id=_required_string(payload, "id", "document"),
            name=str(payload.get("name") or summary.name),
            markdown=markdown.strip(),
            content_kind=str(payload.get("content_kind") or "typed"),
            content_status=content_status,
            page_count=_non_negative_int(payload.get("page_count")),
            ink_pages=tuple(value for value in ink_pages if isinstance(value, int) and value > 0),
        )

    def _require_installed(self) -> None:
        if not self.is_installed():
            raise RemarkdownNotInstalledError(
                "mcp-remote is not installed. Install the official remarkdown bridge first."
            )

    def _require_authorised(self) -> None:
        self._require_installed()
        if not self.has_local_authorisation():
            raise RemarkdownAuthenticationError("remarkdown sign-in is required for this app.")


@asynccontextmanager
async def open_remarkdown_session() -> AsyncIterator[ClientSession]:
    executable = shutil.which("mcp-remote")
    if not executable:
        raise RemarkdownNotInstalledError("mcp-remote is not installed.")
    _secure_auth_directory()
    environment = os.environ.copy()
    environment["MCP_REMOTE_CONFIG_DIR"] = str(AUTH_DIRECTORY)
    parameters = StdioServerParameters(
        command=executable,
        args=[
            REMARKDOWN_MCP_URL,
            "--transport",
            "http-only",
            "--silent",
            "--auth-timeout",
            "300",
            "--ignore-tool",
            "push_markdown",
            "--ignore-tool",
            "refresh_documents",
            "--ignore-tool",
            "fetch_page_chunks",
            "--ignore-tool",
            "email_remarkdown_support",
        ],
        env=environment,
    )
    try:
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            yield session
    except Exception as exc:
        if error := _find_remarkdown_error(exc):
            raise error
        raise RemarkdownError(
            "remarkdown could not be reached or authorised. Retry sign-in from Settings."
        ) from exc
    finally:
        _secure_auth_directory()


async def _call_json(session: ToolSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if getattr(result, "isError", False):
        raise RemarkdownError(f"remarkdown read tool '{name}' failed.")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RemarkdownError(f"remarkdown read tool '{name}' returned invalid data.") from exc
            if isinstance(payload, dict):
                return payload
    raise RemarkdownError(f"remarkdown read tool '{name}' returned no structured data.")


def _is_recent(value: str, threshold: datetime) -> bool:
    if not value:
        return False
    try:
        modified = datetime.fromisoformat(value)
    except ValueError:
        return False
    if modified.tzinfo is None:
        modified = modified.replace(tzinfo=UTC)
    return modified >= threshold


def _content_status_message(status: str) -> str:
    messages = {
        "images_only_outside_window": (
            "This document is outside the transcription window. No paid transcription was started."
        ),
        "transcribing": "This document is still being transcribed by remarkdown.",
        "paused_out_of_credits": "Transcription is paused because no remarkdown credits remain.",
        "awaiting_scope_choice": "Choose a reading scope in remarkdown before loading content.",
        "not_readable": "This document type is not available as text through remarkdown.",
    }
    return messages.get(status, "The selected document is not available as text.")


def _secure_auth_directory() -> None:
    AUTH_DIRECTORY.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(AUTH_DIRECTORY, 0o700)
    for path in AUTH_DIRECTORY.rglob("*"):
        try:
            os.chmod(path, 0o700 if path.is_dir() else 0o600)
        except OSError:
            continue


def terminate_authentication_bridges(parent_pid: int | None = None) -> int:
    """Stop only remarkdown bridge processes started by this PEA process."""
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 0
    expected_parent = parent_pid or os.getpid()
    stopped = 0
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=2)
        if len(fields) != 3:
            continue
        try:
            process_id, process_parent = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        command = fields[2]
        if process_parent != expected_parent:
            continue
        if "mcp-remote" not in command or REMARKDOWN_MCP_URL not in command:
            continue
        try:
            os.kill(process_id, signal.SIGTERM)
        except OSError:
            continue
        stopped += 1
    return stopped


def _required_string(value: dict[str, Any], field: str, object_name: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise RemarkdownError(f"remarkdown returned a {object_name} without a valid {field}.")
    return result


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def _find_remarkdown_error(error: BaseException) -> RemarkdownError | None:
    if isinstance(error, RemarkdownError):
        return error
    for nested in getattr(error, "exceptions", ()):
        if found := _find_remarkdown_error(nested):
            return found
    return None
