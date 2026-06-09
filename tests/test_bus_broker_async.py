"""In-process async tests of the broker's connection handling.

Drives Broker.handle() with asyncio StreamReader fakes so the auth handshake,
frame dispatch, per-pane debounce, and per-connection rate limit are exercised
directly (the live socket test in test_bus.py covers the same paths end-to-end,
but in a subprocess coverage can't see).
"""

from __future__ import annotations

import asyncio

from daemons.bus_broker import Broker
from tools.message.notify_quick import AUTH_OK, OP_UNICAST, WILDCARD
from tools.validation.constants import ROLE_INDEX


class _FakeWriter:
    def __init__(self):
        self.buf = b""
        self.closed = False

    def write(self, data):
        self.buf += data

    async def drain(self):
        pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


async def _serve(broker, payload, wake_sink):
    async def fake_wake(agent):
        wake_sink.append(agent)
    broker._wake_agent = fake_wake          # type: ignore[assignment]
    reader = asyncio.StreamReader()
    reader.feed_data(payload)
    reader.feed_eof()
    writer = _FakeWriter()
    await broker.handle(reader, writer)
    return writer


def test_auth_then_unicast_routes():
    async def run():
        b = Broker(); b.generate_tokens()
        woken: list[str] = []
        frame = OP_UNICAST + bytes([ROLE_INDEX["producers"], 1])
        w = await _serve(b, f"execs:{b.tokens['execs']}\n".encode() + frame, woken)
        assert w.buf[:1] == bytes([AUTH_OK])     # ack starts with AUTH_OK
        assert woken == ["producers.1"]
        assert w.closed
    asyncio.run(run())


def test_bad_token_rejected_no_ack():
    async def run():
        b = Broker(); b.generate_tokens()
        woken: list[str] = []
        w = await _serve(b, b"execs:wrongtoken\nW\x02\x01", woken)
        assert w.buf == b""                       # no ack on auth failure
        assert b.auth_failures == 1
        assert woken == []
    asyncio.run(run())


def test_broadcast_frame_wakes_everyone():
    async def run():
        b = Broker(); b.generate_tokens()
        woken: list[str] = []
        frame = OP_UNICAST + bytes([WILDCARD, WILDCARD])
        await _serve(b, f"alfred:{b.tokens['alfred']}\n".encode() + frame, woken)
        assert "execs" in woken and "producers.1" in woken and len(woken) >= 9
    asyncio.run(run())


def test_rate_limit_drops_flooding_connection():
    async def run():
        b = Broker(); b.generate_tokens()
        woken: list[str] = []
        # 40 unicast frames in one burst -> exceeds 10/s -> connection dropped.
        flood = (OP_UNICAST + bytes([ROLE_INDEX["qas"], 0xFF])) * 40
        await _serve(b, f"execs:{b.tokens['execs']}\n".encode() + flood, woken)
        # It processed some frames before the limiter cut it off, not all 40.
        assert b.frames_seen <= 11
    asyncio.run(run())


def test_wake_agent_debounce():
    async def run():
        b = Broker()
        await b._wake_agent("execs")
        await b._wake_agent("execs")              # within 5s -> debounced
        assert b.wakes_sent == 1 and b.wakes_debounced == 1
    asyncio.run(run())


def test_tmux_send_without_tmux_is_silent(monkeypatch):
    async def run():
        monkeypatch.setattr("daemons.bus_broker.TMUX", "definitely-not-a-binary")
        b = Broker()
        await b._tmux_send("loopy:execs")         # must not raise
    asyncio.run(run())
