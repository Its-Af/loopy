"""Agent memory: briefings, decisions, rotation."""

from __future__ import annotations

import time

from tools import memory
from tools.memory import core


def test_briefing_roundtrip_and_freshness():
    assert memory.briefing_stale("producers.1") is True   # none yet
    memory.write_briefing("I own the auth module.", agent="producers.1")
    b = memory.read_briefing("producers.1")
    assert b.text == "I own the auth module."
    assert not b.stale
    assert memory.briefing_stale("producers.1") is False


def test_briefing_goes_stale(monkeypatch):
    memory.write_briefing("old briefing", agent="producers.1")
    monkeypatch.setattr(core, "BRIEFING_TTL", -1)   # everything is stale now
    assert memory.briefing_stale("producers.1") is True


def test_record_and_read_decisions():
    memory.record_decision("Chose bcrypt", agent="producers.1",
                           rationale="salted + slow")
    memory.record_decision("Added rate limit", agent="producers.1")
    decisions = memory.read_decisions("producers.1")
    assert len(decisions) == 2
    assert decisions[0]["summary"] == "Chose bcrypt"
    assert decisions[0]["rationale"] == "salted + slow"


def test_decisions_limit():
    for i in range(10):
        memory.record_decision(f"d{i}", agent="producers.1")
    last3 = memory.read_decisions("producers.1", limit=3)
    assert [d["summary"] for d in last3] == ["d7", "d8", "d9"]


def test_rotation_bounds_the_log(monkeypatch):
    monkeypatch.setattr(core, "MAX_DECISIONS", 10)
    monkeypatch.setattr(core, "ROTATE_KEEP", 5)
    for i in range(15):
        memory.record_decision(f"d{i}", agent="producers.1")
    kept = memory.read_decisions("producers.1")
    assert len(kept) <= 10
    # The most recent decisions survive rotation.
    assert kept[-1]["summary"] == "d14"
