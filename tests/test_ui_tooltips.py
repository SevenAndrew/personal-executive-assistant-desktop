from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEventLoop, QPoint, QSettings, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTabWidget,
    QTextBrowser,
    QWidget,
)

from pea_app import __version__
from pea_app.agenda_mcp import AgendaNote, AgendaNoteSummary
from pea_app.devonthink_handoff import DevonThinkMinutesSource
from pea_app.guidance import WorkflowGuide
from pea_app.plaud_cli import (
    PlaudRecording,
    PlaudSourceBundle,
    PlaudSummary,
    PlaudTranscript,
)
from pea_app.ui import MainWindow, PlaudJobThread


def _window() -> MainWindow:
    QApplication.instance() or QApplication([])
    QCoreApplication.setOrganizationName("OpenAI-PEA-Tests")
    QCoreApplication.setApplicationName("PEA-Tooltip-Tests")
    QSettings().clear()
    return MainWindow()


def _interactive_widgets(window: MainWindow) -> list[QWidget]:
    types = (
        QCheckBox,
        QComboBox,
        QLineEdit,
        QListWidget,
        QPlainTextEdit,
        QPushButton,
        QTableWidget,
        QTabWidget,
        QTextBrowser,
    )
    return [widget for widget in window.findChildren(QWidget) if isinstance(widget, types)]


def test_every_interactive_control_has_tooltip_guidance() -> None:
    window = _window()

    widgets = _interactive_widgets(window)

    assert widgets
    assert all(widget.property("peaTooltipText") for widget in widgets)
    assert all(widget.accessibleDescription() for widget in widgets)
    window.close()


def test_sidebar_toggle_hides_and_restores_all_tooltips() -> None:
    window = _window()
    widgets = _interactive_widgets(window)

    window._tooltip_toggle.setChecked(False)

    assert window._tooltip_toggle.text() == "Tooltips off"
    assert all(not widget.toolTip() for widget in widgets)

    window._tooltip_toggle.setChecked(True)

    assert window._tooltip_toggle.text() == "Tooltips on"
    assert all(widget.toolTip() for widget in widgets)
    window.close()


def test_guidance_is_permanent_in_the_right_hand_rail() -> None:
    window = _window()
    guides = window.findChildren(WorkflowGuide)

    assert len(guides) == 7
    assert window._guidance_rail.width() == 340
    assert not hasattr(window, "_guidance_toggle")
    assert window._guidance_stack.currentWidget() is window._workflow_guides["minutes"]
    assert window._controlled_mode_label.parentWidget() is window._guidance_rail
    assert window._version_label.parentWidget() is window._guidance_rail
    assert window._controlled_mode_label.objectName() == "controlledMode"
    assert "QLabel#controlledMode { color: #d8b35c;" in window.styleSheet()
    sidebar = window.findChild(QWidget, "sidebar")
    assert sidebar is not None
    sidebar_text = " ".join(label.text() for label in sidebar.findChildren(QLabel))
    assert "Controlled mode" not in sidebar_text
    assert "SevenAndrew" not in sidebar_text
    window.close()


def test_regeneration_is_enabled_only_after_a_preview_exists() -> None:
    window = _window()

    assert not window._regenerate_button.isEnabled()
    assert not window._weekly_regenerate_button.isEnabled()

    window._last_result = object()  # type: ignore[assignment]
    window._last_weekly_result = object()  # type: ignore[assignment]
    window._generation_finished()
    window._weekly_generation_finished()

    assert window._regenerate_button.isEnabled()
    assert window._weekly_regenerate_button.isEnabled()
    window.close()


def test_agenda_note_selection_enables_load_button_after_metadata_arrives() -> None:
    window = _window()
    note = AgendaNoteSummary(
        note_id="note-1",
        title="Current update",
        project_id="project-1",
        project_title="Training",
        start_date="2026-08-06",
        edited_date="2026-08-06T20:00:00Z",
        completed=False,
        on_the_agenda=True,
    )

    window._agenda_thread = None
    window._agenda_completed("notes", [note])

    assert window._agenda_notes.currentData() == note
    assert window._agenda_load_note_button.isEnabled()

    window._agenda_notes.clear()
    window._agenda_thread = object()  # type: ignore[assignment]
    window._agenda_completed("notes", [note])

    assert not window._agenda_load_note_button.isEnabled()
    window._agenda_finished()
    assert window._agenda_load_note_button.isEnabled()
    window.close()


