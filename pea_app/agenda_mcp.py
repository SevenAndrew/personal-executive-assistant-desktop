from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_AGENDA_MCP_URL = "http://127.0.0.1:16106/mcp"
MAX_PROJECTS = 100
MAX_NOTES = 50
MAX_REPORT_NOTES = 10
MAX_NOTE_CHARACTERS = 300_000


class AgendaError(RuntimeError):
    pass


class AgendaConnectionError(AgendaError):
    pass


class ToolSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


SessionFactory = Callable[[], Any]


@dataclass(frozen=True)
class AgendaProject:
    project_id: str
    title: str
    category_title: str
    note_count: int
    archived: bool = False


@dataclass(frozen=True)
class AgendaNoteSummary:
    note_id: str
    title: str
    project_id: str
    project_title: str
    start_date: str
    edited_date: str
    completed: bool
    on_the_agenda: bool


@dataclass(frozen=True)
class AgendaNote:
    note_id: str
    title: str
    project_id: str
    project_title: str
    markdown: str
    created_date: str
    edited_date: str
    completed: bool
    on_the_agenda: bool

    @property
    def source_reference(self) -> str:
        return f"agenda:{self.note_id}"


class AgendaService:
    def __init__(self, session_factory: SessionFactory | None = None) -> None:
        self._session_factory = session_factory or open_agenda_session

    def list_projects(self) -> list[AgendaProject]:
        return anyio.run(self._list_projects)

    def list_notes(self, project: AgendaProject, limit: int = 30) -> list[AgendaNoteSummary]:
        if not 1 <= limit <= MAX_NOTES:
            raise ValueError(f"Agenda note limit must be between 1 and {MAX_NOTES}.")
        return anyio.run(self._list_notes, project, limit)

    def list_recent_notes(
        self,
        projects: list[AgendaProject],
        days: int = 7,
        now: datetime | None = None,
    ) -> list[AgendaNoteSummary]:
        if not projects:
            raise ValueError("At least one active Agenda project is required.")
        if not 1 <= days <= 31:
            raise ValueError("The recent Agenda window must be between 1 and 31 days.")
        effective_now = now or datetime.now(UTC)
        if effective_now.tzinfo is None:
            effective_now = effective_now.replace(tzinfo=UTC)
        return anyio.run(self._list_recent_notes, projects, days, effective_now)

    def get_note(self, summary: AgendaNoteSummary) -> AgendaNote:
        return anyio.run(self._get_note, summary)

    def get_notes(self, summaries: list[AgendaNoteSummary]) -> list[AgendaNote]:
        if not summaries:
            raise ValueError("Select at least one Agenda note.")
        if len(summaries) > MAX_REPORT_NOTES:
            raise ValueError(
                f"Select no more than {MAX_REPORT_NOTES} Agenda notes for one report."
            )
        if len({summary.note_id for summary in summaries}) != len(summaries):
            raise ValueError("The selected Agenda notes contain duplicate identifiers.")
        return anyio.run(self._get_notes, summaries)

    async def _list_projects(self) -> list[AgendaProject]:
        async with self._session_factory() as session:
            payload = await _call_json(
                session,
                "agenda_list_projects",
                {"includeArchived": False},
            )
        raw_projects = _list_field(payload, "projects")
        projects = [_parse_project(item) for item in raw_projects[:MAX_PROJECTS]]
        return sorted(projects, key=lambda item: (item.category_title, item.title))

    async def _list_notes(
        self,
        project: AgendaProject,
        limit: int,
    ) -> list[AgendaNoteSummary]:
        async with self._session_factory() as session:
            payload = await _call_json(
                session,
                "agenda_search_notes",
                {"projectIds": [project.project_id], "limit": limit},
            )
        notes = [_parse_note_summary(item) for item in _list_field(payload, "notes")]
        return sorted(notes, key=lambda item: item.edited_date, reverse=True)

    async def _list_recent_notes(
        self,
        projects: list[AgendaProject],
        days: int,
        now: datetime,
    ) -> list[AgendaNoteSummary]:
        project_ids = list(dict.fromkeys(project.project_id for project in projects))
        async with self._session_factory() as session:
            payload = await _call_json(
                session,
                "agenda_search_notes",
                {"projectIds": project_ids, "limit": MAX_NOTES},
            )
        cutoff = now.astimezone(UTC) - timedelta(days=days)
        notes = [_parse_note_summary(item) for item in _list_field(payload, "notes")]
        recent = [note for note in notes if _note_timestamp(note) >= cutoff]
        return sorted(recent, key=_note_timestamp, reverse=True)

    async def _get_note(self, summary: AgendaNoteSummary) -> AgendaNote:
        async with self._session_factory() as session:
            payload = await _call_json(
                session,
                "agenda_get_note",
                {"noteId": summary.note_id},
            )
        return _validated_note(payload, summary)

    async def _get_notes(self, summaries: list[AgendaNoteSummary]) -> list[AgendaNote]:
        notes: list[AgendaNote] = []
        async with self._session_factory() as session:
            for summary in summaries:
                payload = await _call_json(
                    session,
                    "agenda_get_note",
                    {"noteId": summary.note_id},
                )
                note = _validated_note(payload, summary)
                notes.append(note)
        return notes


