from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSpacerItem, QVBoxLayout


def _explanation(step: str) -> str:
    descriptions = {
        "Select source": "Choose the source material that belongs to this meeting.",
        "Review inputs": "Confirm the date, model and contextual sources before generation.",
        "Generate": "Create one controlled draft with the selected model.",
        "Review": "Check names, decisions, actions and source fidelity.",
        "File or capture": "Review duplicates before filing or creating tasks.",
        "Configure": "Choose the workflow, period, model and destination.",
        "Run": "Allow the selected workflow to complete its controlled read steps.",
        "Confirm": "Authorise the external write only after reviewing the preview.",
        "Open": "Open the verified destination record.",
        "Sources": "Load the records and manual context that belong to this period.",
        "Week and model": "Confirm the ISO week and the required quality profile.",
        "File": "Review duplicates before creating the DEVONthink record.",
        "API key": "Save the OpenAI API key in macOS Keychain.",
        "Authorisations": "Complete the required local and source-system authorisations.",
        "Health check": "Run the complete content-free connection and capability check.",
        "Usage and logs": "Review local API usage statistics and privacy-safe runtime logs.",
    }
    return descriptions.get(step, f"Complete the {step.lower()} stage before continuing.")


class WorkflowGuide(QFrame):
    """Persistent right-hand workflow rail aligned with the active control."""

    def __init__(self, steps: Sequence[str], next_action: str) -> None:
        super().__init__()
        self.setObjectName("workflowGuide")
        self._steps = tuple(steps)
        self._current_step = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(10)
        heading = QLabel("Next step")
        heading.setObjectName("guideHeading")
        layout.addWidget(heading)
        self._summary = QLabel()
        self._summary.setObjectName("guideSummary")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._sources = QLabel("Sources\nNo source loaded")
        self._sources.setObjectName("guideSources")
        self._sources.setWordWrap(True)
        layout.addWidget(self._sources)

        self._top_spacer = QSpacerItem(0, 8)
        layout.addItem(self._top_spacer)
        self._step_frames: list[QFrame] = []
        self._step_titles: list[QLabel] = []
        self._step_details: list[QLabel] = []
        for index, step in enumerate(self._steps):
            frame = QFrame()
            frame.setObjectName("guideStep")
            frame.setProperty("stepState", "pending")
            row = QVBoxLayout(frame)
            row.setContentsMargins(11, 9, 11, 9)
            row.setSpacing(3)
            title = QLabel(f"{index + 1}. {step}")
            title.setObjectName("guideStepTitle")
            detail = QLabel(_explanation(step))
            detail.setObjectName("guideStepDetail")
            detail.setWordWrap(True)
            row.addWidget(title)
            row.addWidget(detail)
            layout.addWidget(frame)
            self._step_frames.append(frame)
            self._step_titles.append(title)
            self._step_details.append(detail)
        layout.addStretch()
        self.set_step(0, next_action)

    @property
    def current_step(self) -> int:
        return self._current_step

    def set_sources(self, sources: Sequence[str]) -> None:
        visible = [source.strip() for source in sources if source.strip()]
        body = "\n".join(f"• {source}" for source in visible) or "No source loaded"
        self._sources.setText(f"Sources\n{body}")

    def align_to(self, target_y: int) -> None:
        estimated_current_offset = self._current_step * 74
        height = max(8, min(300, target_y - 190 - estimated_current_offset))
        self._top_spacer.changeSize(0, height)
        self.layout().invalidate()

    def set_step(self, current_step: int, next_action: str) -> None:
        maximum = len(self._steps)
        self._current_step = max(0, min(current_step, maximum))
        self._summary.setText(
            "Workflow complete" if self._current_step >= maximum else next_action
        )
        for index, frame in enumerate(self._step_frames):
            if index < self._current_step:
                state = "complete"
                marker = "●"
                detail = f"{self._steps[index]} completed."
            elif index == self._current_step and self._current_step < maximum:
                state = "current"
                marker = "●"
                detail = _explanation(self._steps[index])
            else:
                state = "pending"
                marker = "○"
                detail = "Available after the preceding stage."
            self._step_titles[index].setText(f"{marker}  {index + 1}. {self._steps[index]}")
            self._step_details[index].setText(detail)
            frame.setProperty("stepState", state)
            frame.style().unpolish(frame)
            frame.style().polish(frame)


class WorkflowProgressView(QFrame):
    """Vertical traffic-light workflow progress display."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("workflowProgress")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(7)
        self._rows: list[tuple[QFrame, QLabel, QLabel, QLabel]] = []

    def set_steps(self, steps: Sequence[str]) -> None:
        while self._rows:
            frame, *_ = self._rows.pop()
            self._layout.removeWidget(frame)
            frame.deleteLater()
        for step in steps:
            frame = QFrame()
            frame.setObjectName("progressStep")
            frame.setProperty("progressState", "Pending")
            row = QHBoxLayout(frame)
            row.setContentsMargins(12, 8, 12, 8)
            text = QVBoxLayout()
            title = QLabel(step)
            title.setObjectName("progressTitle")
            detail = QLabel("Waiting for the preceding step.")
            detail.setObjectName("progressDetail")
            detail.setWordWrap(True)
            text.addWidget(title)
            text.addWidget(detail)
            status = QLabel("Pending")
            status.setObjectName("progressStatus")
            dot = QLabel("●")
            dot.setObjectName("progressDot")
            dot.setProperty("progressState", "Pending")
            row.addLayout(text, 1)
            row.addWidget(status)
            row.addWidget(dot)
            self._layout.addWidget(frame)
            self._rows.append((frame, detail, status, dot))

    def update_step(self, index: int, status: str, detail: str) -> None:
        if not 0 <= index < len(self._rows):
            return
        frame, detail_label, status_label, dot = self._rows[index]
        resolved_detail = detail
        if not resolved_detail and status in {"Complete", "Ready"}:
            resolved_detail = "Step completed."
        detail_label.setText(resolved_detail or "Waiting for detail.")
        status_label.setText(status)
        frame.setProperty("progressState", status)
        dot.setProperty("progressState", status)
        for widget in (frame, dot):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
