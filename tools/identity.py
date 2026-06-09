"""Agent identity.

Every running Claude Code instance discovers *who it is* from the
``LOOPY_AGENT_ID`` environment variable, set by the operator scripts when the
pane is launched. The id is ``role`` for singleton agents (``execs``,
``alfred``) or ``role.instance`` for scaled roles (``producers.1``).

This module is the single source of truth for "which agent am I" and provides
the canonical filesystem paths that belong to the current agent.
"""

from __future__ import annotations

import os
from pathlib import Path

from tools.project_root import runtime_dir
from tools.validation import ValidationError, split_agent, validate_agent

ENV_VAR = "LOOPY_AGENT_ID"


def current_agent(required: bool = True) -> str | None:
    """Return the current agent id from the environment.

    Raises :class:`ValidationError` if the variable is set but malformed. If it
    is unset and *required* is True, raises; otherwise returns ``None``.
    """
    raw = os.environ.get(ENV_VAR)
    if not raw:
        if required:
            raise ValidationError(
                f"{ENV_VAR} is not set; agents must be launched via the operator scripts"
            )
        return None
    return validate_agent(raw)


def current_role(required: bool = True) -> str | None:
    agent = current_agent(required=required)
    return split_agent(agent)[0] if agent else None


def current_instance(required: bool = True) -> int | None:
    agent = current_agent(required=required)
    if not agent:
        return None
    return split_agent(agent)[1]


def is_scaled(agent_id: str | None = None) -> bool:
    """True if the agent belongs to a multi-instance role (has an instance)."""
    agent_id = agent_id or current_agent()
    return split_agent(agent_id)[1] is not None


def slug(agent_id: str | None = None) -> str:
    """Filesystem-safe slug for an agent (``producers.1`` -> ``producers.1``).

    Agent ids are already filename-safe; this is a thin guarded accessor that
    also validates the supplied id.
    """
    return validate_agent(agent_id or current_agent())


def role_slug(agent_id: str | None = None) -> str:
    """The role portion of an agent id, used for shared (per-role) resources."""
    return split_agent(agent_id or current_agent())[0]


# --- Per-agent runtime paths ----------------------------------------------

def agent_dir(agent_id: str | None = None, *, create: bool = False) -> Path:
    path = runtime_dir() / "agents" / slug(agent_id)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def inbox_dir(agent_id: str | None = None, *, create: bool = False) -> Path:
    """Private inbox directory for an agent."""
    path = runtime_dir() / "inbox" / slug(agent_id)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def shared_inbox_dir(agent_id: str | None = None, *, create: bool = False) -> Path:
    """Shared (per-role) inbox, used to broadcast to every instance of a role."""
    path = runtime_dir() / "inbox" / f"{role_slug(agent_id)}.shared"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def state_path(agent_id: str | None = None) -> Path:
    return runtime_dir() / "state" / f"{slug(agent_id)}.json"


def memory_dir(agent_id: str | None = None, *, create: bool = False) -> Path:
    path = runtime_dir() / "memory" / slug(agent_id)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def results_dir(agent_id: str | None = None, *, create: bool = False) -> Path:
    path = runtime_dir() / "results" / slug(agent_id)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def quarantine_dir(agent_id: str | None = None, *, create: bool = False) -> Path:
    path = runtime_dir() / "quarantine" / slug(agent_id)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
