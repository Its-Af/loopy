"""Agent state heartbeat."""

from __future__ import annotations

import time

from tools import state


def test_write_and_read_increments_loop():
    s = state.write_state("starting")
    assert s.loop == 0 and s.status == "starting"
    s2 = state.write_state("working")
    assert s2.loop == 1
    assert state.read_state("producers.1").status == "working"


def test_task_field_persists_across_loops():
    state.write_state("claimed", task="01ARZ3NDEKTSV4RRFFQ69G5FAV")
    # A later update without specifying task keeps the previous one.
    s = state.write_state("working")
    assert s.task == "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_read_missing_state_is_none(as_agent):
    as_agent("securities")
    assert state.read_state("securities") is None


def test_all_states_and_staleness(as_agent, monkeypatch):
    state.write_state("a", agent="execs")
    state.write_state("b", agent="qas")
    states = {s.agent: s for s in state.all_states()}
    assert set(states) == {"execs", "qas"}
    assert not states["execs"].stale

    # Force an old timestamp -> stale + flagged for respawn.
    old = state.read_state("execs")
    old.updated_at = time.time() - state.STALE_AFTER - 10
    from tools.file.atomic_write import atomic_write_text
    atomic_write_text(state.state_path("execs"), old.to_json())
    assert state.read_state("execs").stale
    assert "execs" in [s.agent for s in state.stale_agents()]