@asynccontextmanager
async def open_agenda_session() -> AsyncIterator[ClientSession]:
    url = os.environ.get("PEA_AGENDA_MCP_URL", DEFAULT_AGENDA_MCP_URL)
    try:
        async with (
            streamable_http_client(url) as (read_stream, write_stream, _),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            yield session
    except Exception as exc:
        if error := _find_agenda_error(exc):
            raise error
        raise AgendaConnectionError(
            "Agenda could not be reached. Keep Agenda open and enable its MCP integration."
        ) from exc


async def _call_json(session: ToolSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await session.call_tool(name, arguments)
    if getattr(result, "isError", False):
        raise AgendaError(f"Agenda MCP read tool '{name}' failed.")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    for item in getattr(result, "content", []):
        text = getattr(item, "text", None)
        if text:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise AgendaError(f"Agenda MCP read tool '{name}' returned invalid data.") from exc
            if isinstance(payload, dict):
                return payload
    raise AgendaError(f"Agenda MCP read tool '{name}' returned no structured data.")


def _list_field(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = payload.get(field)
    if not isinstance(value, list):
        raise AgendaError(f"Agenda returned an invalid '{field}' list.")
    if not all(isinstance(item, dict) for item in value):
        raise AgendaError(f"Agenda returned invalid entries in '{field}'.")
    return value


def _parse_project(value: dict[str, Any]) -> AgendaProject:
    project_id = _required_string(value, "id", "project")
    title = _required_string(value, "title", "project")
    category_title = str(value.get("categoryTitle") or "Uncategorised")
    note_count = value.get("noteCount", 0)
    if not isinstance(note_count, int) or note_count < 0:
        raise AgendaError("Agenda returned an invalid project note count.")
    return AgendaProject(
        project_id=project_id,
        title=title,
        category_title=category_title,
        note_count=note_count,
        archived=bool(value.get("archived", False)),
    )


def _parse_note_summary(value: dict[str, Any]) -> AgendaNoteSummary:
    return AgendaNoteSummary(
        note_id=_required_string(value, "id", "note"),
        title=_required_string(value, "title", "note"),
        project_id=_required_string(value, "projectId", "note"),
        project_title=str(value.get("projectTitle") or "Unknown project"),
        start_date=str(value.get("startDate") or ""),
        edited_date=str(value.get("editedDate") or ""),
        completed=bool(value.get("completed", False)),
        on_the_agenda=bool(value.get("onTheAgenda", False)),
    )


def _parse_note(value: dict[str, Any]) -> AgendaNote:
    markdown = value.get("markdown")
    if not isinstance(markdown, str):
        raise AgendaError("Agenda returned a note without Markdown content.")
    return AgendaNote(
        note_id=_required_string(value, "id", "note"),
        title=_required_string(value, "title", "note"),
        project_id=_required_string(value, "projectId", "note"),
        project_title=str(value.get("projectTitle") or "Unknown project"),
        markdown=markdown,
        created_date=str(value.get("createdDate") or ""),
        edited_date=str(value.get("editedDate") or ""),
        completed=bool(value.get("completed", False)),
        on_the_agenda=bool(value.get("onTheAgenda", False)),
    )


def _validated_note(value: dict[str, Any], summary: AgendaNoteSummary) -> AgendaNote:
    note = _parse_note(value)
    if note.note_id != summary.note_id:
        raise AgendaError("Agenda returned a different note than the one selected.")
    if len(note.markdown) > MAX_NOTE_CHARACTERS:
        raise AgendaError(
            f"The Agenda note exceeds the {MAX_NOTE_CHARACTERS:,}-character pilot limit."
        )
    return note


def _note_timestamp(note: AgendaNoteSummary) -> datetime:
    value = note.edited_date or note.start_date
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _required_string(value: dict[str, Any], field: str, object_name: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise AgendaError(f"Agenda returned a {object_name} without a valid {field}.")
    return result


def _find_agenda_error(error: BaseException) -> AgendaError | None:
    if isinstance(error, AgendaError):
        return error
    for nested in getattr(error, "exceptions", ()):
        if found := _find_agenda_error(nested):
            return found
    return None
