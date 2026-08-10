from __future__ import annotations

from types import SimpleNamespace

from pea_app.ui import MainWindow


def test_pending_devonthink_import_continues_after_review_thread_finished() -> None:
    handoff = object()
    calls: list[tuple[str, object]] = []
    window = SimpleNamespace(
        _pending_import=handoff,
        _pending_import_origin="weekly",
        _devonthink_thread=None,
        _start_devonthink_job=lambda operation, value, origin: calls.append(
            (f"{origin}:{operation}", value)
        ),
    )

    MainWindow._continue_pending_devonthink_import(window)

    assert calls == [("weekly:import", handoff)]
    assert window._pending_import is None


def test_pending_devonthink_import_waits_for_active_review_thread() -> None:
    handoff = object()
    calls: list[tuple[str, object]] = []
    window = SimpleNamespace(
        _pending_import=handoff,
        _pending_import_origin="minutes",
        _devonthink_thread=object(),
        _start_devonthink_job=lambda operation, value, origin: calls.append(
            (f"{origin}:{operation}", value)
        ),
    )

    MainWindow._continue_pending_devonthink_import(window)

    assert calls == []
    assert window._pending_import is handoff
