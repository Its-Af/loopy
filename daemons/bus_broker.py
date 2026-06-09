#!/usr/bin/env python3
"""Message bus broker — instant inter-agent wake notifications.

The bus is a latency optimisation, never a correctness dependency: every agent
still polls its inbox each loop, so if the bus is down the only cost is that a
message waits until the next tick instead of arriving "now". That framing keeps
the broker simple and lets it fail safe.

Architecture
------------
An asyncio server listens on a Unix-domain socket (``.loopy/bus.sock``). A
client (see :mod:`tools.message.notify_quick`) connects, authenticates with its
per-role token, and sends a tiny binary *wake frame* naming a target. The
broker resolves the target to one or more tmux panes and nudges each with
``tmux send-keys`` (and always drops a ``.loopy/wake/<agent>`` marker as a
tmux-independent fallback).

Wire protocol
-------------
Auth   : ``ROLE:TOKEN\\n``  ->  3-byte ack ``[AUTH_OK, role_index, version]``
Unicast: ``W`` + role(1) + instance(1)        (0xFF = wildcard)
Multi  : ``M`` + count(1) + role_index*count
Bcast  : ``W`` + 0xFF + 0xFF

Safety valves
-------------
* **Auth** — tokens are regenerated every startup and written 0600; an
  unauthenticated or wrong-token connection is dropped.
* **Per-connection rate limit** — at most ``MAX_FRAMES_PER_SEC`` frames/s.
* **Per-target debounce** — a given pane is woken at most once per
  ``DEBOUNCE_SECONDS`` no matter how many senders ask.
* **Graceful shutdown** — SIGTERM/SIGINT close the listener, remove the socket,
  and flush a final status file.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import signal
import sys
import time
from pathlib import Path

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRAMEWORK_DIR not in sys.path:
    sys.path.insert(0, _FRAMEWORK_DIR)

from tools.file.atomic_write import atomic_write_text  # noqa: E402
from tools.message.notify_quick import (  # noqa: E402
    AUTH_OK,
    OP_MULTICAST,
    OP_UNICAST,
    PROTOCOL_VERSION,
    WILDCARD,
)
from tools.project_root import bus_socket_path, runtime_dir  # noqa: E402
from tools.validation.constants import (  # noqa: E402
    DEFAULT_ROSTER,
    ROLE_ORDER,
)

DEBOUNCE_SECONDS = 5.0
MAX_FRAMES_PER_SEC = 10
STATUS_INTERVAL = 5.0
AUTH_TIMEOUT = 3.0
MAX_AUTH_LINE = 256
WAKE_KEYS = os.environ.get("LOOPY_WAKE_KEYS", "Enter")
TMUX = os.environ.get("LOOPY_TMUX", "tmux")


def _index_to_role(idx: int) -> str | None:
    return ROLE_ORDER[idx] if 0 <= idx < len(ROLE_ORDER) else None


class Broker:
    def __init__(self) -> None:
        self.sock_path = Path(bus_socket_path())
        self.runtime = runtime_dir()
        self.tokens: dict[str, str] = {}
        self.token_by_value: dict[str, str] = {}
        self.panes: dict[str, str] = {}
        self._panes_mtime = 0.0
        self._last_wake: dict[str, float] = {}     # agent_id -> ts (debounce)
        self.started = time.time()
        self.wakes_sent = 0
        self.wakes_debounced = 0
        self.frames_seen = 0
        self.auth_failures = 0
        self.connections = 0
        self._server: asyncio.AbstractServer | None = None
        self._stopping = asyncio.Event()

    # -- setup --------------------------------------------------------------
    def generate_tokens(self) -> None:
        tdir = self.runtime / "bus" / "tokens"
        tdir.mkdir(parents=True, exist_ok=True)
        os.chmod(tdir, 0o700)
        for role in ROLE_ORDER:
            tok = secrets.token_hex(16)
            self.tokens[role] = tok
            self.token_by_value[tok] = role
            path = tdir / f"{role}.token"
            atomic_write_text(path, tok + "\n", mode=0o600)
            os.chmod(path, 0o600)

    def load_panes(self) -> None:
        """(Re)load the agent->tmux-pane map written by the launcher."""
        path = self.runtime / "panes.json"
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            self.panes = {}
            return
        if mtime == self._panes_mtime:
            return
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                self.panes = {str(k): str(v) for k, v in data.items()}
                self._panes_mtime = mtime
        except (json.JSONDecodeError, OSError):
            pass

    def _instances_for_role(self, role: str) -> list[str]:
        """Live agent ids for a role: from the pane map, else the roster."""
        from_map = [a for a in self.panes if a == role or a.startswith(f"{role}.")]
        if from_map:
            return from_map
        count = DEFAULT_ROSTER.get(role, 1)
        if count <= 1:
            return [role]
        return [f"{role}.{i}" for i in range(1, count + 1)]

    # -- dispatch -----------------------------------------------------------
    def _resolve_targets(self, role_idx: int, instance: int) -> list[str]:
        if role_idx == WILDCARD:                       # broadcast to everyone
            targets: list[str] = []
            for role in ROLE_ORDER:
                targets.extend(self._instances_for_role(role))
            return targets
        role = _index_to_role(role_idx)
        if role is None:
            return []
        if instance == WILDCARD:                       # all instances of role
            return self._instances_for_role(role)
        # Specific instance. Singleton roles are addressed by bare role name.
        if DEFAULT_ROSTER.get(role, 1) <= 1:
            return [role]
        return [f"{role}.{instance}"]

    async def _wake_agent(self, agent: str) -> None:
        now = time.time()
        last = self._last_wake.get(agent, 0.0)
        if now - last < DEBOUNCE_SECONDS:
            self.wakes_debounced += 1
            return
        self._last_wake[agent] = now
        self.wakes_sent += 1
        # Fallback marker first (always works, tmux or not).
        try:
            wdir = self.runtime / "wake"
            wdir.mkdir(parents=True, exist_ok=True)
            (wdir / agent).write_text(f"{now:.3f}\n")
        except OSError:
            pass
        # tmux nudge if we know the pane.
        pane = self.panes.get(agent)
        if pane:
            await self._tmux_send(pane)

    async def _tmux_send(self, pane: str) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                TMUX, "send-keys", "-t", pane, WAKE_KEYS,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except (OSError, asyncio.TimeoutError, FileNotFoundError):
            pass

    # -- connection handling ------------------------------------------------
    async def handle(self, reader: asyncio.StreamReader,
                     writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        peer_role: str | None = None
        try:
            # Authenticate.
            try:
                line = await asyncio.wait_for(reader.readline(), AUTH_TIMEOUT)
            except asyncio.TimeoutError:
                return
            if not line or len(line) > MAX_AUTH_LINE:
                return
            try:
                role, _, token = line.decode("utf-8", "strict").strip().partition(":")
            except UnicodeDecodeError:
                return
            if self.tokens.get(role) != token or not token:
                self.auth_failures += 1
                return
            peer_role = role
            role_idx = ROLE_ORDER.index(role)
            writer.write(bytes([AUTH_OK, role_idx & 0xFF, PROTOCOL_VERSION]))
            await writer.drain()

            # Serve frames with a per-connection rate limit.
            window_start = time.monotonic()
            window_count = 0
            while not self._stopping.is_set():
                op = await reader.readexactly(1)
                now = time.monotonic()
                if now - window_start >= 1.0:
                    window_start, window_count = now, 0
                window_count += 1
                if window_count > MAX_FRAMES_PER_SEC:
                    return  # abusive client; drop the connection
                self.frames_seen += 1
                await self._dispatch_frame(op, reader)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (OSError, ConnectionError):
                pass

    async def _dispatch_frame(self, op: bytes, reader: asyncio.StreamReader) -> None:
        if op == OP_UNICAST:
            body = await reader.readexactly(2)
            self.load_panes()
            for agent in self._resolve_targets(body[0], body[1]):
                await self._wake_agent(agent)
        elif op == OP_MULTICAST:
            count = (await reader.readexactly(1))[0]
            indices = await reader.readexactly(count) if count else b""
            self.load_panes()
            for idx in indices:
                for agent in self._resolve_targets(idx, WILDCARD):
                    await self._wake_agent(agent)
        # Unknown opcodes are ignored (forward-compatible).

    # -- status + lifecycle -------------------------------------------------
    def status(self) -> dict:
        return {
            "pid": os.getpid(),
            "socket": str(self.sock_path),
            "uptime_s": round(time.time() - self.started, 1),
            "connections": self.connections,
            "frames_seen": self.frames_seen,
            "wakes_sent": self.wakes_sent,
            "wakes_debounced": self.wakes_debounced,
            "auth_failures": self.auth_failures,
            "known_panes": len(self.panes),
            "roster": list(ROLE_ORDER),
            "updated_at": round(time.time(), 1),
        }

    def write_status(self) -> None:
        try:
            atomic_write_text(self.runtime / "bus-status.json",
                              json.dumps(self.status(), indent=2))
        except OSError:
            pass

    async def _status_loop(self) -> None:
        while not self._stopping.is_set():
            self.write_status()
            try:
                await asyncio.wait_for(self._stopping.wait(), STATUS_INTERVAL)
            except asyncio.TimeoutError:
                continue

    async def run(self) -> None:
        self.generate_tokens()
        self.load_panes()
        # Remove a stale socket from a previous crash.
        if self.sock_path.exists():
            self.sock_path.unlink()
        self.sock_path.parent.mkdir(parents=True, exist_ok=True)
        self._server = await asyncio.start_unix_server(self.handle,
                                                       path=str(self.sock_path))
        os.chmod(self.sock_path, 0o600)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._stopping.set)
            except NotImplementedError:  # pragma: no cover - non-unix
                pass

        status_task = asyncio.create_task(self._status_loop())
        print(f"loopy-bus: listening on {self.sock_path} (pid {os.getpid()})",
              flush=True)
        async with self._server:
            await self._stopping.wait()

        # Graceful shutdown.
        self._server.close()
        await self._server.wait_closed()
        status_task.cancel()
        self.write_status()
        try:
            self.sock_path.unlink()
        except FileNotFoundError:
            pass
        print("loopy-bus: shut down cleanly", flush=True)


def main() -> int:
    try:
        asyncio.run(Broker().run())
    except KeyboardInterrupt:  # pragma: no cover
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
