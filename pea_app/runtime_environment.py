from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

MACOS_EXECUTABLE_DIRECTORIES = (
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
    Path("/opt/local/bin"),
    Path.home() / ".local" / "bin",
)


def configure_macos_app_environment(
    executable_directories: Iterable[Path] = MACOS_EXECUTABLE_DIRECTORIES,
) -> str:
    """Make user-installed command-line bridges visible to a Finder-launched app."""
    existing = [entry for entry in os.environ.get("PATH", "").split(os.pathsep) if entry]
    additions = [
        str(directory.expanduser())
        for directory in executable_directories
        if directory.expanduser().is_dir()
    ]
    combined = list(dict.fromkeys([*additions, *existing]))
    os.environ["PATH"] = os.pathsep.join(combined)
    return os.environ["PATH"]
