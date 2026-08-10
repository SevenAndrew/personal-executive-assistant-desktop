from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import subprocess
import threading
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

from .models import ActionItem

MAX_CALLBACK_BYTES = 512 * 1024
DEFAULT_TIMEOUT = 12.0
MAX_TITLE_LENGTH = 200
MAX_SOURCE_REFERENCE_LENGTH = 300

OMNIJS_CAPTURE_SCRIPT = r"""
(async () => {
  const request = argument;
  const remaining = task => !task.completed && !task.dropped;
  const noteMarker = () => [
    "PEA-CAPTURE v1",
    `source-reference: ${request.sourceReference}`,
    `fingerprint: ${request.fingerprint}`
  ].join("\n");
  const fingerprintMarker = `fingerprint: ${request.fingerprint}`;
  const sourceMatches = () => flattenedTasks.filter(task =>
    String(task.note || "").split("\n").includes(fingerprintMarker)
  );
  const titleMatches = () => flattenedTasks.filter(task =>
    remaining(task) && task.name.trim().toLocaleLowerCase() === request.titleKey
  );
  const review = () => ({
    sourceMatches: sourceMatches().length,
    titleMatches: titleMatches().length
  });

  let result;
  if (request.operation === "captureReview") {
    result = review();
  } else if (request.operation === "captureCreate") {
    const duplicate = review();
    if (duplicate.sourceMatches || duplicate.titleMatches) {
      result = {created: false, ...duplicate};
    } else {
      const task = new Task(request.title, inbox.ending);
      task.note = noteMarker();
      result = {
        created: true,
        id: task.id.primaryKey,
        name: task.name,
        inInbox: task.inInbox,
        completed: task.completed,
        sourceVerified: String(task.note || "").split("\n").includes(fingerprintMarker)
      };
    }
  } else if (request.operation === "captureVerify") {
    const task = flattenedTasks.find(item => item.id.primaryKey === request.taskId);
    result = {
      found: Boolean(task),
      nameMatches: Boolean(task && task.name === request.title),
      inInbox: Boolean(task && task.inInbox),
      completed: Boolean(task && task.completed),
      dropped: Boolean(task && task.dropped),
      sourceVerified: Boolean(
        task && String(task.note || "").split("\n").includes(fingerprintMarker)
      )
    };
  } else if (request.operation === "captureRetract") {
    const task = flattenedTasks.find(item => item.id.primaryKey === request.taskId);
    const exact = Boolean(
      task &&
      task.name === request.title &&
      !task.dropped &&
      String(task.note || "").split("\n").includes(fingerprintMarker)
    );
    if (!exact) throw new Error("Capture retraction target did not match exactly");
    if (!task.completed) task.markComplete();
    result = {taskId: task.id.primaryKey, completed: task.completed, sourceVerified: true};
  } else {
    throw new Error("Unsupported capture operation");
  }

  const response = URL.FetchRequest.fromString(request.callback);
  response.method = "POST";
  response.headers = {"Content-Type": "application/json", "X-PEA-Token": request.token};
  response.bodyString = JSON.stringify({ok: true, result});
  await response.fetch();
})().catch(async error => {
  try {
    const response = URL.FetchRequest.fromString(argument.callback);
    response.method = "POST";
    response.headers = {"Content-Type": "application/json", "X-PEA-Token": argument.token};
    response.bodyString = JSON.stringify({ok: false, error: `${error.name}: ${error.message}`});
    await response.fetch();
  } catch (_) {}
});
""".strip()


class OmniFocusCaptureError(RuntimeError):
    pass


class OmniFocusCaptureDuplicateError(OmniFocusCaptureError):
    pass


class CaptureBridge(Protocol):
    def call(self, operation: str, **parameters: Any) -> Any: ...


@dataclass(frozen=True)
class CaptureProposal:
    title: str
    source_reference: str
    fingerprint: str

    @property
    def title_key(self) -> str:
        return " ".join(self.title.casefold().split())


@dataclass(frozen=True)
class CaptureReview:
    proposal: CaptureProposal
    source_matches: int
    title_matches: int

    @property
    def is_clear(self) -> bool:
        return self.source_matches == 0 and self.title_matches == 0


@dataclass(frozen=True)
class CaptureReceipt:
    proposal: CaptureProposal
    task_id: str
    item_url: str
    content_verified: bool


@dataclass(frozen=True)
class CaptureRetraction:
    task_id: str
    completed: bool
    source_verified: bool


