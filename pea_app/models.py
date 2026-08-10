from __future__ import annotations

from dataclasses import dataclass
from html import escape

from pydantic import BaseModel, Field


class TopicSummary(BaseModel):
    topic: str = Field(min_length=1)
    summary: list[str] = Field(min_length=1, max_length=2)


class ActionItem(BaseModel):
    action: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    due_date: str | None = None


class MeetingMinutes(BaseModel):
    title: str = Field(min_length=1)
    meeting_date: str = Field(min_length=1)
    participants: list[str] = Field(min_length=1)
    topics: list[TopicSummary]
    decisions: list[str]
    action_items: list[ActionItem]
    verification_notes: list[str]

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", f"**Date:** {self.meeting_date}", ""]

        lines.extend(["## Participants", ""])
        lines.extend(_markdown_list(self.participants, "Not stated in source."))

        lines.extend(["", "## Topics", "", "| Topic | Summary |", "|---|---|"])
        for item in self.topics:
            summary = "<br>".join(f"- {_table_cell(bullet)}" for bullet in item.summary)
            lines.append(f"| {_table_cell(item.topic)} | {summary} |")

        lines.extend(["", "## Decisions", ""])
        lines.extend(_markdown_list(self.decisions, "No decision recorded."))

        lines.extend(["", "## Action items", ""])
        if self.action_items:
            lines.extend(["| Action | Owner | Due date |", "|---|---|---|"])
            for item in self.action_items:
                due_date = item.due_date or "Not stated"
                lines.append(
                    f"| {_table_cell(item.action)} | {_table_cell(item.owner)} | "
                    f"{_table_cell(due_date)} |"
                )
        else:
            lines.append("- No action item recorded.")

        lines.extend(["", "## Verification notes", ""])
        lines.extend(_markdown_list(self.verification_notes, "No verification issue identified."))
        return "\n".join(lines).strip() + "\n"

    def to_html(self) -> str:
        """Return a deterministic, escaped preview of the structured Minutes."""
        sections = [
            f"<h1>{escape(self.title)}</h1>",
            f"<p><strong>Date:</strong> {escape(self.meeting_date)}</p>",
            "<h2>Participants</h2>",
            _html_list(self.participants, "Not stated in source."),
            "<h2>Topics</h2>",
            '<table width="100%" cellspacing="0" cellpadding="0">',
            "<tr><th>Topic</th><th>Summary</th></tr>",
        ]
        for item in self.topics:
            sections.append(
                f"<tr><td>{escape(item.topic)}</td>"
                f"<td>{_html_list(item.summary, 'No summary recorded.')}</td></tr>"
            )
        sections.extend(
            [
                "</table>",
                "<h2>Decisions</h2>",
                _html_list(self.decisions, "No decision recorded."),
                "<h2>Action items</h2>",
            ]
        )
        if self.action_items:
            sections.extend(
                [
                    '<table width="100%" cellspacing="0" cellpadding="0">',
                    "<tr><th>Action</th><th>Owner</th><th>Due date</th></tr>",
                ]
            )
            for item in self.action_items:
                due_date = item.due_date or "Not stated"
                sections.append(
                    f"<tr><td>{escape(item.action)}</td><td>{escape(item.owner)}</td>"
                    f"<td>{escape(due_date)}</td></tr>"
                )
            sections.append("</table>")
        else:
            sections.append(_html_list([], "No action item recorded."))
        sections.extend(
            [
                "<h2>Verification notes</h2>",
                _html_list(self.verification_notes, "No verification issue identified."),
            ]
        )
        return "".join(sections)


class WeeklySummary(BaseModel):
    week_id: str = Field(pattern=r"^\d{4}-W\d{2}$")
    topics: list[TopicSummary] = Field(min_length=1)

    def to_markdown(self) -> str:
        lines = [
            f"# Weekly Summary — {self.week_id}",
            "",
            "| Topic | Summary |",
            "|---|---|",
        ]
        for item in self.topics:
            summary = "<br>".join(f"- {_table_cell(bullet)}" for bullet in item.summary)
            lines.append(f"| {_table_cell(item.topic)} | {summary} |")
        return "\n".join(lines).strip() + "\n"


class DailySummary(BaseModel):
    date_id: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    topics: list[TopicSummary] = Field(min_length=1)

    def to_markdown(self) -> str:
        lines = [
            f"# Daily Summary — {self.date_id}",
            "",
            "| Topic | Summary |",
            "|---|---|",
        ]
        for item in self.topics:
            summary = "<br>".join(f"- {_table_cell(bullet)}" for bullet in item.summary)
            lines.append(f"| {_table_cell(item.topic)} | {summary} |")
        return "\n".join(lines).strip() + "\n"


def _markdown_list(items: list[str], empty_text: str) -> list[str]:
    return [f"- {item}" for item in items] if items else [f"- {empty_text}"]


def _html_list(items: list[str], empty_text: str) -> str:
    values = items or [empty_text]
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


@dataclass(frozen=True)
class ModelProfile:
    key: str
    label: str
    model: str
    reasoning_effort: str
    cost_label: str
    description: str


MODEL_PROFILES: tuple[ModelProfile, ...] = (
    ModelProfile(
        "economy",
        "Economy",
        "gpt-5.6-luna",
        "low",
        "Lowest",
        "Routine minutes and summaries with the lowest expected cost.",
    ),
    ModelProfile(
        "standard",
        "Standard",
        "gpt-5.6-terra",
        "medium",
        "Medium",
        "Balanced quality and cost for more complex source material.",
    ),
    ModelProfile(
        "quality",
        "High quality",
        "gpt-5.6-sol",
        "medium",
        "Highest",
        "Quality-first processing; requires explicit confirmation.",
    ),
)


def get_model_profile(key: str) -> ModelProfile:
    try:
        return next(profile for profile in MODEL_PROFILES if profile.key == key)
    except StopIteration as exc:
        raise ValueError(f"Unknown model profile: {key}") from exc
