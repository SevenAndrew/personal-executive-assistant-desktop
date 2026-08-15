from __future__ import annotations

import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import anyio
from openai import OpenAI
from PySide6.QtCore import QSettings

from .agenda_mcp import open_agenda_session
from .devonthink_handoff import open_devonthink_session
from .models import MODEL_PROFILES
from .omnifocus_mcp import OmniFocusService
from .plaud_cli import PlaudCli
from .remarkdown_mcp import RemarkdownService
from .secrets import resolve_openai_api_key

LOG_DIRECTORY = Path.home() / "Library" / "Logs" / "personal-executive-assistant"
LOG_PATH = LOG_DIRECTORY / "runtime.log"
USAGE_DASHBOARD_URL = "https://platform.openai.com/usage"
BILLING_URL = "https://platform.openai.com/settings/organization/billing/overview"
STARTUP_HEALTH_VERSION = "1"


@dataclass(frozen=True)
class UsageSnapshot:
    requests: int
    input_tokens: int
    output_tokens: int
    last_model: str
    last_updated: str

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class UsageTracker:
    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def record(self, model: str, input_tokens: int | None, output_tokens: int | None) -> None:
        snapshot = self.snapshot()
        self._settings.setValue("usage/requests", snapshot.requests + 1)
        self._settings.setValue(
            "usage/input_tokens",
            snapshot.input_tokens + max(input_tokens or 0, 0),
        )
        self._settings.setValue(
            "usage/output_tokens",
            snapshot.output_tokens + max(output_tokens or 0, 0),
        )
        self._settings.setValue("usage/last_model", model)
        self._settings.setValue("usage/last_updated", datetime.now(UTC).isoformat(timespec="seconds"))
        self._settings.sync()

    def snapshot(self) -> UsageSnapshot:
        return UsageSnapshot(
            requests=_setting_int(self._settings, "usage/requests"),
            input_tokens=_setting_int(self._settings, "usage/input_tokens"),
            output_tokens=_setting_int(self._settings, "usage/output_tokens"),
            last_model=str(self._settings.value("usage/last_model", "Not recorded")),
            last_updated=str(self._settings.value("usage/last_updated", "Not recorded")),
        )


@dataclass(frozen=True)
class HealthResult:
    component: str
    status: str
    detail: str


def health_check_is_complete(results: list[HealthResult]) -> bool:
    """Return true only when every required startup check reports OK."""
    return bool(results) and all(result.status == "OK" for result in results)


