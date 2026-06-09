"""Task store: CRUD, the claim compare-and-set, dependencies, reopen."""

from __future__ import annotations

import multiprocessing as mp

import pytest

from tools.task import crud
from tools.validation import ValidationError


def test_create_and_read():
    t = crud.create_task("Build login", priority="P0", created_by="execs",
                         tags=["auth", "ui"])
    got = crud.read_task(t.id)
    assert got.title == "Build login"
    assert got.priority == "P0"
    assert got.state == "OPEN"
    assert got.tags == ["auth", "ui"]
    assert got.history[0]["event"] == "created"


def test_create_requires_title():
    with pytest.raises(ValidationError):
        crud.create_task("   ")


def test_list_is_time_sorted():
    ids = [crud.create_task(f"t{i}").id for i in range(4)]
    assert [t.id for t in crud.list_tasks()] == sorted(ids)


def test_claim_is_compare_and_set():
    t = crud.create_task("x")
    assert crud.claim_task(t.id, "producers.1").owner == "producers.1"
    assert crud.claim_task(t.id, "producers.2") is None       # already claimed
    assert crud.read_task(t.id).owner == "producers.1"


def test_release_returns_to_pool():
    t = crud.create_task("x")
    crud.claim_task(t.id, "producers.1")
    crud.release_task(t.id, "producers.1")
    assert crud.read_task(t.id).owner is None
    assert crud.claim_task(t.id, "producers.2").owner == "producers.2"


def test_release_only_by_owner():
    t = crud.create_task("x")
    crud.claim_task(t.id, "producers.1")
    with pytest.raises(ValidationError):
        crud.release_task(t.id, "producers.2")


def test_complete_and_reopen():
    t = crud.create_task("x")
    crud.claim_task(t.id, "producers.1")
    crud.complete_task(t.id, "producers.1", note="shipped")
    assert crud.read_task(t.id).is_done
    crud.reopen_task(t.id, "critics", reason="still broken")
    reopened = crud.read_task(t.id)
    assert reopened.state == "REOPENED" and reopened.owner is None


def test_dependency_gating():
    dep = crud.create_task("dependency")
    t = crud.create_task("downstream", blocked_by=[dep.id])
    assert crud.claim_task(t.id, "producers.1") is None     # blocked
    crud.complete_task(dep.id, "producers.2")
    assert crud.claim_task(t.id, "producers.1") is not None  # now free


def test_update_fields():
    t = crud.create_task("x", priority="P3")
    crud.update_task(t.id, actor="execs", priority="P1", state="BLOCKED",
                     note="waiting on infra")
    got = crud.read_task(t.id)
    assert got.priority == "P1" and got.state == "BLOCKED"
    assert any(h["event"] == "updated" for h in got.history)


def test_read_missing_task_raises():
    with pytest.raises(KeyError):
        crud.read_task("01ARZ3NDEKTSV4RRFFQ69G5FAV")


# --- real-concurrency claim race ------------------------------------------
def _claim_worker(root, agent_id, task_ids, q):
    import os
    os.environ["LOOPY_PROJECT_ROOT"] = root
    from tools.project_root import reset_cache
    reset_cache()
    from tools.task import crud as c
    won = [tid for tid in task_ids if c.claim_task(tid, agent_id) is not None]
    q.put(won)


@pytest.mark.slow
def test_concurrent_claims_never_double(isolated_runtime):
    root = str(isolated_runtime)
    ids = [crud.create_task(f"t{i}").id for i in range(8)]
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    # Each worker is a *distinct* agent id — in production no two callers ever
    # share an id, and re-claiming a task you already own is idempotent.
    procs = [ctx.Process(target=_claim_worker,
                         args=(root, f"producers.{w + 1}", list(ids), q))
             for w in range(12)]
    for p in procs:
        p.start()
    won = []
    for _ in procs:
        won.extend(q.get())
    for p in procs:
        p.join()
    assert len(won) == len(set(won)) == len(ids)   # each claimed exactly once
