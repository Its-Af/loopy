#!/usr/bin/env python3
"""Tool-discovery MCP server.

Lets an agent ask "what can I do?" at runtime instead of memorising the CLI.
Backed by :mod:`tools.discovery`, which introspects the live code, so the answer
is always accurate.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp._common import Server  # noqa: E402

srv = Server("loopy-registry")


@srv.tool(
    "registry_list",
    "List every Loopy capability available to me: agent-tool.py CLI commands and "
    "the importable Python subsystems for subagents.",
    {"type": "object", "properties": {}},
)
def registry_list(args: dict) -> dict:
    from tools.discovery import catalog
    return catalog()


@srv.tool(
    "registry_describe",
    "Describe one capability by name (a CLI command or a subsystem module).",
    {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def registry_describe(args: dict) -> dict:
    from tools.discovery import describe
    info = describe(args["name"])
    return info or {"error": f"unknown capability: {args['name']}"}


if __name__ == "__main__":
    srv.run()
