#!/usr/bin/env python3
"""Tmux-control MCP server — lets an agent observe and nudge the squad's panes.

Exposes read-mostly tmux operations: list the squad's windows, capture a pane's
recent output (to see what a teammate is doing), and send a wake. Deliberately
narrow — it cannot kill panes or run arbitrary keys, only the safe coordination
primitives. Wakes prefer the message bus and fall back to ``tmux send-keys``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp._common import Server  # noqa: E402

srv = Server("loopy-tmux")

_TMUX = shutil.which("tmux") or "tmux"


def _session() -> str:
    import os
    return os.environ.get("LOOPY_SESSION", "loopy")


def _run(*args: str) -> tuple[int, str]:
    try:
        p = subprocess.run([_TMUX, *args], capture_output=True, text=True, timeout=5)
        return p.returncode, (p.stdout or p.stderr)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)


@srv.tool(
    "tmux_list_windows",
    "List the windows (one per agent) in the Loopy tmux session.",
    {"type": "object", "properties": {}},
)
def tmux_list_windows(args: dict) -> dict:
    rc, out = _run("list-windows", "-t", _session(), "-F", "#W")
    if rc != 0:
        return {"running": False, "windows": []}
    return {"running": True, "windows": [w for w in out.split() if w]}


@srv.tool(
    "tmux_capture",
    "Capture the recent visible output of an agent's pane, to see what it is "
    "currently doing. Read-only.",
    {
        "type": "object",
        "properties": {
            "agent": {"type": "string", "description": "agent id whose pane to capture"},
            "lines": {"type": "integer", "description": "how many trailing lines (default 40)"},
        },
        "required": ["agent"],
    },
)
def tmux_capture(args: dict) -> dict:
    agent = args["agent"]
    target = f"{_session()}:{agent.replace('.', '-')}"
    rc, out = _run("capture-pane", "-p", "-t", target)
    if rc != 0:
        return {"ok": False, "error": out.strip()}
    n = int(args.get("lines", 40))
    tail = "\n".join(out.splitlines()[-n:])
    return {"ok": True, "agent": agent, "output": tail}


@srv.tool(
    "tmux_wake",
    "Wake an agent so it loops now instead of on its next tick. Uses the message "
    "bus when available, else tmux send-keys.",
    {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "agent id to wake"},
            "shared": {"type": "boolean", "description": "wake all instances of the role"},
        },
        "required": ["target"],
    },
)
def tmux_wake(args: dict) -> dict:
    from tools.message.notify_quick import wake
    ok = wake(args["target"], shared=bool(args.get("shared", False)))
    return {"woke": ok, "via": "bus" if ok else "none"}


if __name__ == "__main__":
    srv.run()
