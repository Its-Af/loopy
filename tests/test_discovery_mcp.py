"""Tool discovery + the from-scratch MCP stdio server."""

from __future__ import annotations

import io
import json

from tools import discovery


# --- discovery -------------------------------------------------------------
def test_cli_commands_introspected():
    cmds = {c.name for c in discovery.cli_commands()}
    # A representative sample of the real CLI surface.
    for expected in ("write-state", "read-inbox", "send-message", "task",
                     "capacity", "regen-todo"):
        assert expected in cmds


def test_catalog_shape():
    cat = discovery.catalog()
    assert cat["cli"] and cat["subsystems"]
    assert all({"name", "kind", "summary"} <= set(c) for c in cat["cli"])


def test_describe_known_and_unknown():
    assert discovery.describe("capacity")["kind"] == "cli"
    assert discovery.describe("tools.message")["kind"] == "subsystem"
    assert discovery.describe("nope") is None


# --- MCP server ------------------------------------------------------------
def _drive(server, *messages) -> list[dict]:
    """Feed JSON-RPC messages through a server and collect its responses."""
    server._in = io.StringIO("\n".join(json.dumps(m) for m in messages) + "\n")
    server._out = io.StringIO()
    server.run()
    out = server._out.getvalue().strip()
    return [json.loads(line) for line in out.splitlines() if line]


def _build_server():
    from mcp._common import Server
    s = Server("test-srv")

    @s.tool("echo", "echo back", {"type": "object",
                                   "properties": {"x": {"type": "string"}}})
    def _echo(args):
        return {"echoed": args.get("x")}

    @s.tool("boom", "always fails")
    def _boom(args):
        raise ValueError("kaboom")

    return s


def test_initialize_handshake():
    s = _build_server()
    out = _drive(s, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {}})
    assert out[0]["result"]["serverInfo"]["name"] == "test-srv"
    assert "protocolVersion" in out[0]["result"]


def test_tools_list_and_call():
    s = _build_server()
    out = _drive(
        s,
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"x": "hi"}}},
    )
    names = {t["name"] for t in out[0]["result"]["tools"]}
    assert names == {"echo", "boom"}
    payload = json.loads(out[1]["result"]["content"][0]["text"])
    assert payload == {"echoed": "hi"}


def test_notification_produces_no_response():
    s = _build_server()
    out = _drive(s, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert out == []        # notifications (no id) get no reply


def test_unknown_tool_is_error():
    s = _build_server()
    out = _drive(s, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                     "params": {"name": "ghost", "arguments": {}}})
    assert out[0]["error"]["code"] == -32602


def test_tool_exception_becomes_iserror():
    s = _build_server()
    out = _drive(s, {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                     "params": {"name": "boom", "arguments": {}}})
    assert out[0]["result"]["isError"] is True
    assert "kaboom" in out[0]["result"]["content"][0]["text"]


def test_unknown_method_is_method_not_found():
    s = _build_server()
    out = _drive(s, {"jsonrpc": "2.0", "id": 7, "method": "does/not/exist"})
    assert out[0]["error"]["code"] == -32601
