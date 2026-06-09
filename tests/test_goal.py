"""Project-goal read/write — preserves the rest of config.md."""

from __future__ import annotations

from tools import goal
from tools.cli import main

SAMPLE_CONFIG = """\
# Loopy Squad Configuration

## Roster
- execs: 1
- producers: 2

## Settings
- session: loopy

## Project goal (free text — read by alfred + execs at startup)

> Describe what you want the squad to build or maintain. This is the human's
> standing instruction; agents read it to orient.
"""


def _write_config(text=SAMPLE_CONFIG):
    p = goal.config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_placeholder_reads_as_empty():
    _write_config()
    assert goal.read_goal() == ""          # placeholder is not a real goal


def test_set_then_read_roundtrip():
    _write_config()
    goal.set_goal("Build a todo REST API in Go with full test coverage.", by="alfred")
    assert goal.read_goal() == "Build a todo REST API in Go with full test coverage."


def test_set_goal_preserves_roster_and_settings():
    _write_config()
    goal.set_goal("Ship the CLI.", by="alfred")
    cfg = goal.config_path().read_text()
    assert "- execs: 1" in cfg and "- producers: 2" in cfg   # roster intact
    assert "- session: loopy" in cfg                          # settings intact
    assert "Ship the CLI." in cfg
    assert "<!-- goal updated:" in cfg                        # stamped


def test_set_goal_is_idempotent_replace():
    _write_config()
    goal.set_goal("First goal.")
    goal.set_goal("Second goal.")
    assert goal.read_goal() == "Second goal."
    # Only one goal section remains.
    assert goal.config_path().read_text().count("## Project goal") == 1


def test_multiline_goal():
    _write_config()
    goal.set_goal("Line one.\n\nLine two with detail.", by="execs")
    assert goal.read_goal() == "Line one.\n\nLine two with detail."


def test_set_goal_creates_config_if_missing():
    # No config.md at all.
    assert not goal.config_path().exists()
    goal.set_goal("Bootstrap goal.")
    assert goal.config_path().exists()
    assert goal.read_goal() == "Bootstrap goal."


def test_empty_goal_rejected():
    import pytest
    with pytest.raises(ValueError):
        goal.set_goal("   ")


def test_summary():
    _write_config()
    assert "no project goal" in goal.goal_summary()
    goal.set_goal("Make it fast.")
    assert goal.goal_summary() == "Make it fast."


# --- CLI ---
def test_cli_set_and_get_goal(capsys):
    _write_config()
    assert main(["set-goal", "Build X", "--by", "alfred"]) == 0
    capsys.readouterr()
    assert main(["get-goal"]) == 0
    assert "Build X" in capsys.readouterr().out


def test_cli_get_goal_empty_exit_1():
    _write_config()
    assert main(["get-goal"]) == 1
