"""Project-root discovery and agent identity."""

from __future__ import annotations

import pytest

from tools import identity
from tools.project_root import (
    bus_socket_path,
    find_project_root,
    runtime_dir,
    todo_path,
)
from tools.validation import ValidationError


def test_env_override_wins(isolated_runtime):
    # conftest sets LOOPY_PROJECT_ROOT to the isolated root.
    assert find_project_root() == isolated_runtime.resolve()
    assert runtime_dir() == isolated_runtime.resolve() / ".loopy"


def test_bus_socket_and_todo_paths(isolated_runtime):
    assert bus_socket_path() == isolated_runtime.resolve() / ".loopy" / "bus.sock"
    assert todo_path() == isolated_runtime.resolve() / "#TODO"


def test_current_agent_from_env():
    assert identity.current_agent() == "producers.1"
    assert identity.current_role() == "producers"
    assert identity.current_instance() == 1
    assert identity.is_scaled() is True


def test_singleton_identity(as_agent):
    as_agent("alfred")
    assert identity.current_agent() == "alfred"
    assert identity.current_instance() is None
    assert identity.is_scaled() is False


def test_missing_identity_raises(monkeypatch):
    monkeypatch.delenv("LOOPY_AGENT_ID", raising=False)
    with pytest.raises(ValidationError):
        identity.current_agent()
    assert identity.current_agent(required=False) is None


def test_malformed_identity_raises(monkeypatch):
    monkeypatch.setenv("LOOPY_AGENT_ID", "nope.99")
    with pytest.raises(ValidationError):
        identity.current_agent()


def test_per_agent_paths(isolated_runtime):
    rt = isolated_runtime.resolve() / ".loopy"
    assert identity.inbox_dir("producers.1") == rt / "inbox" / "producers.1"
    assert identity.shared_inbox_dir("producers.1") == \
        rt / "inbox" / "producers.shared"
    assert identity.state_path("execs") == rt / "state" / "execs.json"
    assert identity.results_dir("execs") == rt / "results" / "execs"
