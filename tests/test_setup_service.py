from __future__ import annotations

import os
import subprocess
from pathlib import Path

from pea_app.setup_service import (
    MCP_REMOTE_PACKAGE,
    PLAUD_PACKAGE,
    SetupAction,
    SetupService,
    SetupStatus,
)


def _result(arguments, returncode: int = 0, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)


def test_setup_check_preserves_dependency_and_authorisation_order(tmp_path: Path) -> None:
    adapter = tmp_path / "adapter"
    (adapter / ".venv/bin").mkdir(parents=True)
    for path in (adapter / ".venv/bin/python", adapter / "server.py", adapter / "bridge.py"):
        path.write_text("ready", encoding="utf-8")
    devonthink = tmp_path / "devonthink-mcp"
    devonthink.write_text("ready", encoding="utf-8")
    paths = {
        "brew": "/opt/homebrew/bin/brew",
        "node": "/opt/homebrew/bin/node",
        "npm": "/opt/homebrew/bin/npm",
        "plaud": "/opt/homebrew/bin/plaud",
        "mcp-remote": "/opt/homebrew/bin/mcp-remote",
        "uv": "/opt/homebrew/bin/uv",
    }

    def runner(arguments, _timeout):
        if arguments[-1] == "--version":
            return _result(arguments, stdout="v22.1.0\n")
        return _result(arguments)

    service = SetupService(
        path_lookup=paths.get,
        runner=runner,
        home=tmp_path,
        devonthink_mcp=devonthink,
        omnifocus_directory=adapter,
        agenda_probe=lambda: True,
        api_key_checker=lambda: True,
        remarkdown_authorisation_checker=lambda: True,
        machine="arm64",
        macos_version="14.7",
    )

    components = service.check()

    assert [component.key for component in components] == [
        "system",
        "homebrew",
        "node",
        "uv",
        "plaud",
        "remarkdown",
        "omnifocus",
        "openai",
        "plaud_auth",
        "remarkdown_auth",
        "agenda",
        "devonthink",
    ]
    assert all(component.status is SetupStatus.READY for component in components[:-1])
    assert components[-1].status is SetupStatus.ATTENTION


def test_missing_node_is_installable_only_when_homebrew_exists(tmp_path: Path) -> None:
    service = SetupService(
        path_lookup={"brew": "/opt/homebrew/bin/brew"}.get,
        home=tmp_path,
        agenda_probe=lambda: False,
        api_key_checker=lambda: False,
        remarkdown_authorisation_checker=lambda: False,
        machine="arm64",
        macos_version="14.0",
    )

    node = next(component for component in service.check() if component.key == "node")

    assert node.status is SetupStatus.MISSING
    assert node.action is SetupAction.INSTALL
    assert service.installation_preview("node") == "/opt/homebrew/bin/brew install node"


def test_homebrew_is_never_installed_automatically(tmp_path: Path) -> None:
    service = SetupService(
        path_lookup=lambda _name: None,
        home=tmp_path,
        agenda_probe=lambda: False,
        api_key_checker=lambda: False,
        remarkdown_authorisation_checker=lambda: False,
        machine="arm64",
        macos_version="14.0",
    )

    homebrew = next(component for component in service.check() if component.key == "homebrew")

    assert homebrew.action is SetupAction.OPEN_URL
    assert homebrew.action_label == "Open instructions"


def test_npm_installations_use_fixed_versions_and_argument_lists(tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def runner(arguments, _timeout):
        calls.append(tuple(arguments))
        return _result(arguments)

    service = SetupService(
        path_lookup={"npm": "/opt/homebrew/bin/npm"}.get,
        runner=runner,
        home=tmp_path,
        machine="arm64",
        macos_version="14.0",
    )

    service.install("plaud")
    service.install("remarkdown")

    assert calls == [
        ("/opt/homebrew/bin/npm", "install", "--global", PLAUD_PACKAGE),
        ("/opt/homebrew/bin/npm", "install", "--global", MCP_REMOTE_PACKAGE),
    ]


def test_omnifocus_adapter_install_is_private_and_read_only(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "server.py").write_text("server", encoding="utf-8")
    (assets / "bridge.py").write_text("bridge", encoding="utf-8")
    destination = tmp_path / "installed"
    calls: list[tuple[str, ...]] = []

    def runner(arguments, _timeout):
        calls.append(tuple(arguments))
        if len(arguments) > 1 and arguments[1] == "venv":
            python = destination / ".venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text("python", encoding="utf-8")
        return _result(arguments)

    service = SetupService(
        path_lookup={"uv": "/opt/homebrew/bin/uv"}.get,
        runner=runner,
        home=tmp_path,
        asset_directory=assets,
        omnifocus_directory=destination,
        machine="arm64",
        macos_version="14.0",
    )

    service.install("omnifocus")

    assert calls[0][:4] == ("/opt/homebrew/bin/uv", "venv", "--python", "3.13")
    assert calls[1][:4] == ("/opt/homebrew/bin/uv", "pip", "install", "--python")
    assert (destination / "server.py").read_text(encoding="utf-8") == "server"
    assert (destination / "bridge.py").read_text(encoding="utf-8") == "bridge"
    assert os.stat(destination).st_mode & 0o777 == 0o700
    assert os.stat(destination / "server.py").st_mode & 0o777 == 0o600


def test_bundled_omnifocus_adapter_has_two_fixed_read_only_operations() -> None:
    assets = Path(__file__).parents[1] / "pea_app/installer_assets/omnifocus"
    server = (assets / "server.py").read_text(encoding="utf-8")
    bridge = (assets / "bridge.py").read_text(encoding="utf-8")

    assert server.count("@mcp.tool") == 2
    assert server.count("readOnlyHint=True") == 2
    assert 'request.operation === "status"' in bridge
    assert 'request.operation === "tasks"' in bridge
    for operation in ("create", "delete", "complete", "modify"):
        assert f'request.operation === "{operation}"' not in bridge
