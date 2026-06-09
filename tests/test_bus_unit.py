"""Unit tests for the bus client (frame construction) and broker routing.

These cover the logic that the live-socket integration test in test_bus.py can't
easily assert byte-for-byte: the exact wake frames the client emits, and how the
broker resolves a frame to target agents.
"""

from __future__ import annotations

import json

from tools.message import notify_quick as nq
from tools.message.notify_quick import OP_MULTICAST, OP_UNICAST, WILDCARD
from tools.validation.constants import ROLE_INDEX


def _capture_frames(monkeypatch):
    frames = []
    monkeypatch.setattr(nq, "_send_frame",
                        lambda role, frame: (frames.append(frame), True)[1])
    return frames


# --- client frame construction --------------------------------------------
def test_unicast_frame_for_specific_instance(monkeypatch):
    frames = _capture_frames(monkeypatch)
    assert nq.wake("producers.2") is True
    assert frames == [OP_UNICAST + bytes([ROLE_INDEX["producers"], 2])]


def test_singleton_wakes_all_instances(monkeypatch):
    frames = _capture_frames(monkeypatch)
    nq.wake("alfred")           # no instance -> wildcard instance
    assert frames[0] == OP_UNICAST + bytes([ROLE_INDEX["alfred"], WILDCARD])


def test_shared_uses_wildcard_instance(monkeypatch):
    frames = _capture_frames(monkeypatch)
    nq.wake("producers", shared=True)
    assert frames[0] == OP_UNICAST + bytes([ROLE_INDEX["producers"], WILDCARD])


def test_broadcast_frame(monkeypatch):
    frames = _capture_frames(monkeypatch)
    nq.broadcast()
    assert frames[0] == OP_UNICAST + bytes([WILDCARD, WILDCARD])


def test_multicast_frame(monkeypatch):
    frames = _capture_frames(monkeypatch)
    nq.wake_roles(["producers", "qas"])
    assert frames[0] == (OP_MULTICAST + bytes([2])
                         + bytes([ROLE_INDEX["producers"], ROLE_INDEX["qas"]]))


def test_send_frame_without_socket_returns_false():
    # No broker running and no token -> best-effort returns False, never raises.
    assert nq.wake("execs") is False


def test_load_token_prefers_env(monkeypatch):
    monkeypatch.setenv("LOOPY_BUS_TOKEN", "envtoken")
    assert nq.load_token("execs") == "envtoken"


def test_load_token_from_file():
    from tools.project_root import runtime_dir
    from tools.file.atomic_write import atomic_write_text
    atomic_write_text(runtime_dir() / "bus" / "tokens" / "execs.token", "filetok\n")
    assert nq.load_token("execs") == "filetok"


# --- broker routing --------------------------------------------------------
def test_broker_resolves_targets():
    from daemons.bus_broker import Broker
    b = Broker()
    prod = ROLE_INDEX["producers"]
    assert b._resolve_targets(prod, 2) == ["producers.2"]
    assert b._resolve_targets(prod, WILDCARD) == ["producers.1", "producers.2",
                                                   "producers.3"]
    assert b._resolve_targets(ROLE_INDEX["execs"], 1) == ["execs"]
    everyone = b._resolve_targets(WILDCARD, WILDCARD)
    assert "execs" in everyone and "users" in everyone and len(everyone) >= 9
    assert b._resolve_targets(99, 1) == []      # unknown role index


def test_broker_instances_from_pane_map():
    from daemons.bus_broker import Broker
    from tools.project_root import runtime_dir
    from tools.file.atomic_write import atomic_write_text
    atomic_write_text(runtime_dir() / "panes.json",
                      json.dumps({"producers.1": "loopy:producers-1",
                                  "producers.5": "loopy:producers-5"}))
    b = Broker()
    b.load_panes()
    # When a pane map exists it is authoritative for that role.
    assert set(b._instances_for_role("producers")) == {"producers.1", "producers.5"}


def test_broker_generate_tokens_and_status():
    from daemons.bus_broker import Broker
    from tools.project_root import runtime_dir
    b = Broker()
    b.generate_tokens()
    tok = (runtime_dir() / "bus" / "tokens" / "execs.token")
    assert tok.exists() and tok.read_text().strip() == b.tokens["execs"]
    st = b.status()
    for key in ("pid", "uptime_s", "wakes_sent", "auth_failures", "roster"):
        assert key in st
