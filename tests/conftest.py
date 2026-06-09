"""Shared pytest fixtures.

Every test runs against a *fresh, isolated* runtime directory so tests can
never see each other's tasks, inboxes or state. We point ``LOOPY_PROJECT_ROOT``
at a per-test ``tmp_path`` and clear the memoised project-root lookup on the way
in and out.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Give each test its own project root + a default agent identity."""
    root = tmp_path / "project"
    root.mkdir()
    (root / ".loopy").mkdir()  # marker so find_project_root anchors here
    monkeypatch.setenv("LOOPY_PROJECT_ROOT", str(root))
    monkeypatch.setenv("LOOPY_AGENT_ID", "producers.1")
    monkeypatch.delenv("LOOPY_BUS_TOKEN", raising=False)
    monkeypatch.delenv("LOOPY_TODO_PATH", raising=False)

    from tools.project_root import reset_cache
    reset_cache()
    yield root
    reset_cache()


@pytest.fixture
def as_agent(monkeypatch):
    """Factory to switch the current agent identity within a test."""
    def _set(agent_id: str):
        monkeypatch.setenv("LOOPY_AGENT_ID", agent_id)
        return agent_id
    return _set
