from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

HELP_TOPICS = (
    (
        "Getting started",
        """
        <h2>Getting started</h2>
        <p>The permanent navy guidance rail on the right shows the current sources and workflow
        steps. Only the next step is highlighted and is vertically aligned with the control that
        requires attention; completed and later steps remain visible but muted.</p>
        <ol>
          <li>Complete the <b>First-run setup</b> check. Each missing dependency is installed only
          after you approve its exact source, command and destination.</li>
          <li>Complete the required API-key, OAuth and macOS application authorisations.</li>
          <li>Allow the automatic <b>System health</b> check to verify every required component.</li>
          <li>Select the page for the source or workflow you want to use.</li>
          <li>Review every preview before confirming a write.</li>
        </ol>
        <p>Hold <b>⌘ Command</b> to display the shortcut reminder. Hover tooltips remain optional.</p>
        <p><img src="{{GUIDANCE_SCREENSHOT}}" width="600"></p>
        <p><i>Example: the guidance strip identifies the current reMarkable step and the next
        required action. The same pattern is used throughout PEA.</i></p>
        """,
    ),
    (
        "Setup assistant",
        """
        <h2>Setup assistant</h2>
        <p>The assistant checks macOS compatibility and the local components used by PEA. The check
        reads executable paths, versions and authorisation status only; it does not read content
        from connected applications.</p>
        <ul>
          <li>Homebrew is never installed automatically.</li>
          <li>Node.js, uv and fixed PLAUD or remarkdown package versions can be installed one at a
          time after a separate confirmation.</li>
          <li>The bundled OmniFocus adapter exposes only aggregate status and bounded task metadata
          through two read-only tools.</li>
          <li>API keys, OAuth sign-ins and macOS permissions remain manual.</li>
        </ul>
        <p>Open it again at any time from <b>Help → Setup assistant</b> or
        <b>Settings → Connections</b>. PEA automatically runs the complete System health check at
        every application start until all required components report <b>OK</b>. Closing the
        assistant or saving only the API key does not complete setup.</p>
        """,
    ),
    (
        "Meeting minutes",
        """
        <h2>Meeting minutes</h2>
        <p><b>Source → Inputs → Generate → Review → File or capture</b></p>
        <ol>
          <li>Select a recent PLAUD recording. The app loads its raw transcript and, where
          available, its derived summary as secondary speaker-identification context.</li>
          <li>Check the date, source reference, model and any manually loaded ChatGPT context.</li>
          <li>Generate and review the Minutes.</li>
          <li>If necessary, select another model and choose <b>Regenerate</b>.</li>
          <li>Review the DEVONthink import or send individual actions to OmniFocus.</li>
        </ol>
        <p>ChatGPT personal Memory is not available through the OpenAI API. A reviewed
        <code>.txt</code> or <code>.md</code> context export must therefore be loaded manually.
        It may clarify established names and roles but cannot prove participation or decisions.</p>
        """,
    ),
    (
        "Agenda",
        """
        <h2>Agenda</h2>
        <p><b>Projects → Notes → Load → Use</b></p>
        <p>Refresh project metadata, then list one project's notes or metadata edited during the
        last seven days across active projects. Load one highlighted note for review, or check up
        to ten notes and load that explicit selection for the Weekly Summary. Unchecked note
        content is not retrieved.</p>
        """,
    ),
    (
        "reMarkable",
        """
        <h2>reMarkable</h2>
        <p><b>Connect → Documents → Load → Review → Inbox</b></p>
        <p>Only existing typed or already-transcribed text is loaded. The app never starts a paid
        transcription. A reviewed document can be filed in the DEVONthink database named
        <b>Inbox</b> after duplicate checks and explicit confirmation.</p>
        """,
    ),
    (
        "OmniFocus",
        """
        <h2>OmniFocus</h2>
        <p>Use the upper controls to review bounded task metadata. Double-click a listed task to
        open it in OmniFocus.</p>
        <p>For a new Inbox capture: select a Minutes action or enter a task title and stable source
        reference, review duplicates, confirm the write, then open the verified task.</p>
        """,
    ),
    (
        "Weekly summary",
        """
        <h2>Weekly summary</h2>
        <p><b>Sources → Week/model → Generate → Review → File</b></p>
        <p>Choose an ISO week and use <b>Load week’s Minutes</b> to retrieve every reviewed PEA
        Minutes record filed in DEVONthink during that week. Selected Agenda and reMarkable notes,
        user-approved work chats and manually dropped <code>.eml</code>, <code>.txt</code> or
        <code>.md</code> email exports can be added before generation. The app never reads a
        mailbox automatically.</p>
        """,
    ),
    (
        "Workflows",
        """
        <h2>Workflows</h2>
        <p><b>Configure → Run → Review → Confirm → Open</b></p>
        <p>Daily Summary loads all reviewed Minutes filed on one selected date; Weekly Summary
        does the same for an ISO week. Both also include work-chat text and email files that you
        manually supplied on the Weekly Summary page. Inspect the combined output in the rendered
        preview; the unchanged Markdown remains available on the adjacent source tab. Then use the
        separate final DEVONthink confirmation. A failed step can be resumed without repeating
        completed work.</p>
        """,
    ),
    (
        "Keyboard shortcuts",
        """
        <h2>Keyboard shortcuts</h2>
        <table cellspacing="8">
          <tr><td><b>Hold ⌘</b></td><td>Display the shortcut reminder</td></tr>
          <tr><td><b>⌘1 … ⌘7</b></td><td>Open the seven main pages</td></tr>
          <tr><td><b>⌘S</b></td><td>Open Settings</td></tr>
          <tr><td><b>⌘R</b></td><td>Regenerate on Minutes or Weekly Summary</td></tr>
          <tr><td><b>⌘T</b></td><td>Toggle hover tooltips</td></tr>
          <tr><td><b>⌘?</b> or <b>F1</b></td><td>Open this Help window</td></tr>
          <tr><td><b>Esc</b></td><td>Close Help</td></tr>
        </table>
        """,
    ),
    (
        "Safety boundaries",
        """
        <h2>Safety boundaries</h2>
        <ul>
          <li>Do not process sensitive HR, medical, recruitment, licensing or formal performance material.</li>
          <li>DEVONthink writes are limited to the database named <code>Inbox</code>.</li>
          <li>PLAUD and handwriting transcriptions remain derived material requiring review.</li>
          <li>DEVONthink and OmniFocus writes require duplicate protection and explicit confirmation.</li>
          <li>Model regeneration creates a new API request and therefore additional token cost.</li>
        </ul>
        """,
    ),
)


