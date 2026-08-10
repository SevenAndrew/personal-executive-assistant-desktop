"""Two-tool read-only OmniFocus MCP server installed by the PEA setup assistant."""

from __future__ import annotations

import json

from bridge import BridgeError, OmniFocusBridge
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

mcp = FastMCP("pea-omnifocus-read-only")
bridge = OmniFocusBridge()


def _response(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _call(operation: str, **parameters: object) -> str:
    try:
        return _response({"ok": True, "result": bridge.call(operation, **parameters)})
    except BridgeError as exc:
        return _response({"ok": False, "error": str(exc)})


@mcp.tool(
    annotations=ToolAnnotations(
        title="Check local OmniFocus status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def omnifocus_status() -> str:
    """Return aggregate GTD counts without task titles, notes or person names."""
    return _call("status")


@mcp.tool(
    annotations=ToolAnnotations(
        title="List bounded OmniFocus task metadata",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def omnifocus_list_tasks(view: str = "available", limit: int = 50) -> str:
    """Return task title, project, effective status, dates and flag only."""
    if view not in {"inbox", "available", "waiting", "flagged", "remaining"}:
        return _response({"ok": False, "error": "Unsupported task view."})
    return _call("tasks", view=view, limit=max(1, min(limit, 100)))


if __name__ == "__main__":
    mcp.run(transport="stdio")