@dataclass(frozen=True)
class MinutesActionCapture:
    action: str
    owner: str
    due_date: str
    proposal: CaptureProposal


def prepare_capture(title: str, source_reference: str) -> CaptureProposal:
    cleaned_title = " ".join(title.strip().split())
    cleaned_source = source_reference.strip()
    if not cleaned_title:
        raise ValueError("An OmniFocus task title is required.")
    if "\n" in title or "\r" in title:
        raise ValueError("The OmniFocus task title must be a single line.")
    if len(cleaned_title) > MAX_TITLE_LENGTH:
        raise ValueError(f"The OmniFocus task title exceeds {MAX_TITLE_LENGTH} characters.")
    if not cleaned_source:
        raise ValueError("A stable source reference is required for duplicate protection.")
    if any(character.isspace() for character in cleaned_source):
        raise ValueError("The source reference must not contain whitespace.")
    if len(cleaned_source) > MAX_SOURCE_REFERENCE_LENGTH:
        raise ValueError(
            f"The source reference exceeds {MAX_SOURCE_REFERENCE_LENGTH} characters."
        )
    fingerprint = hashlib.sha256(
        f"{cleaned_source}\n{cleaned_title.casefold()}".encode()
    ).hexdigest()
    return CaptureProposal(cleaned_title, cleaned_source, fingerprint)


def prepare_minutes_action_captures(
    action_items: list[ActionItem],
    minutes_source_reference: str,
) -> list[MinutesActionCapture]:
    if not action_items:
        return []
    cleaned_source = minutes_source_reference.strip()
    if not cleaned_source:
        raise ValueError(
            "A stable Minutes source reference is required before preparing action captures."
        )
    captures: list[MinutesActionCapture] = []
    for item in action_items:
        action_key = hashlib.sha256(
            (
                f"{cleaned_source}\n{item.action.casefold()}\n"
                f"{item.owner.casefold()}\n{item.due_date or ''}"
            ).encode()
        ).hexdigest()[:24]
        proposal = prepare_capture(item.action, f"minutes-action:{action_key}")
        captures.append(
            MinutesActionCapture(
                action=item.action,
                owner=item.owner,
                due_date=item.due_date or "Not stated",
                proposal=proposal,
            )
        )
    return captures


class OmniFocusCaptureService:
    def __init__(self, bridge: CaptureBridge | None = None) -> None:
        self._bridge = bridge or OmniFocusCaptureBridge()

    def review(self, proposal: CaptureProposal) -> CaptureReview:
        result = self._bridge.call("captureReview", **_proposal_arguments(proposal))
        return CaptureReview(
            proposal=proposal,
            source_matches=_count(result, "sourceMatches"),
            title_matches=_count(result, "titleMatches"),
        )

    def create(self, review: CaptureReview) -> CaptureReceipt:
        if not review.is_clear:
            raise OmniFocusCaptureDuplicateError(
                "Duplicate protection has not cleared this OmniFocus capture."
            )
        proposal = review.proposal
        created = self._bridge.call("captureCreate", **_proposal_arguments(proposal))
        if not isinstance(created, dict):
            raise OmniFocusCaptureError("OmniFocus returned an invalid capture result.")
        if created.get("created") is not True:
            raise OmniFocusCaptureDuplicateError(
                "The final OmniFocus duplicate recheck blocked this capture."
            )
        task_id = created.get("id")
        if not isinstance(task_id, str) or not task_id:
            raise OmniFocusCaptureError("OmniFocus created no verifiable task identifier.")
        verified = self._bridge.call(
            "captureVerify",
            taskId=task_id,
            **_proposal_arguments(proposal),
        )
        valid = (
            isinstance(verified, dict)
            and verified.get("found") is True
            and verified.get("nameMatches") is True
            and verified.get("inInbox") is True
            and verified.get("completed") is False
            and verified.get("dropped") is False
            and verified.get("sourceVerified") is True
        )
        if not valid:
            raise OmniFocusCaptureError(
                "The task was created, but the independent read-back did not match. "
                f"Review omnifocus:///task/{task_id} manually."
            )
        return CaptureReceipt(
            proposal=proposal,
            task_id=task_id,
            item_url=f"omnifocus:///task/{task_id}",
            content_verified=True,
        )

    def retract(self, receipt: CaptureReceipt) -> CaptureRetraction:
        result = self._bridge.call(
            "captureRetract",
            taskId=receipt.task_id,
            **_proposal_arguments(receipt.proposal),
        )
        if not isinstance(result, dict):
            raise OmniFocusCaptureError("OmniFocus returned an invalid retraction result.")
        retraction = CaptureRetraction(
            task_id=str(result.get("taskId") or ""),
            completed=result.get("completed") is True,
            source_verified=result.get("sourceVerified") is True,
        )
        if (
            retraction.task_id != receipt.task_id
            or not retraction.completed
            or not retraction.source_verified
        ):
            raise OmniFocusCaptureError("The test capture could not be retracted safely.")
        return retraction