class HelpDialog(QDialog):
    def __init__(self, logo_path: Path, version: str, parent=None) -> None:
        super().__init__(parent)
        self._guidance_screenshot = logo_path.parent / "help" / "guidance-overview.png"
        self.setWindowTitle("PEA Help")
        self.resize(900, 620)
        self.setMinimumSize(760, 520)

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        logo = QLabel()
        pixmap = QPixmap(str(logo_path))
        logo.setPixmap(
            pixmap.scaled(
                52,
                52,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        header.addWidget(logo)
        heading = QLabel(f"<h1>Personal Executive Assistant</h1><p>Help · Version {version}</p>")
        header.addWidget(heading, 1)
        layout.addLayout(header)

        content = QHBoxLayout()
        self._topics = QListWidget()
        self._topics.setFixedWidth(210)
        self._topics.setProperty("peaTooltipText", "Choose a PEA help topic.")
        for title, _ in HELP_TOPICS:
            QListWidgetItem(title, self._topics)
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setProperty("peaTooltipText", "Read the selected help topic.")
        content.addWidget(self._topics)
        content.addWidget(self._browser, 1)
        layout.addLayout(content, 1)

        close_button = QPushButton("Close")
        close_button.setProperty(
            "peaTooltipText", "Close PEA Help and return to the application."
        )
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)

        self._topics.currentRowChanged.connect(self._show_topic)
        self._topics.setCurrentRow(0)

    def _show_topic(self, index: int) -> None:
        if 0 <= index < len(HELP_TOPICS):
            html = HELP_TOPICS[index][1].replace(
                "{{GUIDANCE_SCREENSHOT}}",
                QUrl.fromLocalFile(str(self._guidance_screenshot)).toString(),
            )
            self._browser.setHtml(html)
