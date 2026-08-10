from __future__ import annotations

import os
import platform
import shlex
import shutil
import socket
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .devonthink_handoff import DEFAULT_DEVONTHINK_MCP
from .remarkdown_mcp import RemarkdownService
from .secrets import has_openai_api_key

MINIMUM_NODE_MAJOR = 20
PLAUD_PACKAGE = "@plaud-ai/cli@0.3.7"
MCP_REMOTE_PACKAGE = "mcp-remote@0.1.38"
OMNIFOCUS_MCP_PACKAGE = "mcp==1.29.0"
HOMEBREW_URL = "https://brew.sh/"
NODE_DOWNLOAD_URL = "https://nodejs.org/en/download"
UV_INSTALL_URL = "https://docs.astral.sh/uv/getting-started/installation/"
INSTALLER_ASSET_DIRECTORY = Path(__file__).resolve().parent / "installer_assets" / "omnifocus"


class SetupStatus(Enum):
    READY = "Ready"
    ATTENTION = "Attention"
    MISSING = "Missing"
    BLOCKED = "Blocked"


class SetupAction(Enum):
    NONE = "none"
    INSTALL = "install"
    OPEN_URL = "open_url"
    OPEN_APP = "open_app"
    CONFIGURE = "configure"


@dataclass(frozen=True)
class SetupComponent:
    key: str
    name: str
    purpose: str
    status: SetupStatus
    detail: str
    action: SetupAction = SetupAction.NONE
    action_label: str = ""
    action_target: str = ""
    required: bool = True


CommandRunner = Callable[[Sequence[str], int], subprocess.CompletedProcess[str]]
PathLookup = Callable[[str], str | None]
AgendaProbe = Callable[[], bool]


def _run_command(arguments: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def _agenda_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 16106), timeout=0.25):
            return True
    except OSError:
        return False


