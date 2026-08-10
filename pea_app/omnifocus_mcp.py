from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEFAULT_OMNIFOCUS_DIRECTORY = Path.home() / ".local/share/codex-mcp/omnifocus-controlled"
TASK_VIEWS = ("inbox", "available", "waiting", "flagged", "remaining")
MAX_TASKS = 100


def task_deep_link(task_id: str) -> str:
    cleaned = task_id.strip()
    if not cleaned:
        raise ValueError("An OmniFocus task identifier is required.")
    return f"omnifocus:///task/{quote(cleaned, safe='')}"


class OmniFocusError(RuntimeError):
    pass


class OmniFocusConnectionError(OmniFocusError):
    pass


class ToolSession(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


SessionFactory = Callable[[], Any]


@dataclass(frozen=True)
class OmniFocusStatus:
    application: str
    version: str
    inbox: int
    projects: int
    active_projects: int
    tags: int
    open_tasks: int
    available_or_next: int
    waiting: int
    flagged: int


@dataclass(frozen=True)
class OmniFocusTask:
    task_id: str
    name: str
    project: str
    flagged: bool
    due: str
    defer: str
    status: str


class OmniFocusService:
    def __init__(self, session_factory: SessionFactory | None = None) -> None:
        self._session_factory = session_factory or open_omnifocus_session

    def status(self) -> OmniFocusStatus:
        return anyio.run(self._status)

    def list_tasks(self, view: str = "available", limit: int = 50) -> list[OmniFocusTask]:
        if view not in TASK_VIEWS:
            raise ValueError("Unsupported OmniFocus task view.")
        if not 1 <= limit <= MAX_TASKS:
            raise ValueError(f"OmniFocus task limit must be between 1 and {MAX_TASKS}.")
        return anyio.run(self._list_tasks, view, limit)

    async def _status(self) -> OmniFocusStatus:
        async with self._session_factory() as session:
            result = await _call_result(session, "omnifocus_status", {})
        if not isinstance(result, dict):
            raise OmniFocusError("OmniFocus returned an invalid status object.")
        return OmniFocusStatus(
            application=_required_string(result, "application", "status"),
            version=_required_string(result, "version", "status"),
            inbox=_required_count(result, "inbox"),
            projects=_required_count(result, "projects"),
            active_projects=_required_count(result, "activeProjects"),
            tags=_required_count(result, "tags"),
            open_tasks=_required_count(result, "openTasks"),
            available_or_next=_required_count(result, "availableOrNext"),
            waiting=_required_count(result, "waiting"),
            flagged=_required_count(result, "flagged"),
        )

    async def _list_tasks(self, view: str, limit: int) -> list[OmniFocusTask]:
        async with self._session_factory() as session:
            result = await _call_result(
                session,
                "omnifocus_list_tasks",
                {"view": view, "limit": limit},
            )
        if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
            raise OmniFocusError("OmniFocus returned an invalid task list.")
        return [_parse_task(item) for item in result]


@asynccontextmanager
async def open_omnifocus_session() -> AsyncIterator[ClientSession]:
    directory = Path(
        os.environ.get("PEA_OMNIFOCUS_MCP_DIRECTORY", str(DEFAULT_OMNIFOCUS_DIRECTORY))
    ).expanduser()
    python = directory / ".venv/bin/python"
    server = directory / "server.py"
    if not python.is_file() or not server.is_file():
        raise OmniFocusConnectionError(
            "The controlled OmniFocus MCP adapter is not installed on this Mac."
        )
    parameters = StdioServerParameters(command=str(python), args=[str(server)])
    try:
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            yield session
    except Exception as exc:
        if error := _find_omnifocus_error(exc):
            raise error
        raise OmniFocusConnectionError(
            "OmniFocus could not be reached. Keep OmniFocus open, enable external scripts and "
            "approve only the reviewed controlled bridge."
        ) from exc


async def _call_result(session: ToolSession, name: str, arguments: dict[str, Any]) -> Any:
    response = await session.call_tool(name, arguments)
    if getattr(response, "isError", False):
        raise OmniFocusError(f"OmniFocus MCP tool '{name}' failed.")
    payload = _response_payload(response, name)
    if payload.get("ok") is not True:
        message = payload.get("error")
        raise OmniFocusError(str(message or "OmniFocus returned an unspecified error."))
    return payload.get("result")


def _response_payload(response: Any, name: str) -> dict[str, Any]:
    structured = getattr(response, "structuredContent", None)
    if isinstance(structured, dict) and "ok" in structured:
        return structured
    for item in getattr(response, "content", []):
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OmniFocusError(f"OmniFocus MCP tool '{name}' returned invalid data.") from exc
        if isinstance(payload, dict):
            return payload
    raise OmniFocusError(f"OmniFocus MCP tool '{name}' returned no structured data.")


def _parse_task(value: dict[str, Any]) -> OmniFocusTask:
    return OmniFocusTask(
        task_id=_required_string(value, "id", "task"),
        name=_required_string(value, "name", "task"),
        project=str(value.get("project") or "Inbox"),
        flagged=bool(value.get("flagged", False)),
        due=str(value.get("due") or ""),
        defer=str(value.get("defer") or ""),
        status=_required_string(value, "status", "task"),
    )


def _required_string(value: dict[str, Any], field: str, object_name: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise OmniFocusError(f"OmniFocus returned a {object_name} without a valid {field}.")
    return result


def _required_count(value: dict[str, Any], field: str) -> int:
    result = value.get(field)
    if not isinstance(result, int) or isinstance(result, bool) or result < 0:
        raise OmniFocusError(f"OmniFocus returned an invalid '{field}' count.")
    return result


def _find_omnifocus_error(error: BaseException) -> OmniFocusError | None:
    if isinstance(error, OmniFocusError):
        return error
    for nested in getattr(error, "exceptions", ()):
        if found := _find_omnifocus_error(nested):
            return found
    return None