def test_checked_agenda_notes_become_individual_weekly_sources() -> None:
    window = _window()
    notes = [
        AgendaNote(
            note_id=f"note-{index}",
            title=f"Update {index}",
            project_id="project-1",
            project_title="Training",
            markdown=f"## Update {index}\n\nApproved content.",
            created_date="2026-08-05T10:00:00Z",
            edited_date="2026-08-06T20:00:00Z",
            completed=False,
            on_the_agenda=True,
        )
        for index in (1, 2)
    ]

    window._agenda_completed("report_notes", notes)
    sources = window._weekly_sources("2026-W32")

    agenda_sources = [source for source in sources if source.source_reference.startswith("agenda:")]
    assert [source.source_reference for source in agenda_sources] == [
        "agenda:note-1",
        "agenda:note-2",
    ]
    assert window._weekly_use_agenda.text() == "Selected Agenda notes (2)"
    assert window._weekly_use_agenda.isChecked()
    assert "Update 1" in window._agenda_note_text.toPlainText()
    assert "Update 2" in window._agenda_note_text.toPlainText()
    assert window._agenda_source_reference.text() == "agenda:note-1; agenda:note-2"
    window.close()


def test_weekly_summary_uses_all_loaded_minutes_for_selected_week() -> None:
    window = _window()
    records = [
        DevonThinkMinutesSource(
            f"minutes-{index}",
            f"Meeting {index}",
            "2026-08-06T10:00:00+02:00",
            f"# Meeting {index}\n\nApproved content.",
        )
        for index in (1, 2)
    ]

    window._weekly_minutes_loaded(records)
    sources = window._weekly_sources("2026-W32")

    minute_sources = [source for source in sources if source.source_kind == "reviewed DEVONthink Minutes"]
    assert len(minute_sources) == 2
    assert window._weekly_use_minutes.text() == "Minutes from selected week"
    assert "2 reviewed Minutes" in window._weekly_status.text()
    window.close()


def test_workflows_offer_daily_and_weekly_period_summaries() -> None:
    window = _window()
    choices = {
        window._workflow_choice.itemData(index)
        for index in range(window._workflow_choice.count())
    }

    assert {"daily_summary", "weekly_summary"} <= choices
    window.close()


def test_weekly_preview_renders_markdown_and_supports_large_view() -> None:
    window = _window()
    markdown = "# Weekly Summary — 2026-W32\n\n| Topic | Summary |\n|---|---|\n| Training | - Plan reviewed |"

    window._set_weekly_preview(markdown)

    assert window._weekly_preview_tabs.currentWidget() is window._weekly_preview_rendered
    assert window._weekly_preview.toPlainText() == markdown
    assert "Training" in window._weekly_preview_rendered.toPlainText()
    window._weekly_preview_size_toggle.setChecked(True)
    assert window._weekly_preview_tabs.minimumHeight() == 480
    assert window._weekly_preview_size_toggle.text() == "Compact view"
    window.close()


def test_workflow_preview_renders_markdown_and_preserves_source() -> None:
    window = _window()
    markdown = (
        "# Daily Summary — 2026-08-10\n\n"
        "| Topic | Summary |\n|---|---|\n"
        "| Training | - Plan reviewed<br>- Owner confirmed |"
    )

    window._set_workflow_preview(markdown)

    assert window._workflow_preview_tabs.currentWidget() is window._workflow_preview_rendered
    assert window._workflow_preview.toPlainText() == markdown
    assert "Daily Summary" in window._workflow_preview_rendered.toPlainText()
    assert "Owner confirmed" in window._workflow_preview_rendered.toPlainText()
    assert "<table" in window._workflow_preview_rendered.toHtml()
    window.close()


def test_command_shortcuts_and_context_are_visible_in_guidance() -> None:
    window = _window()
    window._contextual_memory.setPlainText("Approved role context")
    window._update_guidance_sources()

    assert window._page_shortcuts[0].key().toString() == "Ctrl+1"
    assert "⌘1…7" in window._shortcut_hint.text()
    assert "ChatGPT context import" in window._workflow_guides["minutes"]._sources.text()
    window.close()


def test_startup_resets_all_model_profiles_to_economy() -> None:
    QApplication.instance() or QApplication([])
    QCoreApplication.setOrganizationName("OpenAI-PEA-Tests")
    QCoreApplication.setApplicationName("PEA-Tooltip-Tests")
    QSettings().clear()
    QSettings().setValue("default_model_profile", "quality")

    window = MainWindow()

    assert window._model_combo.currentData().key == "economy"
    assert window._weekly_model_combo.currentData().key == "economy"
    assert window._workflow_model.currentData().key == "economy"
    window.close()


def test_repeated_plaud_bundle_loads_finish_before_thread_cleanup(monkeypatch) -> None:
    recording = PlaudRecording("recording-1", "Coordination", "2026-08-10", "00:15:00")
    bundle = PlaudSourceBundle(
        transcript=PlaudTranscript(recording, "[00:00 - 00:10]\nSpeaker 1: Update."),
        summary=PlaudSummary(recording, "Speaker 1 is Alex."),
    )

    class FakePlaudCli:
        def get_source_bundle(self, selected: PlaudRecording) -> PlaudSourceBundle:
            assert selected == recording
            return bundle

        def is_installed(self) -> bool:
            return True

        def is_authenticated(self) -> bool:
            return True

    monkeypatch.setattr("pea_app.ui.PlaudCli", FakePlaudCli)
    window = _window()

    for _ in range(2):
        window._start_plaud_job("transcript", recording)
        thread = window._plaud_thread
        assert isinstance(thread, PlaudJobThread)
        completed = QEventLoop()
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(completed.quit)
        thread.finished.connect(completed.quit)
        deadline.start(2_000)
        completed.exec()
        deadline.stop()

        assert not thread.isRunning()
        assert window._plaud_thread is None
        QApplication.processEvents()

    assert window._source_reference.text() == "plaud:recording-1"
    assert window._meeting_date.text() == "2026-08-10"
    assert "Speaker 1: Update." in window._transcript.toPlainText()
    assert window._plaud_summary.toPlainText() == "Speaker 1 is Alex."
    window.close()