class SetupService:
    def __init__(
        self,
        *,
        path_lookup: PathLookup = shutil.which,
        runner: CommandRunner = _run_command,
        home: Path | None = None,
        asset_directory: Path = INSTALLER_ASSET_DIRECTORY,
        devonthink_mcp: Path = DEFAULT_DEVONTHINK_MCP,
        omnifocus_directory: Path | None = None,
        agenda_probe: AgendaProbe = _agenda_available,
        api_key_checker: Callable[[], bool] = has_openai_api_key,
        remarkdown_authorisation_checker: Callable[[], bool] = (
            RemarkdownService.has_local_authorisation
        ),
        machine: str | None = None,
        macos_version: str | None = None,
    ) -> None:
        self._path_lookup = path_lookup
        self._runner = runner
        self._home = (home or Path.home()).expanduser()
        self._assets = asset_directory
        self._devonthink_mcp = devonthink_mcp
        self._omnifocus_directory = (
            omnifocus_directory or self._home / ".local/share/codex-mcp/omnifocus-controlled"
        )
        self._agenda_probe = agenda_probe
        self._api_key_checker = api_key_checker
        self._remarkdown_authorisation_checker = remarkdown_authorisation_checker
        self._machine = machine or platform.machine()
        self._macos_version = macos_version if macos_version is not None else platform.mac_ver()[0]

    def check(self) -> list[SetupComponent]:
        brew = self._path_lookup("brew")
        node = self._path_lookup("node")
        npm = self._path_lookup("npm")
        plaud = self._path_lookup("plaud")
        mcp_remote = self._path_lookup("mcp-remote")
        uv = self._path_lookup("uv")
        return [
            self._system_component(),
            self._homebrew_component(brew),
            self._node_component(node, brew),
            self._uv_component(uv, brew),
            self._executable_component(
                "plaud",
                "PLAUD CLI",
                "Read selected PLAUD recording metadata and transcripts.",
                plaud,
                npm,
                PLAUD_PACKAGE,
            ),
            self._executable_component(
                "remarkdown",
                "remarkdown bridge",
                "Connect the app to the authorised remarkdown MCP endpoint.",
                mcp_remote,
                npm,
                MCP_REMOTE_PACKAGE,
            ),
            self._omnifocus_component(uv),
            self._authorisation_component(
                "openai",
                "OpenAI API key",
                "Generate controlled Minutes and summaries.",
                self._api_key_checker(),
                "Save key",
            ),
            self._authorisation_component(
                "plaud_auth",
                "PLAUD authorisation",
                "Permit the official PLAUD CLI to access this user's account.",
                bool(plaud and self._command_succeeds((plaud, "me"), 8)),
                "Sign in",
                blocked=plaud is None,
            ),
            self._authorisation_component(
                "remarkdown_auth",
                "remarkdown authorisation",
                "Authorise the private local OAuth cache used by the bridge.",
                bool(mcp_remote and self._remarkdown_authorisation_checker()),
                "Sign in",
                blocked=mcp_remote is None,
            ),
            self._agenda_component(),
            self._devonthink_component(),
        ]

    def install(self, key: str) -> str:
        if key == "node":
            brew = self._required_executable("brew")
            self._run_checked((brew, "install", "node"), 900)
            return "Node.js was installed through Homebrew."
        if key == "uv":
            brew = self._required_executable("brew")
            self._run_checked((brew, "install", "uv"), 900)
            return "uv was installed through Homebrew."
        if key == "plaud":
            npm = self._required_executable("npm")
            self._run_checked((npm, "install", "--global", PLAUD_PACKAGE), 900)
            return "The official PLAUD CLI was installed."
        if key == "remarkdown":
            npm = self._required_executable("npm")
            self._run_checked((npm, "install", "--global", MCP_REMOTE_PACKAGE), 900)
            return "The remarkdown bridge was installed."
        if key == "omnifocus":
            self._install_omnifocus_adapter()
            return "The bundled read-only OmniFocus adapter was installed."
        raise ValueError("This setup component has no automatic installation action.")

    def installation_preview(self, key: str) -> str:
        if key == "node":
            return self._command_preview("brew", "install", "node")
        if key == "uv":
            return self._command_preview("brew", "install", "uv")
        if key == "plaud":
            return self._command_preview("npm", "install", "--global", PLAUD_PACKAGE)
        if key == "remarkdown":
            return self._command_preview(
                "npm", "install", "--global", MCP_REMOTE_PACKAGE
            )
        if key == "omnifocus":
            uv = self._path_lookup("uv") or "uv"
            environment = self._omnifocus_directory / ".venv"
            python = environment / "bin/python"
            return "\n".join(
                (
                    shlex.join((uv, "venv", "--python", "3.13", str(environment))),
                    shlex.join(
                        (uv, "pip", "install", "--python", str(python), OMNIFOCUS_MCP_PACKAGE)
                    ),
                    f"Copy the bundled reviewed adapter to {self._omnifocus_directory}",
                )
            )
        return "No automatic installation command is available."

    @staticmethod
    def installation_source(key: str) -> str:
        return {
            "node": "Official Homebrew node formula",
            "uv": "Official Homebrew uv formula",
            "plaud": "npm registry package @plaud-ai/cli 0.3.7",
            "remarkdown": "Experimental npm registry package mcp-remote 0.1.38",
            "omnifocus": "Reviewed read-only adapter bundled with this PEA application",
        }.get(key, "Not applicable")

    def _system_component(self) -> SetupComponent:
        try:
            major = int(self._macos_version.split(".", 1)[0])
        except (ValueError, IndexError):
            major = 0
        ready = self._machine == "arm64" and major >= 13
        return SetupComponent(
            "system",
            "Mac compatibility",
            "Run the Apple-silicon PEA bundle on a supported macOS release.",
            SetupStatus.READY if ready else SetupStatus.BLOCKED,
            (
                f"Apple silicon · macOS {self._macos_version}"
                if ready
                else "This bundle requires Apple silicon and macOS 13 or newer."
            ),
        )

    @staticmethod
    def _homebrew_component(brew: str | None) -> SetupComponent:
        return SetupComponent(
            "homebrew",
            "Homebrew installer support",
            "Install missing command-line dependencies from reviewed formulae.",
            SetupStatus.READY if brew else SetupStatus.ATTENTION,
            "Homebrew available." if brew else "Optional installer support is not available.",
            SetupAction.NONE if brew else SetupAction.OPEN_URL,
            "Open instructions" if not brew else "",
            HOMEBREW_URL if not brew else "",
            required=False,
        )

    def _node_component(self, node: str | None, brew: str | None) -> SetupComponent:
        version = self._node_version(node)
        if version >= MINIMUM_NODE_MAJOR:
            return SetupComponent(
                "node",
                "Node.js",
                "Run the official PLAUD CLI and the remarkdown bridge.",
                SetupStatus.READY,
                f"Node.js {version} is available.",
            )
        if brew:
            return SetupComponent(
                "node",
                "Node.js",
                "Run the official PLAUD CLI and the remarkdown bridge.",
                SetupStatus.MISSING,
                f"Node.js {MINIMUM_NODE_MAJOR} or newer is required.",
                SetupAction.INSTALL,
                "Install",
            )
        return SetupComponent(
            "node",
            "Node.js",
            "Run the official PLAUD CLI and the remarkdown bridge.",
            SetupStatus.MISSING,
            "Install Homebrew first or use the official Node.js installer.",
            SetupAction.OPEN_URL,
            "Open Node.js",
            NODE_DOWNLOAD_URL,
        )

    @staticmethod
    def _uv_component(uv: str | None, brew: str | None) -> SetupComponent:
        if uv:
            return SetupComponent(
                "uv",
                "uv installer runtime",
                "Create the isolated Python environment for the OmniFocus adapter.",
                SetupStatus.READY,
                "uv is available.",
                required=False,
            )
        return SetupComponent(
            "uv",
            "uv installer runtime",
            "Create the isolated Python environment for the OmniFocus adapter.",
            SetupStatus.MISSING,
            "uv is required only to install the controlled OmniFocus adapter.",
            SetupAction.INSTALL if brew else SetupAction.OPEN_URL,
            "Install" if brew else "Open instructions",
            "" if brew else UV_INSTALL_URL,
            required=False,
        )

    @staticmethod
    def _executable_component(
        key: str,
        name: str,
        purpose: str,
        executable: str | None,
        npm: str | None,
        package: str,
    ) -> SetupComponent:
        if executable:
            return SetupComponent(
                key,
                name,
                purpose,
                SetupStatus.READY,
                f"Installed at {executable}.",
            )
        return SetupComponent(
            key,
            name,
            purpose,
            SetupStatus.MISSING if npm else SetupStatus.BLOCKED,
            (
                f"Package {package} is not installed."
                if npm
                else "Install Node.js before this npm package."
            ),
            SetupAction.INSTALL if npm else SetupAction.NONE,
            "Install" if npm else "",
        )

    def _omnifocus_component(self, uv: str | None) -> SetupComponent:
        directory = self._omnifocus_directory
        ready = all(
            path.is_file()
            for path in (directory / ".venv/bin/python", directory / "server.py", directory / "bridge.py")
        )
        if ready:
            return SetupComponent(
                "omnifocus",
                "Controlled OmniFocus adapter",
                "Provide aggregate status and bounded task metadata through two read-only tools.",
                SetupStatus.READY,
                f"Installed at {directory}.",
            )
        return SetupComponent(
            "omnifocus",
            "Controlled OmniFocus adapter",
            "Provide aggregate status and bounded task metadata through two read-only tools.",
            SetupStatus.MISSING if uv else SetupStatus.BLOCKED,
            "Bundled adapter is not installed." if uv else "Install uv before the adapter.",
            SetupAction.INSTALL if uv else SetupAction.NONE,
            "Install" if uv else "",
        )

    @staticmethod
    def _authorisation_component(
        key: str,
        name: str,
        purpose: str,
        available: bool,
        action_label: str,
        *,
        blocked: bool = False,
    ) -> SetupComponent:
        if available:
            return SetupComponent(key, name, purpose, SetupStatus.READY, "Available on this Mac.")
        return SetupComponent(
            key,
            name,
            purpose,
            SetupStatus.BLOCKED if blocked else SetupStatus.ATTENTION,
            "Install the required component first." if blocked else "User authorisation is required.",
            SetupAction.NONE if blocked else SetupAction.CONFIGURE,
            "" if blocked else action_label,
            key,
        )

    def _agenda_component(self) -> SetupComponent:
        available = self._agenda_probe()
        return SetupComponent(
            "agenda",
            "Agenda MCP",
            "Read explicitly selected Agenda projects and notes.",
            SetupStatus.READY if available else SetupStatus.ATTENTION,
            "Local MCP endpoint is available." if available else "Open Agenda and enable MCP.",
            SetupAction.NONE if available else SetupAction.OPEN_APP,
            "Open Agenda" if not available else "",
            "Agenda",
        )

    def _devonthink_component(self) -> SetupComponent:
        available = self._devonthink_mcp.is_file()
        return SetupComponent(
            "devonthink",
            "DEVONthink MCP",
            "Review duplicates and perform explicitly confirmed record writes.",
            SetupStatus.ATTENTION if available else SetupStatus.MISSING,
            (
                "MCP executable installed; verify permission with System health."
                if available
                else "Install DEVONthink and enable its MCP integration."
            ),
            SetupAction.OPEN_APP,
            "Open DEVONthink",
            "DEVONthink",
        )

    def _node_version(self, executable: str | None) -> int:
        if not executable:
            return 0
        try:
            result = self._runner((executable, "--version"), 10)
        except (OSError, subprocess.SubprocessError):
            return 0
        value = result.stdout.strip().lstrip("v") if result.returncode == 0 else ""
        try:
            return int(value.split(".", 1)[0])
        except (ValueError, IndexError):
            return 0

    def _command_succeeds(self, arguments: Sequence[str], timeout: int) -> bool:
        try:
            return self._runner(arguments, timeout).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def _required_executable(self, name: str) -> str:
        executable = self._path_lookup(name)
        if not executable:
            raise RuntimeError(f"{name} is not available. Refresh the setup check first.")
        return executable

    def _command_preview(self, *arguments: str) -> str:
        executable = self._path_lookup(arguments[0]) or arguments[0]
        return shlex.join((executable, *arguments[1:]))

    def _run_checked(self, arguments: Sequence[str], timeout: int) -> None:
        try:
            result = self._runner(arguments, timeout)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("The installation timed out without a verified result.") from exc
        except OSError as exc:
            raise RuntimeError("The approved installer command could not be started.") from exc
        if result.returncode == 0:
            return
        detail = (result.stderr or result.stdout or "No installer detail was returned.").strip()
        raise RuntimeError(f"Installation failed: {detail[-2_000:]}")

    def _install_omnifocus_adapter(self) -> None:
        uv = self._required_executable("uv")
        server_source = self._assets / "server.py"
        bridge_source = self._assets / "bridge.py"
        if not server_source.is_file() or not bridge_source.is_file():
            raise RuntimeError("The signed app bundle does not contain the reviewed adapter assets.")

        directory = self._omnifocus_directory
        environment = directory / ".venv"
        python = environment / "bin/python"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)
        if not python.is_file():
            self._run_checked((uv, "venv", "--python", "3.13", str(environment)), 900)
        self._run_checked(
            (uv, "pip", "install", "--python", str(python), OMNIFOCUS_MCP_PACKAGE),
            900,
        )
        for source, name in ((server_source, "server.py"), (bridge_source, "bridge.py")):
            temporary = directory / f".{name}.new"
            shutil.copyfile(source, temporary)
            os.chmod(temporary, 0o600)
            os.replace(temporary, directory / name)
