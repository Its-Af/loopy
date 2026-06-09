"""Input validation primitives.

Every value that crosses a trust boundary — an agent id read from the
environment, a target supplied to ``send_message``, a ULID parsed from a
filename, a status written to shared state — passes through one of these
functions first. They raise :class:`ValidationError` on bad input and return a
normalised value on success, so callers never have to second-guess a value
once it has been validated.
"""

from __future__ import annotations

from . import constants as C


class ValidationError(ValueError):
    """Raised when untrusted input fails validation."""


def validate_role(role: object) -> str:
    """Return *role* if it is a known squad role, else raise."""
    if not isinstance(role, str):
        raise ValidationError(f"role must be a string, got {type(role).__name__}")
    role = role.strip()
    if role not in C.VALID_ROLES:
        raise ValidationError(
            f"unknown role {role!r}; expected one of {sorted(C.VALID_ROLES)}"
        )
    return role


def validate_instance(instance: object) -> int:
    """Return *instance* as an int in ``[1, MAX_INSTANCE]``, else raise."""
    if isinstance(instance, bool):  # bool is an int subclass — reject explicitly
        raise ValidationError("instance must not be a boolean")
    if isinstance(instance, str):
        if not C.INSTANCE_RE.match(instance):
            raise ValidationError(f"malformed instance {instance!r}")
        instance = int(instance)
    if not isinstance(instance, int):
        raise ValidationError(f"instance must be an int, got {type(instance).__name__}")
    if not 1 <= instance <= C.MAX_INSTANCE:
        raise ValidationError(f"instance {instance} out of range 1..{C.MAX_INSTANCE}")
    return instance


def validate_agent(agent_id: object) -> str:
    """Validate a full agent id of the form ``role`` or ``role.instance``.

    Returns the normalised id. Note this checks *shape* and that the role is
    known; it does not consult the live roster for instance counts.
    """
    if not isinstance(agent_id, str):
        raise ValidationError(
            f"agent id must be a string, got {type(agent_id).__name__}"
        )
    agent_id = agent_id.strip()
    if len(agent_id) > C.MAX_AGENT_ID_LEN:
        raise ValidationError("agent id too long")
    if not C.AGENT_ID_RE.match(agent_id):
        raise ValidationError(f"malformed agent id {agent_id!r}")

    role, _, instance = agent_id.partition(".")
    validate_role(role)
    if instance:
        validate_instance(instance)
    return agent_id


def split_agent(agent_id: str) -> tuple[str, int | None]:
    """Split a validated agent id into ``(role, instance | None)``."""
    agent_id = validate_agent(agent_id)
    role, _, instance = agent_id.partition(".")
    return role, (int(instance) if instance else None)


def validate_ulid(value: object) -> str:
    """Validate and upper-case a ULID string."""
    if not isinstance(value, str):
        raise ValidationError("ULID must be a string")
    up = value.strip().upper()
    if not C.ULID_RE.match(up):
        raise ValidationError(f"malformed ULID {value!r}")
    return up


def validate_status(status: object) -> str:
    """Validate a one-line status string (single line, length-capped)."""
    if not isinstance(status, str):
        raise ValidationError("status must be a string")
    status = status.strip()
    if not status:
        raise ValidationError("status must not be empty")
    if "\n" in status or "\r" in status:
        raise ValidationError("status must be a single line")
    if len(status) > C.MAX_STATUS_LEN:
        raise ValidationError(f"status exceeds {C.MAX_STATUS_LEN} chars")
    return status


def validate_slug(value: object, *, field: str = "value") -> str:
    """Validate a conservative filename-safe slug."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string")
    value = value.strip()
    if not C.SLUG_RE.match(value):
        raise ValidationError(f"malformed {field} {value!r}")
    if ".." in value:
        raise ValidationError(f"{field} must not contain '..'")
    return value


def validate_task_state(state: object) -> str:
    if not isinstance(state, str) or state.upper() not in C.TASK_STATES:
        raise ValidationError(f"invalid task state {state!r}")
    return state.upper()


def validate_priority(priority: object) -> str:
    if not isinstance(priority, str) or priority.upper() not in C.TASK_PRIORITIES:
        raise ValidationError(f"invalid priority {priority!r}")
    return priority.upper()
