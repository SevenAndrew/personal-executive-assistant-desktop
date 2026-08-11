from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QSettings

from pea_app.diagnostics import (
    HealthResult,
    HealthService,
    UsageTracker,
    configure_runtime_logging,
    health_check_is_complete,
    log_event,
    read_log_tail,
)


def test_startup_health_requires_every_component_to_be_ok() -> None:
    assert health_check_is_complete([HealthResult("OpenAI API", "OK", "ready")])
    assert not health_check_is_complete([])
    assert not health_check_is_complete(
        [
            HealthResult("OpenAI API", "OK", "ready"),
            HealthResult("PLAUD", "Attention", "sign-in required"),
        ]
    )


def test_usage_tracker_persists_aggregate_tokens(tmp_path: Path) -> None:
    settings = QSettings(str(tmp_path / "usage.ini"), QSettings.Format.IniFormat)
    tracker = UsageTracker(settings)

    tracker.record("gpt-5.6-luna", 120, 30)
    tracker.record("gpt-5.6-terra", 200, 50)
    snapshot = tracker.snapshot()

    assert snapshot.requests == 2
    assert snapshot.input_tokens == 320
    assert snapshot.output_tokens == 80
    assert snapshot.total_tokens == 400
    assert snapshot.last_model == "gpt-5.6-terra"


def test_runtime_log_is_private_bounded_and_sanitised(tmp_path: Path) -> None:
    path = tmp_path / "runtime.log"
    logger = configure_runtime_logging(path)

    log_event("test\nevent", operation="health\ncheck")
    for handler in logger.handlers:
        handler.flush()

    content = read_log_tail(path)
    assert "event=test event" in content
    assert "operation=health check" in content
    assert path.stat().st_mode & 0o777 == 0o600

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)


class FakeModels:
    def retrieve(self, model: str) -> object:
        return SimpleNamespace(id=model)


class FakePlaud:
    def is_installed(self) -> bool:
        return True

    def is_authenticated(self) -> bool:
        return True


class FakeRemarkdown:
    def is_installed(self) -> bool:
        return True

    def has_local_authorisation(self) -> bool:
        return False


class FakeOmniFocus:
    def status(self) -> Any:
        return SimpleNamespace(application="OmniFocus", version="4.8.13")


def tool_session_factory(names: set[str]) -> Any:
    class FakeSession:
        async def list_tools(self) -> Any:
            return SimpleNamespace(tools=[SimpleNamespace(name=name) for name in names])

    @asynccontextmanager
    async def factory() -> Any:
        yield FakeSession()

    return factory


def test_health_check_validates_connections_without_reading_content() -> None:
    agenda_tools = {"agenda_list_projects", "agenda_search_notes", "agenda_get_note"}
    devonthink_tools = {
        "get_databases",
        "lookup_records",
        "create_record",
        "get_record_properties",
        "get_record_text",
    }
    service = HealthService(
        openai_client_factory=lambda **_: SimpleNamespace(models=FakeModels()),
        api_key_resolver=lambda: "sk-test",
        plaud_factory=FakePlaud,
        omnifocus_factory=FakeOmniFocus,
        remarkdown_factory=FakeRemarkdown,
        agenda_session_factory=tool_session_factory(agenda_tools),
        devonthink_session_factory=tool_session_factory(devonthink_tools),
    )

    results = {result.component: result for result in service.run()}

    assert results["OpenAI API"].status == "OK"
    assert results["PLAUD"].status == "OK"
    assert results["OmniFocus MCP"].status == "OK"
    assert results["Agenda MCP"].status == "OK"
    assert results["DEVONthink MCP"].status == "OK"
    assert results["remarkdown"].status == "Attention"
