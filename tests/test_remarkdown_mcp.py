from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pea_app.remarkdown_mcp import (
    REMARKDOWN_MCP_URL,
    RemarkdownDocumentSummary,
    RemarkdownError,
    RemarkdownService,
    terminate_authentication_bridges,
)


class FakeSession:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return SimpleNamespace(
            isError=False,
            structuredContent=self.responses[name],
            content=[],
        )


def session_factory(session: FakeSession) -> Any:
    @asynccontextmanager
    async def factory() -> Any:
        yield session

    return factory


def authorised_service(monkeypatch: pytest.MonkeyPatch, session: FakeSession) -> RemarkdownService:
    monkeypatch.setattr(RemarkdownService, "is_installed", staticmethod(lambda: True))
    monkeypatch.setattr(
        RemarkdownService, "has_local_authorisation", staticmethod(lambda: True)
    )
    return RemarkdownService(session_factory(session))


def test_whoami_parses_bounded_account_status(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        {
            "whoami": {
                "remarkable_paired": True,
                "reading": {
                    "folder": "PEA",
                    "scope": "folder",
                    "transcription_window": "30 days",
                    "credits": {"balance": 42, "paused": False},
                    "documents": {"synced": 12, "total": 15},
                },
            }
        }
    )

    identity = authorised_service(monkeypatch, session).whoami()

    assert identity.paired is True
    assert identity.folder == "PEA"
    assert identity.transcription_window == "30 days"
    assert identity.credit_balance == 42
    assert session.calls == [("whoami", {})]


def test_recent_document_list_filters_age_and_folders(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        {
            "list_documents": {
                "items": [
                    {
                        "id": "recent",
                        "name": "Recent note",
                        "kind": "DocumentType",
                        "parent": "PEA",
                        "modified": "2026-08-05T12:00:00Z",
                        "content_status": "transcribed",
                    },
                    {
                        "id": "old",
                        "name": "Old note",
                        "kind": "DocumentType",
                        "modified": "2026-06-01T12:00:00Z",
                        "content_status": "typed",
                    },
                    {
                        "id": "folder",
                        "name": "Folder",
                        "kind": "CollectionType",
                        "modified": "2026-08-05T12:00:00Z",
                    },
                ]
            }
        }
    )

    documents = authorised_service(monkeypatch, session).list_recent_documents(
        now=datetime(2026, 8, 6, tzinfo=UTC)
    )

    assert [document.document_id for document in documents] == ["recent"]
    assert documents[0].text_ready is True


def test_fetch_uses_cache_only_for_selected_ready_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(
        {
            "fetch_document": {
                "status": "ok",
                "id": "selected",
                "name": "Selected note",
                "content_kind": "transcribed",
                "content_status": "transcribed",
                "markdown": "Reviewed text",
                "page_count": 2,
                "ink_pages": [1, 2],
            }
        }
    )
    summary = RemarkdownDocumentSummary(
        "selected", "Selected note", "PEA", "2026-08-05T12:00:00Z", "transcribed"
    )

    document = authorised_service(monkeypatch, session).fetch_document(summary)

    assert document.markdown == "Reviewed text"
    assert document.source_kind == "handwriting transcribed by remarkdown"
    assert session.calls == [("fetch_document", {"id": "selected", "force": False})]


def test_document_outside_window_is_blocked_before_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession({})
    summary = RemarkdownDocumentSummary(
        "old", "Old note", "PEA", "2026-01-01T12:00:00Z", "images_only_outside_window"
    )

    with pytest.raises(RemarkdownError, match="No paid transcription was started"):
        authorised_service(monkeypatch, session).fetch_document(summary)

    assert session.calls == []


def test_local_authorisation_detects_private_token_cache(tmp_path: Path) -> None:
    token_directory = tmp_path / "server"
    token_directory.mkdir()
    (token_directory / "server_tokens.json").write_text(
        json.dumps({"access_token": "present"}), encoding="utf-8"
    )

    assert RemarkdownService.has_local_authorisation(tmp_path) is True


def test_authentication_recovery_stops_only_own_remarkdown_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process_table = SimpleNamespace(
        stdout=(
            f"101 55 node /opt/homebrew/bin/mcp-remote {REMARKDOWN_MCP_URL}\n"
            f"102 77 node /opt/homebrew/bin/mcp-remote {REMARKDOWN_MCP_URL}\n"
            "103 55 node /opt/homebrew/bin/mcp-remote https://example.test/mcp\n"
        )
    )
    stopped: list[tuple[int, int]] = []
    monkeypatch.setattr("pea_app.remarkdown_mcp.subprocess.run", lambda *_, **__: process_table)
    monkeypatch.setattr(
        "pea_app.remarkdown_mcp.os.kill", lambda pid, sig: stopped.append((pid, sig))
    )

    count = terminate_authentication_bridges(parent_pid=55)

    assert count == 1
    assert [pid for pid, _ in stopped] == [101]
