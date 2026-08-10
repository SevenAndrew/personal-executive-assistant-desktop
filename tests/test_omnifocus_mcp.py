from __future__ import annotations

import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from pea_app.omnifocus_mcp import OmniFocusError, OmniFocusService, task_deep_link

STATUS = {
    "ok": True,
    "result": {
        "application": "OmniFocus",
        "version": "4.8.12",
        "inbox": 3,
        "projects": 21,
        "activeProjects": 18,
        "tags": 90,
        "openTasks": 70,
        "availableOrNext": 22,
        "waiting": 7,
        "flagged": 4,
    },
}

TASKS = {
    "ok": True,
    "result": [
        {
            "id": "task-1",
            "name": "Review training plan",
            "project": "Training",
            "tags": ["Office", "Person name is deliberately discarded"],
            "flagged": True,
            "due": "2026-08-12T10:00:00.000Z",
            "defer": None,
            "status": "Available",
            "note": "Must never be retained.",
        }
    ],
}


class FakeSession:
    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return SimpleNamespace(
            isError=False,
            structuredContent=None,
            content=[SimpleNamespace(text=json.dumps(self.payloads[name]))],
        )


def session_factory(session: FakeSession) -> Any:
    @asynccontextmanager
    async def factory() -> Any:
        yield session

    return factory


def test_reads_aggregate_status() -> None:
    session = FakeSession({"omnifocus_status": STATUS})

    status = OmniFocusService(session_factory(session)).status()

    assert status.application == "OmniFocus"
    assert status.active_projects == 18
    assert status.available_or_next == 22
    assert session.calls == [("omnifocus_status", {})]


def test_lists_bounded_task_metadata_without_notes_or_tags() -> None:
    session = FakeSession({"omnifocus_list_tasks": TASKS})

    tasks = OmniFocusService(session_factory(session)).list_tasks("available", 25)

    assert tasks[0].name == "Review training plan"
    assert tasks[0].project == "Training"
    assert not hasattr(tasks[0], "note")
    assert not hasattr(tasks[0], "tags")
    assert session.calls == [("omnifocus_list_tasks", {"view": "available", "limit": 25})]


def test_builds_encoded_task_deep_link() -> None:
    assert task_deep_link(" task/1 ") == "omnifocus:///task/task%2F1"


def test_rejects_empty_task_deep_link() -> None:
    with pytest.raises(ValueError, match="identifier"):
        task_deep_link("   ")


def test_rejects_unsupported_view_before_call() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        OmniFocusService().list_tasks("people", 25)


def test_surfaces_controlled_adapter_error() -> None:
    session = FakeSession(
        {"omnifocus_status": {"ok": False, "error": "External script approval required."}}
    )

    with pytest.raises(OmniFocusError, match="approval"):
        OmniFocusService(session_factory(session)).status()
