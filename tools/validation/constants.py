"""Canonical constants shared by the validation layer.

Centralising the roster, limits and patterns here keeps every other module —
identity, inbox, tasks, the bus, the operator scripts — agreeing on exactly
what a valid agent id, status or ULID looks like.
"""

from __future__ import annotations

import re

# --- Squad roster ----------------------------------------------------------
# Maps each role to its default number of instances. ``alfred`` and ``execs``
# are singletons; ``producers`` is the only role that scales out by default.
# Hosts may override instance counts via .loopy/config.md, but the *set* of
# valid role names is fixed by the framework.
DEFAULT_ROSTER: dict[str, int] = {
    "execs": 1,
    "alfred": 1,
    "producers": 3,
    "qas": 1,
    "critics": 1,
    "securities": 1,
    "users": 1,
}

VALID_ROLES: frozenset[str] = frozenset(DEFAULT_ROSTER)

#: Stable ordering used to assign each role a numeric index on the bus wire
#: protocol. Never reorder — indices are part of the protocol.
ROLE_ORDER: tuple[str, ...] = (
    "execs",
    "alfred",
    "producers",
    "qas",
    "critics",
    "securities",
    "users",
)

ROLE_INDEX: dict[str, int] = {role: i for i, role in enumerate(ROLE_ORDER)}

# --- Limits ----------------------------------------------------------------
MAX_INSTANCE = 32              # hard ceiling on instances per role
MAX_AGENT_ID_LEN = 64
MAX_STATUS_LEN = 280           # one-line status string

# --- Patterns --------------------------------------------------------------
ROLE_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
INSTANCE_RE = re.compile(r"^[0-9]{1,2}$")
# An agent id is "role" (singleton) or "role.instance" (scaled role).
AGENT_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}(?:\.[0-9]{1,2})?$")
ULID_RE = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
# Conservative slug for filenames / task ids supplied by humans.
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# --- Task + state vocabularies ---------------------------------------------
TASK_STATES: frozenset[str] = frozenset(
    {"OPEN", "CLAIMED", "IN_PROGRESS", "BLOCKED", "REVIEW", "DONE", "REOPENED"}
)
TASK_PRIORITIES: frozenset[str] = frozenset({"P0", "P1", "P2", "P3"})
