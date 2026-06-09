"""Edge cases across modules: malformed inputs, fallbacks, defensive parsing."""

from __future__ import annotations

import json

import pytest


# --- project_root ----------------------------------------------------------
def test_runtime_subdir_creates(isolated_runtime):
    from tools.project_root import runtime_subdir
    p = runtime_subdir("a", "b", create=True)
    assert p.is_dir() and p.name == "b"


def test_todo_path_env_override(monkeypatch, tmp_path):
    from tools.project_root import todo_path
    monkeypatch.setenv("LOOPY_TODO_PATH", str(tmp_path / "BOARD"))
    assert todo_path() == tmp_path / "BOARD"


def test_find_root_walks_up_to_marker(tmp_path, monkeypatch):
    from tools.project_root import find_project_root, reset_cache
    monkeypatch.delenv("LOOPY_PROJECT_ROOT", raising=False)
    root = tmp_path / "proj"
    (root / ".loopy").mkdir(parents=True)
    deep = root / "src" / "pkg"
    deep.mkdir(parents=True)
    reset_cache()
    assert find_project_root(deep) == root.resolve()
    reset_cache()


# --- identity paths --------------------------------------------------------
def test_identity_path_helpers(isolated_runtime):
    from tools import identity
    rt = isolated_runtime.resolve() / ".loopy"
    assert identity.memory_dir("execs", create=True).is_dir()
    assert identity.results_dir("qas") == rt / "results" / "qas"
    assert identity.quarantine_dir("execs") == rt / "quarantine" / "execs"
    assert identity.agent_dir("alfred", create=True).is_dir()


# --- inbox defensive parsing ----------------------------------------------
def test_inbox_ignores_non_message_files(isolated_runtime):
    from tools.message import inbox, read_inbox, send_message
    send_message("execs", "producers.1", "real", notify=False)
    # Drop junk into the inbox dir; readers must skip it, not crash.
    idir = isolated_runtime / ".loopy" / "inbox" / "execs"
    (idir / "README.txt").write_text("not a message")
    (idir / "garbage").write_text("xxx")
    msgs = read_inbox("execs")
    assert len(msgs) == 1 and msgs[0].body == "real"


def test_task_list_skips_corrupt_files(isolated_runtime):
    from tools.task import crud
    crud.create_task("good one")
    bad = crud.tasks_dir() / "01BADBADBADBADBADBADBADBAD.json"
    bad.write_text("{ not valid json")
    tasks = crud.list_tasks()
    assert len(tasks) == 1 and tasks[0].title == "good one"


def test_state_skips_corrupt(isolated_runtime):
    from tools import state
    state.write_state("ok", agent="execs")
    (isolated_runtime / ".loopy" / "state" / "broken.json").write_text("nope")
    agents = {s.agent for s in state.all_states()}
    assert "execs" in agents


# --- capacity explicit thresholds -----------------------------------------
def test_capacity_waits_on_high_load(monkeypatch):
    from tools import capacity
    monkeypatch.setattr(capacity.os, "getloadavg", lambda: (999.0, 0, 0))
    monkeypatch.setattr(capacity, "_count_claude_processes", lambda: 0)
    cap = capacity.check("execs", max_load_per_cpu=0.1)
    assert not cap.clear and "load" in cap.reason


def test_capacity_waits_on_too_many_procs(monkeypatch):
    from tools import capacity
    monkeypatch.setattr(capacity, "_count_claude_processes", lambda: 9999)
    cap = capacity.check("execs", max_claude=10)
    assert not cap.clear and "claude procs" in cap.reason


# --- prune + rotation extras ----------------------------------------------
def test_inbox_prune_shared_noop_when_fresh():
    from tools.message import inbox
    inbox.send_message("producers", "execs", "fresh", shared=True, notify=False)
    assert inbox.prune_shared("producers", ttl=3600) == 0   # nothing old enough


# --- CLI extra commands ----------------------------------------------------
def test_cli_record_decision_and_metrics(capsys):
    from tools.cli import main
    assert main(["record-decision", "chose X", "--rationale", "because Y"]) == 0
    from tools.memory import read_decisions
    assert read_decisions("producers.1")[0]["summary"] == "chose X"

    main(["--json", "post-result", "execs", "build", "--summary", "ok"])
    capsys.readouterr()
    assert main(["read-results", "--agent", "execs"]) == 0


def test_cli_read_state_all(capsys):
    from tools.cli import main
    main(["write-state", "x", "--agent", "execs"])
    capsys.readouterr()
    code = main(["--json", "read-state", "--all"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and any(s["agent"] == "execs" for s in out)
