"""Subagent results, latency metrics, and the capacity gate."""

from __future__ import annotations

import time

from tools import results, metrics
from tools.capacity import Capacity, check


# --- results ---------------------------------------------------------------
def test_post_and_pop_results():
    results.post_result("execs", "build", ok=True, summary="green")
    results.post_result("execs", "test", ok=False, summary="3 failures")
    assert results.pending_count("execs") == 2
    got = results.read_results("execs")
    assert len(got) == 2 and results.pending_count("execs") == 0
    assert {r.kind for r in got} == {"build", "test"}
    assert any(not r.ok for r in got)


def test_results_peek_does_not_consume():
    results.post_result("execs", "review", summary="LGTM")
    assert len(results.read_results("execs", consume=False)) == 1
    assert results.pending_count("execs") == 1


def test_reserve_result_path_then_fill():
    rid, path = results.reserve_result_path("execs", "implement")
    assert not path.exists()
    path.write_text('{"id": "%s", "parent": "execs", "kind": "implement", '
                    '"ok": true, "summary": "done"}' % rid)
    got = results.read_results("execs")
    assert len(got) == 1 and got[0].summary == "done"


def test_results_carry_payload():
    results.post_result("execs", "scan", payload={"vulns": 2}, summary="found 2")
    r = results.read_results("execs")[0]
    assert r.payload == {"vulns": 2}


# --- metrics ---------------------------------------------------------------
def test_measure_records_sample():
    with metrics.measure("loop", agent="producers.1"):
        time.sleep(0.01)
    st = metrics.summarize("loop")
    assert st is not None and st.count == 1
    assert st.max_ms >= 10


def test_over_budget_counted():
    metrics.record("loop", 70_000, agent="producers.1")     # 70s > 60s budget
    metrics.record("loop", 100, agent="producers.1")
    st = metrics.summarize("loop")
    assert st.count == 2 and st.over_budget == 1


def test_summarize_unknown_kind_is_none():
    assert metrics.summarize("does-not-exist") is None


def test_percentiles_ordering():
    for v in [10, 20, 30, 40, 1000]:
        metrics.record("x", v)
    st = metrics.summarize("x")
    assert st.p50_ms <= st.p95_ms <= st.max_ms


# --- capacity --------------------------------------------------------------
def test_capacity_returns_verdict():
    cap = check("execs")
    assert isinstance(cap, Capacity)
    assert cap.verdict in ("CLEAR", "WAIT")
    assert "verdict" in cap.as_dict()


def test_capacity_waits_when_inflight_high():
    # Two in-flight subagent results trip the default max-inflight gate.
    results.post_result("execs", "a")
    results.post_result("execs", "b")
    cap = check("execs", max_inflight=2)
    assert not cap.clear
    assert "in flight" in cap.reason


def test_capacity_clear_with_headroom():
    cap = check("execs", max_claude=100000, max_inflight=100,
                max_load_per_cpu=100000)
    assert cap.clear
