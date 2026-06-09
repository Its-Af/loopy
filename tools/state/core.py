"""Agent state — the one-line "what am I doing right now" board.

Every loop an agent rewrites its state file. Other agents (and ``status.sh``)
read these to answer "who is alive, who is stuck, who is working on what"
without interrupting anyone. State is deliberately tiny and write-cheap; it is
a heartbeat, not a journal (that is what :mod:`tools.memory` is for).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from tools.file.atomic_write import atomic_write_text
from tools.identity import current_agent
from tools.project_root import runtime_dir
from tools.validation import validate_agent, validate_status

# An agent is considered stale (possibly dead) if it has not updated its state
# within this many seconds — a few missed 5-minute loops.
STALE_AFTER = 18 * 60


@dataclass
class AgentState:
    agent: str
    status: str = "starting"
    updated_at: float = field(default_factory=time.time)
    pid: Optional[int] = None
    loop: int = 0
    task: Optional[str] = None      # task id currently held, if any
    detail: str = ""

    @property
    def age(self) -> float:
        return time.time() - self.updated_at

    @property
    def stale(self) -> bool:
        return self.age > STALE_AFTER

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "AgentState":
        data = json.loads(text)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _state_dir(*, create: bool = False) -> Path:
    d = runtime_dir() / "state"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(agent: str) -> Path:
    return _state_dir() / f"{validate_agent(agent)}.json"


def write_state(status: str, *, agent: str | None = None, task: str | None = None,
                detail: str = "", increment_loop: bool = True) -> AgentState:
    """Update the calling agent's state. This is step 1 of every loop."""
    agent = validate_agent(agent or current_agent())
    status = validate_status(status)

    prev = read_state(agent)
    loop = (prev.loop + 1) if (prev and increment_loop) else (prev.loop if prev else 0)
    state = AgentState(
        agent=agent,
        status=status,
        updated_at=time.time(),
        pid=os.getpid(),
        loop=loop,
        task=task if task is not None else (prev.task if prev else None),
        detail=detail,
    )
    _state_dir(create=True)
    atomic_write_text(state_path(agent), state.to_json())
    return state


def read_state(agent: str | None = None) -> Optional[AgentState]:
    agent = validate_agent(agent or current_agent())
    try:
        return AgentState.from_json(state_path(agent).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def all_states() -> list[AgentState]:
    """Every known agent state, for the health dashboard."""
    d = _state_dir()
    if not d.is_dir():
        return []
    out: list[AgentState] = []
    for path in sorted(d.iterdir()):
        if not path.name.endswith(".json"):
            continue
        try:
            out.append(AgentState.from_json(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def stale_agents() -> list[AgentState]:
    """Agents whose heartbeat has gone quiet — candidates for respawn/reassign."""
    return [s for s in all_states() if s.stale]
