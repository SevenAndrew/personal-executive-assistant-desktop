from __future__ import annotations

from email import policy
from email.parser import BytesParser
from pathlib import Path

ALLOWED_SOURCE_SUFFIXES = {".eml", ".md", ".txt"}
MAX_MANUAL_SOURCE_BYTES = 5_000_000


def load_manual_source_files(paths: list[Path]) -> str:
    sections: list[str] = []
    total = 0
    for path in paths:
        if path.suffix.casefold() not in ALLOWED_SOURCE_SUFFIXES:
            raise ValueError("Use .eml, .txt or .md files only.")
        size = path.stat().st_size
        total += size
        if total > MAX_MANUAL_SOURCE_BYTES:
            raise ValueError("The selected source files exceed the 5 MB safety limit.")
        if path.suffix.casefold() == ".eml":
            content = _email_text(path)
        else:
            content = path.read_text(encoding="utf-8")
        sections.append(f"--- {path.name} ---\n{content.strip()}")
    return "\n\n".join(section for section in sections if section.strip())


def _email_text(path: Path) -> str:
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    headers = [
        f"Subject: {message.get('subject', '')}",
        f"From: {message.get('from', '')}",
        f"To: {message.get('to', '')}",
        f"Date: {message.get('date', '')}",
    ]
    body = message.get_body(preferencelist=("plain",)) if message.is_multipart() else message
    payload = body.get_content() if body is not None else ""
    return "\n".join(headers) + "\n\n" + str(payload)
