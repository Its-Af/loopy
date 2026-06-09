"""Minimal MCP stdio server framework (standard library only).

Loopy ships its own tiny MCP server base so the framework keeps its
"no third-party runtime dependencies" promise — there is no need to install the
`mcp` SDK to expose these tools to Claude Code. It implements the subset of the
Model Context Protocol that Claude Code actually drives over stdio:

* JSON-RPC 2.0, one JSON object per line, over stdin/stdout;
* the ``initialize`` handshake and ``notifications/initialized``;
* ``tools/list`` and ``tools/call``;
* ``ping``.

A server is built by registering tools (name, description, JSON-schema, handler)
and calling :meth:`Server.run`.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from dataclasses import dataclass
from typing import Any, Callable

# Make tools.* importable regardless of how the server is launched.
_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRAMEWORK_DIR not in sys.path:
    sys.path.insert(0, _FRAMEWORK_DIR)

PROTOCOL_VERSION = "2024-11-05"

ToolHandler = Callable[[dict], Any]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: ToolHandler

    def spec(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class Server:
    def __init__(self, name: str, version: str = "0.1.0") -> None:
        self.name = name
        self.version = version
        self._tools: dict[str, Tool] = {}
        self._in = sys.stdin
        self._out = sys.stdout

    def tool(self, name: str, description: str, input_schema: dict | None = None):
        """Decorator to register a tool handler."""
        schema = input_schema or {"type": "object", "properties": {}}

        def deco(fn: ToolHandler) -> ToolHandler:
            self._tools[name] = Tool(name, description, schema, fn)
            return fn
        return deco

    # -- wire helpers -------------------------------------------------------
    def _send(self, obj: dict) -> None:
        self._out.write(json.dumps(obj) + "\n")
        self._out.flush()

    def _result(self, req_id: Any, result: dict) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _error(self, req_id: Any, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": code, "message": message}})

    # -- dispatch -----------------------------------------------------------
    def _handle(self, msg: dict) -> None:
        method = msg.get("method")
        req_id = msg.get("id")
        is_notification = req_id is None

        if method == "initialize":
            self._result(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": self.name, "version": self.version},
            })
        elif method == "notifications/initialized":
            return  # notification, no response
        elif method == "ping":
            self._result(req_id, {})
        elif method == "tools/list":
            self._result(req_id, {"tools": [t.spec() for t in self._tools.values()]})
        elif method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            args = params.get("arguments") or {}
            tool = self._tools.get(name)
            if tool is None:
                self._error(req_id, -32602, f"unknown tool: {name}")
                return
            try:
                out = tool.handler(args)
                text = out if isinstance(out, str) else json.dumps(out, default=str)
                self._result(req_id, {"content": [{"type": "text", "text": text}]})
            except Exception as exc:  # surface tool errors as MCP tool errors
                self._result(req_id, {
                    "content": [{"type": "text", "text": f"error: {exc}"}],
                    "isError": True,
                })
                traceback.print_exc(file=sys.stderr)
        elif is_notification:
            return  # ignore unknown notifications
        else:
            self._error(req_id, -32601, f"method not found: {method}")

    def run(self) -> None:
        for line in self._in:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._error(None, -32700, "parse error")
                continue
            try:
                self._handle(msg)
            except Exception as exc:  # never let one bad message kill the server
                self._error(msg.get("id"), -32603, f"internal error: {exc}")
                traceback.print_exc(file=sys.stderr)
