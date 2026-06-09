"""Validation layer: roles, instances, agent ids, ULIDs, statuses, slugs."""

from __future__ import annotations

import pytest

from tools.validation import (
    ValidationError,
    split_agent,
    validate_agent,
    validate_instance,
    validate_priority,
    validate_role,
    validate_slug,
    validate_status,
    validate_task_state,
    validate_ulid,
)


@pytest.mark.parametrize("role", ["execs", "alfred", "producers", "qas",
                                   "critics", "securities", "users"])
def test_valid_roles(role):
    assert validate_role(role) == role


@pytest.mark.parametrize("role", ["", "Producers", "producer", "root", 7, None])
def test_invalid_roles(role):
    with pytest.raises(ValidationError):
        validate_role(role)


def test_validate_agent_singleton_and_scaled():
    assert validate_agent("alfred") == "alfred"
    assert validate_agent("producers.3") == "producers.3"
    assert validate_agent("  execs  ") == "execs"


@pytest.mark.parametrize("bad", [
    "producers.0",       # instance must be >= 1
    "producers.99",      # exceeds MAX_INSTANCE
    "producers.",        # empty instance
    "nope.1",            # unknown role
    "../etc/passwd",
    "producers.1.2",
    "Producers.1",       # uppercase
    "a" * 80,
])
def test_validate_agent_rejects(bad):
    with pytest.raises(ValidationError):
        validate_agent(bad)


def test_split_agent():
    assert split_agent("producers.2") == ("producers", 2)
    assert split_agent("alfred") == ("alfred", None)


def test_validate_instance_bounds_and_types():
    assert validate_instance(1) == 1
    assert validate_instance("5") == 5
    with pytest.raises(ValidationError):
        validate_instance(0)
    with pytest.raises(ValidationError):
        validate_instance(99)
    with pytest.raises(ValidationError):
        validate_instance(True)   # bool must be rejected


def test_validate_ulid_normalises_case():
    assert validate_ulid("01ARZ3NDEKTSV4RRFFQ69G5FAV".lower()) == \
        "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    with pytest.raises(ValidationError):
        validate_ulid("not-a-ulid")


def test_validate_status():
    assert validate_status("working on auth") == "working on auth"
    with pytest.raises(ValidationError):
        validate_status("")
    with pytest.raises(ValidationError):
        validate_status("two\nlines")
    with pytest.raises(ValidationError):
        validate_status("x" * 5000)


def test_validate_slug_blocks_traversal():
    assert validate_slug("good-name_1.txt") == "good-name_1.txt"
    with pytest.raises(ValidationError):
        validate_slug("../escape")
    with pytest.raises(ValidationError):
        validate_slug("with/slash")


def test_state_and_priority_vocab():
    assert validate_task_state("done") == "DONE"
    assert validate_priority("p0") == "P0"
    with pytest.raises(ValidationError):
        validate_task_state("FINISHED")
    with pytest.raises(ValidationError):
        validate_priority("P9")