class HealthService:
    def __init__(
        self,
        openai_client_factory: Callable[..., Any] = OpenAI,
        api_key_resolver: Callable[[], str] = resolve_openai_api_key,
        plaud_factory: Callable[[], PlaudCli] = PlaudCli,
        omnifocus_factory: Callable[[], OmniFocusService] = OmniFocusService,
        remarkdown_factory: Callable[[], RemarkdownService] = RemarkdownService,
        agenda_session_factory: Callable[[], Any] = open_agenda_session,
        devonthink_session_factory: Callable[[], Any] = open_devonthink_session,
    ) -> None:
        self._openai_client_factory = openai_client_factory
        self._api_key_resolver = api_key_resolver
        self._plaud_factory = plaud_factory
        self._omnifocus_factory = omnifocus_factory
        self._remarkdown_factory = remarkdown_factory
        self._agenda_session_factory = agenda_session_factory
        self._devonthink_session_factory = devonthink_session_factory

    def run(self) -> list[HealthResult]:
        results = [
            self._check_openai(),
            self._check_node(),
            self._check_plaud(),
            self._check_omnifocus(),
        ]
        results.append(
            self._check_mcp(
                "Agenda MCP",
                self._agenda_session_factory,
                {"agenda_list_projects", "agenda_search_notes", "agenda_get_note"},
            )
        )
        results.append(
            self._check_mcp(
                "DEVONthink MCP",
                self._devonthink_session_factory,
                {
                    "get_databases",
                    "lookup_records",
                    "create_record",
                    "get_record_properties",
                    "get_record_text",
                },
            )
        )
        results.append(self._check_remarkdown())
        return results

    def _check_openai(self) -> HealthResult:
        try:
            client = self._openai_client_factory(api_key=self._api_key_resolver())
            client.models.retrieve(MODEL_PROFILES[0].model)
        except Exception:  # noqa: BLE001 - health checks return bounded status only.
            return HealthResult(
                "OpenAI API",
                "Unavailable",
                "The key is missing, rejected or cannot reach the model endpoint.",
            )
        return HealthResult(
            "OpenAI API",
            "OK",
            f"Key accepted; {MODEL_PROFILES[0].model} is available. No inference was run.",
        )

    @staticmethod
    def _check_node() -> HealthResult:
        executable = shutil.which("node")
        if not executable:
            return HealthResult("Node.js", "Unavailable", "Node.js is not installed or not on PATH.")
        try:
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return HealthResult("Node.js", "Unavailable", "Node.js could not be started.")
        version = result.stdout.strip() if result.returncode == 0 else "version unavailable"
        status = "OK" if result.returncode == 0 else "Unavailable"
        return HealthResult("Node.js", status, version)

    def _check_plaud(self) -> HealthResult:
        try:
            client = self._plaud_factory()
            if not client.is_installed():
                return HealthResult("PLAUD", "Unavailable", "Official PLAUD CLI not installed.")
            if not client.is_authenticated():
                return HealthResult("PLAUD", "Attention", "CLI installed; sign-in required.")
        except Exception:  # noqa: BLE001 - health checks return bounded status only.
            return HealthResult("PLAUD", "Unavailable", "PLAUD status check failed.")
        return HealthResult("PLAUD", "OK", "Official CLI installed and authorised.")

    def _check_omnifocus(self) -> HealthResult:
        try:
            status = self._omnifocus_factory().status()
        except Exception:  # noqa: BLE001 - health checks return bounded status only.
            return HealthResult(
                "OmniFocus MCP",
                "Unavailable",
                "The controlled local adapter, OmniFocus or external-script approval is unavailable.",
            )
        return HealthResult(
            "OmniFocus MCP",
            "OK",
            f"Controlled local adapter connected to {status.application} {status.version}; "
            "aggregate status only.",
        )

    def _check_remarkdown(self) -> HealthResult:
        try:
            service = self._remarkdown_factory()
            if not service.is_installed():
                return HealthResult(
                    "remarkdown", "Unavailable", "Official MCP bridge not installed."
                )
            if not service.has_local_authorisation():
                return HealthResult(
                    "remarkdown", "Attention", "Bridge installed; app sign-in required."
                )
            identity = service.whoami()
            if not identity.paired:
                return HealthResult(
                    "remarkdown", "Attention", "Signed in; reMarkable pairing is required."
                )
        except Exception:  # noqa: BLE001 - health checks return bounded status only.
            return HealthResult(
                "remarkdown", "Unavailable", "Connection or authorisation check failed."
            )
        paused = "; transcription paused" if identity.transcription_paused else ""
        return HealthResult(
            "remarkdown",
            "OK",
            f"Signed in and paired; window {identity.transcription_window}; "
            f"{identity.credit_balance:,} credit(s){paused}. No document content was read.",
        )

    @staticmethod
    def _check_mcp(
        component: str,
        session_factory: Callable[[], Any],
        expected_tools: set[str],
    ) -> HealthResult:
        try:
            tools = anyio.run(_list_mcp_tools, session_factory)
        except Exception:  # noqa: BLE001 - health checks return bounded status only.
            return HealthResult(
                component,
                "Unavailable",
                "Connection or authorisation check failed; keep the application and MCP enabled.",
            )
        missing = sorted(expected_tools - tools)
        if missing:
            return HealthResult(
                component,
                "Attention",
                f"Connected, but expected capabilities are missing: {', '.join(missing)}.",
            )
        return HealthResult(
            component,
            "OK",
            "Connected and expected capabilities are advertised; no content was read.",
        )


async def _list_mcp_tools(session_factory: Callable[[], Any]) -> set[str]:
    async with session_factory() as session:
        result = await session.list_tools()
    return {tool.name for tool in result.tools}


def configure_runtime_logging(log_path: Path = LOG_PATH) -> logging.Logger:
    logger = logging.getLogger("pea_app.runtime")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    resolved = log_path.resolve()
    if any(getattr(handler, "baseFilename", None) == str(resolved) for handler in logger.handlers):
        return logger

    log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(log_path.parent, 0o700)
    log_path.touch(exist_ok=True)
    os.chmod(log_path, 0o600)
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def log_event(event: str, **fields: object) -> None:
    details = " ".join(
        f"{key}={_safe_log_value(value)}" for key, value in sorted(fields.items())
    )
    message = f"event={_safe_log_value(event)}"
    if details:
        message = f"{message} {details}"
    logging.getLogger("pea_app.runtime").info(message)


def read_log_tail(log_path: Path = LOG_PATH, max_lines: int = 300) -> str:
    if not log_path.is_file():
        return "No runtime log has been created yet."
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "The runtime log could not be read."
    return "\n".join(lines[-max(max_lines, 1) :]) or "The runtime log is empty."


def _setting_int(settings: QSettings, key: str) -> int:
    try:
        return max(int(settings.value(key, 0)), 0)
    except (TypeError, ValueError):
        return 0


def _safe_log_value(value: object) -> str:
    return str(value).replace("\n", " ").replace("\r", " ")[:120]
