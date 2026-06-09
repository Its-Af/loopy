"""Message bus: target resolution (unit) and live wake dispatch (integration)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

FRAMEWORK_DIR = Path(__file__).resolve().parents[1]


# --- unit: target resolution ----------------------------------------------
def test_resolve_targets_unicast_and_wildcards():
    from daemons.bus_broker import Broker
    from tools.message.notify_quick import WILDCARD
    from tools.validation.constants import ROLE_INDEX

    b = Broker()
    prod = ROLE_INDEX["producers"]
    # Specific producers instance.
    assert b._resolve_targets(prod, 2) == ["producers.2"]
    # All producers instances (wildcard instance) -> from default roster (3).
    assert b._resolve_targets(prod, WILDCARD) == ["producers.1", "producers.2",
                                                   "producers.3"]
    # Singleton role addressed by bare name.
    assert b._resolve_targets(ROLE_INDEX["execs"], 1) == ["execs"]
    # Full broadcast covers every role.
    everyone = b._resolve_targets(WILDCARD, WILDCARD)
    assert "execs" in everyone and "producers.1" in everyone and "users" in everyone


# --- integration: live broker ---------------------------------------------
def _wait_for(path: str, timeout=5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(path):
            return True
        time.sleep(0.02)
    return False


@pytest.mark.slow
def test_live_wake_dispatch(isolated_runtime, tmp_path):
    root = str(isolated_runtime)
    # macOS caps AF_UNIX paths at ~104 chars and pytest's tmp_path is long, so
    # use the LOOPY_BUS_SOCK override with a short path (the documented escape
    # hatch for deeply-nested project roots).
    import tempfile
    sock = os.path.join(tempfile.gettempdir(), f"loopy-bus-{os.getpid()}.sock")
    env = dict(os.environ, LOOPY_PROJECT_ROOT=root, LOOPY_BUS_SOCK=sock)
    proc = subprocess.Popen(
        [sys.executable, str(FRAMEWORK_DIR / "daemons" / "bus_broker.py")],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_for(sock), "broker socket never appeared"
        tok = Path(f"{root}/.loopy/bus/tokens/execs.token").read_text().strip()

        # Authenticate and unicast-wake producers.1.
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(sock)
        s.sendall(f"execs:{tok}\n".encode())
        ack = s.recv(3)
        assert ack and ack[0] == 0x01            # AUTH_OK
        from tools.validation.constants import ROLE_INDEX
        s.sendall(b"W" + bytes([ROLE_INDEX["producers"], 1]))
        s.close()

        assert _wait_for(f"{root}/.loopy/wake/producers.1", 3.0), \
            "wake marker not created"

        # A bad token gets no ack.
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(sock)
        s.sendall(b"execs:wrong\n")
        assert s.recv(3) == b""
        s.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Socket cleaned up + final status flushed on shutdown.
    assert not os.path.exists(sock)
    status = json.loads(Path(f"{root}/.loopy/bus-status.json").read_text())
    assert status["wakes_sent"] >= 1
    assert status["auth_failures"] >= 1