def test_agenda_report_checkboxes_have_visible_checked_and_unchecked_styles() -> None:
    window = _window()

    style = window._agenda_report_candidates.styleSheet()

    assert "indicator:unchecked" in style
    assert "border: 2px solid #71808d" in style
    assert "indicator:checked" in style
    assert "checkmark.svg" in style
    window.close()


def test_long_pages_scroll_instead_of_compressing_controls() -> None:
    window = _window()

    pages = [window._pages.widget(index) for index in range(window._pages.count())]

    assert len(pages) == 7
    assert all(isinstance(page, QScrollArea) for page in pages)
    assert all(page.widget().minimumHeight() >= 700 for page in pages)
    window.close()


def test_weekly_summary_fits_the_standard_window_without_scrolling() -> None:
    window = _window()
    window.resize(1260, 820)
    window.show()
    QApplication.processEvents()

    window._navigation.setCurrentRow(4)
    QApplication.processEvents()
    weekly_page = window._pages.currentWidget()

    assert isinstance(weekly_page, QScrollArea)
    assert weekly_page.verticalScrollBar().maximum() == 0
    window.close()


def test_remarkable_page_fits_the_standard_window_without_scrolling() -> None:
    window = _window()
    window.resize(1260, 820)
    window.show()
    QApplication.processEvents()

    window._navigation.setCurrentRow(2)
    QApplication.processEvents()
    remarkable_page = window._pages.currentWidget()

    assert isinstance(remarkable_page, QScrollArea)
    assert remarkable_page.verticalScrollBar().maximum() == 0
    window.close()


def test_minutes_related_fields_are_arranged_in_shared_rows() -> None:
    window = _window()
    window.resize(1260, 820)
    window.show()
    QApplication.processEvents()

    assert window._source_reference.geometry().y() == window._meeting_date.geometry().y()
    assert window._target_database.geometry().y() == window._destination.geometry().y()
    window.close()


def test_sidebar_logo_is_right_aligned_beside_the_brand() -> None:
    window = _window()
    window.show()
    QApplication.processEvents()

    logo = window.findChild(QLabel, "sidebarLogo")
    brand = window.findChild(QLabel, "brand")

    assert logo is not None
    assert brand is not None
    assert logo.geometry().left() > brand.geometry().center().x()
    assert logo.geometry().top() <= brand.geometry().top()
    window.close()


def test_minutes_preview_defaults_to_rendered_markdown_and_preserves_source() -> None:
    window = _window()
    markdown = "# Weekly coordination\n\n- Decision recorded\n- Action assigned"
    rendered_html = (
        "<h1>Weekly coordination</h1><table><tr><th>Decision</th></tr>"
        "<tr><td>Recorded</td></tr></table>"
    )

    window._set_minutes_preview(markdown, rendered_html)

    assert window._preview_tabs.currentWidget() is window._preview_rendered
    assert window._preview.toPlainText() == markdown
    assert "Weekly coordination" in window._preview_rendered.toPlainText()
    assert "<h1" in window._preview_rendered.toHtml()
    assert "Recorded" in window._preview_rendered.toPlainText()
    window.close()


def test_minutes_editors_are_stacked_and_have_a_size_toggle() -> None:
    window = _window()
    window.show()
    QApplication.processEvents()

    transcript_top = window._transcript.mapTo(window, QPoint(0, 0)).y()
    preview_top = window._preview_tabs.mapTo(window, QPoint(0, 0)).y()

    assert preview_top > transcript_top + window._transcript.height()
    assert window._editor_size_toggle.isChecked()
    assert window._transcript.minimumHeight() == 380
    assert window._preview_tabs.minimumHeight() == 380

    window._editor_size_toggle.setChecked(False)

    assert window._editor_size_toggle.text() == "Editor size: Compact"
    assert window._transcript.minimumHeight() == 220
    assert window._preview_tabs.minimumHeight() == 220
    window.close()


def test_help_window_branding_and_topics_are_available() -> None:
    window = _window()

    window._show_help()

    assert window._help_dialog is not None
    assert window._help_dialog.windowTitle() == "PEA Help"
    assert window._help_dialog._topics.count() >= 8
    assert any(
        label.text() == f"v{__version__} · © SevenAndrew 2026"
        for label in window.findChildren(QLabel)
    )
    window._help_dialog.close()
    window.close()
