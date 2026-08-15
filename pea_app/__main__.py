from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .diagnostics import configure_runtime_logging, log_event
from .runtime_environment import configure_macos_app_environment
from .ui import MainWindow


def main() -> int:
    configure_macos_app_environment()
    configure_runtime_logging()
    log_event("application_started")
    application = QApplication(sys.argv)
    application.setApplicationName("Personal Executive Assistant")
    application.setOrganizationName("PEA")
    window = MainWindow()
    window.show()
    QTimer.singleShot(500, window.run_startup_checks)
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
