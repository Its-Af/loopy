"""Additional CLI coverage: briefings, bus commands, stdin, human output."""

from __future__ import annotations

import io

import pytest

from tools.cli import main


def test_briefing_roundtrip(capsys):
    assert main(["write-briefing", "I own auth", "--agent", "producers.1"]) == 0
    capsys.readouterr()
    assert main(["read-briefing", "--agent", "producers.1"]) == 0
    assert "I own auth" in capsys.readouterr().out


def test_read_briefing_missing_returns_1():
    assert main(["read-briefing", "--agent", "securities"]) == 1


def test_notify_and_broadcast_without_bus_exit_1():
    assert main(["notify", "execs"]) == 1
    assert main(["broadcast"]) == 1


def test_send_message_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("piped body"))
    assert main(["send-message", "execs", "-", "--from", "alfred", "--quiet"]) == 0
    capsys.readouterr()
    main(["--json", "read-inbox", "--agent", "execs"])
    import json
    msgs = json.loads(capsys.readouterr().out)
    assert msgs[0]["body"] == "piped body"


def test_task_show_missing_returns_1():
    assert main(["task", "show", "01ARZ3NDEKTSV4RRFFQ69G5FAV"]) == 1


def test_human_output_paths_do_not_crash(capsys):
    # Exercise the non-JSON rendering branches for a few commands.
    main(["write-state", "working"])
    main(["task", "create", "demo task", "--priority", "P1"])
    capsys.readouterr()
    assert main(["task", "list"]) == 0
    assert "demo task" in capsys.readouterr().out
    assert main(["status"]) == 0
    assert "agents:" in capsys.readouterr().out
    assert main(["read-inbox"]) == 0          # empty inbox human path
    assert "empty" in capsys.readouterr().out.lower()
    assert main(["metrics"]) == 1             # no samples yet


def test_regen_todo_command(capsys):
    main(["task", "create", "x"])
    capsys.readouterr()
    assert main(["regen-todo"]) == 0
    assert "regenerated" in capsys.readouterr().out


def test_task_release_via_cli(capsys):
    import json
    main(["--json", "task", "create", "rel"])
    tid = json.loads(capsys.readouterr().out)["id"]
    main(["task", "claim", tid, "--owner", "producers.1"])
    capsys.readouterr()
    assert main(["task", "release", tid, "--owner", "producers.1"]) == 0
