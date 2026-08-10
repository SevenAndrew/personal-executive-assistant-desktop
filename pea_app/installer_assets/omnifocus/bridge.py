"""Fixed read-only Omni Automation bridge used by the PEA OmniFocus MCP server."""

from __future__ import annotations

import hmac
import json
import secrets
import subprocess
import threading
import urllib.parse
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MAX_CALLBACK_BYTES = 2 * 1024 * 1024
DEFAULT_TIMEOUT = 10.0

OMNIJS_BRIDGE_SCRIPT = r"""
(async () => {
  const request = argument;
  const remaining = task => !task.completed && !task.dropped;
  const dateString = value => value ? value.toISOString() : null;
  const statusString = task =>
    String(task.taskStatus).match(/Task.Status: ([^\]]+)/)?.[1] || String(task.taskStatus);
  const taskRecord = task => ({
    id: task.id.primaryKey,
    name: task.name,
    project: task.containingProject ? task.containingProject.name : null,
    flagged: task.flagged,
    due: dateString(task.dueDate),
    defer: dateString(task.deferDate),
    status: statusString(task)
  });

  let result;
  if (request.operation === "status") {
    const open = flattenedTasks.filter(remaining);
    result = {
      application: app.name,
      version: app.userVersion.versionString,
      inbox: inbox.filter(remaining).length,
      projects: flattenedProjects.length,
      activeProjects: flattenedProjects.filter(project =>
        String(project.status).includes("Active")
      ).length,
      tags: flattenedTags.length,
      openTasks: open.length,
      availableOrNext: open.filter(task => ["Available", "Next"].includes(
        statusString(task)
      )).length,
      waiting: open.filter(task => task.tags.some(tag => tag.name === "(Waiting for)")).length,
      flagged: open.filter(task => task.flagged).length
    };
  } else if (request.operation === "tasks") {
    let tasks;
    if (request.view === "inbox") tasks = inbox.filter(remaining);
    else {
      tasks = flattenedTasks.filter(remaining);
      if (request.view === "available") {
        tasks = tasks.filter(task => ["Available", "Next"].includes(statusString(task)));
      } else if (request.view === "waiting") {
        tasks = tasks.filter(task => task.tags.some(tag => tag.name === "(Waiting for)"));
      } else if (request.view === "flagged") tasks = tasks.filter(task => task.flagged);
      else if (request.view !== "remaining") throw new Error("Unsupported task view");
    }
    result = tasks.slice(0, request.limit).map(taskRecord);
  } else {
    throw new Error("Unsupported bridge operation");
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


class BridgeError(RuntimeError):
    pass


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
            if not 0 < length <= MAX_CALLBACK_BYTES:
                self.send_error(413)
                return
            try:
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise TypeError("Callback payload must be an object.")
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


class OmniFocusBridge:
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
            raise BridgeError(f"Could not invoke OmniFocus: {exc}") from exc

    def call(self, operation: str, **parameters: Any) -> Any:
        request_id = secrets.token_urlsafe(18)
        token = secrets.token_urlsafe(32)
        path = f"/omnifocus-callback/{request_id}"
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
                    "script": OMNIJS_BRIDGE_SCRIPT,
                    "arg": json.dumps(argument, ensure_ascii=False, separators=(",", ":")),
                },
                quote_via=urllib.parse.quote,
            )
            self._launcher(f"omnifocus://localhost/omnijs-run?{query}")
            if not state.event.wait(self.timeout):
                raise BridgeError(
                    "OmniFocus did not answer in time. Keep it open, enable external scripts and "
                    "approve only the reviewed read-only bridge."
                )
            if state.error:
                raise BridgeError(state.error)
            if state.payload is None:
                raise BridgeError("OmniFocus returned no callback payload.")
            if not state.payload.get("ok"):
                raise BridgeError(str(state.payload.get("error", "Unknown OmniFocus error")))
            return state.payload.get("result")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
