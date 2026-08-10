from __future__ import annotations

import http.client
import json
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from pea_app.models import ActionItem
from pea_app.omnifocus_capture import (
    OMNIJS_CAPTURE_SCRIPT,
    CaptureReceipt,
    CaptureReview,
    OmniFocusCaptureBridge,
    OmniFocusCaptureDuplicateError,
    OmniFocusCaptureError,
    OmniFocusCaptureService,
    _CallbackState,
    _handler_for,
    prepare_capture,
    prepare_minutes_action_captures,
)


class FakeBridge:
    def __init__(self, responses: dict[str, list[object]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call(self, operation: str, **parameters: object) -> object:
        self.calls.append((operation, parameters))
        return self.responses[operation].pop(0)


def test_prepare_capture_normalises_and_fingerprints() -> None:
    proposal = prepare_capture("  Review   training plan  ", "manual:training-plan")

    assert proposal.title == "Review training plan"
    assert proposal.title_key == "review training plan"
    assert len(proposal.fingerprint) == 64


def test_minutes_action_captures_preserve_owner_due_date_and_stable_reference() -> None:
    actions = [
        ActionItem(action="Update the plan.", owner="Alex", due_date="2026-08-12"),
        ActionItem(action="Confirm capacity.", owner="Unassigned"),
    ]

    first = prepare_minutes_action_captures(actions, "plaud:meeting-1")
    second = prepare_minutes_action_captures(actions, "plaud:meeting-1")

    assert first[0].owner == "Alex"
    assert first[0].due_date == "2026-08-12"
    assert first[1].due_date == "Not stated"
    assert first[0].proposal.source_reference.startswith("minutes-action:")
    assert first[0].proposal.source_reference == second[0].proposal.source_reference


def test_minutes_action_reference_changes_with_owner_or_source() -> None:
    alex = [ActionItem(action="Update the plan.", owner="Alex")]
    sam = [ActionItem(action="Update the plan.", owner="Sam")]

    reference = prepare_minutes_action_captures(alex, "plaud:meeting-1")[0].proposal

    assert reference.source_reference != prepare_minutes_action_captures(
        sam, "plaud:meeting-1"
    )[0].proposal.source_reference
    assert reference.source_reference != prepare_minutes_action_captures(
        alex, "plaud:meeting-2"
    )[0].proposal.source_reference


def test_review_returns_bounded_duplicate_counts() -> None:
    bridge = FakeBridge({"captureReview": [{"sourceMatches": 1, "titleMatches": 2}]})
    proposal = prepare_capture("Review plan", "manual:plan")

    review = OmniFocusCaptureService(bridge).review(proposal)

    assert not review.is_clear
    assert review.source_matches == 1
    assert bridge.calls[0][0] == "captureReview"


def test_create_rechecks_and_independently_verifies() -> None:
    bridge = FakeBridge(
        {
            "captureCreate": [
                {
                    "created": True,
                    "id": "task-1",
                    "name": "Review plan",
                    "inInbox": True,
                    "completed": False,
                    "sourceVerified": True,
                }
            ],
            "captureVerify": [
                {
                    "found": True,
                    "nameMatches": True,
                    "inInbox": True,
                    "completed": False,
                    "dropped": False,
                    "sourceVerified": True,
                }
            ],
        }
    )
    proposal = prepare_capture("Review plan", "manual:plan")
    review = CaptureReview(proposal, 0, 0)

    receipt = OmniFocusCaptureService(bridge).create(review)

    assert receipt.content_verified
    assert receipt.item_url == "omnifocus:///task/task-1"
    assert [operation for operation, _ in bridge.calls] == ["captureCreate", "captureVerify"]


def test_create_blocks_stale_clear_review_when_final_recheck_finds_duplicate() -> None:
    bridge = FakeBridge(
        {"captureCreate": [{"created": False, "sourceMatches": 1, "titleMatches": 0}]}
    )
    proposal = prepare_capture("Review plan", "manual:plan")

    with pytest.raises(OmniFocusCaptureDuplicateError, match="final"):
        OmniFocusCaptureService(bridge).create(CaptureReview(proposal, 0, 0))


def test_retraction_completes_only_exact_verified_capture() -> None:
    bridge = FakeBridge(
        {
            "captureRetract": [
                {"taskId": "task-1", "completed": True, "sourceVerified": True}
            ]
        }
    )
    proposal = prepare_capture("Review plan", "manual:plan")
    receipt = CaptureReceipt(proposal, "task-1", "omnifocus:///task/task-1", True)

    retraction = OmniFocusCaptureService(bridge).retract(receipt)

    assert retraction.completed


def test_bridge_rejects_any_operation_outside_fixed_allow_list() -> None:
    with pytest.raises(OmniFocusCaptureError, match="Unsupported"):
        OmniFocusCaptureBridge(launcher=lambda _: None).call("arbitraryScript")


def test_bridge_url_uses_static_script_and_data_argument() -> None:
    captured: list[str] = []

    def launcher(url: str) -> None:
        captured.append(url)
        raise OmniFocusCaptureError("stop after URL inspection")

    proposal = prepare_capture("Review plan", "manual:plan")
    with pytest.raises(OmniFocusCaptureError, match="inspection"):
        OmniFocusCaptureBridge(launcher=launcher).call(
            "captureReview",
            title=proposal.title,
            titleKey=proposal.title_key,
            sourceReference=proposal.source_reference,
            fingerprint=proposal.fingerprint,
        )

    query = urllib.parse.parse_qs(urllib.parse.urlparse(captured[0]).query)
    assert query["script"] == [OMNIJS_CAPTURE_SCRIPT]
    assert "Review plan" not in query["script"][0]
    assert "Review plan" in query["arg"][0]


def test_callback_rejects_wrong_token_and_accepts_exact_path_and_token() -> None:
    state = _CallbackState("/capture/exact", "secret-token")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        body = json.dumps({"ok": True, "result": {"sourceMatches": 0}}).encode()
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request(
            "POST",
            "/capture/exact",
            body=body,
            headers={"Content-Type": "application/json", "X-PEA-Token": "wrong"},
        )
        assert connection.getresponse().status == 403
        assert state.payload is None

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request(
            "POST",
            "/capture/exact",
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-PEA-Token": "secret-token",
            },
        )
        assert connection.getresponse().status == 204
        assert state.event.wait(1)
        assert state.payload == {"ok": True, "result": {"sourceMatches": 0}}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
