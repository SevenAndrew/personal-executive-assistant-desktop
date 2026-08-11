from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QObject,
    QPoint,
    QSettings,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .agenda_mcp import AgendaNote, AgendaNoteSummary, AgendaProject, AgendaService
from .devonthink_handoff import (
    WRITABLE_DATABASES,
    DevonThinkHandoff,
    DevonThinkMinutesSource,
    DevonThinkService,
    ImportReceipt,
    ImportReview,
    format_duplicate_review_message,
    prepare_handoff,
    prepare_remarkable_handoff,
)
from .diagnostics import (
    BILLING_URL,
    LOG_DIRECTORY,
    STARTUP_HEALTH_VERSION,
    USAGE_DASHBOARD_URL,
    HealthResult,
    HealthService,
    UsageTracker,
    health_check_is_complete,
    log_event,
    read_log_tail,
)
from .guidance import WorkflowGuide, WorkflowProgressView
from .help_window import HelpDialog
from .manual_sources import load_manual_source_files
from .models import MODEL_PROFILES, ModelProfile
from .omnifocus_capture import (
    CaptureProposal,
    CaptureReceipt,
    CaptureReview,
    MinutesActionCapture,
    OmniFocusCaptureService,
    format_capture_duplicate,
    prepare_capture,
    prepare_minutes_action_captures,
)
from .omnifocus_mcp import OmniFocusService, OmniFocusStatus, OmniFocusTask, task_deep_link
from .openai_minutes import GenerationResult, OpenAIMinutesService
from .openai_weekly import (
    OpenAIWeeklyService,
    WeeklyGenerationResult,
    WeeklySource,
    validate_week_id,
    weekly_source_reference,
)
from .plaud_cli import PlaudCli, PlaudRecording, PlaudSourceBundle
from .remarkdown_mcp import (
    RemarkdownDocument,
    RemarkdownDocumentSummary,
    RemarkdownIdentity,
    RemarkdownService,
    terminate_authentication_bridges,
)
from .secrets import APIKeyStorageError, has_openai_api_key, store_openai_api_key
from .setup_assistant import SetupAssistant
from .workflows import (
    DailySummaryWorkflow,
    DailyWorkflowCheckpoint,
    LatestPlaudCheckpoint,
    LatestPlaudWorkflow,
    WeeklySummaryWorkflow,
    WeeklyWorkflowCheckpoint,
    WorkflowImportService,
    WorkflowReady,
    minutes_to_weekly_sources,
    week_date_range,
)

ASSET_DIRECTORY = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSET_DIRECTORY / "pea-logo.png"

APP_STYLESHEET = """
QMainWindow, QWidget { background: #f4f6f8; color: #17212b; }
QLabel { background: transparent; }
QFrame#sidebar { background: #17212b; border: none; }
QLabel#brand { color: white; font-size: 20px; font-weight: 700; }
QLabel#brandSub { color: #aab6c2; font-size: 12px; }
QLabel#sidebarLogo { background: transparent; border: none; padding: 0; }
QPushButton#tooltipToggle, QPushButton#sidebarAction {
    background: #263746; color: #dce5ed; text-align: left; padding: 8px 10px;
}
QPushButton#tooltipToggle:checked {
    background: #49677f; color: white;
}
QListWidget#navigation { background: transparent; color: #dce5ed; border: none; outline: none; }
QListWidget#navigation::item { padding: 11px 12px; margin: 2px 0; border-radius: 6px; }
QListWidget#navigation::item:selected { background: #49677f; color: white; }
QFrame#card { background: white; border: 1px solid #dfe5eb; border-radius: 10px; }
QFrame#guidanceRail, QStackedWidget#guidanceStack, QFrame#workflowGuide {
    background: #17212b; border: none;
}
QLabel#controlledMode { color: #d8b35c; font-size: 12px; }
QLabel#guidanceFooter { color: #aab6c2; font-size: 12px; }
QLabel#guideHeading { color: #ffffff; font-size: 18px; font-weight: 700; }
QLabel#guideSummary { color: #dce5ed; font-size: 13px; font-weight: 600; }
QLabel#guideSources { background: #263746; color: #b9c7d2; border-radius: 7px; padding: 10px; }
QFrame#guideStep { border-radius: 7px; }
QFrame#guideStep[stepState="current"] { background: #49677f; border: 1px solid #8299aa; }
QFrame#guideStep[stepState="complete"] { background: #1e2d38; }
QFrame#guideStep[stepState="pending"] { background: #192630; }
QFrame#guideStep[stepState="current"] QLabel { color: #ffffff; }
QFrame#guideStep[stepState="complete"] QLabel { color: #8495a2; }
QFrame#guideStep[stepState="pending"] QLabel { color: #60717e; }
QLabel#guideStepTitle { font-weight: 650; }
QLabel#guideStepDetail { font-size: 11px; }
QFrame#workflowProgress { background: transparent; }
QFrame#progressStep { background: #f6f8f9; border: 1px solid #dfe5eb; border-radius: 7px; }
QFrame#progressStep[progressState="Running"] { background: #eef2f4; border-color: #8299aa; }
QFrame#progressStep[progressState="Blocked"], QFrame#progressStep[progressState="Failed"] { border-color: #b87970; }
QLabel#progressTitle { font-weight: 600; }
QLabel#progressDetail { color: #66737e; font-size: 11px; }
QLabel#progressStatus { color: #66737e; }
QLabel#progressDot { color: #9aa5ad; font-size: 18px; }
QLabel#progressDot[progressState="Complete"], QLabel#progressDot[progressState="Ready"] { color: #2f8057; }
QLabel#progressDot[progressState="Running"] { color: #b18435; }
QLabel#progressDot[progressState="Blocked"], QLabel#progressDot[progressState="Failed"] { color: #a13b2b; }
QLabel#pageTitle { font-size: 24px; font-weight: 700; }
QLabel#pageSub { color: #5f6b76; }
QLabel#warning { background: #f3efe5; color: #5c5140; border: 1px solid #d7cbb6;
                 border-radius: 7px; padding: 9px; }
QLabel#statusOk { color: #1f7a45; font-weight: 600; }
QLabel#statusMissing { color: #a13b2b; font-weight: 600; }
QPushButton { background: #e9edf2; border: none; border-radius: 6px; padding: 8px 13px; }
QPushButton:hover { background: #dce3ea; }
QPushButton#primary { background: #49677f; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #3e596e; }
QPushButton:disabled { color: #8b96a1; background: #edf0f3; }
QPushButton#primary:disabled { color: #8b96a1; background: #edf0f3; }
QPlainTextEdit, QTextBrowser, QLineEdit, QComboBox { background: white;
    border: 1px solid #cfd7df; border-radius: 6px; padding: 6px; }
QLineEdit, QComboBox { min-height: 22px; }
"""


class LocalMarkdownPreview(QTextBrowser):
    """Render generated Markdown without retrieving linked external resources."""

    def loadResource(self, resource_type: int, name: QUrl) -> QByteArray:
        del resource_type, name
        return QByteArray()


class ManualEmailDropEdit(QPlainTextEdit):
    files_loaded = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        try:
            loaded = load_manual_source_files(paths)
        except (OSError, UnicodeError, ValueError) as exc:
            QMessageBox.warning(self, "Email upload rejected", str(exc))
            return
        if loaded:
            existing = self.toPlainText().strip()
            self.setPlainText(f"{existing}\n\n{loaded}".strip())
            self.files_loaded.emit(len(paths))
            event.acceptProposedAction()


class GenerationWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        transcript: str,
        profile: ModelProfile,
        meeting_date: str,
        plaud_summary: str = "",
        contextual_memory: str = "",
    ) -> None:
        super().__init__()
        self._transcript = transcript
        self._profile = profile
        self._meeting_date = meeting_date
        self._plaud_summary = plaud_summary
        self._contextual_memory = contextual_memory

    @Slot()
    def run(self) -> None:
        try:
            result = OpenAIMinutesService().generate(
                self._transcript,
                self._profile,
                self._meeting_date,
                self._plaud_summary,
                self._contextual_memory,
            )
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event(
                "minutes_generation_failed",
                error_type=type(exc).__name__,
                error_category=getattr(exc, "category", "unexpected"),
            )
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class WeeklyGenerationWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        week_id: str,
        sources: list[WeeklySource],
        profile: ModelProfile,
    ) -> None:
        super().__init__()
        self._week_id = week_id
        self._sources = sources
        self._profile = profile

    @Slot()
    def run(self) -> None:
        try:
            result = OpenAIWeeklyService().generate(
                self._week_id,
                self._sources,
                self._profile,
            )
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event("weekly_generation_failed", error_type=type(exc).__name__)
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class MinutesArchiveWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, start_date: str, end_date: str, database: str) -> None:
        super().__init__()
        self._start_date = start_date
        self._end_date = end_date
        self._database = database

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(
                DevonThinkService().load_minutes(
                    self._start_date, self._end_date, self._database
                )
            )
        except Exception as exc:  # noqa: BLE001 - Qt worker boundary.
            log_event("minutes_archive_load_failed", error_type=type(exc).__name__)
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class WorkflowRunnerWorker(QObject):
    progress = Signal(int, str, str)
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        checkpoint: LatestPlaudCheckpoint | DailyWorkflowCheckpoint | WeeklyWorkflowCheckpoint,
    ) -> None:
        super().__init__()
        self._checkpoint = checkpoint

    @Slot()
    def run(self) -> None:
        try:
            if isinstance(self._checkpoint, LatestPlaudCheckpoint):
                result = LatestPlaudWorkflow().run(self._checkpoint, self.progress.emit)
            elif isinstance(self._checkpoint, DailyWorkflowCheckpoint):
                result = DailySummaryWorkflow().run(self._checkpoint, self.progress.emit)
            else:
                result = WeeklySummaryWorkflow().run(self._checkpoint, self.progress.emit)
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event("workflow_run_failed", error_type=type(exc).__name__)
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class WorkflowImportWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, ready: WorkflowReady) -> None:
        super().__init__()
        self._ready = ready

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(WorkflowImportService().import_ready(self._ready))
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event("workflow_import_failed", error_type=type(exc).__name__)
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class DevonThinkWorker(QObject):
    completed = Signal(str, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, operation: str, handoff: DevonThinkHandoff) -> None:
        super().__init__()
        self._operation = operation
        self._handoff = handoff

    @Slot()
    def run(self) -> None:
        try:
            service = DevonThinkService()
            if self._operation == "review":
                result = service.review(self._handoff)
            else:
                result = service.import_record(self._handoff)
            self.completed.emit(self._operation, result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event(
                "devonthink_operation_failed",
                operation=self._operation,
                error_type=type(exc).__name__,
            )
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class PlaudJobThread(QThread):
    completed = Signal(str, object)
    failed = Signal(str)

    def __init__(
        self,
        operation: str,
        recording: PlaudRecording | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._operation = operation
        self._recording = recording

    def run(self) -> None:
        try:
            client = PlaudCli()
            if self._operation == "list":
                result: object = client.list_recordings()
            elif self._operation == "login":
                client.login()
                result = True
            elif self._recording is not None:
                result = client.get_source_bundle(self._recording)
            else:
                raise ValueError("A PLAUD recording is required.")
            self.completed.emit(self._operation, result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event(
                "plaud_operation_failed",
                operation=self._operation,
                error_type=type(exc).__name__,
            )
            self.failed.emit(str(exc))


class AgendaWorker(QObject):
    completed = Signal(str, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        operation: str,
        project: AgendaProject | None = None,
        note: AgendaNoteSummary | None = None,
        projects: list[AgendaProject] | None = None,
        notes: list[AgendaNoteSummary] | None = None,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._project = project
        self._note = note
        self._projects = projects or []
        self._notes = notes or []

    @Slot()
    def run(self) -> None:
        try:
            service = AgendaService()
            if self._operation == "projects":
                result: object = service.list_projects()
            elif self._operation == "notes" and self._project is not None:
                result = service.list_notes(self._project)
            elif self._operation == "note" and self._note is not None:
                result = service.get_note(self._note)
            elif self._operation == "recent" and self._projects:
                result = service.list_recent_notes(self._projects)
            elif self._operation == "report_notes" and self._notes:
                result = service.get_notes(self._notes)
            else:
                raise ValueError("A valid Agenda selection is required.")
            self.completed.emit(self._operation, result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event(
                "agenda_read_failed",
                operation=self._operation,
                error_type=type(exc).__name__,
            )
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class OmniFocusWorker(QObject):
    completed = Signal(str, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, operation: str, view: str = "available", limit: int = 50) -> None:
        super().__init__()
        self._operation = operation
        self._view = view
        self._limit = limit

    @Slot()
    def run(self) -> None:
        try:
            service = OmniFocusService()
            if self._operation == "status":
                result: object = service.status()
            elif self._operation == "tasks":
                result = service.list_tasks(self._view, self._limit)
            else:
                raise ValueError("A valid OmniFocus read operation is required.")
            self.completed.emit(self._operation, result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event(
                "omnifocus_read_failed",
                operation=self._operation,
                error_type=type(exc).__name__,
            )
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class OmniFocusCaptureWorker(QObject):
    completed = Signal(str, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        operation: str,
        proposal: CaptureProposal | None = None,
        review: CaptureReview | None = None,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._proposal = proposal
        self._review = review

    @Slot()
    def run(self) -> None:
        try:
            service = OmniFocusCaptureService()
            if self._operation == "review" and self._proposal is not None:
                result: object = service.review(self._proposal)
            elif self._operation == "create" and self._review is not None:
                result = service.create(self._review)
            else:
                raise ValueError("A valid OmniFocus capture operation is required.")
            self.completed.emit(self._operation, result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event(
                "omnifocus_capture_failed",
                operation=self._operation,
                error_type=type(exc).__name__,
            )
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class RemarkdownWorker(QObject):
    completed = Signal(str, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        operation: str,
        document: RemarkdownDocumentSummary | None = None,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._document = document

    @Slot()
    def run(self) -> None:
        try:
            service = RemarkdownService()
            if self._operation == "login":
                result: object = service.login()
            elif self._operation == "status":
                result = service.whoami()
            elif self._operation == "list":
                result = service.list_recent_documents()
            elif self._operation == "document" and self._document is not None:
                result = service.fetch_document(self._document)
            else:
                raise ValueError("A valid remarkdown operation is required.")
            self.completed.emit(self._operation, result)
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event(
                "remarkdown_read_failed",
                operation=self._operation,
                error_type=type(exc).__name__,
            )
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class HealthWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)
    finished = Signal()

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(HealthService().run())
        except Exception as exc:  # noqa: BLE001 - Qt boundary must report worker failures.
            log_event("health_check_failed", error_type=type(exc).__name__)
            self.failed.emit("The health check could not be completed.")
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Personal Executive Assistant")
        self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.resize(1_600, 960)
        self.setMinimumSize(1_250, 760)
        self.setStyleSheet(APP_STYLESHEET)
        self._settings = QSettings()
        self._settings.setValue("default_model_profile", "economy")
        self._tooltips_enabled = self._settings.value("show_tooltips", True, type=bool)
        self._workflow_guides: dict[str, WorkflowGuide] = {}
        self._guidance_targets: dict[str, tuple[QWidget, ...]] = {}
        self._shortcut_hint_visible = False
        self._help_dialog: HelpDialog | None = None
        self._setup_dialog: SetupAssistant | None = None
        self._thread: QThread | None = None
        self._worker: GenerationWorker | None = None
        self._devonthink_thread: QThread | None = None
        self._devonthink_worker: DevonThinkWorker | None = None
        self._pending_import: DevonThinkHandoff | None = None
        self._pending_import_origin = "minutes"
        self._devonthink_origin = "minutes"
        self._plaud_thread: PlaudJobThread | None = None
        self._agenda_thread: QThread | None = None
        self._agenda_worker: AgendaWorker | None = None
        self._agenda_note_summaries: dict[str, AgendaNoteSummary] = {}
        self._agenda_report_notes: list[AgendaNote] = []
        self._omnifocus_thread: QThread | None = None
        self._omnifocus_worker: OmniFocusWorker | None = None
        self._omnifocus_capture_thread: QThread | None = None
        self._omnifocus_capture_worker: OmniFocusCaptureWorker | None = None
        self._omnifocus_capture_review: CaptureReview | None = None
        self._omnifocus_capture_receipt: CaptureReceipt | None = None
        self._minutes_action_captures: list[MinutesActionCapture] = []
        self._remarkdown_thread: QThread | None = None
        self._remarkdown_worker: RemarkdownWorker | None = None
        self._last_remarkdown_document: RemarkdownDocument | None = None
        self._remarkdown_authorisation_recovered = False
        self._remarkdown_auth_timer = QTimer(self)
        self._remarkdown_auth_timer.setInterval(1_000)
        self._remarkdown_auth_timer.timeout.connect(
            self._recover_remarkdown_authorisation
        )
        self._health_thread: QThread | None = None
        self._health_worker: HealthWorker | None = None
        self._startup_health_pending = False
        self._health_check_is_startup = False
        self._close_after_health = False
        self._weekly_thread: QThread | None = None
        self._weekly_worker: WeeklyGenerationWorker | None = None
        self._minutes_archive_thread: QThread | None = None
        self._minutes_archive_worker: MinutesArchiveWorker | None = None
        self._weekly_minutes_sources: list[WeeklySource] = []
        self._weekly_minutes_week = ""
        self._workflow_thread: QThread | None = None
        self._workflow_worker: WorkflowRunnerWorker | WorkflowImportWorker | None = None
        self._workflow_checkpoint: (
            LatestPlaudCheckpoint | DailyWorkflowCheckpoint | WeeklyWorkflowCheckpoint | None
        ) = None
        self._workflow_ready: WorkflowReady | None = None
        self._workflow_receipt: ImportReceipt | None = None
        self._workflow_usage_recorded = False
        self._usage_tracker = UsageTracker(self._settings)
        self._last_result: GenerationResult | None = None
        self._last_weekly_result: WeeklyGenerationResult | None = None
        self._plaud_summary_text = ""

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_sidebar())
        self._pages = QStackedWidget()
        for page in (
            self._build_minutes_page(),
            self._build_agenda_page(),
            self._build_remarkable_page(),
            self._build_omnifocus_page(),
            self._build_weekly_summary_page(),
            self._build_workflows_page(),
            self._build_settings_page(),
        ):
            self._pages.addWidget(self._scrollable_page(page))
        root_layout.addWidget(self._pages, 1)
        self._guidance_rail = QFrame()
        self._guidance_rail.setObjectName("guidanceRail")
        self._guidance_rail.setFixedWidth(340)
        guidance_layout = QVBoxLayout(self._guidance_rail)
        guidance_layout.setContentsMargins(0, 0, 0, 16)
        guidance_layout.setSpacing(8)
        self._guidance_stack = QStackedWidget()
        self._guidance_stack.setObjectName("guidanceStack")
        for guide in self._workflow_guides.values():
            self._guidance_stack.addWidget(guide)
        guidance_layout.addWidget(self._guidance_stack, 1)
        self._controlled_mode_label = QLabel("Controlled mode · Confirmed writes only")
        self._controlled_mode_label.setObjectName("controlledMode")
        self._controlled_mode_label.setContentsMargins(18, 0, 18, 0)
        guidance_layout.addWidget(self._controlled_mode_label)
        self._version_label = QLabel(f"v{__version__} · © SevenAndrew 2026")
        self._version_label.setObjectName("guidanceFooter")
        self._version_label.setContentsMargins(18, 0, 18, 0)
        guidance_layout.addWidget(self._version_label)
        root_layout.addWidget(self._guidance_rail)
        self.setCentralWidget(root)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self._build_application_menu()
        self._configure_tooltips()
        self._apply_tooltip_visibility()
        self._configure_guidance_targets()
        for index in range(self._pages.count()):
            page = self._pages.widget(index)
            if isinstance(page, QScrollArea):
                page.verticalScrollBar().valueChanged.connect(self._sync_guidance_position)
        self._update_guidance_sources()
        QTimer.singleShot(100, self._focus_navigation_and_scroll_to_top)
        QTimer.singleShot(500, self._focus_navigation_and_scroll_to_top)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(225)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)

        header = QHBoxLayout()
        header.setSpacing(8)
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        brand = QLabel("PEA")
        brand.setObjectName("brand")
        subtitle = QLabel("Local control centre")
        subtitle.setObjectName("brandSub")
        header_text.addWidget(brand)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)

        logo = QLabel()
        logo.setObjectName("sidebarLogo")
        logo.setFixedSize(54, 54)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(
            QPixmap(str(LOGO_PATH)).scaled(
                50,
                50,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        header.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)
        layout.addSpacing(12)

        self._navigation = QListWidget()
        self._navigation.setObjectName("navigation")
        for label in (
            "Minutes",
            "Agenda",
            "reMarkable",
            "OmniFocus",
            "Weekly summary",
            "Workflows",
            "Settings",
        ):
            QListWidgetItem(label, self._navigation)
        self._navigation.setCurrentRow(0)
        self._navigation.currentRowChanged.connect(self._switch_page)
        self._page_shortcuts: list[QShortcut] = []
        for index in range(7):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.activated.connect(
                lambda selected_index=index: self._navigation.setCurrentRow(selected_index)
            )
            self._page_shortcuts.append(shortcut)
        layout.addWidget(self._navigation)

        self._help_button = QPushButton("Help and shortcuts")
        self._help_button.setObjectName("sidebarAction")
        self._help_button.clicked.connect(self._show_help)
        layout.addWidget(self._help_button)

        self._tooltip_toggle = QPushButton(
            "Tooltips on" if self._tooltips_enabled else "Tooltips off"
        )
        self._tooltip_toggle.setObjectName("tooltipToggle")
        self._tooltip_toggle.setCheckable(True)
        self._tooltip_toggle.setChecked(self._tooltips_enabled)
        self._tooltip_toggle.toggled.connect(self._toggle_tooltips)
        layout.addWidget(self._tooltip_toggle)

        self._shortcut_hint = QLabel(
            "⌘1…7  Pages\n⌘R  Regenerate\n⌘T  Tooltips\n⌘?  Help"
        )
        self._shortcut_hint.setObjectName("brandSub")
        self._shortcut_hint.setVisible(False)
        layout.addWidget(self._shortcut_hint)

        return sidebar

    def _build_application_menu(self) -> None:
        navigate = self.menuBar().addMenu("Navigate")
        for index, label in enumerate(
            ("Minutes", "Agenda", "reMarkable", "OmniFocus", "Weekly summary", "Workflows", "Settings")
        ):
            action = QAction(label, self)
            action.setShortcut(QKeySequence(f"Ctrl+{index + 1}"))
            action.triggered.connect(
                lambda _checked=False, selected_index=index: self._navigation.setCurrentRow(
                    selected_index
                )
            )
            navigate.addAction(action)
        navigate.addSeparator()
        settings_action = QAction("Settings", self)
        settings_action.setShortcut(QKeySequence("Ctrl+S"))
        settings_action.triggered.connect(lambda: self._navigation.setCurrentRow(6))
        navigate.addAction(settings_action)

        actions = self.menuBar().addMenu("Actions")
        regenerate = QAction("Regenerate with selected model", self)
        regenerate.setShortcut(QKeySequence("Ctrl+R"))
        regenerate.triggered.connect(self._regenerate_current_page)
        actions.addAction(regenerate)
        tooltips = QAction("Toggle tooltips", self)
        tooltips.setShortcut(QKeySequence("Ctrl+T"))
        tooltips.triggered.connect(lambda: self._tooltip_toggle.toggle())
        actions.addAction(tooltips)

        help_menu = self.menuBar().addMenu("Help")
        help_action = QAction("PEA Help", self)
        help_action.setShortcuts([QKeySequence("Ctrl+Shift+/"), QKeySequence("F1")])
        help_action.triggered.connect(self._show_help)
        help_menu.addAction(help_action)
        setup_action = QAction("Setup assistant", self)
        setup_action.triggered.connect(self._show_setup_assistant)
        help_menu.addAction(setup_action)

    def _add_workflow_guide(
        self,
        layout: QVBoxLayout,
        key: str,
        steps: tuple[str, ...],
        next_action: str,
    ) -> None:
        guide = WorkflowGuide(steps, next_action)
        self._workflow_guides[key] = guide

    def _set_guide(self, key: str, step: int, next_action: str) -> None:
        guide = self._workflow_guides.get(key)
        if guide is not None:
            guide.set_step(step, next_action)
            self._sync_guidance_position()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._health_thread is not None and self._health_thread.isRunning():
            self._close_after_health = True
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)

    @Slot()
    def _show_help(self) -> None:
        if self._help_dialog is None:
            self._help_dialog = HelpDialog(LOGO_PATH, __version__, self)
            self._configure_tooltips()
            self._apply_tooltip_visibility()
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    @Slot()
    def _show_setup_assistant(self) -> None:
        if self._setup_dialog is None:
            self._setup_dialog = SetupAssistant(self._settings, self.windowIcon(), self)
            self._setup_dialog.configuration_requested.connect(
                self._handle_setup_configuration
            )
            self._setup_dialog.finished.connect(self._setup_dialog_closed)
        self._setup_dialog.show()
        self._setup_dialog.raise_()
        self._setup_dialog.activateWindow()

    @Slot()
    def show_setup_assistant_if_first_run(self) -> None:
        if not self._settings.value("setup/assistant_seen", False, type=bool):
            self._show_setup_assistant()

    @Slot()
    def run_startup_checks(self) -> None:
        """Verify this Mac on every launch until all required checks have passed."""
        if self._settings.value("health/startup_version", "") == STARTUP_HEALTH_VERSION:
            return
        self._startup_health_pending = True
        if not self._settings.value("setup/assistant_seen", False, type=bool):
            self._show_setup_assistant()
            return
        self._run_startup_health_check()

    def _run_startup_health_check(self) -> None:
        if not self._startup_health_pending or self._health_thread is not None:
            return
        self._health_check_is_startup = True
        self._run_health_check()

    @Slot(int)
    def _setup_dialog_closed(self, _result: int) -> None:
        if self._setup_dialog is not None:
            self._setup_dialog.deleteLater()
        self._setup_dialog = None
        if self._startup_health_pending:
            QTimer.singleShot(0, self._run_startup_health_check)

    @Slot(str)
    def _handle_setup_configuration(self, target: str) -> None:
        if target in {"openai", "plaud_auth", "health"}:
            self._navigation.setCurrentRow(6)
            if target == "plaud_auth":
                QTimer.singleShot(0, self._sign_in_plaud)
            elif target == "health":
                QTimer.singleShot(0, self._run_health_check)
        elif target == "remarkdown_auth":
            self._navigation.setCurrentRow(2)
            QTimer.singleShot(0, lambda: self._start_remarkdown_job("login"))

    @Slot()
    def _regenerate_current_page(self) -> None:
        index = self._pages.currentIndex()
        if index == 0 and self._regenerate_button.isEnabled():
            self._generate_minutes()
        elif index == 4 and self._weekly_regenerate_button.isEnabled():
            self._generate_weekly_summary()
        else:
            QMessageBox.information(
                self,
                "Regeneration unavailable",
                "Generate a Minutes or Weekly Summary preview first, then choose another model "
                "and regenerate it.",
            )

    def _configure_tooltips(self) -> None:
        def register(widget: QWidget, text: str) -> None:
            widget.setProperty("peaTooltipText", text)
            widget.setAccessibleDescription(text)

        register(
            self._navigation,
            "Choose an application page. Keyboard shortcuts ⌘1 to ⌘7 are also "
            "available on macOS.",
        )
        register(
            self._tooltip_toggle,
            "Turn hover-over help for the complete application on or off.",
        )
        register(
            self._help_button,
            "Open the PEA Help window with workflows, safety boundaries and keyboard shortcuts.",
        )
        register(
            self._setup_button,
            "Check local dependencies and review each installation or authorisation step.",
        )
        register(
            self._editor_size_toggle,
            "Switch the stacked Transcript and Minutes preview between large and compact heights.",
        )

        button_help = {
            "Refresh recordings": "List recent PLAUD recordings without loading a transcript.",
            "Load raw transcript": "Load the raw transcript for the selected PLAUD recording.",
            "Load transcript": "Load a transcript from a local text or Markdown file.",
            "Generate minutes": "Send the approved transcript to the selected OpenAI model and generate a reviewable Minutes draft.",
            "Regenerate with selected model": "Create a new draft from the same inputs using the model currently selected. This makes another API request and incurs additional token cost.",
            "Copy preview": "Copy the current generated preview to the clipboard.",
            "Review DEVONthink import": "Check the destination and possible duplicates before any DEVONthink write.",
            "Action items → OmniFocus": "Open the OmniFocus page with action items extracted from the current Minutes.",
            "Refresh projects": "List active Agenda projects without loading note content.",
            "List project notes": "List note metadata for the selected Agenda project.",
            "List last 7 days": "List metadata for Agenda notes edited during the last seven days across active projects.",
            "Load selected note": "Load the full Markdown of the selected Agenda note through the read-only connector.",
            "Load checked notes for weekly report": "Load the full Markdown only for the checked Agenda notes and make them available to Weekly Summary.",
            "Sign in to remarkdown": "Start or recover the local remarkdown authorisation process.",
            "Refresh connection status": "Check the remarkdown identity, access scope and connection status.",
            "Refresh recent documents": "List recent reMarkable document metadata without starting transcription.",
            "Load existing text": "Load text only when remarkdown already marks the selected document as typed or transcribed.",
            "Review DEVONthink Inbox import": "Check the fixed Inbox destination and possible duplicates before importing the loaded reMarkable document.",
            "Refresh aggregate status": "Load OmniFocus counts only; task titles are not read.",
            "Load task metadata": "Load bounded local task metadata for the selected OmniFocus view.",
            "Use selected action": "Copy the selected Minutes action into the capture fields for review; no task is created.",
            "Review Inbox capture": "Validate the proposed task and check OmniFocus for duplicates; no task is created.",
            "Confirm and create in OmniFocus Inbox": "Create the reviewed task after duplicate protection has cleared it.",
            "Open created task": "Open the task created during this capture in OmniFocus.",
            "Load week’s Minutes": "Load all reviewed PEA Minutes filed in DEVONthink during the selected ISO week.",
            "Generate weekly summary": "Generate a weekly Topic/Summary table from the explicitly selected sources.",
            "Start workflow": "Run the selected controlled workflow up to its review point.",
            "Resume from failed step": "Continue the current workflow from its last recoverable failed step.",
            "Confirm and write to DEVONthink": "Write the reviewed workflow output to DEVONthink after duplicate checks.",
            "Open DEVONthink record": "Open the DEVONthink record created by the current workflow.",
            "Save API key in macOS Keychain": "Store an OpenAI API key securely in the macOS Keychain.",
            "Sign in to PLAUD": "Start the official PLAUD CLI sign-in process.",
            "Run health check": "Check configured connections and capabilities without reading application content.",
            "Refresh local statistics": "Refresh token and request counters recorded by this local PEA installation.",
            "Open OpenAI usage dashboard": "Open the official OpenAI usage dashboard in the browser.",
            "Open billing and credit balance": "Open the official OpenAI billing and credit page in the browser.",
            "Refresh log": "Reload the privacy-filtered local runtime log.",
            "Open log folder": "Open the local folder containing the rotating PEA runtime log.",
        }
        for button in self.findChildren(QPushButton):
            help_text = button_help.get(button.text())
            if help_text:
                register(button, help_text)

        widget_help = (
            (self._plaud_recordings, "Choose a recent PLAUD recording; only its metadata is listed until you load it."),
            (self._model_combo, "Choose the OpenAI model profile used to generate Minutes."),
            (self._source_reference, "Enter or review the stable source reference used for provenance and duplicate protection."),
            (self._meeting_date, "Enter the meeting date in YYYY-MM-DD format."),
            (self._target_database, "Choose the approved DEVONthink database for the Minutes record."),
            (self._destination, "Optionally specify an existing DEVONthink group UUID or path; leave blank to use the database inbox."),
            (self._transcript, "Review or paste the anonymised source transcript that may be sent to OpenAI."),
            (self._preview_rendered, "Read the generated Minutes as a formatted Markdown document."),
            (self._preview, "Review the unchanged Markdown source used for copying and controlled handoffs."),
            (self._agenda_projects, "Choose an active Agenda project after refreshing the project list."),
            (self._agenda_notes, "Choose a note from the selected Agenda project."),
            (self._agenda_report_candidates, "Check the Agenda notes that may be included in the weekly report."),
            (self._agenda_note_text, "Review the selected Agenda note; this field is read-only."),
            (self._agenda_source_reference, "Shows the stable read-only reference for the loaded Agenda note."),
            (self._remarkdown_documents, "Choose a recent reMarkable document whose existing text may be loaded."),
            (self._remarkdown_text, "Review existing typed or transcribed reMarkable text; this field is read-only."),
            (self._remarkdown_source_reference, "Shows the stable remarkdown reference for the loaded document."),
            (self._omnifocus_view, "Choose the bounded OmniFocus task view to load."),
            (self._omnifocus_limit, "Set the maximum number of OmniFocus task records to retrieve."),
            (self._omnifocus_minutes_action, "Select an action item from the most recently generated Minutes."),
            (self._omnifocus_capture_title, "Enter the concise action that should become the OmniFocus Inbox task title."),
            (self._omnifocus_capture_source, "Enter a stable source reference for provenance and duplicate checking."),
            (self._omnifocus_tasks, "Review local task metadata; double-click a task to open it in OmniFocus."),
            (self._weekly_week, "Enter the ISO reporting week in YYYY-Www format."),
            (self._weekly_model_combo, "Choose the OpenAI model profile used for the weekly summary."),
            (self._weekly_target_database, "Choose the approved DEVONthink database for the weekly summary."),
            (self._weekly_destination, "Optionally specify an existing DEVONthink destination; leave blank to use the inbox."),
            (self._weekly_use_minutes, "Include or exclude all reviewed DEVONthink Minutes loaded for the selected ISO week."),
            (self._weekly_use_agenda, "Include or exclude the currently loaded Agenda note from the weekly summary."),
            (self._weekly_use_remarkdown, "Include or exclude the currently loaded reMarkable note from the weekly summary."),
            (self._weekly_updates, "Add approved weekly context, such as non-sensitive work-chat updates."),
            (self._weekly_emails, "Drag user-selected .eml, .txt or .md email exports here; the app never reads a mailbox automatically."),
            (self._weekly_preview_rendered, "Read the weekly summary as a formatted Markdown document."),
            (self._weekly_preview, "Review the generated weekly Topic/Summary table before copying or importing it."),
            (self._workflow_choice, "Choose the controlled multi-step workflow to run."),
            (self._workflow_model, "Choose the OpenAI model profile used by this workflow."),
            (self._workflow_week, "Enter the date or ISO week used by the selected period-summary workflow."),
            (self._workflow_database, "Choose the approved DEVONthink destination database for this workflow."),
            (self._workflow_destination, "Optionally specify an existing DEVONthink group UUID or path."),
            (self._workflow_progress, "Review the status and detail of each workflow step."),
            (self._workflow_preview_rendered, "Read the combined workflow output as a formatted Markdown document."),
            (self._workflow_preview, "Review the unchanged workflow Markdown source before any DEVONthink write."),
            (self._health_table, "Review the latest connection and capability health-check results."),
            (self._runtime_log, "Review recent privacy-filtered application events and error types."),
        )
        for widget, help_text in widget_help:
            register(widget, help_text)

        for widget in self.findChildren(QWidget):
            if widget.property("peaTooltipText"):
                continue
            fallback = ""
            if isinstance(widget, QPushButton) and widget.text():
                fallback = f"Activate {widget.text()}."
            elif isinstance(widget, QComboBox):
                fallback = "Choose one of the available options."
            elif isinstance(widget, QLineEdit):
                fallback = widget.placeholderText() or "Enter or review this value."
            elif isinstance(widget, QPlainTextEdit):
                fallback = widget.placeholderText() or "Review this text."
            elif isinstance(widget, QCheckBox):
                fallback = f"Turn {widget.text()} on or off."
            elif isinstance(widget, QListWidget):
                fallback = "Choose an item from this list."
            elif isinstance(widget, QTableWidget):
                fallback = "Review the available records in this table."
            elif isinstance(widget, QTabWidget):
                fallback = "Choose a settings section."
            if fallback:
                register(widget, fallback)

    def _apply_tooltip_visibility(self) -> None:
        for widget in self.findChildren(QWidget):
            text = widget.property("peaTooltipText")
            if isinstance(text, str) and text:
                widget.setToolTip(text if self._tooltips_enabled else "")

    @Slot(bool)
    def _toggle_tooltips(self, enabled: bool) -> None:
        self._tooltips_enabled = enabled
        self._settings.setValue("show_tooltips", enabled)
        self._tooltip_toggle.setText("Tooltips on" if enabled else "Tooltips off")
        self._apply_tooltip_visibility()

    @Slot(bool)
    def _toggle_minutes_editor_size(self, large: bool) -> None:
        self._settings.setValue("minutes_large_editors", large)
        self._apply_minutes_editor_size()

    def _apply_minutes_editor_size(self) -> None:
        large = self._editor_size_toggle.isChecked()
        height = 380 if large else 220
        self._transcript.setMinimumHeight(height)
        self._preview_tabs.setMinimumHeight(height)
        self._editor_size_toggle.setText(
            "Editor size: Large" if large else "Editor size: Compact"
        )
        self._transcript.updateGeometry()
        self._preview_tabs.updateGeometry()

    @Slot(bool)
    def _toggle_weekly_preview_size(self, large: bool) -> None:
        self._settings.setValue("weekly_large_preview", large)
        self._apply_weekly_preview_size()

    def _apply_weekly_preview_size(self) -> None:
        large = self._weekly_preview_size_toggle.isChecked()
        self._weekly_preview_tabs.setMinimumHeight(480 if large else 250)
        self._weekly_preview_size_toggle.setText(
            "Compact view" if large else "Large view"
        )
        self._weekly_preview_tabs.updateGeometry()

    def _scrollable_page(self, page: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _page_shell(
        self, title: str, subtitle: str, *, minimum_height: int = 780
    ) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setMinimumSize(760, minimum_height)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 26, 30, 24)
        layout.setSpacing(12)
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSub")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return page, layout

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        return card, layout

    def _build_minutes_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Meeting minutes",
            "Create reviewable minutes from an anonymised transcript using one controlled API call.",
            minimum_height=840,
        )
        self._add_workflow_guide(
            layout,
            "minutes",
            ("Select source", "Review inputs", "Generate", "Review", "File or capture"),
            "Select or load a transcript",
        )
        warning = QLabel(
            "Pilot boundary: do not process sensitive personal, recruitment, licensing, welfare, "
            "disciplinary, appeal or formal performance material."
        )
        warning.setObjectName("warning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        plaud_card, plaud_layout = self._card()
        plaud_layout.addWidget(QLabel("PLAUD source"))
        plaud_row = QHBoxLayout()
        self._plaud_recordings = QComboBox()
        self._plaud_recordings.setMinimumWidth(420)
        self._plaud_recordings.setPlaceholderText("Refresh to list recent recordings")
        self._plaud_refresh_button = QPushButton("Refresh recordings")
        self._plaud_refresh_button.clicked.connect(self._refresh_plaud_recordings)
        self._plaud_load_button = QPushButton("Load raw transcript")
        self._plaud_load_button.setObjectName("primary")
        self._plaud_load_button.clicked.connect(self._load_selected_plaud_transcript)
        self._plaud_load_button.setEnabled(False)
        plaud_row.addWidget(self._plaud_recordings, 1)
        plaud_row.addWidget(self._plaud_refresh_button)
        plaud_row.addWidget(self._plaud_load_button)
        plaud_layout.addLayout(plaud_row)
        plaud_note = QLabel(
            "Only the recording you select is retrieved. The raw transcript remains authoritative; "
            "the PLAUD summary is used only as secondary speaker and name context."
        )
        plaud_note.setObjectName("pageSub")
        plaud_note.setWordWrap(True)
        plaud_layout.addWidget(plaud_note)
        layout.addWidget(plaud_card)

        context_card, context_layout = self._card()
        context_header = QHBoxLayout()
        context_header.addWidget(QLabel("Interpretation context"))
        context_header.addStretch()
        self._context_load_button = QPushButton("Load ChatGPT context export")
        self._context_load_button.clicked.connect(self._load_contextual_memory)
        context_header.addWidget(self._context_load_button)
        context_layout.addLayout(context_header)
        context_note = QLabel(
            "ChatGPT personal Memory is not exposed through the OpenAI API. Load a reviewed "
            "non-sensitive text or Markdown export manually when relevant. Context may resolve "
            "names and roles but cannot prove attendance, decisions or actions."
        )
        context_note.setObjectName("pageSub")
        context_note.setWordWrap(True)
        context_layout.addWidget(context_note)
        context_tabs = QTabWidget()
        self._plaud_summary = QPlainTextEdit()
        self._plaud_summary.setReadOnly(True)
        self._plaud_summary.setPlaceholderText(
            "The selected recording’s PLAUD summary will appear here when available."
        )
        self._contextual_memory = QPlainTextEdit()
        self._contextual_memory.setPlaceholderText(
            "Load or paste only the approved contextual information needed for this meeting."
        )
        context_tabs.addTab(self._plaud_summary, "PLAUD speaker context")
        context_tabs.addTab(self._contextual_memory, "ChatGPT context (manual)")
        self._contextual_memory.textChanged.connect(self._update_guidance_sources)
        context_tabs.setMaximumHeight(170)
        context_layout.addWidget(context_tabs)
        layout.addWidget(context_card)

        controls, controls_layout = self._card()
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self._model_combo = QComboBox()
        default_profile = self._settings.value("default_model_profile", "economy")
        for index, profile in enumerate(MODEL_PROFILES):
            self._model_combo.addItem(
                f"{profile.label} — {profile.model} (cost: {profile.cost_label.lower()})",
                profile,
            )
            if profile.key == default_profile:
                self._model_combo.setCurrentIndex(index)
        self._model_combo.currentIndexChanged.connect(self._model_changed)
        self._model_description = QLabel()
        self._model_description.setObjectName("pageSub")
        self._source_reference = QLineEdit()
        self._source_reference.setPlaceholderText(
            "PLAUD recording ID or another stable source reference"
        )
        self._meeting_date = QLineEdit()
        self._meeting_date.setPlaceholderText("YYYY-MM-DD; populated automatically from PLAUD")
        self._target_database = QComboBox()
        for database in WRITABLE_DATABASES:
            self._target_database.addItem(database)
        self._destination = QLineEdit()
        self._destination.setPlaceholderText("Optional existing group UUID or path; blank uses inbox")
        form.addWidget(QLabel("Model profile"), 0, 0)
        form.addWidget(self._model_combo, 0, 1, 1, 3)
        form.addWidget(self._model_description, 1, 1, 1, 3)
        form.addWidget(QLabel("Source reference"), 2, 0)
        form.addWidget(self._source_reference, 2, 1)
        form.addWidget(QLabel("Meeting date"), 2, 2)
        form.addWidget(self._meeting_date, 2, 3)
        form.addWidget(QLabel("DEVONthink database"), 3, 0)
        form.addWidget(self._target_database, 3, 1)
        form.addWidget(QLabel("Destination"), 3, 2)
        form.addWidget(self._destination, 3, 3)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        controls_layout.addLayout(form)

        button_grid = QGridLayout()
        button_grid.setHorizontalSpacing(8)
        button_grid.setVerticalSpacing(8)
        load_button = QPushButton("Load transcript")
        load_button.clicked.connect(self._load_transcript)
        self._generate_button = QPushButton("Generate minutes")
        self._generate_button.setObjectName("primary")
        self._generate_button.clicked.connect(self._generate_minutes)
        self._regenerate_button = QPushButton("Regenerate with selected model")
        self._regenerate_button.clicked.connect(self._generate_minutes)
        self._regenerate_button.setEnabled(False)
        copy_button = QPushButton("Copy preview")
        copy_button.clicked.connect(self._copy_preview)
        self._devonthink_button = QPushButton("Review DEVONthink import")
        self._devonthink_button.clicked.connect(self._prepare_devonthink_handoff)
        self._minutes_omnifocus_button = QPushButton("Action items → OmniFocus")
        self._minutes_omnifocus_button.clicked.connect(
            self._open_minutes_actions_in_omnifocus
        )
        self._minutes_omnifocus_button.setEnabled(False)
        for position, button in enumerate(
            (
                load_button,
                self._generate_button,
                self._regenerate_button,
                copy_button,
                self._devonthink_button,
                self._minutes_omnifocus_button,
            )
        ):
            button_grid.addWidget(button, position // 3, position % 3)
        for column in range(3):
            button_grid.setColumnStretch(column, 1)
        controls_layout.addLayout(button_grid)
        layout.addWidget(controls)

        editor_toolbar = QHBoxLayout()
        editor_toolbar.addStretch()
        self._editor_size_toggle = QPushButton()
        self._editor_size_toggle.setCheckable(True)
        self._editor_size_toggle.setChecked(
            self._settings.value("minutes_large_editors", True, type=bool)
        )
        self._editor_size_toggle.toggled.connect(self._toggle_minutes_editor_size)
        editor_toolbar.addWidget(self._editor_size_toggle)
        layout.addLayout(editor_toolbar)

        editors = QVBoxLayout()
        transcript_card, transcript_layout = self._card()
        transcript_layout.addWidget(QLabel("Transcript"))
        self._transcript = QPlainTextEdit()
        self._transcript.setPlaceholderText("Paste an anonymised transcript here.")
        transcript_layout.addWidget(self._transcript)
        editors.addWidget(transcript_card)

        preview_card, preview_layout = self._card()
        preview_layout.addWidget(QLabel("Minutes preview"))
        self._preview_tabs = QTabWidget()
        self._preview_rendered = LocalMarkdownPreview()
        self._preview_rendered.setOpenExternalLinks(False)
        self._preview_rendered.setOpenLinks(False)
        self._preview_rendered.setPlaceholderText(
            "The formatted Minutes document will appear here after generation."
        )
        self._preview_rendered.document().setDefaultStyleSheet(
            "h1, h2, h3 { color: #17212b; margin-top: 12px; margin-bottom: 6px; }"
            "table { border-collapse: collapse; margin: 8px 0; }"
            "th { background: #eef2f4; font-weight: 600; }"
            "th, td { border: 1px solid #cfd7df; padding: 6px 8px; }"
            "li { margin-bottom: 4px; }"
        )
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlaceholderText(
            "The unchanged Markdown source will appear here after generation."
        )
        self._preview_tabs.addTab(self._preview_rendered, "Rendered preview")
        self._preview_tabs.addTab(self._preview, "Markdown source")
        preview_layout.addWidget(self._preview_tabs)
        editors.addWidget(preview_card)
        layout.addLayout(editors)
        self._apply_minutes_editor_size()

        self._status = QLabel("Ready. No data has been sent.")
        self._status.setObjectName("pageSub")
        layout.addWidget(self._status)
        self._model_changed()
        return page

    def _build_agenda_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Agenda updates",
            "Review one note or prepare an explicit multi-note selection for the weekly report.",
            minimum_height=700,
        )
        self._add_workflow_guide(
            layout,
            "agenda",
            ("Projects", "Notes", "Load", "Use"),
            "Refresh active projects",
        )
        warning = QLabel(
            "Do not load sensitive HR, recruitment, welfare, medical, disciplinary, appeal or "
            "formal performance notes. Agenda remains a reflection and decision layer."
        )
        warning.setObjectName("warning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        controls, controls_layout = self._card()
        project_row = QHBoxLayout()
        self._agenda_projects = QComboBox()
        self._agenda_projects.setPlaceholderText("Refresh to list active Agenda projects")
        self._agenda_projects.currentIndexChanged.connect(self._agenda_project_changed)
        self._agenda_refresh_projects_button = QPushButton("Refresh projects")
        self._agenda_refresh_projects_button.clicked.connect(self._refresh_agenda_projects)
        self._agenda_list_notes_button = QPushButton("List project notes")
        self._agenda_list_notes_button.clicked.connect(self._list_agenda_notes)
        self._agenda_list_notes_button.setEnabled(False)
        self._agenda_recent_notes_button = QPushButton("List last 7 days")
        self._agenda_recent_notes_button.clicked.connect(self._list_recent_agenda_notes)
        self._agenda_recent_notes_button.setEnabled(False)
        project_row.addWidget(self._agenda_projects, 1)
        project_row.addWidget(self._agenda_refresh_projects_button)
        project_row.addWidget(self._agenda_list_notes_button)
        project_row.addWidget(self._agenda_recent_notes_button)
        controls_layout.addLayout(project_row)

        note_row = QHBoxLayout()
        self._agenda_notes = QComboBox()
        self._agenda_notes.setPlaceholderText("Select a project, then list its notes")
        self._agenda_notes.currentIndexChanged.connect(self._agenda_note_changed)
        self._agenda_load_note_button = QPushButton("Load selected note")
        self._agenda_load_note_button.setObjectName("primary")
        self._agenda_load_note_button.clicked.connect(self._load_selected_agenda_note)
        self._agenda_load_note_button.setEnabled(False)
        note_row.addWidget(self._agenda_notes, 1)
        note_row.addWidget(self._agenda_load_note_button)
        controls_layout.addLayout(note_row)

        controls_layout.addWidget(QLabel("Weekly report selection"))
        report_row = QHBoxLayout()
        self._agenda_report_candidates = QListWidget()
        self._agenda_report_candidates.setObjectName("agendaReportCandidates")
        checkmark_path = (ASSET_DIRECTORY / "checkmark.svg").as_posix()
        self._agenda_report_candidates.setStyleSheet(
            "QListWidget#agendaReportCandidates::indicator { width: 18px; height: 18px; }"
            "QListWidget#agendaReportCandidates::indicator:unchecked {"
            " border: 2px solid #71808d; border-radius: 4px; background: #ffffff; }"
            "QListWidget#agendaReportCandidates::indicator:unchecked:hover {"
            " border-color: #49677f; background: #eef2f4; }"
            "QListWidget#agendaReportCandidates::indicator:checked {"
            " border: 2px solid #49677f; border-radius: 4px; background: #49677f;"
            f" image: url({checkmark_path}); }}"
        )
        self._agenda_report_candidates.setMinimumHeight(125)
        self._agenda_report_candidates.itemChanged.connect(
            self._agenda_report_selection_changed
        )
        self._agenda_load_report_notes_button = QPushButton(
            "Load checked notes for weekly report"
        )
        self._agenda_load_report_notes_button.setObjectName("primary")
        self._agenda_load_report_notes_button.clicked.connect(
            self._load_agenda_report_notes
        )
        self._agenda_load_report_notes_button.setEnabled(False)
        report_row.addWidget(self._agenda_report_candidates, 1)
        report_row.addWidget(
            self._agenda_load_report_notes_button,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        controls_layout.addLayout(report_row)
        self._agenda_report_status = QLabel("No Agenda notes selected for the weekly report.")
        self._agenda_report_status.setObjectName("pageSub")
        self._agenda_report_status.setWordWrap(True)
        controls_layout.addWidget(self._agenda_report_status)

        scope_note = QLabel(
            "Project and last-seven-days views read metadata only. Full Markdown is retrieved "
            "only for the highlighted note or the notes you explicitly check for the report."
        )
        scope_note.setObjectName("pageSub")
        scope_note.setWordWrap(True)
        controls_layout.addWidget(scope_note)
        layout.addWidget(controls)

        note_card, note_layout = self._card()
        self._agenda_note_title = QLabel("No Agenda note loaded")
        note_layout.addWidget(self._agenda_note_title)
        self._agenda_note_text = QPlainTextEdit()
        self._agenda_note_text.setReadOnly(True)
        self._agenda_note_text.setPlaceholderText("The selected Agenda note will appear here.")
        note_layout.addWidget(self._agenda_note_text)
        self._agenda_source_reference = QLineEdit()
        self._agenda_source_reference.setReadOnly(True)
        self._agenda_source_reference.setPlaceholderText("Stable Agenda source reference")
        note_layout.addWidget(self._agenda_source_reference)
        layout.addWidget(note_card, 1)

        self._agenda_status = QLabel("Ready. No Agenda content has been read.")
        self._agenda_status.setObjectName("pageSub")
        layout.addWidget(self._agenda_status)
        return page

    def _build_placeholder_page(self, title: str, subtitle: str) -> QWidget:
        page, layout = self._page_shell(title, subtitle)
        card, card_layout = self._card()
        status = QLabel("Integration not yet enabled")
        status.setObjectName("statusMissing")
        detail = QLabel(
            "This workflow will use the approved source connector, show a reviewable preview, "
            "check duplicates and require confirmation before any DEVONthink write."
        )
        detail.setWordWrap(True)
        card_layout.addWidget(status)
        card_layout.addWidget(detail)
        card_layout.addStretch()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(card, 1)
        return page

    def _build_remarkable_page(self) -> QWidget:
        page, layout = self._page_shell(
            "reMarkable notes",
            "Review existing text from one selected recent document through remarkdown.",
            minimum_height=700,
        )
        self._add_workflow_guide(
            layout,
            "remarkable",
            ("Connect", "Documents", "Load", "Review", "Inbox"),
            "Check the remarkdown connection",
        )
        warning = QLabel(
            "This reader never starts a paid transcription. It lists only documents modified in "
            "the last 30 days and loads text only when remarkdown already marks it as typed or "
            "transcribed. Transcribed handwriting remains derived content and requires review."
        )
        warning.setObjectName("warning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        controls, controls_layout = self._card()
        connection_header = QHBoxLayout()
        connection_header.addWidget(QLabel("remarkdown connection"))
        connection_header.addStretch()
        self._remarkdown_login_button = QPushButton("Sign in to remarkdown")
        self._remarkdown_login_button.clicked.connect(self._sign_in_remarkdown)
        self._remarkdown_status_button = QPushButton("Refresh connection status")
        self._remarkdown_status_button.clicked.connect(self._refresh_remarkdown_identity)
        connection_header.addWidget(self._remarkdown_login_button)
        connection_header.addWidget(self._remarkdown_status_button)
        controls_layout.addLayout(connection_header)
        self._remarkdown_connection_status = QLabel()
        controls_layout.addWidget(self._remarkdown_connection_status)
        self._remarkdown_identity = QLabel(
            "Pairing, reading scope, transcription window and credit status have not been checked."
        )
        self._remarkdown_identity.setObjectName("pageSub")
        self._remarkdown_identity.setWordWrap(True)
        controls_layout.addWidget(self._remarkdown_identity)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        controls_layout.addWidget(separator)

        document_row = QHBoxLayout()
        self._remarkdown_documents = QComboBox()
        self._remarkdown_documents.setPlaceholderText("Sign in, then refresh recent documents")
        self._remarkdown_documents.currentIndexChanged.connect(
            self._remarkdown_document_changed
        )
        self._remarkdown_list_button = QPushButton("Refresh recent documents")
        self._remarkdown_list_button.clicked.connect(self._list_remarkdown_documents)
        self._remarkdown_load_button = QPushButton("Load existing text")
        self._remarkdown_load_button.setObjectName("primary")
        self._remarkdown_load_button.clicked.connect(self._load_selected_remarkdown_document)
        self._remarkdown_load_button.setEnabled(False)
        document_row.addWidget(self._remarkdown_documents, 1)
        document_row.addWidget(self._remarkdown_list_button)
        document_row.addWidget(self._remarkdown_load_button)
        controls_layout.addLayout(document_row)
        self._remarkdown_document_status = QLabel(
            "No document metadata has been retrieved."
        )
        self._remarkdown_document_status.setObjectName("pageSub")
        self._remarkdown_document_status.setWordWrap(True)
        controls_layout.addWidget(self._remarkdown_document_status)
        layout.addWidget(controls)

        content_card, content_layout = self._card()
        self._remarkdown_document_title = QLabel("No reMarkable document loaded")
        content_layout.addWidget(self._remarkdown_document_title)
        self._remarkdown_text = QPlainTextEdit()
        self._remarkdown_text.setReadOnly(True)
        self._remarkdown_text.setPlaceholderText(
            "Existing typed or transcribed text from the selected document will appear here."
        )
        content_layout.addWidget(self._remarkdown_text, 1)
        self._remarkdown_source_reference = QLineEdit()
        self._remarkdown_source_reference.setReadOnly(True)
        self._remarkdown_source_reference.setPlaceholderText("Stable remarkdown source reference")
        import_row = QHBoxLayout()
        import_row.addWidget(self._remarkdown_source_reference, 1)
        import_target = QLabel("DEVONthink target: Inbox · Database inbox")
        import_target.setObjectName("pageSub")
        import_row.addWidget(import_target)
        self._remarkdown_devonthink_button = QPushButton(
            "Review DEVONthink Inbox import"
        )
        self._remarkdown_devonthink_button.clicked.connect(
            self._prepare_remarkdown_devonthink_handoff
        )
        self._remarkdown_devonthink_button.setEnabled(False)
        import_row.addWidget(self._remarkdown_devonthink_button)
        content_layout.addLayout(import_row)
        layout.addWidget(content_card, 1)

        self._remarkdown_status = QLabel("Ready. No reMarkable content has been read.")
        self._remarkdown_status.setObjectName("pageSub")
        layout.addWidget(self._remarkdown_status)
        self._refresh_remarkdown_local_status()
        return page

    def _build_omnifocus_page(self) -> QWidget:
        page, layout = self._page_shell(
            "OmniFocus",
            "Review commitments and prepare controlled, source-referenced Inbox captures.",
            minimum_height=940,
        )
        self._add_workflow_guide(
            layout,
            "omnifocus",
            ("Choose activity", "Load or prepare", "Review", "Confirm", "Open"),
            "Load a task view or prepare an Inbox capture",
        )
        warning = QLabel(
            "Task names and project names remain local and are never sent to OpenAI. Existing "
            "notes, attachments and tags are not loaded or retained; a new capture receives only "
            "a bounded PEA provenance marker. Do not process sensitive HR, medical, recruitment, "
            "licensing or formal performance material."
        )
        warning.setObjectName("warning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        overview_card, overview_layout = self._card()
        overview_row = QHBoxLayout()
        overview_row.addWidget(QLabel("GTD overview"))
        self._omnifocus_overview = QLabel(
            "No OmniFocus data has been read. Aggregate status does not include task titles."
        )
        self._omnifocus_overview.setObjectName("pageSub")
        overview_row.addWidget(self._omnifocus_overview, 1)
        self._omnifocus_overview_button = QPushButton("Refresh aggregate status")
        self._omnifocus_overview_button.setObjectName("primary")
        self._omnifocus_overview_button.clicked.connect(self._refresh_omnifocus_overview)
        overview_row.addWidget(self._omnifocus_overview_button)
        overview_layout.addLayout(overview_row)
        layout.addWidget(overview_card)

        controls, controls_layout = self._card()
        task_row = QHBoxLayout()
        task_row.addWidget(QLabel("Task view"))
        self._omnifocus_view = QComboBox()
        for label, value in (
            ("Inbox", "inbox"),
            ("Available / next", "available"),
            ("Waiting For", "waiting"),
            ("Flagged", "flagged"),
            ("All remaining", "remaining"),
        ):
            self._omnifocus_view.addItem(label, value)
        self._omnifocus_view.setCurrentIndex(1)
        task_row.addWidget(self._omnifocus_view)
        task_row.addWidget(QLabel("Maximum tasks"))
        self._omnifocus_limit = QComboBox()
        for limit in (25, 50, 100):
            self._omnifocus_limit.addItem(str(limit), limit)
        self._omnifocus_limit.setCurrentIndex(1)
        task_row.addWidget(self._omnifocus_limit)
        self._omnifocus_tasks_button = QPushButton("Load task metadata")
        self._omnifocus_tasks_button.clicked.connect(self._load_omnifocus_tasks)
        task_row.addWidget(self._omnifocus_tasks_button)
        scope = QLabel(
            "Local metadata only; no OpenAI request or external write."
        )
        scope.setObjectName("pageSub")
        task_row.addWidget(scope, 1)
        controls_layout.addLayout(task_row)
        layout.addWidget(controls)

        capture_card, capture_layout = self._card()
        minutes_action_row = QHBoxLayout()
        minutes_action_row.addWidget(QLabel("Controlled Inbox capture"))
        minutes_action_row.addWidget(QLabel("Minutes action item"))
        self._omnifocus_minutes_action = QComboBox()
        self._omnifocus_minutes_action.setPlaceholderText(
            "Generate Minutes with action items first"
        )
        self._omnifocus_minutes_action.setToolTip(
            "Select an action item from the most recently generated Minutes. "
            "Nothing is written to OmniFocus at this stage."
        )
        self._omnifocus_minutes_action.currentIndexChanged.connect(
            self._omnifocus_minutes_action_changed
        )
        self._omnifocus_use_minutes_action_button = QPushButton("Use selected action")
        self._omnifocus_use_minutes_action_button.setToolTip(
            "Copy the selected Minutes action into the task title and source-reference fields "
            "for review. This does not create an OmniFocus task."
        )
        self._omnifocus_use_minutes_action_button.clicked.connect(
            self._use_selected_minutes_action
        )
        self._omnifocus_use_minutes_action_button.setEnabled(False)
        minutes_action_row.addWidget(self._omnifocus_minutes_action, 1)
        minutes_action_row.addWidget(self._omnifocus_use_minutes_action_button)
        capture_layout.addLayout(minutes_action_row)
        self._omnifocus_minutes_action_detail = QLabel(
            "Owner and due date will be shown here; no assignment is made automatically."
        )
        self._omnifocus_minutes_action_detail.setObjectName("pageSub")
        capture_layout.addWidget(self._omnifocus_minutes_action_detail)
        capture_form = QHBoxLayout()
        self._omnifocus_capture_title = QLineEdit()
        self._omnifocus_capture_title.setPlaceholderText("One concise next action")
        self._omnifocus_capture_title.setToolTip(
            "Enter the concise action that should become the OmniFocus Inbox task title."
        )
        self._omnifocus_capture_title.textChanged.connect(self._omnifocus_capture_changed)
        self._omnifocus_capture_source = QLineEdit()
        self._omnifocus_capture_source.setPlaceholderText(
            "Stable reference, for example manual:weekly-review-2026-W32"
        )
        self._omnifocus_capture_source.setToolTip(
            "Enter a stable reference to the source record. It supports provenance and "
            "duplicate checking."
        )
        self._omnifocus_capture_source.textChanged.connect(self._omnifocus_capture_changed)
        capture_form.addWidget(QLabel("Task title"))
        capture_form.addWidget(self._omnifocus_capture_title, 1)
        capture_form.addWidget(QLabel("Source reference"))
        capture_form.addWidget(self._omnifocus_capture_source, 1)
        capture_layout.addLayout(capture_form)
        capture_buttons = QHBoxLayout()
        self._omnifocus_capture_review_button = QPushButton("Review Inbox capture")
        self._omnifocus_capture_review_button.setToolTip(
            "Validate the proposed task and check OmniFocus for duplicates. "
            "Review does not write to OmniFocus."
        )
        self._omnifocus_capture_review_button.clicked.connect(
            self._review_omnifocus_capture
        )
        self._omnifocus_capture_confirm_button = QPushButton(
            "Confirm and create in OmniFocus Inbox"
        )
        self._omnifocus_capture_confirm_button.setToolTip(
            "Create the reviewed task in the OmniFocus Inbox. This becomes available only "
            "after duplicate protection has cleared the proposal."
        )
        self._omnifocus_capture_confirm_button.setObjectName("primary")
        self._omnifocus_capture_confirm_button.clicked.connect(
            self._confirm_omnifocus_capture
        )
        self._omnifocus_capture_confirm_button.setEnabled(False)
        self._omnifocus_capture_open_button = QPushButton("Open created task")
        self._omnifocus_capture_open_button.setToolTip(
            "Open the task created during this capture in OmniFocus."
        )
        self._omnifocus_capture_open_button.clicked.connect(
            self._open_omnifocus_capture
        )
        self._omnifocus_capture_open_button.setEnabled(False)
        capture_buttons.addWidget(self._omnifocus_capture_review_button)
        capture_buttons.addWidget(self._omnifocus_capture_confirm_button)
        capture_buttons.addWidget(self._omnifocus_capture_open_button)
        self._omnifocus_capture_status = QLabel(
            "Enter one task and a stable source reference. Review does not write to OmniFocus."
        )
        self._omnifocus_capture_status.setObjectName("pageSub")
        self._omnifocus_capture_status.setWordWrap(True)
        capture_buttons.addWidget(self._omnifocus_capture_status, 1)
        capture_layout.addLayout(capture_buttons)
        layout.addWidget(capture_card)

        tasks_card, tasks_layout = self._card()
        tasks_layout.addWidget(QLabel("Selected task view · Double-click a task to open it"))
        self._omnifocus_tasks = QTableWidget(0, 6)
        self._omnifocus_tasks.setHorizontalHeaderLabels(
            ["Task", "Project", "Status", "Due", "Deferred", "Flagged"]
        )
        self._omnifocus_tasks.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._omnifocus_tasks.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._omnifocus_tasks.itemDoubleClicked.connect(self._open_omnifocus_task)
        self._omnifocus_tasks.setToolTip("Double-click a task to open it in OmniFocus.")
        self._omnifocus_tasks.verticalHeader().setVisible(False)
        self._omnifocus_tasks.verticalHeader().setDefaultSectionSize(30)
        self._omnifocus_tasks.setMinimumHeight(174)
        self._omnifocus_tasks.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._omnifocus_tasks.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        for column in range(2, 6):
            self._omnifocus_tasks.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        tasks_layout.addWidget(self._omnifocus_tasks, 1)
        layout.addWidget(tasks_card, 1)

        self._omnifocus_status = QLabel("Ready. No OmniFocus content has been read.")
        self._omnifocus_status.setObjectName("pageSub")
        layout.addWidget(self._omnifocus_status)
        return page

    def _build_weekly_summary_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Weekly summary",
            "Combine all reviewed Minutes from the ISO week with explicitly selected sources.",
            minimum_height=760,
        )
        self._add_workflow_guide(
            layout,
            "weekly",
            ("Sources", "Week and model", "Generate", "Review", "File"),
            "Load and select the approved weekly sources",
        )
        warning = QLabel(
            "Only the sources selected below are sent to OpenAI. Exclude sensitive HR, medical, "
            "welfare, recruitment, disciplinary, appeal or formal performance material."
        )
        warning.setObjectName("warning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        controls, controls_layout = self._card()
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        current_iso = datetime.now().astimezone().date().isocalendar()
        self._weekly_week = QLineEdit(f"{current_iso.year}-W{current_iso.week:02d}")
        self._weekly_week.setPlaceholderText("YYYY-Www")
        self._weekly_week.editingFinished.connect(self._weekly_period_changed)
        self._weekly_model_combo = QComboBox()
        default_profile = self._settings.value("default_model_profile", "economy")
        for index, profile in enumerate(MODEL_PROFILES):
            self._weekly_model_combo.addItem(
                f"{profile.label} — {profile.model} (cost: {profile.cost_label.lower()})",
                profile,
            )
            if profile.key == default_profile:
                self._weekly_model_combo.setCurrentIndex(index)
        self._weekly_target_database = QComboBox()
        for database in WRITABLE_DATABASES:
            self._weekly_target_database.addItem(database)
        self._weekly_destination = QLineEdit()
        self._weekly_destination.setPlaceholderText(
            "Optional existing group UUID or path; blank uses inbox"
        )
        form.addWidget(QLabel("ISO week"), 0, 0)
        form.addWidget(self._weekly_week, 0, 1)
        form.addWidget(QLabel("Model profile"), 0, 2)
        form.addWidget(self._weekly_model_combo, 0, 3)
        form.addWidget(QLabel("DEVONthink database"), 1, 0)
        form.addWidget(self._weekly_target_database, 1, 1)
        form.addWidget(QLabel("Destination"), 1, 2)
        form.addWidget(self._weekly_destination, 1, 3)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 2)
        controls_layout.addLayout(form)

        source_row = QHBoxLayout()
        self._weekly_use_minutes = QCheckBox("Minutes from selected week")
        self._weekly_use_agenda = QCheckBox("Current Agenda note")
        self._weekly_use_remarkdown = QCheckBox("Current reMarkable note")
        for checkbox in (
            self._weekly_use_minutes,
            self._weekly_use_agenda,
            self._weekly_use_remarkdown,
        ):
            checkbox.setChecked(True)
            source_row.addWidget(checkbox)
        source_row.addStretch()
        self._weekly_load_minutes_button = QPushButton("Load week’s Minutes")
        self._weekly_load_minutes_button.clicked.connect(self._load_weekly_minutes)
        source_row.addWidget(self._weekly_load_minutes_button)
        controls_layout.addLayout(source_row)
        self._weekly_source_status = QLabel()
        self._weekly_source_status.setObjectName("pageSub")
        self._weekly_source_status.setWordWrap(True)
        controls_layout.addWidget(self._weekly_source_status)

        button_row = QHBoxLayout()
        self._weekly_generate_button = QPushButton("Generate weekly summary")
        self._weekly_generate_button.setObjectName("primary")
        self._weekly_generate_button.clicked.connect(self._generate_weekly_summary)
        self._weekly_regenerate_button = QPushButton("Regenerate with selected model")
        self._weekly_regenerate_button.clicked.connect(self._generate_weekly_summary)
        self._weekly_regenerate_button.setEnabled(False)
        weekly_copy = QPushButton("Copy preview")
        weekly_copy.clicked.connect(self._copy_weekly_preview)
        self._weekly_devonthink_button = QPushButton("Review DEVONthink import")
        self._weekly_devonthink_button.clicked.connect(
            self._prepare_weekly_devonthink_handoff
        )
        button_row.addWidget(self._weekly_generate_button)
        button_row.addWidget(self._weekly_regenerate_button)
        button_row.addWidget(weekly_copy)
        button_row.addWidget(self._weekly_devonthink_button)
        button_row.addStretch()
        controls_layout.addLayout(button_row)
        layout.addWidget(controls)

        editors = QHBoxLayout()
        updates_card, updates_layout = self._card()
        updates_layout.addWidget(QLabel("Additional user-approved sources"))
        source_tabs = QTabWidget()
        self._weekly_updates = QPlainTextEdit()
        self._weekly_updates.setPlaceholderText(
            "Paste only the work-related chat messages that should contribute to this summary."
        )
        source_tabs.addTab(self._weekly_updates, "Work-related chats")
        self._weekly_updates.textChanged.connect(self._update_guidance_sources)
        self._weekly_emails = ManualEmailDropEdit()
        self._weekly_emails.setPlaceholderText(
            "Drag .eml, .txt or .md email exports here. Nothing is read from a mailbox."
        )
        self._weekly_emails.files_loaded.connect(
            lambda count: self._weekly_status.setText(
                f"Loaded {count} user-selected email file(s). No data has been sent."
            )
        )
        source_tabs.addTab(self._weekly_emails, "Emails (manual upload)")
        self._weekly_emails.textChanged.connect(self._update_guidance_sources)
        updates_layout.addWidget(source_tabs)
        editors.addWidget(updates_card, 1)

        preview_card, preview_layout = self._card()
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("Weekly summary preview"))
        preview_header.addStretch()
        self._weekly_preview_size_toggle = QPushButton("Large view")
        self._weekly_preview_size_toggle.setCheckable(True)
        self._weekly_preview_size_toggle.setChecked(
            self._settings.value("weekly_large_preview", False, type=bool)
        )
        self._weekly_preview_size_toggle.toggled.connect(
            self._toggle_weekly_preview_size
        )
        preview_header.addWidget(self._weekly_preview_size_toggle)
        preview_layout.addLayout(preview_header)
        self._weekly_preview_tabs = QTabWidget()
        self._weekly_preview_rendered = LocalMarkdownPreview()
        self._weekly_preview_rendered.setOpenExternalLinks(False)
        self._weekly_preview_rendered.setOpenLinks(False)
        self._weekly_preview_rendered.setPlaceholderText(
            "The formatted weekly summary will appear here."
        )
        self._weekly_preview = QPlainTextEdit()
        self._weekly_preview.setReadOnly(True)
        self._weekly_preview.setPlaceholderText(
            "The unchanged Markdown source will appear here."
        )
        self._weekly_preview_tabs.addTab(self._weekly_preview_rendered, "Rendered preview")
        self._weekly_preview_tabs.addTab(self._weekly_preview, "Markdown source")
        preview_layout.addWidget(self._weekly_preview_tabs)
        editors.addWidget(preview_card, 1)
        layout.addLayout(editors, 1)

        self._weekly_status = QLabel("Ready. No weekly source has been sent.")
        self._weekly_status.setObjectName("pageSub")
        layout.addWidget(self._weekly_status)
        self._refresh_weekly_source_status()
        self._apply_weekly_preview_size()
        return page

    def _build_workflows_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Workflows",
            "Run controlled multi-step workflows with one final external-write confirmation.",
            minimum_height=940,
        )
        self._add_workflow_guide(
            layout,
            "workflows",
            ("Configure", "Run", "Review", "Confirm", "Open"),
            "Choose a workflow, model and destination",
        )
        warning = QLabel(
            "Starting a workflow may retrieve the selected source and make one OpenAI API "
            "request. Review the generated preview before using the final DEVONthink write button."
        )
        warning.setObjectName("warning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        controls, controls_layout = self._card()
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self._workflow_choice = QComboBox()
        self._workflow_choice.addItem(
            "Latest PLAUD → Minutes → DEVONthink", "latest_plaud_minutes"
        )
        self._workflow_choice.addItem(
            "Daily Summary — all reviewed Minutes for one day", "daily_summary"
        )
        self._workflow_choice.addItem(
            "Weekly Summary — all reviewed Minutes for one week", "weekly_summary"
        )
        self._workflow_choice.currentIndexChanged.connect(self._workflow_selection_changed)
        self._workflow_model = QComboBox()
        default_profile = self._settings.value("default_model_profile", "economy")
        for index, profile in enumerate(MODEL_PROFILES):
            self._workflow_model.addItem(
                f"{profile.label} — {profile.model} (cost: {profile.cost_label.lower()})",
                profile,
            )
            if profile.key == default_profile:
                self._workflow_model.setCurrentIndex(index)
        self._workflow_model.currentIndexChanged.connect(self._workflow_selection_changed)
        self._workflow_week = QLineEdit(datetime.now().astimezone().date().isoformat())
        self._workflow_week.setPlaceholderText("YYYY-MM-DD")
        self._workflow_database = QComboBox()
        for database in WRITABLE_DATABASES:
            self._workflow_database.addItem(database)
        self._workflow_destination = QLineEdit()
        self._workflow_destination.setPlaceholderText(
            "Optional existing group UUID or path; blank uses inbox"
        )
        form.addWidget(QLabel("Workflow"), 0, 0)
        form.addWidget(self._workflow_choice, 0, 1)
        form.addWidget(QLabel("Model profile"), 0, 2)
        form.addWidget(self._workflow_model, 0, 3)
        self._workflow_period_label = QLabel("Date")
        form.addWidget(self._workflow_period_label, 1, 0)
        form.addWidget(self._workflow_week, 1, 1)
        form.addWidget(QLabel("DEVONthink database"), 1, 2)
        form.addWidget(self._workflow_database, 1, 3)
        form.addWidget(QLabel("Destination"), 2, 0)
        form.addWidget(self._workflow_destination, 2, 1, 1, 3)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)
        controls_layout.addLayout(form)
        self._workflow_cost = QLabel()
        self._workflow_cost.setObjectName("pageSub")
        self._workflow_cost.setWordWrap(True)
        controls_layout.addWidget(self._workflow_cost)

        buttons = QGridLayout()
        buttons.setHorizontalSpacing(8)
        buttons.setVerticalSpacing(8)
        self._workflow_start_button = QPushButton("Start workflow")
        self._workflow_start_button.setObjectName("primary")
        self._workflow_start_button.clicked.connect(self._start_selected_workflow)
        self._workflow_resume_button = QPushButton("Resume from failed step")
        self._workflow_resume_button.clicked.connect(self._resume_workflow)
        self._workflow_resume_button.setEnabled(False)
        self._workflow_confirm_button = QPushButton("Confirm and write to DEVONthink")
        self._workflow_confirm_button.clicked.connect(self._confirm_workflow_import)
        self._workflow_confirm_button.setEnabled(False)
        self._workflow_open_button = QPushButton("Open DEVONthink record")
        self._workflow_open_button.clicked.connect(self._open_workflow_record)
        self._workflow_open_button.setEnabled(False)
        for position, button in enumerate(
            (
                self._workflow_start_button,
                self._workflow_resume_button,
                self._workflow_confirm_button,
                self._workflow_open_button,
            )
        ):
            buttons.addWidget(button, position // 2, position % 2)
        buttons.setColumnStretch(0, 1)
        buttons.setColumnStretch(1, 1)
        controls_layout.addLayout(buttons)
        layout.addWidget(controls)

        progress_card, progress_layout = self._card()
        progress_layout.addWidget(QLabel("Workflow progress"))
        self._workflow_progress = WorkflowProgressView()
        self._workflow_progress.setMinimumHeight(300)
        progress_layout.addWidget(self._workflow_progress)
        layout.addWidget(progress_card)

        preview_card, preview_layout = self._card()
        preview_layout.addWidget(QLabel("Combined review preview"))
        self._workflow_preview_tabs = QTabWidget()
        self._workflow_preview_rendered = LocalMarkdownPreview()
        self._workflow_preview_rendered.setOpenExternalLinks(False)
        self._workflow_preview_rendered.setOpenLinks(False)
        self._workflow_preview_rendered.setPlaceholderText(
            "The formatted workflow output will appear here before any external write."
        )
        self._workflow_preview = QPlainTextEdit()
        self._workflow_preview.setReadOnly(True)
        self._workflow_preview.setPlaceholderText(
            "The unchanged workflow Markdown source will appear here before any external write."
        )
        self._workflow_preview_tabs.addTab(
            self._workflow_preview_rendered, "Rendered preview"
        )
        self._workflow_preview_tabs.addTab(self._workflow_preview, "Markdown source")
        preview_layout.addWidget(self._workflow_preview_tabs, 1)
        layout.addWidget(preview_card, 1)
        self._workflow_status = QLabel("Ready. No workflow has been started.")
        self._workflow_status.setObjectName("pageSub")
        layout.addWidget(self._workflow_status)
        self._workflow_selection_changed()
        return page

    def _build_settings_page(self) -> QWidget:
        page, layout = self._page_shell(
            "Settings",
            "Manage credentials, connection health, local API usage and privacy-safe diagnostics.",
            minimum_height=840,
        )
        self._add_workflow_guide(
            layout,
            "settings",
            ("API key", "Authorisations", "Health check", "Usage and logs"),
            "Check the API key and source authorisations",
        )
        tabs = QTabWidget()

        connections = QWidget()
        connections_layout = QVBoxLayout(connections)
        connections_layout.setContentsMargins(8, 12, 8, 8)
        connections_layout.setSpacing(12)
        setup_card, setup_layout = self._card()
        setup_layout.addWidget(QLabel("First-run setup"))
        setup_note = QLabel(
            "Check local dependencies, review fixed installation commands and continue to the "
            "required user-controlled authorisations."
        )
        setup_note.setObjectName("pageSub")
        setup_note.setWordWrap(True)
        setup_layout.addWidget(setup_note)
        self._setup_button = QPushButton("Open setup assistant")
        self._setup_button.setObjectName("primary")
        self._setup_button.clicked.connect(self._show_setup_assistant)
        setup_layout.addWidget(self._setup_button, 0, Qt.AlignmentFlag.AlignLeft)
        connections_layout.addWidget(setup_card)

        card, card_layout = self._card()
        card_layout.addWidget(QLabel("OpenAI API"))
        self._key_status = QLabel()
        card_layout.addWidget(self._key_status)
        save_button = QPushButton("Save API key in macOS Keychain")
        save_button.setObjectName("primary")
        save_button.clicked.connect(self._save_api_key)
        card_layout.addWidget(save_button, 0, Qt.AlignmentFlag.AlignLeft)
        note = QLabel(
            "The key is never displayed, stored in this repository or included in application logs."
        )
        note.setObjectName("pageSub")
        note.setWordWrap(True)
        card_layout.addWidget(note)

        card_layout.addSpacing(16)
        card_layout.addWidget(QLabel("PLAUD CLI"))
        self._plaud_status = QLabel()
        card_layout.addWidget(self._plaud_status)
        self._plaud_login_button = QPushButton("Sign in to PLAUD")
        self._plaud_login_button.clicked.connect(self._sign_in_plaud)
        card_layout.addWidget(self._plaud_login_button, 0, Qt.AlignmentFlag.AlignLeft)
        plaud_note = QLabel(
            "PLAUD authentication is managed by the official local CLI and is not stored in this "
            "repository or in the application settings."
        )
        plaud_note.setObjectName("pageSub")
        plaud_note.setWordWrap(True)
        card_layout.addWidget(plaud_note)
        connections_layout.addWidget(card)

        health_card, health_layout = self._card()
        health_layout.addWidget(QLabel("System health"))
        health_note = QLabel(
            "Checks connection and advertised capabilities without reading application content or "
            "running an OpenAI inference. Until every required check reports OK, this full check "
            "runs again automatically at each application start."
        )
        health_note.setObjectName("pageSub")
        health_note.setWordWrap(True)
        health_layout.addWidget(health_note)
        self._health_button = QPushButton("Run health check")
        self._health_button.setObjectName("primary")
        self._health_button.clicked.connect(self._run_health_check)
        health_layout.addWidget(self._health_button, 0, Qt.AlignmentFlag.AlignLeft)
        self._health_table = QTableWidget(0, 3)
        self._health_table.setHorizontalHeaderLabels(["Component", "Status", "Detail"])
        self._health_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._health_table.verticalHeader().setVisible(False)
        self._health_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._health_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._health_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        health_layout.addWidget(self._health_table)
        self._health_status = QLabel("Health check not yet run.")
        self._health_status.setObjectName("pageSub")
        health_layout.addWidget(self._health_status)
        connections_layout.addWidget(health_card, 1)
        tabs.addTab(connections, "Connections")

        usage = QWidget()
        usage_layout = QVBoxLayout(usage)
        usage_layout.setContentsMargins(8, 12, 8, 8)
        usage_card, usage_card_layout = self._card()
        usage_card_layout.addWidget(QLabel("OpenAI usage recorded by this installation"))
        usage_note = QLabel(
            "These counters include successful API calls made by this PEA installation from this "
            "version onwards. They are local operational metadata and may not equal organisation-wide usage."
        )
        usage_note.setObjectName("pageSub")
        usage_note.setWordWrap(True)
        usage_card_layout.addWidget(usage_note)
        usage_form = QFormLayout()
        self._usage_requests = QLabel()
        self._usage_input = QLabel()
        self._usage_output = QLabel()
        self._usage_total = QLabel()
        self._usage_last_model = QLabel()
        self._usage_last_updated = QLabel()
        usage_form.addRow("Successful API calls", self._usage_requests)
        usage_form.addRow("Input tokens", self._usage_input)
        usage_form.addRow("Output tokens", self._usage_output)
        usage_form.addRow("Total tokens", self._usage_total)
        usage_form.addRow("Last model", self._usage_last_model)
        usage_form.addRow("Last recorded", self._usage_last_updated)
        usage_card_layout.addLayout(usage_form)
        usage_buttons = QHBoxLayout()
        refresh_usage = QPushButton("Refresh local statistics")
        refresh_usage.clicked.connect(self._refresh_usage_statistics)
        dashboard_button = QPushButton("Open OpenAI usage dashboard")
        dashboard_button.clicked.connect(self._open_usage_dashboard)
        billing_button = QPushButton("Open billing and credit balance")
        billing_button.clicked.connect(self._open_billing_dashboard)
        usage_buttons.addWidget(refresh_usage)
        usage_buttons.addWidget(dashboard_button)
        usage_buttons.addWidget(billing_button)
        usage_buttons.addStretch()
        usage_card_layout.addLayout(usage_buttons)
        billing_note = QLabel(
            "Exact organisation spend and remaining prepaid credit require the OpenAI Usage/Billing "
            "dashboard and the appropriate organisation permission. The normal project API key is "
            "not elevated to an Admin key for this purpose."
        )
        billing_note.setObjectName("warning")
        billing_note.setWordWrap(True)
        usage_card_layout.addWidget(billing_note)
        usage_card_layout.addStretch()
        usage_layout.addWidget(usage_card, 1)
        tabs.addTab(usage, "API usage")

        logs = QWidget()
        logs_layout = QVBoxLayout(logs)
        logs_layout.setContentsMargins(8, 12, 8, 8)
        log_card, log_layout = self._card()
        log_layout.addWidget(QLabel("Runtime log"))
        log_note = QLabel(
            "The rotating local log records event names, status and error types only. It excludes "
            "keys, transcripts, generated minutes and Agenda or DEVONthink content."
        )
        log_note.setObjectName("pageSub")
        log_note.setWordWrap(True)
        log_layout.addWidget(log_note)
        log_buttons = QHBoxLayout()
        refresh_log = QPushButton("Refresh log")
        refresh_log.clicked.connect(self._refresh_runtime_log)
        open_log_folder = QPushButton("Open log folder")
        open_log_folder.clicked.connect(self._open_log_folder)
        log_buttons.addWidget(refresh_log)
        log_buttons.addWidget(open_log_folder)
        log_buttons.addStretch()
        log_layout.addLayout(log_buttons)
        self._runtime_log = QPlainTextEdit()
        self._runtime_log.setReadOnly(True)
        log_layout.addWidget(self._runtime_log, 1)
        logs_layout.addWidget(log_card, 1)
        tabs.addTab(logs, "Runtime log")

        layout.addWidget(tabs, 1)
        self._refresh_key_status()
        self._refresh_plaud_status()
        self._refresh_usage_statistics()
        self._refresh_runtime_log()
        return page

    @Slot(int)
    def _switch_page(self, index: int) -> None:
        self._pages.setCurrentIndex(index)
        self._guidance_stack.setCurrentIndex(index)
        self._scroll_current_page_to_top()
        if index == 4:
            self._refresh_weekly_source_status()
        if index == 5:
            self._workflow_selection_changed()
        if index == 6:
            self._refresh_key_status()
            self._refresh_plaud_status()
            self._refresh_usage_statistics()
            self._refresh_runtime_log()
        self._update_guidance_sources()
        QTimer.singleShot(0, self._sync_guidance_position)

    def _configure_guidance_targets(self) -> None:
        self._guidance_targets = {
            "minutes": (
                self._plaud_recordings,
                self._model_combo,
                self._generate_button,
                self._preview_tabs,
                self._devonthink_button,
            ),
            "agenda": (
                self._agenda_refresh_projects_button,
                self._agenda_projects,
                self._agenda_notes,
                self._agenda_note_text,
            ),
            "remarkable": (
                self._remarkdown_status_button,
                self._remarkdown_list_button,
                self._remarkdown_documents,
                self._remarkdown_text,
            ),
            "omnifocus": (
                self._omnifocus_overview_button,
                self._omnifocus_tasks_button,
                self._omnifocus_tasks,
                self._omnifocus_capture_review_button,
                self._omnifocus_capture_confirm_button,
            ),
            "weekly": (
                self._weekly_load_minutes_button,
                self._weekly_week,
                self._weekly_generate_button,
                self._weekly_preview_tabs,
                self._weekly_devonthink_button,
            ),
            "workflows": (
                self._workflow_choice,
                self._workflow_start_button,
                self._workflow_preview_tabs,
                self._workflow_confirm_button,
                self._workflow_open_button,
            ),
            "settings": (
                self._health_button,
                self._plaud_login_button,
                self._health_button,
                self._runtime_log,
            ),
        }

    def _sync_guidance_position(self, _value: int | None = None) -> None:
        keys = tuple(self._workflow_guides)
        index = self._pages.currentIndex()
        if not 0 <= index < len(keys):
            return
        key = keys[index]
        guide = self._workflow_guides[key]
        targets = self._guidance_targets.get(key, ())
        if targets:
            target_index = min(guide.current_step, len(targets) - 1)
            target_y = targets[target_index].mapTo(self, QPoint(0, 0)).y()
            guide.align_to(target_y)

    def _update_guidance_sources(self) -> None:
        keys = tuple(self._workflow_guides)
        index = self._pages.currentIndex()
        if not 0 <= index < len(keys):
            return
        key = keys[index]
        sources: list[str] = []
        if key == "minutes":
            if self._transcript.toPlainText().strip():
                sources.append("Raw PLAUD transcript or manual transcript")
            if self._plaud_summary_text:
                sources.append("PLAUD summary (secondary speaker context)")
            if self._contextual_memory.toPlainText().strip():
                sources.append("User-approved ChatGPT context import")
        elif key == "weekly":
            if self._weekly_minutes_sources:
                sources.append(f"{len(self._weekly_minutes_sources)} DEVONthink Minutes")
            if self._agenda_report_notes:
                sources.append(f"{len(self._agenda_report_notes)} selected Agenda notes")
            if self._weekly_updates.toPlainText().strip():
                sources.append("User-approved work chats")
            if self._weekly_emails.toPlainText().strip():
                sources.append("Manually uploaded emails")
            if self._contextual_memory.toPlainText().strip():
                sources.append("User-approved ChatGPT context import")
        elif key == "workflows":
            sources.append("Reviewed DEVONthink Minutes for selected period")
            if self._weekly_updates.toPlainText().strip():
                sources.append("User-approved work chats")
            if self._weekly_emails.toPlainText().strip():
                sources.append("Manually uploaded emails")
            if self._contextual_memory.toPlainText().strip():
                sources.append("User-approved ChatGPT context import")
        elif key == "agenda" and self._agenda_report_notes:
            sources.append(f"{len(self._agenda_report_notes)} selected Agenda notes")
        elif key == "remarkable" and self._last_remarkdown_document is not None:
            sources.append("Selected existing reMarkable text")
        self._workflow_guides[key].set_sources(sources)

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key.Key_Control, Qt.Key.Key_Meta} and not event.isAutoRepeat():
            self._shortcut_hint_visible = True
            self._shortcut_hint.setVisible(True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() in {Qt.Key.Key_Control, Qt.Key.Key_Meta} and not event.isAutoRepeat():
            self._shortcut_hint_visible = False
            self._shortcut_hint.setVisible(False)
        super().keyReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_guidance_position)

    def _scroll_current_page_to_top(self) -> None:
        current_page = self._pages.currentWidget()
        if isinstance(current_page, QScrollArea):
            current_page.verticalScrollBar().setValue(0)

    def _focus_navigation_and_scroll_to_top(self) -> None:
        self._navigation.setFocus()
        self._scroll_current_page_to_top()

    @Slot()
    def _model_changed(self) -> None:
        profile = self._model_combo.currentData()
        if profile is not None:
            self._model_description.setText(profile.description)
            self._settings.setValue("default_model_profile", profile.key)

    @Slot()
    def _load_transcript(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Load transcript",
            "",
            "Text documents (*.txt *.md);;All files (*)",
        )
        if not selected:
            return
        path = Path(selected)
        if path.stat().st_size > 2_000_000:
            QMessageBox.warning(self, "File too large", "The pilot limit is 2 MB per transcript.")
            return
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            log_event("local_transcript_load_failed", error_type=type(exc).__name__)
            QMessageBox.critical(self, "Transcript not loaded", str(exc))
            return
        self._transcript.setPlainText(content)
        self._plaud_summary_text = ""
        self._plaud_summary.clear()
        self._source_reference.setText(path.name)
        self._meeting_date.clear()
        self._set_guide("minutes", 1, "Review the source reference, date and model")
        self._update_guidance_sources()

    @Slot()
    def _load_contextual_memory(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Load reviewed ChatGPT context",
            "",
            "Context documents (*.txt *.md);;All files (*)",
        )
        if not selected:
            return
        path = Path(selected)
        if path.suffix.casefold() not in {".txt", ".md"}:
            QMessageBox.warning(self, "Context not loaded", "Use a .txt or .md export.")
            return
        if path.stat().st_size > 1_000_000:
            QMessageBox.warning(self, "Context too large", "The context limit is 1 MB.")
            return
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            QMessageBox.critical(self, "Context not loaded", str(exc))
            return
        self._contextual_memory.setPlainText(content)
        self._status.setText(
            "User-approved contextual memory loaded. No API request was made."
        )
        self._update_guidance_sources()

    @Slot()
    def _save_api_key(self) -> None:
        api_key, accepted = QInputDialog.getText(
            self,
            "OpenAI API key",
            "The key will be stored in the macOS Keychain:",
            QLineEdit.EchoMode.Password,
        )
        if not accepted or not api_key:
            return
        try:
            store_openai_api_key(api_key)
        except (ValueError, APIKeyStorageError) as exc:
            log_event("openai_key_store_failed", error_type=type(exc).__name__)
            QMessageBox.critical(self, "API key not saved", str(exc))
            return
        log_event("openai_key_stored")
        self._settings.remove("health/startup_version")
        self._settings.sync()
        self._refresh_key_status()
        QMessageBox.information(self, "OpenAI API key", "The key was stored securely.")

    def _refresh_key_status(self) -> None:
        if has_openai_api_key():
            self._key_status.setText("API key available")
            self._key_status.setObjectName("statusOk")
            self._set_guide("settings", 1, "Check the source-system authorisations")
        else:
            self._key_status.setText("API key not configured")
            self._key_status.setObjectName("statusMissing")
            self._set_guide("settings", 0, "Save the OpenAI API key in macOS Keychain")
        self._key_status.style().unpolish(self._key_status)
        self._key_status.style().polish(self._key_status)

    def _refresh_plaud_status(self) -> None:
        client = PlaudCli()
        if not client.is_installed():
            self._plaud_status.setText("Official PLAUD CLI not installed")
            self._plaud_status.setObjectName("statusMissing")
            self._plaud_login_button.setEnabled(False)
        elif client.is_authenticated():
            self._plaud_status.setText("PLAUD CLI installed and signed in")
            self._plaud_status.setObjectName("statusOk")
            self._plaud_login_button.setEnabled(False)
        else:
            self._plaud_status.setText("PLAUD CLI installed; sign-in required")
            self._plaud_status.setObjectName("statusMissing")
            self._plaud_login_button.setEnabled(True)
        self._plaud_status.style().unpolish(self._plaud_status)
        self._plaud_status.style().polish(self._plaud_status)

    @Slot()
    def _run_health_check(self) -> None:
        if self._health_thread is not None:
            return
        log_event("health_check_started")
        self._health_button.setEnabled(False)
        self._health_status.setText("Checking local integrations and authorisation …")
        self._health_thread = QThread(self)
        self._health_worker = HealthWorker()
        self._health_worker.moveToThread(self._health_thread)
        self._health_thread.started.connect(self._health_worker.run)
        self._health_worker.completed.connect(self._health_completed)
        self._health_worker.failed.connect(self._health_failed)
        self._health_worker.finished.connect(self._health_thread.quit)
        self._health_worker.finished.connect(self._health_worker.deleteLater)
        self._health_thread.finished.connect(self._health_thread.deleteLater)
        self._health_thread.finished.connect(self._health_finished)
        self._health_thread.start()

    @Slot(object)
    def _health_completed(self, result: object) -> None:
        if not isinstance(result, list) or not all(
            isinstance(item, HealthResult) for item in result
        ):
            self._health_failed("The health check returned invalid results.")
            return
        self._health_table.setRowCount(len(result))
        colours = {
            "OK": QColor("#1f7a45"),
            "Attention": QColor("#9a6b00"),
            "Unavailable": QColor("#a13b2b"),
        }
        for row, health in enumerate(result):
            component = QTableWidgetItem(health.component)
            status = QTableWidgetItem(health.status)
            detail = QTableWidgetItem(health.detail)
            font = status.font()
            font.setBold(True)
            status.setFont(font)
            status.setForeground(colours.get(health.status, QColor("#17212b")))
            self._health_table.setItem(row, 0, component)
            self._health_table.setItem(row, 1, status)
            self._health_table.setItem(row, 2, detail)
        ok_count = sum(item.status == "OK" for item in result)
        attention_count = sum(item.status == "Attention" for item in result)
        unavailable_count = sum(item.status == "Unavailable" for item in result)
        complete = health_check_is_complete(result)
        if complete:
            self._settings.setValue("health/startup_version", STARTUP_HEALTH_VERSION)
        else:
            self._settings.remove("health/startup_version")
        self._settings.sync()
        self._health_status.setText(
            f"Health check complete: {ok_count} OK, {attention_count} attention, "
            f"{unavailable_count} unavailable."
        )
        self._set_guide("settings", 3, "Review usage statistics and privacy-safe logs")
        log_event(
            "health_check_completed",
            ok=ok_count,
            attention=attention_count,
            unavailable=unavailable_count,
        )
        self._refresh_runtime_log()
        if self._health_check_is_startup and not complete and not self._close_after_health:
            unresolved = ", ".join(
                f"{item.component} ({item.status})"
                for item in result
                if item.status != "OK"
            )
            self._navigation.setCurrentRow(6)
            QMessageBox.warning(
                self,
                "System setup is not complete",
                "PEA still requires attention on this Mac:\n\n"
                f"{unresolved}\n\n"
                "The full System health check will run again at every application start until "
                "all required components report OK. Review the details in Settings → Connections.",
            )

    @Slot(str)
    def _health_failed(self, message: str) -> None:
        self._settings.remove("health/startup_version")
        self._settings.sync()
        self._health_status.setText(message)
        if self._health_check_is_startup and not self._close_after_health:
            self._navigation.setCurrentRow(6)
            QMessageBox.warning(
                self,
                "System health check incomplete",
                f"{message}\n\nThe check will run again at the next application start.",
            )

    @Slot()
    def _health_finished(self) -> None:
        self._health_thread = None
        self._health_worker = None
        self._health_button.setEnabled(True)
        self._startup_health_pending = False
        self._health_check_is_startup = False
        if self._close_after_health:
            self._close_after_health = False
            QTimer.singleShot(0, self.close)

    @Slot()
    def _refresh_usage_statistics(self) -> None:
        snapshot = self._usage_tracker.snapshot()
        self._usage_requests.setText(f"{snapshot.requests:,}")
        self._usage_input.setText(f"{snapshot.input_tokens:,}")
        self._usage_output.setText(f"{snapshot.output_tokens:,}")
        self._usage_total.setText(f"{snapshot.total_tokens:,}")
        self._usage_last_model.setText(snapshot.last_model)
        self._usage_last_updated.setText(snapshot.last_updated)

    @Slot()
    def _open_usage_dashboard(self) -> None:
        QDesktopServices.openUrl(QUrl(USAGE_DASHBOARD_URL))
        log_event("usage_dashboard_opened")

    @Slot()
    def _open_billing_dashboard(self) -> None:
        QDesktopServices.openUrl(QUrl(BILLING_URL))
        log_event("billing_dashboard_opened")

    @Slot()
    def _refresh_runtime_log(self) -> None:
        self._runtime_log.setPlainText(read_log_tail())
        scrollbar = self._runtime_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def _open_log_folder(self) -> None:
        LOG_DIRECTORY.mkdir(parents=True, exist_ok=True, mode=0o700)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIRECTORY)))
        log_event("log_folder_opened")

    @Slot()
    def _sign_in_plaud(self) -> None:
        answer = QMessageBox.question(
            self,
            "Confirm PLAUD sign-in",
            "Continue to PLAUD in your browser? This creates persistent local OAuth access for "
            "the official PLAUD CLI on this Mac.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            log_event("plaud_login_started")
            self._start_plaud_job("login")

    @Slot()
    def _refresh_plaud_recordings(self) -> None:
        self._start_plaud_job("list")

    @Slot()
    def _load_selected_plaud_transcript(self) -> None:
        recording = self._plaud_recordings.currentData()
        if not isinstance(recording, PlaudRecording):
            QMessageBox.warning(self, "PLAUD recording required", "Select a recording first.")
            return
        self._start_plaud_job("transcript", recording)

    def _start_plaud_job(
        self,
        operation: str,
        recording: PlaudRecording | None = None,
    ) -> None:
        log_event("plaud_operation_started", operation=operation)
        self._set_plaud_controls_enabled(False)
        if operation == "list":
            self._status.setText("Retrieving the latest PLAUD recording metadata …")
        elif operation == "transcript":
            self._status.setText("Retrieving the selected raw PLAUD transcript …")
        else:
            self._status.setText("Waiting for PLAUD sign-in in the browser …")
        thread = PlaudJobThread(operation, recording, self)
        self._plaud_thread = thread
        thread.completed.connect(self._plaud_completed)
        thread.failed.connect(self._plaud_failed)
        thread.finished.connect(self._plaud_finished)
        thread.start()

    @Slot(str, object)
    def _plaud_completed(self, operation: str, result: object) -> None:
        if operation == "list":
            recordings = result
            if not isinstance(recordings, list):
                self._plaud_failed("PLAUD returned an invalid recordings list.")
                return
            self._plaud_recordings.clear()
            for recording in recordings:
                if isinstance(recording, PlaudRecording):
                    label = f"{recording.date} · {recording.name} · {recording.duration}"
                    self._plaud_recordings.addItem(label, recording)
            self._plaud_load_button.setEnabled(self._plaud_recordings.count() > 0)
            self._status.setText(
                f"Loaded {self._plaud_recordings.count()} recent PLAUD recording(s)."
            )
            self._set_guide("minutes", 0, "Select a recording and load its raw transcript")
            log_event("plaud_recordings_loaded", count=self._plaud_recordings.count())
        elif operation == "transcript" and isinstance(result, PlaudSourceBundle):
            transcript = result.transcript
            self._transcript.setPlainText(transcript.text)
            self._source_reference.setText(transcript.recording.source_reference)
            self._meeting_date.setText(transcript.recording.date)
            self._plaud_summary_text = result.summary.text if result.summary else ""
            self._plaud_summary.setPlainText(self._plaud_summary_text)
            self._status.setText(
                f"Loaded {transcript.source_kind} and "
                f"{'PLAUD speaker context' if result.summary else 'no derived summary'}: "
                f"{transcript.recording.name}. No API request was made."
            )
            self._set_guide("minutes", 1, "Review the source reference, date and model")
            log_event("plaud_transcript_loaded")
            self._update_guidance_sources()
        elif operation == "login":
            self._refresh_plaud_status()
            self._status.setText("PLAUD sign-in completed.")
            log_event("plaud_login_completed")
            QMessageBox.information(self, "PLAUD", "PLAUD sign-in completed successfully.")

    @Slot(str)
    def _plaud_failed(self, message: str) -> None:
        self._status.setText("PLAUD operation failed. No transcript was changed.")
        QMessageBox.critical(self, "PLAUD operation failed", message)

    @Slot()
    def _plaud_finished(self) -> None:
        thread = self.sender()
        if thread is self._plaud_thread:
            self._plaud_thread = None
        if isinstance(thread, QThread):
            QTimer.singleShot(0, thread.deleteLater)
        self._set_plaud_controls_enabled(True)

    def _set_plaud_controls_enabled(self, enabled: bool) -> None:
        self._plaud_refresh_button.setEnabled(enabled)
        self._plaud_load_button.setEnabled(enabled and self._plaud_recordings.count() > 0)
        if hasattr(self, "_plaud_login_button"):
            client = PlaudCli()
            self._plaud_login_button.setEnabled(
                enabled and client.is_installed() and not client.is_authenticated()
            )

    @Slot()
    def _refresh_agenda_projects(self) -> None:
        self._start_agenda_job("projects")

    @Slot()
    def _list_agenda_notes(self) -> None:
        project = self._agenda_projects.currentData()
        if not isinstance(project, AgendaProject):
            QMessageBox.warning(self, "Agenda project required", "Select a project first.")
            return
        self._start_agenda_job("notes", project=project)

    @Slot()
    def _list_recent_agenda_notes(self) -> None:
        projects = [
            project
            for index in range(self._agenda_projects.count())
            if isinstance(
                project := self._agenda_projects.itemData(index),
                AgendaProject,
            )
        ]
        if not projects:
            QMessageBox.warning(
                self,
                "Agenda projects required",
                "Refresh the active Agenda projects first.",
            )
            return
        self._start_agenda_job("recent", projects=projects)

    @Slot()
    def _load_selected_agenda_note(self) -> None:
        note = self._agenda_notes.currentData()
        if not isinstance(note, AgendaNoteSummary):
            QMessageBox.warning(self, "Agenda note required", "Select a note first.")
            return
        self._start_agenda_job("note", note=note)

    @Slot()
    def _load_agenda_report_notes(self) -> None:
        notes = self._checked_agenda_note_summaries()
        if not notes:
            QMessageBox.warning(
                self,
                "Agenda report selection required",
                "Check at least one Agenda note first.",
            )
            return
        self._start_agenda_job("report_notes", notes=notes)

    @Slot(int)
    def _agenda_project_changed(self, _index: int) -> None:
        self._agenda_notes.clear()
        self._agenda_report_candidates.clear()
        self._agenda_note_summaries.clear()
        self._agenda_note_title.setText("No Agenda note loaded")
        self._agenda_note_text.clear()
        self._agenda_source_reference.clear()
        self._set_agenda_controls_enabled(self._agenda_thread is None)

    @Slot(int)
    def _agenda_note_changed(self, _index: int) -> None:
        self._set_agenda_controls_enabled(self._agenda_thread is None)

    @Slot(QListWidgetItem)
    def _agenda_report_selection_changed(self, _item: QListWidgetItem) -> None:
        if self._agenda_report_notes:
            self._agenda_report_notes = []
            self._agenda_note_title.setText("No Agenda note loaded")
            self._agenda_note_text.clear()
            self._agenda_source_reference.clear()
            self._weekly_use_agenda.setText("Current Agenda note")
            self._refresh_weekly_source_status()
        count = len(self._checked_agenda_note_summaries())
        if count:
            self._agenda_report_status.setText(
                f"{count} note{'s' if count != 1 else ''} checked; load the selection to make "
                "it available to Weekly Summary."
            )
        else:
            self._agenda_report_status.setText(
                "No Agenda notes selected for the weekly report."
            )
        self._set_agenda_controls_enabled(self._agenda_thread is None)

    def _checked_agenda_note_summaries(self) -> list[AgendaNoteSummary]:
        selected: list[AgendaNoteSummary] = []
        for index in range(self._agenda_report_candidates.count()):
            item = self._agenda_report_candidates.item(index)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            note_id = item.data(Qt.ItemDataRole.UserRole)
            summary = self._agenda_note_summaries.get(str(note_id))
            if summary is not None:
                selected.append(summary)
        return selected

    def _start_agenda_job(
        self,
        operation: str,
        project: AgendaProject | None = None,
        note: AgendaNoteSummary | None = None,
        projects: list[AgendaProject] | None = None,
        notes: list[AgendaNoteSummary] | None = None,
    ) -> None:
        log_event("agenda_read_started", operation=operation)
        self._set_agenda_controls_enabled(False)
        if operation == "projects":
            self._agenda_status.setText("Retrieving active Agenda project metadata …")
        elif operation == "notes":
            self._agenda_status.setText("Retrieving note metadata for the selected project …")
        elif operation == "recent":
            self._agenda_status.setText(
                "Retrieving note metadata edited during the last seven days …"
            )
        elif operation == "report_notes":
            self._agenda_status.setText(
                "Retrieving the checked Agenda notes for the weekly report …"
            )
        else:
            self._agenda_status.setText("Retrieving the selected Agenda note …")
        self._agenda_thread = QThread(self)
        self._agenda_worker = AgendaWorker(operation, project, note, projects, notes)
        self._agenda_worker.moveToThread(self._agenda_thread)
        self._agenda_thread.started.connect(self._agenda_worker.run)
        self._agenda_worker.completed.connect(self._agenda_completed)
        self._agenda_worker.failed.connect(self._agenda_failed)
        self._agenda_worker.finished.connect(self._agenda_thread.quit)
        self._agenda_worker.finished.connect(self._agenda_worker.deleteLater)
        self._agenda_thread.finished.connect(self._agenda_thread.deleteLater)
        self._agenda_thread.finished.connect(self._agenda_finished)
        self._agenda_thread.start()

    @Slot(str, object)
    def _agenda_completed(self, operation: str, result: object) -> None:
        if operation == "projects":
            projects = result
            if not isinstance(projects, list) or not all(
                isinstance(project, AgendaProject) for project in projects
            ):
                self._agenda_failed("Agenda returned an invalid project list.")
                return
            self._agenda_projects.clear()
            for project in projects:
                label = (
                    f"{project.category_title} · {project.title} "
                    f"({project.note_count} note{'s' if project.note_count != 1 else ''})"
                )
                self._agenda_projects.addItem(label, project)
            self._agenda_status.setText(
                f"Loaded {self._agenda_projects.count()} active Agenda project(s). No note text was read."
            )
            self._set_guide("agenda", 1, "Select a project and list its notes")
            log_event("agenda_projects_loaded", count=self._agenda_projects.count())
        elif operation in {"notes", "recent"}:
            notes = result
            if not isinstance(notes, list) or not all(
                isinstance(note, AgendaNoteSummary) for note in notes
            ):
                self._agenda_failed("Agenda returned an invalid note list.")
                return
            self._populate_agenda_note_metadata(notes)
            scope = "the last seven days" if operation == "recent" else "the selected project"
            self._agenda_status.setText(
                f"Loaded {self._agenda_notes.count()} note reference(s) for {scope}."
            )
            self._set_guide(
                "agenda",
                2,
                "Load one highlighted note or check notes for the weekly report",
            )
            log_event("agenda_note_references_loaded", count=self._agenda_notes.count())
        elif operation == "note" and isinstance(result, AgendaNote):
            self._agenda_note_title.setText(f"{result.title} · {result.project_title}")
            self._agenda_note_text.setPlainText(result.markdown)
            self._agenda_source_reference.setText(result.source_reference)
            self._agenda_status.setText(
                "Loaded one selected Agenda note through the local read-only MCP path."
            )
            self._set_guide("agenda", 3, "Review the note or include it in Weekly Summary")
            log_event("agenda_note_loaded")
            self._refresh_weekly_source_status()
        elif operation == "report_notes":
            notes = result
            if not isinstance(notes, list) or not all(
                isinstance(note, AgendaNote) for note in notes
            ):
                self._agenda_failed("Agenda returned an invalid report-note selection.")
                return
            self._agenda_report_notes = notes
            count = len(notes)
            self._agenda_note_title.setText(
                f"Weekly report selection · {count} Agenda note{'s' if count != 1 else ''}"
            )
            self._agenda_note_text.setPlainText(
                "\n\n---\n\n".join(
                    f"# {note.title}\n\n{note.markdown}" for note in notes
                )
            )
            self._agenda_source_reference.setText(
                "; ".join(note.source_reference for note in notes)
            )
            self._agenda_report_status.setText(
                f"{count} Agenda note{'s' if count != 1 else ''} loaded for the weekly report."
            )
            self._weekly_use_agenda.setText(f"Selected Agenda notes ({count})")
            self._weekly_use_agenda.setChecked(True)
            self._refresh_weekly_source_status()
            self._set_guide("agenda", 3, "Review the selection in Weekly Summary")
            log_event("agenda_report_notes_loaded", count=count)

    def _populate_agenda_note_metadata(self, notes: list[AgendaNoteSummary]) -> None:
        self._agenda_notes.clear()
        self._agenda_report_candidates.clear()
        self._agenda_note_summaries = {note.note_id: note for note in notes}
        for note in notes:
            date = (note.start_date or note.edited_date)[:10] or "Undated"
            status = " · On the Agenda" if note.on_the_agenda else ""
            self._agenda_notes.addItem(f"{date} · {note.title}{status}", note)
            candidate = QListWidgetItem(
                f"{date} · {note.project_title} · {note.title}{status}"
            )
            candidate.setData(Qt.ItemDataRole.UserRole, note.note_id)
            candidate.setFlags(candidate.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            candidate.setCheckState(Qt.CheckState.Unchecked)
            self._agenda_report_candidates.addItem(candidate)
        if self._agenda_notes.count() > 0:
            self._agenda_notes.setCurrentIndex(0)

    @Slot(str)
    def _agenda_failed(self, message: str) -> None:
        self._agenda_status.setText("Agenda read failed. No external data was changed.")
        QMessageBox.critical(self, "Agenda read failed", message)

    @Slot()
    def _agenda_finished(self) -> None:
        self._agenda_thread = None
        self._agenda_worker = None
        self._set_agenda_controls_enabled(True)

    def _set_agenda_controls_enabled(self, enabled: bool) -> None:
        self._agenda_refresh_projects_button.setEnabled(enabled)
        self._agenda_recent_notes_button.setEnabled(
            enabled and self._agenda_projects.count() > 0
        )
        self._agenda_list_notes_button.setEnabled(
            enabled and isinstance(self._agenda_projects.currentData(), AgendaProject)
        )
        self._agenda_load_note_button.setEnabled(
            enabled and isinstance(self._agenda_notes.currentData(), AgendaNoteSummary)
        )
        self._agenda_load_report_notes_button.setEnabled(
            enabled and bool(self._checked_agenda_note_summaries())
        )

    @Slot()
    def _refresh_omnifocus_overview(self) -> None:
        self._start_omnifocus_job("status")

    @Slot()
    def _load_omnifocus_tasks(self) -> None:
        view = self._omnifocus_view.currentData()
        limit = self._omnifocus_limit.currentData()
        if not isinstance(view, str) or not isinstance(limit, int):
            QMessageBox.warning(
                self,
                "OmniFocus view required",
                "Select a supported task view and limit.",
            )
            return
        self._start_omnifocus_job("tasks", view=view, limit=limit)

    def _start_omnifocus_job(
        self,
        operation: str,
        view: str = "available",
        limit: int = 50,
    ) -> None:
        if self._omnifocus_thread is not None:
            return
        self._set_omnifocus_controls_enabled(False)
        self._omnifocus_status.setText(
            "Retrieving aggregate OmniFocus status …"
            if operation == "status"
            else "Retrieving bounded task metadata from the selected OmniFocus view …"
        )
        log_event("omnifocus_read_started", operation=operation, view=view, limit=limit)
        self._omnifocus_thread = QThread(self)
        self._omnifocus_worker = OmniFocusWorker(operation, view, limit)
        self._omnifocus_worker.moveToThread(self._omnifocus_thread)
        self._omnifocus_thread.started.connect(self._omnifocus_worker.run)
        self._omnifocus_worker.completed.connect(self._omnifocus_completed)
        self._omnifocus_worker.failed.connect(self._omnifocus_failed)
        self._omnifocus_worker.finished.connect(self._omnifocus_thread.quit)
        self._omnifocus_worker.finished.connect(self._omnifocus_worker.deleteLater)
        self._omnifocus_thread.finished.connect(self._omnifocus_thread.deleteLater)
        self._omnifocus_thread.finished.connect(self._omnifocus_finished)
        self._omnifocus_thread.start()

    @Slot(str, object)
    def _omnifocus_completed(self, operation: str, result: object) -> None:
        if operation == "status" and isinstance(result, OmniFocusStatus):
            self._omnifocus_overview.setText(
                f"{result.application} {result.version} · Inbox {result.inbox} · "
                f"Available/Next {result.available_or_next} · Waiting {result.waiting} · "
                f"Flagged {result.flagged} · Open {result.open_tasks} · "
                f"Active projects {result.active_projects}"
            )
            self._omnifocus_status.setText(
                "Aggregate OmniFocus status loaded. No task title was read."
            )
            self._set_guide("omnifocus", 1, "Load a task view or prepare an Inbox capture")
            log_event("omnifocus_status_loaded")
            return
        if operation == "tasks" and isinstance(result, list) and all(
            isinstance(task, OmniFocusTask) for task in result
        ):
            self._omnifocus_tasks.setRowCount(len(result))
            for row, task in enumerate(result):
                values = (
                    task.name,
                    task.project,
                    task.status,
                    task.due[:10] if task.due else "—",
                    task.defer[:10] if task.defer else "—",
                    "Yes" if task.flagged else "No",
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, task.task_id)
                    self._omnifocus_tasks.setItem(row, column, item)
            self._omnifocus_status.setText(
                f"Loaded {len(result)} task record(s). Notes, attachments and tags were discarded."
            )
            self._set_guide("omnifocus", 2, "Review tasks or double-click one to open it")
            log_event("omnifocus_tasks_loaded", count=len(result))
            return
        self._omnifocus_failed("OmniFocus returned an invalid controlled result.")

    @Slot(QTableWidgetItem)
    def _open_omnifocus_task(self, item: QTableWidgetItem) -> None:
        task_id = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(task_id, str) or not task_id.strip():
            QMessageBox.warning(
                self,
                "OmniFocus task unavailable",
                "This row has no valid OmniFocus task reference. Reload the task metadata.",
            )
            return
        if not QDesktopServices.openUrl(QUrl(task_deep_link(task_id))):
            QMessageBox.warning(
                self,
                "Could not open OmniFocus task",
                "OmniFocus did not accept the selected task link.",
            )
            return
        self._omnifocus_status.setText("Opened the selected task in OmniFocus.")
        log_event("omnifocus_task_opened")

    @Slot(str)
    def _omnifocus_failed(self, message: str) -> None:
        self._omnifocus_status.setText("OmniFocus read failed. No data was changed.")
        QMessageBox.critical(self, "OmniFocus read failed", message)

    @Slot()
    def _omnifocus_finished(self) -> None:
        self._omnifocus_thread = None
        self._omnifocus_worker = None
        self._set_omnifocus_controls_enabled(True)

    def _set_omnifocus_controls_enabled(self, enabled: bool) -> None:
        self._omnifocus_overview_button.setEnabled(enabled)
        self._omnifocus_tasks_button.setEnabled(enabled)
        self._omnifocus_view.setEnabled(enabled)
        self._omnifocus_limit.setEnabled(enabled)

    def _refresh_minutes_action_capture_options(self) -> None:
        self._omnifocus_minutes_action.clear()
        for capture in self._minutes_action_captures:
            due = capture.due_date if capture.due_date != "Not stated" else "no due date"
            self._omnifocus_minutes_action.addItem(
                f"{capture.action} — {capture.owner} — {due}",
                capture,
            )
        available = bool(self._minutes_action_captures)
        self._omnifocus_use_minutes_action_button.setEnabled(available)
        self._minutes_omnifocus_button.setEnabled(available)
        self._omnifocus_minutes_action_changed(
            self._omnifocus_minutes_action.currentIndex()
        )

    @Slot(int)
    def _omnifocus_minutes_action_changed(self, _index: int) -> None:
        capture = self._omnifocus_minutes_action.currentData()
        if isinstance(capture, MinutesActionCapture):
            self._omnifocus_minutes_action_detail.setText(
                f"Owner: {capture.owner} · Due: {capture.due_date}. "
                "Review these fields before deciding whether this belongs in your Inbox."
            )
            self._omnifocus_use_minutes_action_button.setEnabled(True)
        else:
            self._omnifocus_minutes_action_detail.setText(
                "Owner and due date will be shown here; no assignment is made automatically."
            )
            self._omnifocus_use_minutes_action_button.setEnabled(False)

    @Slot()
    def _use_selected_minutes_action(self) -> None:
        capture = self._omnifocus_minutes_action.currentData()
        if not isinstance(capture, MinutesActionCapture):
            return
        self._omnifocus_capture_title.setText(capture.proposal.title)
        self._omnifocus_capture_source.setText(capture.proposal.source_reference)
        self._omnifocus_capture_status.setText(
            "Minutes action copied into the proposal. Review owner, due date and task wording, "
            "then run the duplicate check."
        )
        self._omnifocus_capture_title.setFocus()

    @Slot()
    def _open_minutes_actions_in_omnifocus(self) -> None:
        if not self._minutes_action_captures:
            return
        self._navigation.setCurrentRow(3)
        self._omnifocus_minutes_action.setFocus()

    @Slot()
    def _omnifocus_capture_changed(self) -> None:
        if self._omnifocus_capture_thread is not None:
            return
        self._omnifocus_capture_review = None
        self._omnifocus_capture_receipt = None
        self._omnifocus_capture_confirm_button.setEnabled(False)
        self._omnifocus_capture_open_button.setEnabled(False)
        self._omnifocus_capture_status.setText(
            "Capture changed. Run the duplicate review before any write."
        )

    @Slot()
    def _review_omnifocus_capture(self) -> None:
        try:
            proposal = prepare_capture(
                self._omnifocus_capture_title.text(),
                self._omnifocus_capture_source.text(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Inbox capture incomplete", str(exc))
            return
        self._omnifocus_capture_review = None
        self._omnifocus_capture_receipt = None
        self._omnifocus_capture_open_button.setEnabled(False)
        self._start_omnifocus_capture_job("review", proposal=proposal)

    @Slot()
    def _confirm_omnifocus_capture(self) -> None:
        review = self._omnifocus_capture_review
        if review is None or not review.is_clear:
            return
        self._start_omnifocus_capture_job("create", review=review)

    def _start_omnifocus_capture_job(
        self,
        operation: str,
        proposal: CaptureProposal | None = None,
        review: CaptureReview | None = None,
    ) -> None:
        if self._omnifocus_capture_thread is not None:
            return
        self._set_omnifocus_capture_controls_enabled(False)
        self._omnifocus_capture_status.setText(
            "Checking the OmniFocus Inbox and remaining tasks for duplicates …"
            if operation == "review"
            else "Creating the confirmed Inbox task and independently verifying it …"
        )
        log_event("omnifocus_capture_started", operation=operation)
        self._omnifocus_capture_thread = QThread(self)
        self._omnifocus_capture_worker = OmniFocusCaptureWorker(
            operation,
            proposal=proposal,
            review=review,
        )
        self._omnifocus_capture_worker.moveToThread(self._omnifocus_capture_thread)
        self._omnifocus_capture_thread.started.connect(self._omnifocus_capture_worker.run)
        self._omnifocus_capture_worker.completed.connect(self._omnifocus_capture_completed)
        self._omnifocus_capture_worker.failed.connect(self._omnifocus_capture_failed)
        self._omnifocus_capture_worker.finished.connect(
            self._omnifocus_capture_thread.quit
        )
        self._omnifocus_capture_worker.finished.connect(
            self._omnifocus_capture_worker.deleteLater
        )
        self._omnifocus_capture_thread.finished.connect(
            self._omnifocus_capture_thread.deleteLater
        )
        self._omnifocus_capture_thread.finished.connect(
            self._omnifocus_capture_finished
        )
        self._omnifocus_capture_thread.start()

    @Slot(str, object)
    def _omnifocus_capture_completed(self, operation: str, result: object) -> None:
        if operation == "review" and isinstance(result, CaptureReview):
            self._omnifocus_capture_review = result
            if result.is_clear:
                self._omnifocus_capture_status.setText(
                    "Duplicate review clear. Check the title and source reference, then use the "
                    "single final confirmation button."
                )
                self._omnifocus_capture_confirm_button.setEnabled(True)
                self._set_guide("omnifocus", 3, "Confirm the reviewed Inbox capture")
                log_event("omnifocus_capture_review_clear")
            else:
                self._omnifocus_capture_status.setText(
                    "Duplicate protection blocked this capture. No task was created."
                )
                log_event(
                    "omnifocus_capture_duplicate_blocked",
                    source_matches=result.source_matches,
                    title_matches=result.title_matches,
                )
                QMessageBox.warning(
                    self,
                    "OmniFocus duplicate found",
                    format_capture_duplicate(result),
                )
            return
        if operation == "create" and isinstance(result, CaptureReceipt):
            self._omnifocus_capture_receipt = result
            self._omnifocus_capture_confirm_button.setEnabled(False)
            self._omnifocus_capture_open_button.setEnabled(True)
            self._omnifocus_capture_status.setText(
                "OmniFocus Inbox capture completed and independently verified."
            )
            self._set_guide("omnifocus", 4, "Open the verified task in OmniFocus")
            log_event("omnifocus_capture_completed")
            message = QMessageBox(self)
            message.setWindowTitle("OmniFocus Inbox capture complete")
            message.setIcon(QMessageBox.Icon.Information)
            message.setTextFormat(Qt.TextFormat.RichText)
            message.setText(
                "The task was created in the OmniFocus Inbox and verified.<br><br>"
                f"<b>Task:</b> {escape(result.proposal.title)}<br>"
                f'<a href="{result.item_url}">Open task in OmniFocus</a>'
            )
            message.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            message.exec()
            return
        self._omnifocus_capture_failed("OmniFocus returned an invalid capture result.")

    @Slot(str)
    def _omnifocus_capture_failed(self, message: str) -> None:
        self._omnifocus_capture_status.setText(
            "OmniFocus capture failed or was blocked. No automatic retry was attempted."
        )
        QMessageBox.critical(self, "OmniFocus capture failed", message)

    @Slot()
    def _omnifocus_capture_finished(self) -> None:
        self._omnifocus_capture_thread = None
        self._omnifocus_capture_worker = None
        self._set_omnifocus_capture_controls_enabled(True)

    def _set_omnifocus_capture_controls_enabled(self, enabled: bool) -> None:
        self._omnifocus_capture_title.setEnabled(enabled)
        self._omnifocus_capture_source.setEnabled(enabled)
        self._omnifocus_capture_review_button.setEnabled(enabled)
        self._omnifocus_capture_confirm_button.setEnabled(
            enabled
            and self._omnifocus_capture_review is not None
            and self._omnifocus_capture_review.is_clear
            and self._omnifocus_capture_receipt is None
        )
        self._omnifocus_capture_open_button.setEnabled(
            enabled and self._omnifocus_capture_receipt is not None
        )

    @Slot()
    def _open_omnifocus_capture(self) -> None:
        if self._omnifocus_capture_receipt is not None:
            QDesktopServices.openUrl(QUrl(self._omnifocus_capture_receipt.item_url))

    def _refresh_remarkdown_local_status(self) -> None:
        service = RemarkdownService()
        if not service.is_installed():
            text = "remarkdown bridge not installed"
            authorised = False
        elif service.has_local_authorisation():
            text = "remarkdown bridge installed; local authorisation available"
            authorised = True
        else:
            text = "remarkdown bridge installed; sign-in required"
            authorised = False
        self._remarkdown_connection_status.setText(text)
        self._remarkdown_connection_status.setObjectName(
            "statusOk" if authorised else "statusMissing"
        )
        self._remarkdown_connection_status.style().unpolish(
            self._remarkdown_connection_status
        )
        self._remarkdown_connection_status.style().polish(
            self._remarkdown_connection_status
        )
        self._remarkdown_login_button.setEnabled(service.is_installed() and not authorised)
        self._remarkdown_status_button.setEnabled(authorised)
        self._remarkdown_list_button.setEnabled(authorised)

    @Slot()
    def _sign_in_remarkdown(self) -> None:
        answer = QMessageBox.question(
            self,
            "Confirm remarkdown sign-in",
            "Continue to remarkdown in your browser? This creates persistent local OAuth access "
            "in a private PEA application-data folder on this Mac. It is not stored in Git or "
            "included in application logs.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start_remarkdown_job("login")

    @Slot()
    def _refresh_remarkdown_identity(self) -> None:
        self._start_remarkdown_job("status")

    @Slot()
    def _list_remarkdown_documents(self) -> None:
        self._start_remarkdown_job("list")

    @Slot()
    def _load_selected_remarkdown_document(self) -> None:
        document = self._remarkdown_documents.currentData()
        if not isinstance(document, RemarkdownDocumentSummary):
            QMessageBox.warning(
                self, "reMarkable document required", "Select a document first."
            )
            return
        if not document.text_ready:
            QMessageBox.information(
                self,
                "Existing text unavailable",
                "The selected document has no existing typed or transcribed text. No paid "
                "transcription was started.",
            )
            return
        self._start_remarkdown_job("document", document)

    @Slot(int)
    def _remarkdown_document_changed(self, _index: int) -> None:
        document = self._remarkdown_documents.currentData()
        ready = isinstance(document, RemarkdownDocumentSummary) and document.text_ready
        self._remarkdown_load_button.setEnabled(ready and self._remarkdown_thread is None)
        self._last_remarkdown_document = None
        self._remarkdown_devonthink_button.setEnabled(False)
        self._remarkdown_text.clear()
        self._remarkdown_source_reference.clear()
        self._remarkdown_document_title.setText("No reMarkable document loaded")
        if isinstance(document, RemarkdownDocumentSummary):
            availability = (
                "Existing text is available."
                if document.text_ready
                else "Existing text is unavailable; no paid transcription will be started."
            )
            self._remarkdown_document_status.setText(
                f"Content status: {document.content_status}. {availability}"
            )

    def _start_remarkdown_job(
        self,
        operation: str,
        document: RemarkdownDocumentSummary | None = None,
    ) -> None:
        if self._remarkdown_thread is not None:
            return
        log_event("remarkdown_read_started", operation=operation)
        self._set_remarkdown_controls_enabled(False)
        messages = {
            "login": "Waiting for remarkdown sign-in in the browser …",
            "status": "Checking remarkdown connection and reading scope …",
            "list": "Retrieving metadata for recent reMarkable documents …",
            "document": "Retrieving existing text for the selected document …",
        }
        self._remarkdown_status.setText(messages[operation])
        self._remarkdown_thread = QThread(self)
        self._remarkdown_worker = RemarkdownWorker(operation, document)
        self._remarkdown_worker.moveToThread(self._remarkdown_thread)
        self._remarkdown_thread.started.connect(self._remarkdown_worker.run)
        self._remarkdown_worker.completed.connect(self._remarkdown_completed)
        self._remarkdown_worker.failed.connect(self._remarkdown_failed)
        self._remarkdown_worker.finished.connect(self._remarkdown_thread.quit)
        self._remarkdown_worker.finished.connect(self._remarkdown_worker.deleteLater)
        self._remarkdown_thread.finished.connect(self._remarkdown_thread.deleteLater)
        self._remarkdown_thread.finished.connect(self._remarkdown_finished)
        self._remarkdown_thread.start()
        if operation == "login":
            self._remarkdown_auth_timer.start()

    @Slot()
    def _recover_remarkdown_authorisation(self) -> None:
        if self._remarkdown_thread is None:
            self._remarkdown_auth_timer.stop()
            return
        if not RemarkdownService.has_local_authorisation():
            return
        self._remarkdown_auth_timer.stop()
        self._remarkdown_authorisation_recovered = True
        self._remarkdown_status.setText(
            "Browser authorisation received; reconnecting to remarkdown …"
        )
        terminate_authentication_bridges()
        log_event("remarkdown_browser_authorisation_received")

    @Slot(str, object)
    def _remarkdown_completed(self, operation: str, result: object) -> None:
        if operation in {"login", "status"} and isinstance(result, RemarkdownIdentity):
            self._remarkdown_auth_timer.stop()
            self._remarkdown_authorisation_recovered = False
            pairing = "paired" if result.paired else "not paired"
            credits = f"{result.credit_balance:,} credit(s)"
            if result.transcription_paused:
                credits += "; transcription paused"
            self._remarkdown_identity.setText(
                f"reMarkable: {pairing}. Reading folder: {result.folder}. Scope: {result.scope}. "
                f"Transcription window: {result.transcription_window}. Credits: {credits}. "
                f"Sync: {result.documents_synced:,}/{result.documents_total:,} documents."
            )
            self._refresh_remarkdown_local_status()
            self._remarkdown_status.setText("remarkdown connection status refreshed.")
            self._set_guide("remarkable", 1, "Refresh recent reMarkable documents")
            log_event("remarkdown_status_checked", paired=result.paired)
            if operation == "login":
                QMessageBox.information(
                    self, "remarkdown", "remarkdown sign-in completed successfully."
                )
        elif operation == "list" and isinstance(result, list) and all(
            isinstance(item, RemarkdownDocumentSummary) for item in result
        ):
            self._remarkdown_documents.clear()
            for document in result:
                date = document.modified[:10] or "Undated"
                self._remarkdown_documents.addItem(
                    f"{date} · {document.name} · {document.content_status}", document
                )
            self._remarkdown_status.setText(
                f"Loaded {len(result)} document reference(s) from the last 30 days. No document "
                "text was read."
            )
            self._set_guide("remarkable", 2, "Select a document and load its existing text")
            log_event("remarkdown_documents_loaded", count=len(result))
        elif operation == "document" and isinstance(result, RemarkdownDocument):
            self._last_remarkdown_document = result
            self._remarkdown_document_title.setText(
                f"{result.name} · {result.source_kind} · {result.page_count} page(s)"
            )
            self._remarkdown_text.setPlainText(result.markdown)
            self._remarkdown_source_reference.setText(result.source_reference)
            self._remarkdown_devonthink_button.setEnabled(
                self._devonthink_thread is None
            )
            self._remarkdown_status.setText(
                "Loaded existing text for one selected reMarkable document. No paid "
                "transcription or external write was started."
            )
            self._set_guide("remarkable", 3, "Review the text, then prepare the Inbox import")
            log_event("remarkdown_document_loaded", source_kind=result.content_kind)
        else:
            self._remarkdown_failed("remarkdown returned an invalid result.")

    @Slot(str)
    def _remarkdown_failed(self, message: str) -> None:
        if self._remarkdown_authorisation_recovered:
            return
        self._remarkdown_status.setText(
            "remarkdown read failed. No paid transcription or external write was attempted."
        )
        QMessageBox.critical(self, "remarkdown read failed", message)

    @Slot()
    def _remarkdown_finished(self) -> None:
        self._remarkdown_thread = None
        self._remarkdown_worker = None
        self._set_remarkdown_controls_enabled(True)
        if self._remarkdown_authorisation_recovered:
            self._remarkdown_authorisation_recovered = False
            QTimer.singleShot(0, self._refresh_remarkdown_identity)

    def _set_remarkdown_controls_enabled(self, enabled: bool) -> None:
        service = RemarkdownService()
        authorised = service.has_local_authorisation()
        self._remarkdown_login_button.setEnabled(
            enabled and service.is_installed() and not authorised
        )
        self._remarkdown_status_button.setEnabled(enabled and authorised)
        self._remarkdown_list_button.setEnabled(enabled and authorised)
        document = self._remarkdown_documents.currentData()
        self._remarkdown_load_button.setEnabled(
            enabled
            and isinstance(document, RemarkdownDocumentSummary)
            and document.text_ready
        )
        self._remarkdown_devonthink_button.setEnabled(
            enabled
            and self._last_remarkdown_document is not None
            and self._devonthink_thread is None
        )

    @Slot()
    def _workflow_selection_changed(self) -> None:
        workflow_key = self._workflow_choice.currentData()
        period_summary = workflow_key in {"daily_summary", "weekly_summary"}
        weekly = workflow_key == "weekly_summary"
        self._workflow_week.setEnabled(period_summary)
        self._workflow_period_label.setText("ISO week" if weekly else "Date")
        self._workflow_week.setPlaceholderText("YYYY-Www" if weekly else "YYYY-MM-DD")
        current_value = self._workflow_week.text().strip()
        if weekly and "-W" not in current_value:
            current_iso = datetime.now().astimezone().date().isocalendar()
            self._workflow_week.setText(f"{current_iso.year}-W{current_iso.week:02d}")
        elif workflow_key == "daily_summary" and "-W" in current_value:
            self._workflow_week.setText(datetime.now().astimezone().date().isoformat())
        checkpoint_key = None
        if isinstance(self._workflow_checkpoint, LatestPlaudCheckpoint):
            checkpoint_key = "latest_plaud_minutes"
        elif isinstance(self._workflow_checkpoint, WeeklyWorkflowCheckpoint):
            checkpoint_key = "weekly_summary"
        elif isinstance(self._workflow_checkpoint, DailyWorkflowCheckpoint):
            checkpoint_key = "daily_summary"
        if (
            self._workflow_thread is None
            and checkpoint_key is not None
            and checkpoint_key != workflow_key
        ):
            self._workflow_checkpoint = None
            self._workflow_ready = None
            self._workflow_receipt = None
            self._set_workflow_preview("")
            self._workflow_resume_button.setEnabled(False)
            self._workflow_confirm_button.setEnabled(False)
            self._workflow_open_button.setEnabled(False)
            self._workflow_status.setText("Ready. No workflow has been started.")
        profile = self._workflow_model.currentData()
        if isinstance(profile, ModelProfile):
            self._settings.setValue("default_model_profile", profile.key)
            source_detail = (
                "all reviewed DEVONthink Minutes filed in the selected period"
                if period_summary
                else "the raw transcript of the latest PLAUD recording"
            )
            self._workflow_cost.setText(
                f"This workflow uses {source_detail} and plans one {profile.cost_label.lower()}-"
                "cost OpenAI request. Exact token usage is shown after generation."
            )
        if self._workflow_thread is None and self._workflow_checkpoint is None:
            self._initialise_workflow_progress(workflow_key)

    @staticmethod
    def _workflow_steps(workflow_key: str) -> tuple[str, ...]:
        if workflow_key in {"daily_summary", "weekly_summary"}:
            return (
                "Load reviewed Minutes for period",
                "Generate period summary",
                "Prepare review preview",
                "Check DEVONthink duplicates",
                "Await final confirmation",
            )
        return (
            "Select latest PLAUD recording",
            "Load raw transcript",
            "Load PLAUD speaker context",
            "Generate minutes",
            "Prepare review preview",
            "Check DEVONthink duplicates",
            "Await final confirmation",
        )

    def _initialise_workflow_progress(self, workflow_key: str) -> None:
        self._workflow_progress.set_steps(self._workflow_steps(workflow_key))

    @Slot()
    def _start_selected_workflow(self) -> None:
        if self._workflow_thread is not None:
            return
        profile = self._workflow_model.currentData()
        if not isinstance(profile, ModelProfile):
            QMessageBox.warning(self, "Model required", "Select a model profile first.")
            return
        if profile.key == "quality":
            answer = QMessageBox.question(
                self,
                "Confirm higher-cost model",
                "Sol is the highest-cost profile. Continue with one API request?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        workflow_key = str(self._workflow_choice.currentData())
        try:
            if workflow_key == "weekly_summary":
                week_id = validate_week_id(self._workflow_week.text())
                checkpoint: (
                    LatestPlaudCheckpoint | DailyWorkflowCheckpoint | WeeklyWorkflowCheckpoint
                ) = (
                    WeeklyWorkflowCheckpoint(
                        week_id=week_id,
                        sources=self._manual_summary_sources(week_id),
                        profile=profile,
                        target_database=self._workflow_database.currentText(),
                        destination=self._workflow_destination.text(),
                    )
                )
            elif workflow_key == "daily_summary":
                from .openai_daily import validate_date_id

                date_id = validate_date_id(self._workflow_week.text())
                checkpoint = DailyWorkflowCheckpoint(
                    date_id=date_id,
                    sources=self._manual_summary_sources(date_id),
                    profile=profile,
                    target_database=self._workflow_database.currentText(),
                    destination=self._workflow_destination.text(),
                )
            else:
                checkpoint = LatestPlaudCheckpoint(
                    profile=profile,
                    target_database=self._workflow_database.currentText(),
                    destination=self._workflow_destination.text(),
                    contextual_memory=self._contextual_memory.toPlainText().strip(),
                )
        except ValueError as exc:
            QMessageBox.warning(self, "Workflow sources incomplete", str(exc))
            return

        self._workflow_checkpoint = checkpoint
        self._workflow_ready = None
        self._workflow_receipt = None
        self._workflow_usage_recorded = False
        self._set_workflow_preview("")
        self._workflow_confirm_button.setEnabled(False)
        self._workflow_open_button.setEnabled(False)
        self._workflow_resume_button.setEnabled(False)
        self._initialise_workflow_progress(workflow_key)
        self._start_workflow_runner()

    @Slot()
    def _resume_workflow(self) -> None:
        if self._workflow_thread is not None or self._workflow_checkpoint is None:
            return
        self._workflow_ready = None
        self._workflow_confirm_button.setEnabled(False)
        self._workflow_resume_button.setEnabled(False)
        self._start_workflow_runner()

    def _start_workflow_runner(self) -> None:
        checkpoint = self._workflow_checkpoint
        if checkpoint is None or self._workflow_thread is not None:
            return
        self._workflow_start_button.setEnabled(False)
        self._workflow_status.setText(
            "Workflow running. Completed steps will be retained if a later step fails."
        )
        log_event(
            "workflow_started",
            workflow=(
                "latest_plaud_minutes"
                if isinstance(checkpoint, LatestPlaudCheckpoint)
                else "daily_summary"
                if isinstance(checkpoint, DailyWorkflowCheckpoint)
                else "weekly_summary"
            ),
            model=checkpoint.profile.model,
        )
        self._set_guide("workflows", 1, "Wait for the workflow to reach its review point")
        self._workflow_thread = QThread(self)
        self._workflow_worker = WorkflowRunnerWorker(checkpoint)
        self._workflow_worker.moveToThread(self._workflow_thread)
        self._workflow_thread.started.connect(self._workflow_worker.run)
        self._workflow_worker.progress.connect(self._workflow_progress_changed)
        self._workflow_worker.completed.connect(self._workflow_completed)
        self._workflow_worker.failed.connect(self._workflow_failed)
        self._workflow_worker.finished.connect(self._workflow_thread.quit)
        self._workflow_worker.finished.connect(self._workflow_worker.deleteLater)
        self._workflow_thread.finished.connect(self._workflow_thread.deleteLater)
        self._workflow_thread.finished.connect(self._workflow_finished)
        self._workflow_thread.start()

    @Slot(int, str, str)
    def _workflow_progress_changed(self, step: int, status: str, detail: str) -> None:
        self._workflow_progress.update_step(step, status, detail)

    @Slot(object)
    def _workflow_completed(self, result: object) -> None:
        if not isinstance(result, WorkflowReady):
            self._workflow_failed("The workflow returned an invalid review result.")
            return
        self._workflow_ready = result
        self._set_workflow_preview(result.preview)
        if not self._workflow_usage_recorded:
            self._usage_tracker.record(result.model, result.input_tokens, result.output_tokens)
            self._workflow_usage_recorded = True
            self._refresh_usage_statistics()
        usage = ""
        if result.input_tokens is not None and result.output_tokens is not None:
            usage = (
                f" {result.input_tokens:,} input and {result.output_tokens:,} output tokens."
            )
        if result.can_write:
            self._workflow_status.setText(
                "Preview and duplicate check complete. Review the output, then use the single "
                f"final write confirmation.{usage}"
            )
            self._workflow_confirm_button.setEnabled(True)
            self._set_guide("workflows", 2, "Review the output, then confirm the DEVONthink write")
        else:
            self._workflow_status.setText(
                "Duplicate protection blocked the write. No DEVONthink record was created."
            )
            QMessageBox.warning(
                self,
                "DEVONthink duplicate found",
                format_duplicate_review_message(result.review),
            )
        log_event(
            "workflow_review_completed",
            workflow=result.workflow_key,
            duplicate_clear=result.can_write,
            model=result.model,
            input_tokens=result.input_tokens or 0,
            output_tokens=result.output_tokens or 0,
        )

    def _set_workflow_preview(self, markdown: str) -> None:
        self._workflow_preview.setPlainText(markdown)
        rendered_markdown = (
            markdown.replace("<br>", "\u2028")
            .replace("<br/>", "\u2028")
            .replace("<br />", "\u2028")
        )
        self._workflow_preview_rendered.setMarkdown(rendered_markdown)
        self._workflow_preview_tabs.setCurrentIndex(0)

    @Slot(str)
    def _workflow_failed(self, message: str) -> None:
        checkpoint = self._workflow_checkpoint
        failed_step = checkpoint.failed_step if checkpoint is not None else None
        if failed_step is not None:
            self._workflow_progress_changed(
                failed_step,
                "Failed",
                "This step failed; completed in-memory steps are retained for Resume.",
            )
        self._workflow_status.setText(
            "Workflow paused after an error. No DEVONthink write was attempted."
        )
        self._workflow_resume_button.setEnabled(checkpoint is not None)
        QMessageBox.critical(self, "Workflow paused", message)

    @Slot()
    def _workflow_finished(self) -> None:
        self._workflow_thread = None
        self._workflow_worker = None
        self._workflow_start_button.setEnabled(True)
        self._workflow_resume_button.setEnabled(
            self._workflow_checkpoint is not None and self._workflow_ready is None
        )

    @Slot()
    def _confirm_workflow_import(self) -> None:
        ready = self._workflow_ready
        if self._workflow_thread is not None or ready is None or not ready.can_write:
            return
        self._workflow_confirm_button.setEnabled(False)
        self._workflow_start_button.setEnabled(False)
        self._workflow_status.setText(
            "Writing the confirmed record to DEVONthink and verifying its content …"
        )
        self._set_guide("workflows", 3, "Wait for DEVONthink verification")
        log_event("workflow_import_confirmed", workflow=ready.workflow_key)
        self._workflow_thread = QThread(self)
        self._workflow_worker = WorkflowImportWorker(ready)
        self._workflow_worker.moveToThread(self._workflow_thread)
        self._workflow_thread.started.connect(self._workflow_worker.run)
        self._workflow_worker.completed.connect(self._workflow_import_completed)
        self._workflow_worker.failed.connect(self._workflow_import_failed)
        self._workflow_worker.finished.connect(self._workflow_thread.quit)
        self._workflow_worker.finished.connect(self._workflow_worker.deleteLater)
        self._workflow_thread.finished.connect(self._workflow_thread.deleteLater)
        self._workflow_thread.finished.connect(self._workflow_import_finished)
        self._workflow_thread.start()

    @Slot(object)
    def _workflow_import_completed(self, result: object) -> None:
        if not isinstance(result, ImportReceipt):
            self._workflow_import_failed("DEVONthink returned an invalid import receipt.")
            return
        self._workflow_receipt = result
        self._workflow_status.setText("DEVONthink import completed and verified.")
        self._workflow_open_button.setEnabled(True)
        self._set_guide("workflows", 4, "Open the verified DEVONthink record")
        log_event("workflow_import_completed")
        message = QMessageBox(self)
        message.setWindowTitle("DEVONthink import complete")
        message.setIcon(QMessageBox.Icon.Information)
        message.setTextFormat(Qt.TextFormat.RichText)
        message.setText(
            "The Markdown record was created and its content was verified.<br><br>"
            f"<b>Database:</b> {escape(result.database_name)}<br>"
            f"<b>Location:</b> {escape(result.location or 'Database inbox')}<br>"
            f'<a href="{result.item_url}">Open record in DEVONthink</a>'
        )
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        message.exec()

    @Slot(str)
    def _workflow_import_failed(self, message: str) -> None:
        self._workflow_status.setText(
            "DEVONthink import failed or was blocked during the final duplicate recheck."
        )
        QMessageBox.critical(self, "DEVONthink import failed", message)

    @Slot()
    def _workflow_import_finished(self) -> None:
        self._workflow_thread = None
        self._workflow_worker = None
        self._workflow_start_button.setEnabled(True)
        self._workflow_confirm_button.setEnabled(
            self._workflow_receipt is None
            and self._workflow_ready is not None
            and self._workflow_ready.can_write
        )

    @Slot()
    def _open_workflow_record(self) -> None:
        if self._workflow_receipt is not None:
            QDesktopServices.openUrl(QUrl(self._workflow_receipt.item_url))

    @Slot()
    def _weekly_period_changed(self) -> None:
        if self._weekly_week.text().strip() != self._weekly_minutes_week:
            self._weekly_minutes_sources = []
            self._weekly_minutes_week = ""
        self._refresh_weekly_source_status()

    @Slot()
    def _load_weekly_minutes(self) -> None:
        if self._minutes_archive_thread is not None:
            return
        try:
            week_id = validate_week_id(self._weekly_week.text())
            start, end = week_date_range(week_id)
        except ValueError as exc:
            QMessageBox.warning(self, "ISO week required", str(exc))
            return
        self._weekly_load_minutes_button.setEnabled(False)
        self._weekly_source_status.setText(
            f"Loading reviewed Minutes filed in {week_id} from DEVONthink …"
        )
        self._minutes_archive_thread = QThread(self)
        self._minutes_archive_worker = MinutesArchiveWorker(
            start, end, self._weekly_target_database.currentText()
        )
        self._minutes_archive_worker.moveToThread(self._minutes_archive_thread)
        self._minutes_archive_thread.started.connect(self._minutes_archive_worker.run)
        self._minutes_archive_worker.completed.connect(self._weekly_minutes_loaded)
        self._minutes_archive_worker.failed.connect(self._weekly_minutes_load_failed)
        self._minutes_archive_worker.finished.connect(self._minutes_archive_thread.quit)
        self._minutes_archive_worker.finished.connect(
            self._minutes_archive_worker.deleteLater
        )
        self._minutes_archive_thread.finished.connect(
            self._minutes_archive_thread.deleteLater
        )
        self._minutes_archive_thread.finished.connect(self._weekly_minutes_load_finished)
        self._minutes_archive_thread.start()

    @Slot(object)
    def _weekly_minutes_loaded(self, result: object) -> None:
        records = result if isinstance(result, list) else []
        if not all(isinstance(item, DevonThinkMinutesSource) for item in records):
            self._weekly_minutes_load_failed("DEVONthink returned invalid Minutes metadata.")
            return
        self._weekly_minutes_sources = minutes_to_weekly_sources(records)
        self._weekly_minutes_week = self._weekly_week.text().strip()
        self._weekly_use_minutes.setChecked(bool(records))
        self._refresh_weekly_source_status()
        self._weekly_status.setText(
            f"Loaded {len(records)} reviewed Minutes record(s) for "
            f"{self._weekly_minutes_week}. No data has been sent to OpenAI."
        )

    @Slot(str)
    def _weekly_minutes_load_failed(self, message: str) -> None:
        self._weekly_source_status.setText("The selected week’s Minutes could not be loaded.")
        QMessageBox.critical(self, "Minutes load failed", message)

    @Slot()
    def _weekly_minutes_load_finished(self) -> None:
        self._minutes_archive_thread = None
        self._minutes_archive_worker = None
        self._weekly_load_minutes_button.setEnabled(True)

    @Slot()
    def _refresh_weekly_source_status(self) -> None:
        agenda_selection_count = len(self._agenda_report_notes)
        self._weekly_use_agenda.setText(
            f"Selected Agenda notes ({agenda_selection_count})"
            if agenda_selection_count
            else "Current Agenda note"
        )
        availability = (
            (
                self._weekly_use_minutes,
                bool(
                    self._weekly_minutes_sources
                    and self._weekly_minutes_week == self._weekly_week.text().strip()
                ),
                "Minutes for selected week",
            ),
            (
                self._weekly_use_agenda,
                bool(
                    self._agenda_report_notes
                    or (
                        self._agenda_note_text.toPlainText().strip()
                        and self._agenda_source_reference.text().strip()
                    )
                ),
                "Agenda selection",
            ),
            (
                self._weekly_use_remarkdown,
                bool(
                    self._remarkdown_text.toPlainText().strip()
                    and self._remarkdown_source_reference.text().strip()
                ),
                "reMarkable note",
            ),
        )
        labels: list[str] = []
        for checkbox, available, label in availability:
            checkbox.setEnabled(available)
            if not available:
                checkbox.setChecked(False)
            labels.append(f"{label}: {'available' if available else 'not loaded'}")
        self._weekly_source_status.setText(" · ".join(labels))
        if any(available for _, available, _ in availability):
            self._set_guide("weekly", 1, "Confirm the ISO week and model profile")
        else:
            self._set_guide("weekly", 0, "Load and select the approved weekly sources")

    def _weekly_sources(self, week_id: str) -> list[WeeklySource]:
        sources: list[WeeklySource] = []
        if self._weekly_use_minutes.isChecked():
            sources.extend(self._weekly_minutes_sources)
        if self._weekly_use_agenda.isChecked():
            if self._agenda_report_notes:
                sources.extend(
                    WeeklySource(
                        note.title,
                        note.source_reference,
                        note.markdown,
                        "selected Agenda management note",
                    )
                    for note in self._agenda_report_notes
                )
            else:
                sources.append(
                    WeeklySource(
                        "Current Agenda note",
                        self._agenda_source_reference.text(),
                        self._agenda_note_text.toPlainText(),
                        "selected Agenda management note",
                    )
                )
        if self._weekly_use_remarkdown.isChecked():
            sources.append(
                WeeklySource(
                    "Current reMarkable note",
                    self._remarkdown_source_reference.text(),
                    self._remarkdown_text.toPlainText(),
                    "selected existing remarkdown text",
                )
            )
        updates = self._weekly_updates.toPlainText().strip()
        if updates:
            sources.append(
                WeeklySource(
                    "Additional approved updates",
                    f"manual:{week_id}",
                    updates,
                    "user-supplied weekly updates",
                )
            )
        emails = self._weekly_emails.toPlainText().strip()
        if emails:
            sources.append(
                WeeklySource(
                    "Manually uploaded work email",
                    f"manual-email:{week_id}",
                    emails,
                    "user-selected email export",
                )
            )
        contextual_memory = self._contextual_memory.toPlainText().strip()
        if contextual_memory:
            sources.append(
                WeeklySource(
                    "User-approved ChatGPT context",
                    f"manual-context:{week_id}",
                    contextual_memory,
                    "user-reviewed contextual memory export",
                )
            )
        return sources

    def _manual_summary_sources(self, period_id: str) -> list[WeeklySource]:
        sources: list[WeeklySource] = []
        chats = self._weekly_updates.toPlainText().strip()
        if chats:
            sources.append(
                WeeklySource(
                    "User-approved work-related chats",
                    f"manual-chat:{period_id}",
                    chats,
                    "user-selected work-related chat",
                )
            )
        emails = self._weekly_emails.toPlainText().strip()
        if emails:
            sources.append(
                WeeklySource(
                    "User-uploaded work email",
                    f"manual-email:{period_id}",
                    emails,
                    "user-selected email export",
                )
            )
        contextual_memory = self._contextual_memory.toPlainText().strip()
        if contextual_memory:
            sources.append(
                WeeklySource(
                    "User-approved ChatGPT context",
                    f"manual-context:{period_id}",
                    contextual_memory,
                    "user-reviewed contextual memory export",
                )
            )
        return sources

    @Slot()
    def _generate_weekly_summary(self) -> None:
        try:
            week_id = validate_week_id(self._weekly_week.text())
            sources = self._weekly_sources(week_id)
            if not sources:
                raise ValueError("Load, select or enter at least one weekly-summary source.")
        except ValueError as exc:
            QMessageBox.warning(self, "Weekly sources incomplete", str(exc))
            return
        profile = self._weekly_model_combo.currentData()
        if not isinstance(profile, ModelProfile):
            QMessageBox.warning(self, "Model required", "Select a model profile first.")
            return
        if profile.key == "quality":
            answer = QMessageBox.question(
                self,
                "Confirm higher-cost model",
                "Sol is the highest-cost profile. Continue with one API request?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._weekly_generate_button.setEnabled(False)
        self._weekly_regenerate_button.setEnabled(False)
        self._set_guide("weekly", 2, "Wait for the new summary, then review it")
        self._weekly_status.setText(
            f"Generating {week_id} with {profile.model} from {len(sources)} selected source(s) …"
        )
        log_event(
            "weekly_generation_started",
            model=profile.model,
            source_count=len(sources),
        )
        self._weekly_thread = QThread(self)
        self._weekly_worker = WeeklyGenerationWorker(week_id, sources, profile)
        self._weekly_worker.moveToThread(self._weekly_thread)
        self._weekly_thread.started.connect(self._weekly_worker.run)
        self._weekly_worker.completed.connect(self._weekly_generation_completed)
        self._weekly_worker.failed.connect(self._weekly_generation_failed)
        self._weekly_worker.finished.connect(self._weekly_thread.quit)
        self._weekly_worker.finished.connect(self._weekly_worker.deleteLater)
        self._weekly_thread.finished.connect(self._weekly_thread.deleteLater)
        self._weekly_thread.finished.connect(self._weekly_generation_finished)
        self._weekly_thread.start()

    @Slot(object)
    def _weekly_generation_completed(self, result: object) -> None:
        if not isinstance(result, WeeklyGenerationResult):
            self._weekly_generation_failed("OpenAI returned an invalid weekly summary.")
            return
        self._last_weekly_result = result
        self._usage_tracker.record(result.model, result.input_tokens, result.output_tokens)
        self._refresh_usage_statistics()
        self._set_weekly_preview(result.summary.to_markdown())
        usage = ""
        if result.input_tokens is not None and result.output_tokens is not None:
            usage = (
                f" Input: {result.input_tokens:,} tokens; "
                f"output: {result.output_tokens:,} tokens."
            )
        self._weekly_status.setText(
            f"Weekly summary preview generated with {result.model}.{usage}"
        )
        self._weekly_regenerate_button.setEnabled(True)
        self._set_guide("weekly", 3, "Review the summary or select another model and regenerate")
        log_event(
            "weekly_generation_completed",
            model=result.model,
            input_tokens=result.input_tokens or 0,
            output_tokens=result.output_tokens or 0,
        )

    def _set_weekly_preview(self, markdown: str) -> None:
        self._weekly_preview.setPlainText(markdown)
        self._weekly_preview_rendered.setMarkdown(markdown)
        self._weekly_preview_tabs.setCurrentIndex(0)

    @Slot(str)
    def _weekly_generation_failed(self, message: str) -> None:
        self._weekly_status.setText("Weekly summary generation failed. No write was attempted.")
        QMessageBox.critical(self, "Weekly summary generation failed", message)

    @Slot()
    def _weekly_generation_finished(self) -> None:
        self._weekly_generate_button.setEnabled(True)
        self._weekly_regenerate_button.setEnabled(self._last_weekly_result is not None)
        self._weekly_thread = None
        self._weekly_worker = None

    @Slot()
    def _copy_weekly_preview(self) -> None:
        text = self._weekly_preview.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)
            self._weekly_status.setText("Weekly summary preview copied to the clipboard.")

    @Slot()
    def _prepare_remarkdown_devonthink_handoff(self) -> None:
        document = self._last_remarkdown_document
        if document is None:
            QMessageBox.warning(
                self,
                "reMarkable document required",
                "Load one reMarkable document with existing text before reviewing an import.",
            )
            return
        try:
            handoff = prepare_remarkable_handoff(
                document.name,
                document.markdown,
                document.source_reference,
            )
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "reMarkable handoff incomplete", str(exc))
            return
        self._start_devonthink_job("review", handoff, origin="remarkable")

    @Slot()
    def _prepare_weekly_devonthink_handoff(self) -> None:
        try:
            handoff = prepare_handoff(
                self._weekly_preview.toPlainText(),
                weekly_source_reference(self._weekly_week.text()),
                self._weekly_target_database.currentText(),
                self._weekly_destination.text(),
                record_kind="weekly-summary",
            )
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Weekly handoff incomplete", str(exc))
            return
        self._start_devonthink_job("review", handoff, origin="weekly")

    @Slot()
    def _generate_minutes(self) -> None:
        transcript = self._transcript.toPlainText().strip()
        if not transcript:
            QMessageBox.warning(self, "Transcript required", "Paste or load a transcript first.")
            return
        profile = self._model_combo.currentData()
        if profile.key == "quality":
            answer = QMessageBox.question(
                self,
                "Confirm higher-cost model",
                "Sol is the highest-cost profile. Continue with one API request?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._generate_button.setEnabled(False)
        self._regenerate_button.setEnabled(False)
        self._set_guide("minutes", 2, "Wait for the new Minutes draft, then review it")
        self._status.setText(f"Generating with {profile.model}; one API request is planned …")
        log_event("minutes_generation_started", model=profile.model)
        self._thread = QThread(self)
        self._worker = GenerationWorker(
            transcript,
            profile,
            self._meeting_date.text(),
            self._plaud_summary_text,
            self._contextual_memory.toPlainText(),
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.completed.connect(self._generation_completed)
        self._worker.failed.connect(self._generation_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._generation_finished)
        self._thread.start()

    @Slot(object)
    def _generation_completed(self, result: GenerationResult) -> None:
        self._last_result = result
        action_note = ""
        try:
            self._minutes_action_captures = prepare_minutes_action_captures(
                result.minutes.action_items,
                self._source_reference.text(),
            )
        except ValueError:
            self._minutes_action_captures = []
            if result.minutes.action_items:
                action_note = " Add a stable source reference to prepare OmniFocus captures."
        self._refresh_minutes_action_capture_options()
        self._usage_tracker.record(result.model, result.input_tokens, result.output_tokens)
        self._refresh_usage_statistics()
        self._set_minutes_preview(result.minutes.to_markdown(), result.minutes.to_html())
        usage = ""
        if result.input_tokens is not None and result.output_tokens is not None:
            usage = f" Input: {result.input_tokens:,} tokens; output: {result.output_tokens:,} tokens."
        self._status.setText(
            f"Preview generated with {result.model}.{usage}{action_note}"
        )
        self._regenerate_button.setEnabled(True)
        self._set_guide("minutes", 3, "Review the Minutes or select another model and regenerate")
        log_event(
            "minutes_generation_completed",
            model=result.model,
            input_tokens=result.input_tokens or 0,
            output_tokens=result.output_tokens or 0,
            action_count=len(self._minutes_action_captures),
        )

    def _set_minutes_preview(self, markdown: str, rendered_html: str | None = None) -> None:
        self._preview.setPlainText(markdown)
        if rendered_html is None:
            self._preview_rendered.setMarkdown(markdown)
        else:
            self._preview_rendered.setHtml(rendered_html)
        self._preview_tabs.setCurrentIndex(0)

    @Slot(str)
    def _generation_failed(self, message: str) -> None:
        if self._last_result is None:
            self._status.setText("Generation failed. No external write was attempted.")
            title = "Minutes generation failed"
        else:
            self._status.setText("Regeneration failed. The existing preview has been retained.")
            title = "Minutes were not regenerated"
        QMessageBox.critical(self, title, message)

    @Slot()
    def _generation_finished(self) -> None:
        self._generate_button.setEnabled(True)
        self._regenerate_button.setEnabled(self._last_result is not None)
        self._thread = None
        self._worker = None

    @Slot()
    def _copy_preview(self) -> None:
        text = self._preview.toPlainText()
        if text:
            QGuiApplication.clipboard().setText(text)
            self._status.setText("Preview copied to the clipboard.")

    @Slot()
    def _prepare_devonthink_handoff(self) -> None:
        try:
            handoff = prepare_handoff(
                self._preview.toPlainText(),
                self._source_reference.text(),
                self._target_database.currentText(),
                self._destination.text(),
            )
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Handoff incomplete", str(exc))
            return
        self._start_devonthink_job("review", handoff)

    def _start_devonthink_job(
        self,
        operation: str,
        handoff: DevonThinkHandoff,
        origin: str = "minutes",
    ) -> None:
        if self._devonthink_thread is not None:
            return
        self._devonthink_origin = origin
        log_event("devonthink_operation_started", operation=operation, origin=origin)
        self._devonthink_button_for(origin).setEnabled(False)
        if operation == "review":
            self._set_devonthink_status(
                origin, "Checking DEVONthink connection, target and duplicates …"
            )
        else:
            self._set_devonthink_status(
                origin, "Writing the confirmed record and verifying it …"
            )
        self._devonthink_thread = QThread(self)
        self._devonthink_worker = DevonThinkWorker(operation, handoff)
        self._devonthink_worker.moveToThread(self._devonthink_thread)
        self._devonthink_thread.started.connect(self._devonthink_worker.run)
        self._devonthink_worker.completed.connect(self._devonthink_completed)
        self._devonthink_worker.failed.connect(self._devonthink_failed)
        self._devonthink_worker.finished.connect(self._devonthink_thread.quit)
        self._devonthink_worker.finished.connect(self._devonthink_worker.deleteLater)
        self._devonthink_thread.finished.connect(self._devonthink_thread.deleteLater)
        self._devonthink_thread.finished.connect(self._devonthink_finished)
        self._devonthink_thread.start()

    @Slot(str, object)
    def _devonthink_completed(self, operation: str, result: object) -> None:
        if operation == "review":
            review = result
            if not isinstance(review, ImportReview):
                self._devonthink_failed("DEVONthink returned an invalid review result.")
                return
            if not review.is_clear:
                self._set_devonthink_status(
                    self._devonthink_origin,
                    "Import blocked by duplicate protection. No record was written.",
                )
                log_event(
                    "devonthink_duplicate_blocked",
                    source_matches=len(review.source_matches),
                    title_matches=len(review.title_matches),
                )
                QMessageBox.warning(
                    self,
                    "DEVONthink duplicate found",
                    format_duplicate_review_message(review),
                )
                return

            handoff = review.handoff
            guide_key = {
                "minutes": "minutes",
                "weekly": "weekly",
                "remarkable": "remarkable",
            }.get(self._devonthink_origin)
            if guide_key is not None:
                self._set_guide(
                    guide_key,
                    4,
                    "Confirm the duplicate-clear DEVONthink write",
                )
            answer = QMessageBox.question(
                self,
                "Confirm DEVONthink import",
                "The duplicate check is clear. Create this Markdown record?\n\n"
                f"Title: {handoff.title}\n"
                f"Target: {review.target_description}\n"
                f"Source: {handoff.source_reference}\n"
                f"Fingerprint: {handoff.content_fingerprint[:16]}…",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._pending_import = handoff
                self._pending_import_origin = self._devonthink_origin
                log_event("devonthink_import_confirmed")
                QTimer.singleShot(0, self._continue_pending_devonthink_import)
            else:
                self._set_devonthink_status(
                    self._devonthink_origin,
                    "DEVONthink import cancelled. No record was written.",
                )
                log_event("devonthink_import_cancelled")
            return

        receipt = result
        if not isinstance(receipt, ImportReceipt):
            self._devonthink_failed("DEVONthink returned an invalid import receipt.")
            return
        self._set_devonthink_status(
            self._devonthink_origin, "DEVONthink import completed and verified."
        )
        guide_key = {
            "minutes": "minutes",
            "weekly": "weekly",
            "remarkable": "remarkable",
        }.get(self._devonthink_origin)
        if guide_key is not None:
            self._set_guide(guide_key, 5, "The verified record is ready to open")
        log_event("devonthink_import_completed")
        message = QMessageBox(self)
        message.setWindowTitle("DEVONthink import complete")
        message.setIcon(QMessageBox.Icon.Information)
        message.setTextFormat(Qt.TextFormat.RichText)
        message.setText(
            "The Markdown record was created and its content was verified.<br><br>"
            f"<b>Database:</b> {escape(receipt.database_name)}<br>"
            f"<b>Location:</b> {escape(receipt.location or 'Database inbox')}<br>"
            f'<a href="{receipt.item_url}">Open record in DEVONthink</a>'
        )
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        message.exec()

    @Slot(str)
    def _devonthink_failed(self, message: str) -> None:
        self._pending_import = None
        self._set_devonthink_status(
            self._devonthink_origin,
            "DEVONthink operation failed. No retry was attempted.",
        )
        QMessageBox.critical(self, "DEVONthink operation failed", message)

    @Slot()
    def _devonthink_finished(self) -> None:
        self._devonthink_thread = None
        self._devonthink_worker = None
        self._devonthink_button_for(self._devonthink_origin).setEnabled(True)
        self._continue_pending_devonthink_import()

    @Slot()
    def _continue_pending_devonthink_import(self) -> None:
        if self._pending_import is None or self._devonthink_thread is not None:
            return
        handoff = self._pending_import
        origin = self._pending_import_origin
        self._pending_import = None
        self._start_devonthink_job("import", handoff, origin=origin)

    def _devonthink_button_for(self, origin: str) -> QPushButton:
        if origin == "weekly":
            return self._weekly_devonthink_button
        if origin == "remarkable":
            return self._remarkdown_devonthink_button
        return self._devonthink_button

    def _set_devonthink_status(self, origin: str, message: str) -> None:
        if origin == "weekly":
            self._weekly_status.setText(message)
        elif origin == "remarkable":
            self._remarkdown_status.setText(message)
        else:
            self._status.setText(message)
