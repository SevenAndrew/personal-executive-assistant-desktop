from __future__ import annotations

import subprocess

from PySide6.QtCore import QSettings, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .diagnostics import log_event
from .setup_service import SetupAction, SetupComponent, SetupService, SetupStatus


class SetupInstallWorker(QThread):
    completed = Signal(str, str)
    failed = Signal(str, str)

    def __init__(self, service: SetupService, key: str, parent=None) -> None:
        super().__init__(parent)
        self._service = service
        self._key = key

    def run(self) -> None:
        try:
            message = self._service.install(self._key)
        except Exception as exc:  # noqa: BLE001 - background boundary reports bounded failures.
            self.failed.emit(self._key, str(exc))
            return
        self.completed.emit(self._key, message)


class SetupAssistant(QDialog):
    configuration_requested = Signal(str)

    def __init__(
        self,
        settings: QSettings,
        icon: QIcon,
        parent=None,
        *,
        service: SetupService | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._service = service or SetupService()
        self._components: dict[str, SetupComponent] = {}
        self._worker: SetupInstallWorker | None = None
        self.setWindowTitle("PEA setup assistant")
        self.setWindowIcon(icon)
        self.resize(1_120, 720)
        self.setMinimumSize(900, 600)

        layout = QVBoxLayout(self)
        heading = QLabel("First-run setup")
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        introduction = QLabel(
            "PEA checks this Mac without reading application content. Missing dependencies are "
            "installed one at a time only after you review and approve the exact source, command "
            "and destination. Authorisation remains under your control."
        )
        introduction.setWordWrap(True)
        introduction.setObjectName("pageSub")
        layout.addWidget(introduction)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Component", "Status", "Detail", "Action"])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        layout.addWidget(self._table, 1)

        self._status = QLabel("Ready to check this Mac.")
        self._status.setObjectName("pageSub")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        note = QLabel(
            "Homebrew itself is never installed automatically. macOS permission prompts, API "
            "keys and OAuth sign-ins must be completed by you. Run System health afterwards to "
            "verify the live MCP connections."
        )
        note.setObjectName("warning")
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        self._refresh_button = QPushButton("Check again")
        self._refresh_button.clicked.connect(self.refresh)
        self._health_button = QPushButton("Continue to System health")
        self._health_button.clicked.connect(lambda: self._request_configuration("health"))
        finish_button = QPushButton("Finish for now")
        finish_button.setObjectName("primary")
        finish_button.clicked.connect(self.accept)
        buttons.addWidget(self._refresh_button)
        buttons.addStretch()
        buttons.addWidget(self._health_button)
        buttons.addWidget(finish_button)
        layout.addLayout(buttons)
        self.finished.connect(self._mark_seen)
        self.refresh()

    def _mark_seen(self) -> None:
        self._settings.setValue("setup/assistant_seen", True)
        self._settings.sync()

    def refresh(self) -> None:
        components = self._service.check()
        self._components = {component.key: component for component in components}
        self._table.setRowCount(len(components))
        colours = {
            SetupStatus.READY: QColor("#1f7a45"),
            SetupStatus.ATTENTION: QColor("#9a6b00"),
            SetupStatus.MISSING: QColor("#a13b2b"),
            SetupStatus.BLOCKED: QColor("#6e7781"),
        }
        for row, component in enumerate(components):
            name = QTableWidgetItem(component.name)
            name.setToolTip(component.purpose)
            status = QTableWidgetItem(component.status.value)
            status.setForeground(colours[component.status])
            font = status.font()
            font.setBold(True)
            status.setFont(font)
            detail = QTableWidgetItem(component.detail)
            detail.setToolTip(component.purpose)
            self._table.setItem(row, 0, name)
            self._table.setItem(row, 1, status)
            self._table.setItem(row, 2, detail)
            if component.action is not SetupAction.NONE:
                action = QPushButton(component.action_label)
                action.setProperty("setupComponent", component.key)
                action.setToolTip(component.purpose)
                action.clicked.connect(
                    lambda _checked=False, key=component.key: self._run_action(key)
                )
                self._table.setCellWidget(row, 3, action)
        ready = sum(component.status is SetupStatus.READY for component in components)
        attention = sum(component.status is SetupStatus.ATTENTION for component in components)
        missing = sum(
            component.status in {SetupStatus.MISSING, SetupStatus.BLOCKED}
            for component in components
        )
        self._status.setText(
            f"Setup check complete: {ready} ready, {attention} require attention, "
            f"{missing} missing or blocked."
        )

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Installation in progress",
                "Wait for the approved installation to finish before closing setup.",
            )
            event.ignore()
            return
        self._mark_seen()
        event.accept()

    def _run_action(self, key: str) -> None:
        component = self._components[key]
        if component.action is SetupAction.INSTALL:
            self._confirm_install(component)
        elif component.action is SetupAction.OPEN_URL:
            QDesktopServices.openUrl(QUrl(component.action_target))
            log_event("setup_guidance_opened", component=key)
        elif component.action is SetupAction.OPEN_APP:
            self._open_application(component)
        elif component.action is SetupAction.CONFIGURE:
            self._request_configuration(component.action_target)

    def _confirm_install(self, component: SetupComponent) -> None:
        confirmation = QMessageBox(self)
        confirmation.setWindowTitle(f"Install {component.name}")
        confirmation.setIcon(QMessageBox.Icon.Question)
        confirmation.setText(
            f"Install {component.name} on this Mac?\n\nPurpose: {component.purpose}\n\n"
            f"Source: {self._service.installation_source(component.key)}"
        )
        confirmation.setInformativeText(
            "The following fixed command or steps will be run without a shell:\n\n"
            f"{self._service.installation_preview(component.key)}"
        )
        confirmation.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        confirmation.setDefaultButton(QMessageBox.StandardButton.No)
        if confirmation.exec() != QMessageBox.StandardButton.Yes:
            log_event("setup_install_cancelled", component=component.key)
            return
        self._start_install(component)

    def _start_install(self, component: SetupComponent) -> None:
        if self._worker is not None:
            return
        log_event("setup_install_started", component=component.key)
        self._set_controls_enabled(False)
        self._status.setText(f"Installing {component.name} …")
        self._worker = SetupInstallWorker(self._service, component.key, self)
        self._worker.completed.connect(self._install_completed)
        self._worker.failed.connect(self._install_failed)
        self._worker.finished.connect(self._install_finished)
        self._worker.start()

    def _install_completed(self, key: str, message: str) -> None:
        log_event("setup_install_completed", component=key)
        QMessageBox.information(self, "Installation complete", message)

    def _install_failed(self, key: str, message: str) -> None:
        log_event("setup_install_failed", component=key)
        QMessageBox.critical(self, "Installation failed", message)

    def _install_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        self._set_controls_enabled(True)
        self.refresh()

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._refresh_button.setEnabled(enabled)
        self._health_button.setEnabled(enabled)
        for row in range(self._table.rowCount()):
            if button := self._table.cellWidget(row, 3):
                button.setEnabled(enabled)

    def _open_application(self, component: SetupComponent) -> None:
        try:
            subprocess.Popen(
                ["/usr/bin/open", "-a", component.action_target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            QMessageBox.warning(
                self,
                f"{component.name} unavailable",
                f"macOS could not open {component.action_target}. Install the application first.",
            )
            return
        log_event("setup_application_opened", component=component.key)
        QMessageBox.information(
            self,
            component.name,
            f"{component.detail}\n\nReturn to PEA and choose Check again or run System health.",
        )

    def _request_configuration(self, target: str) -> None:
        self.configuration_requested.emit(target)
        self.accept()
