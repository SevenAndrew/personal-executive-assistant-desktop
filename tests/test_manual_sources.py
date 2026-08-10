from pathlib import Path

import pytest

from pea_app.manual_sources import load_manual_source_files


def test_manual_email_upload_extracts_headers_and_plain_body(tmp_path: Path) -> None:
    source = tmp_path / "update.eml"
    source.write_bytes(
        b"Subject: Training update\nFrom: sender@example.test\nTo: team@example.test\n"
        b"Date: Thu, 6 Aug 2026 09:00:00 +0200\n\nCourse planning is complete."
    )

    text = load_manual_source_files([source])

    assert "Subject: Training update" in text
    assert "Course planning is complete." in text


def test_manual_email_upload_rejects_unsupported_files(tmp_path: Path) -> None:
    source = tmp_path / "attachment.pdf"
    source.write_bytes(b"not a supported source")

    with pytest.raises(ValueError, match=".eml"):
        load_manual_source_files([source])