def format_capture_duplicate(review: CaptureReview) -> str:
    return (
        "No task was created because OmniFocus already contains a matching capture.\n\n"
        f"Source-reference matches: {review.source_matches}\n"
        f"Open title matches: {review.title_matches}\n\n"
        "Review the existing task separately before changing the proposed capture."
    )


class _CallbackState:
    def __init__(self, path: str, token: str) -> None:
        self.path = path
        self.token = token
        self.event = threading.Event()
        self.payload: dict[str, Any] | None = None
        self.error: str | None = None


def _handler_for(state: _CallbackState) -> type[BaseHTTPRequestHandler]:
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path != state.path or not hmac.compare_digest(
                self.headers.get("X-PEA-Token", ""), state.token
            ):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400)
                return
            if length <= 0 or length > MAX_CALLBACK_BYTES:
                self.send_error(413)
                return
            try:
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise TypeError("callback payload must be an object")
                state.payload = payload
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
                state.error = f"Invalid callback payload: {exc}"
                self.send_error(400)
                state.event.set()
                return
            self.send_response(204)
            self.end_headers()
            state.event.set()

        def log_message(self, format: str, *args: object) -> None:
            return

    return CallbackHandler


class OmniFocusCaptureBridge:
    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        launcher: Callable[[str], None] | None = None,
    ) -> None:
        self.timeout = timeout
        self._launcher = launcher or self._launch_url

    @staticmethod
    def _launch_url(url: str) -> None:
        try:
            subprocess.run(
                ["/usr/bin/open", "-g", url],
                check=True,
                timeout=5,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise OmniFocusCaptureError(f"Could not invoke OmniFocus: {exc}") from exc

    def call(self, operation: str, **parameters: Any) -> Any:
        if operation not in {
            "captureReview",
            "captureCreate",
            "captureVerify",
            "captureRetract",
        }:
            raise OmniFocusCaptureError("Unsupported controlled capture operation.")
        request_id = secrets.token_urlsafe(18)
        token = secrets.token_urlsafe(32)
        path = f"/omnifocus-capture/{request_id}"
        state = _CallbackState(path, token)
        server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            argument = {
                "operation": operation,
                "callback": f"http://127.0.0.1:{port}{path}",
                "token": token,
                **parameters,
            }
            query = urllib.parse.urlencode(
                {
                    "script": OMNIJS_CAPTURE_SCRIPT,
                    "arg": json.dumps(argument, ensure_ascii=False, separators=(",", ":")),
                },
                quote_via=urllib.parse.quote,
            )
            self._launcher(f"omnifocus://localhost/omnijs-run?{query}")
            if not state.event.wait(self.timeout):
                raise OmniFocusCaptureError(
                    "OmniFocus did not answer in time. Check that it is running, external scripts "
                    "are enabled and this reviewed capture script is approved."
                )
            if state.error:
                raise OmniFocusCaptureError(state.error)
            if state.payload is None:
                raise OmniFocusCaptureError("OmniFocus returned no callback payload.")
            if state.payload.get("ok") is not True:
                raise OmniFocusCaptureError(
                    str(state.payload.get("error") or "Unknown OmniFocus capture error.")
                )
            return state.payload.get("result")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)


def _proposal_arguments(proposal: CaptureProposal) -> dict[str, str]:
    return {
        "title": proposal.title,
        "titleKey": proposal.title_key,
        "sourceReference": proposal.source_reference,
        "fingerprint": proposal.fingerprint,
    }


def _count(result: Any, field: str) -> int:
    if not isinstance(result, dict):
        raise OmniFocusCaptureError("OmniFocus returned an invalid duplicate review.")
    value = result.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise OmniFocusCaptureError("OmniFocus returned an invalid duplicate count.")
    return value
