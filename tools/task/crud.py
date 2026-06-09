"""Task store — the shared work queue every agent reads and writes.

Each task is a single JSON file named by ULID under ``.loopy/tasks/`` so a
directory listing is already chronological. The one operation that *must* be
correct under concurrency is **claiming**: two producers must never both end up
owning the same task. Claiming therefore takes an advisory lock on the task
file, re-reads it under the lock, and only commits the claim if the task is
still free — a compare-and-set. Everything else is plain read/modify/write,
also under the lock to avoid lost updates.

The human-readable ``#TODO`` index is a *projection* of this store, regenerated
by :mod:`tools.task.index`; the JSON files are the source of truth.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from tools.file.atomic_write import atomic_write_text, create_exclusive
from tools.file.locking import file_lock
from tools.project_root import runtime_dir
from tools.ulid import monotonic_ulid
from tools.validation import (
    ValidationError,
    validate_agent,
    validate_priority,
    validate_task_state,
    validate_ulid,
)

OPEN_STATES = {"OPEN", "REOPENED"}
ACTIVE_STATES = {"CLAIMED", "IN_PROGRESS", "BLOCKED", "REVIEW"}
TERMINAL_STATES = {"DONE"}


def tasks_dir(*, create: bool = False) -> Path:
    d = runtime_dir() / "tasks"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    state: str = "OPEN"
    priority: str = "P2"
    owner: Optional[str] = None
    created_by: str = "execs"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    blocked_by: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "Task":
        data = json.loads(text)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def is_open(self) -> bool:
        return self.state in OPEN_STATES

    @property
    def is_done(self) -> bool:
        return self.state in TERMINAL_STATES


def _path(task_id: str) -> Path:
    return tasks_dir() / f"{validate_ulid(task_id)}.json"


def _log(task: Task, event: str, actor: str, **extra) -> None:
    entry = {"t": round(time.time(), 3), "event": event, "actor": actor}
    entry.update(extra)
    task.history.append(entry)
    task.updated_at = time.time()


# --------------------------------------------------------------------------
# Create / read / list
# --------------------------------------------------------------------------
def create_task(title: str, *, description: str = "", priority: str = "P2",
                created_by: str = "execs", tags: Iterable[str] | None = None,
                blocked_by: Iterable[str] | None = None) -> Task:
    title = title.strip()
    if not title:
        raise ValidationError("task title must not be empty")
    priority = validate_priority(priority)
    created_by = validate_agent(created_by)

    task = Task(
        id=monotonic_ulid(),
        title=title,
        description=description.strip(),
        priority=priority,
        created_by=created_by,
        tags=sorted({t.strip() for t in (tags or []) if t.strip()}),
        blocked_by=[validate_ulid(b) for b in (blocked_by or [])],
    )
    _log(task, "created", created_by, title=title, priority=priority)
    tasks_dir(create=True)
    if not create_exclusive(_path(task.id), task.to_json().encode("utf-8")):
        # ULID collision is essentially impossible; surface loudly if it happens.
        raise RuntimeError(f"task id collision: {task.id}")
    return task


def read_task(task_id: str) -> Task:
    try:
        return Task.from_json(_path(task_id).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise KeyError(f"no such task: {task_id}") from exc


def task_exists(task_id: str) -> bool:
    return _path(task_id).exists()


def list_tasks(*, state: str | None = None, owner: str | None = None,
               priority: str | None = None,
               include_done: bool = True) -> list[Task]:
    out: list[Task] = []
    d = tasks_dir()
    if not d.is_dir():
        return out
    for path in sorted(d.iterdir()):
        if not path.name.endswith(".json"):
            continue
        try:
            task = Task.from_json(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if state and task.state != validate_task_state(state):
            continue
        if owner and task.owner != owner:
            continue
        if priority and task.priority != validate_priority(priority):
            continue
        if not include_done and task.is_done:
            continue
        out.append(task)
    return out


# --------------------------------------------------------------------------
# Mutations (all under an advisory lock on the task file)
# --------------------------------------------------------------------------
def _mutate(task_id: str, fn) -> Task:
    path = _path(task_id)
    if not path.exists():
        raise KeyError(f"no such task: {task_id}")
    with file_lock(path, timeout=10.0):
        task = Task.from_json(path.read_text(encoding="utf-8"))
        result = fn(task)
        if result is False:
            return task  # mutation declined; caller inspects state
        atomic_write_text(path, task.to_json())
        return task


def claim_task(task_id: str, owner: str) -> Optional[Task]:
    """Atomically claim a task. Returns the task if claimed, else ``None``.

    Succeeds only when the task is currently open (OPEN/REOPENED) and has no
    blocking dependencies still outstanding.
    """
    owner = validate_agent(owner)

    def _claim(task: Task):
        if not task.is_open or task.owner is not None:
            return False
        # Respect dependencies: cannot start while blockers are unfinished.
        for dep in task.blocked_by:
            try:
                if not read_task(dep).is_done:
                    return False
            except KeyError:
                continue
        task.owner = owner
        task.state = "CLAIMED"
        _log(task, "claimed", owner)
        return True

    task = _mutate(task_id, _claim)
    return task if task.owner == owner and task.state in ACTIVE_STATES else None


def release_task(task_id: str, owner: str, *, reason: str = "") -> Task:
    """Release a claim, returning the task to OPEN. Only the owner may release."""
    owner = validate_agent(owner)

    def _release(task: Task):
        if task.owner != owner:
            raise ValidationError(
                f"{owner} cannot release task owned by {task.owner}"
            )
        task.owner = None
        task.state = "REOPENED" if task.state != "DONE" else task.state
        _log(task, "released", owner, reason=reason)

    return _mutate(task_id, _release)


def update_task(task_id: str, *, actor: str, state: str | None = None,
                priority: str | None = None, title: str | None = None,
                description: str | None = None,
                add_tags: Iterable[str] | None = None,
                note: str | None = None) -> Task:
    actor = validate_agent(actor)

    def _update(task: Task):
        if state is not None:
            task.state = validate_task_state(state)
        if priority is not None:
            task.priority = validate_priority(priority)
        if title is not None:
            task.title = title.strip()
        if description is not None:
            task.description = description.strip()
        if add_tags:
            task.tags = sorted(set(task.tags) | {t.strip() for t in add_tags})
        _log(task, "updated", actor, note=note or "", state=task.state)

    return _mutate(task_id, _update)


def complete_task(task_id: str, owner: str, *, note: str = "") -> Task:
    """Mark a task DONE. Records who completed it."""
    owner = validate_agent(owner)

    def _complete(task: Task):
        task.state = "DONE"
        _log(task, "completed", owner, note=note)

    return _mutate(task_id, _complete)


def reopen_task(task_id: str, actor: str, *, reason: str) -> Task:
    """Re-open a task a reviewer judged not actually done (critics do this)."""
    actor = validate_agent(actor)

    def _reopen(task: Task):
        task.state = "REOPENED"
        task.owner = None
        _log(task, "reopened", actor, reason=reason)

    return _mutate(task_id, _reopen)
