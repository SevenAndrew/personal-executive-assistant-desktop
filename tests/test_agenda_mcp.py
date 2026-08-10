from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from pea_app.agenda_mcp import AgendaError, AgendaProject, AgendaService

PROJECTS = {
    "projects": [
        {
            "id": "project-training",
            "title": "Training Delivery & Student Cohorts",
            "categoryId": "category-work",
            "categoryTitle": "10 Work Areas",
            "archived": False,
            "noteCount": 2,
        },
        {
            "id": "project-weekly",
            "title": "Weekly Reviews",
            "categoryId": "category-gtd",
            "categoryTitle": "00 GTD System",
            "archived": False,
            "noteCount": 1,
        },
    ]
}

NOTES = {
    "notes": [
        {
            "id": "note-older",
            "title": "Earlier update",
            "projectId": "project-training",
            "projectTitle": "Training Delivery & Student Cohorts",
            "startDate": "2026-08-04",
            "editedDate": "2026-08-04T09:00:00Z",
            "completed": False,
            "onTheAgenda": False,
            "snippet": "Not retained by the adapter.",
        },
        {
            "id": "note-newer",
            "title": "Current update",
            "projectId": "project-training",
            "projectTitle": "Training Delivery & Student Cohorts",
            "startDate": "2026-08-06",
            "editedDate": "2026-08-06T09:00:00Z",
            "completed": False,
            "onTheAgenda": True,
            "snippet": "Not retained by the adapter.",
        },
    ],
    "truncated": False,
    "totalCount": 2,
}

NOTE = {
    "id": "note-newer",
    "title": "Current update",
    "projectId": "project-training",
    "projectTitle": "Training Delivery & Student Cohorts",
    "markdown": "## Update\n\nThe planning assumption requires confirmation.",
    "createdDate": "2026-08-05T10:00:00Z",
    "editedDate": "2026-08-06T09:00:00Z",
    "completed": False,
    "onTheAgenda": True,
    "pinned": False,
    "footnote": False,
}


class FakeAgendaSession:
    def __init__(self, responses: dict[str, list[dict[str, Any]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        payload = self.responses[name].pop(0)
        return SimpleNamespace(
            isError=False,
            structuredContent=None,
            content=[SimpleNamespace(text=json.dumps(payload))],
        )


def session_factory(session: FakeAgendaSession) -> Any:
    @asynccontextmanager
    async def factory() -> Any:
        yield session

    return factory


def test_lists_unarchived_projects_without_note_content() -> None:
    session = FakeAgendaSession({"agenda_list_projects": [PROJECTS]})

    projects = AgendaService(session_factory(session)).list_projects()

    assert [project.title for project in projects] == [
        "Weekly Reviews",
        "Training Delivery & Student Cohorts",
    ]
    assert projects[1].note_count == 2
    assert session.calls == [("agenda_list_projects", {"includeArchived": False})]


def test_lists_only_selected_project_and_sorts_by_edit_date() -> None:
    project = AgendaProject(
        project_id="project-training",
        title="Training Delivery & Student Cohorts",
        category_title="10 Work Areas",
        note_count=2,
    )
    session = FakeAgendaSession({"agenda_search_notes": [NOTES]})

    notes = AgendaService(session_factory(session)).list_notes(project, limit=30)

    assert [note.note_id for note in notes] == ["note-newer", "note-older"]
    assert session.calls == [
        ("agenda_search_notes", {"projectIds": ["project-training"], "limit": 30})
    ]
    assert not hasattr(notes[0], "snippet")


def test_lists_last_seven_days_across_active_projects_using_metadata_only() -> None:
    projects = [
        AgendaProject("project-training", "Training", "10 Work Areas", 2),
        AgendaProject("project-weekly", "Weekly", "00 GTD System", 1),
    ]
    payload = {
        "notes": [
            *NOTES["notes"],
            {
                "id": "note-old",
                "title": "Old note",
                "projectId": "project-weekly",
                "projectTitle": "Weekly",
                "startDate": "2026-06-01",
                "editedDate": "2026-06-01T09:00:00Z",
                "completed": False,
                "onTheAgenda": False,
            },
        ]
    }
    session = FakeAgendaSession({"agenda_search_notes": [payload]})

    notes = AgendaService(session_factory(session)).list_recent_notes(
        projects,
        now=datetime(2026, 8, 6, 22, tzinfo=UTC),
    )

    assert [note.note_id for note in notes] == ["note-newer", "note-older"]
    assert session.calls == [
        (
            "agenda_search_notes",
            {
                "projectIds": ["project-training", "project-weekly"],
                "limit": 50,
            },
        )
    ]


def test_loads_only_selected_note_and_adds_stable_source_reference() -> None:
    project = AgendaProject("project-training", "Training", "10 Work Areas", 1)
    session = FakeAgendaSession({"agenda_search_notes": [NOTES], "agenda_get_note": [NOTE]})
    service = AgendaService(session_factory(session))
    summary = service.list_notes(project)[0]

    note = service.get_note(summary)

    assert note.markdown.startswith("## Update")
    assert note.source_reference == "agenda:note-newer"
    assert session.calls[-1] == ("agenda_get_note", {"noteId": "note-newer"})


def test_loads_only_explicit_report_note_selection() -> None:
    project = AgendaProject("project-training", "Training", "10 Work Areas", 2)
    second_note = {
        **NOTE,
        "id": "note-older",
        "title": "Earlier update",
        "editedDate": "2026-08-04T09:00:00Z",
    }
    session = FakeAgendaSession(
        {
            "agenda_search_notes": [NOTES],
            "agenda_get_note": [NOTE, second_note],
        }
    )
    service = AgendaService(session_factory(session))
    summaries = service.list_notes(project)

    notes = service.get_notes(summaries)

    assert [note.note_id for note in notes] == ["note-newer", "note-older"]
    assert session.calls[-2:] == [
        ("agenda_get_note", {"noteId": "note-newer"}),
        ("agenda_get_note", {"noteId": "note-older"}),
    ]


def test_rejects_unstructured_tool_output() -> None:
    class InvalidSession:
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            return SimpleNamespace(
                isError=False,
                structuredContent=None,
                content=[SimpleNamespace(text="not-json")],
            )

    with pytest.raises(AgendaError, match="invalid data"):
        AgendaService(session_factory(InvalidSession())).list_projects()
