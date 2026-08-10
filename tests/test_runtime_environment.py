from __future__ import annotations

import os
from pathlib import Path

from pea_app.runtime_environment import configure_macos_app_environment


def test_configure_macos_app_environment_prepends_existing_directories(
    monkeypatch, tmp_path: Path
) -> None:
    homebrew = tmp_path / "homebrew" / "bin"
    local = tmp_path / "local" / "bin"
    homebrew.mkdir(parents=True)
    local.mkdir(parents=True)
    monkeypatch.setenv("PATH", f"/usr/bin{os.pathsep}{homebrew}")

    configured = configure_macos_app_environment(
        (homebrew, tmp_path / "missing", local, homebrew)
    )

    assert configured.split(os.pathsep) == [str(homebrew), str(local), "/usr/bin"]
    assert os.environ["PATH"] == configured


def test_configure_macos_app_environment_keeps_an_empty_path_valid(
    monkeypatch, tmp_path: Path
) -> None:
    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    monkeypatch.delenv("PATH", raising=False)

    assert configure_macos_app_environment((executable_directory,)) == str(executable_directory)
