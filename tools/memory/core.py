"""Persistent agent memory: briefings, decisions, and rotation.

State (:mod:`tools.state`) answers "what am I doing this second"; memory answers
"what do I know and why did I choose it". Two artifacts:

* **briefing.md** — a living summary the agent rewrites for itself. It is read
  at startup and refreshed whenever it goes stale (>24h by default), giving an
  agent continuity across restarts and context windows.
* **decisions.jsonl** — an append-only log of consequential choices, so a
  reviewer (or the agent's future self) can reconstruct *why* something was
  done. Rotated to stay bounded.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.file.atomic_write import atomic_write_text
from tools.file.locking import file_lock
from tools.identity import current_agent
from tools.project_root import runtime_dir
from tools.validation import validate_agent

BRIEFING_TTL = 24 * 3600        # rewrite a briefing older than this
MAX_DECISIONS = 500             # keep the most recent N decisions
ROTATE_KEEP = 400               # ... trimming back to this on rotation


def _mem_dir(agent: str, *, create: bool = False) -> Path:
    d = runtime_dir() / "memory" / validate_agent(agent)
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def briefing_path(agent: str | None = None) -> Path:
    return _mem_dir(agent or current_agent()) / "briefing.md"


def decisions_path(agent: str | None = None) -> Path:
    return _mem_dir(agent or current_agent()) / "decisions.jsonl"


# --------------------------------------------------------------------------
# Briefings
# --------------------------------------------------------------------------
@dataclass
class Briefing:
    text: str
    updated_at: float

    @property
    def age(self) -> float:
        return time.time() - self.updated_at

    @property
    def stale(self) -> bool:
        return self.age > BRIEFING_TTL


def write_briefing(text: str, *, agent: str | None = None) -> Briefing:
    agent = validate_agent(agent or current_agent())
    _mem_dir(agent, create=True)
    stamp = f"<!-- updated_at: {time.time():.3f} -->\n"
    atomic_write_text(briefing_path(agent), stamp + text.rstrip() + "\n")
    return Briefing(text=text, updated_at=time.time())


def read_briefing(agent: str | None = None) -> Optional[Briefing]:
    agent = validate_agent(agent or current_agent())
    path = briefing_path(agent)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    updated_at = path.stat().st_mtime
    body = raw
    if raw.startswith("<!-- updated_at:"):
        first, _, rest = raw.partition("\n")
        try:
            updated_at = float(first.split("updated_at:")[1].split("-->")[0].strip())
        except (IndexError, ValueError):
            pass
        body = rest
    return Briefing(text=body.strip(), updated_at=updated_at)


def briefing_stale(agent: str | None = None) -> bool:
    """True if the briefing is missing or older than :data:`BRIEFING_TTL`.

    This backs LOOP step 2b: "if briefing stale >24h, rewrite".
    """
    b = read_briefing(agent)
    return b is None or b.stale


# --------------------------------------------------------------------------
# Decisions
# --------------------------------------------------------------------------
def record_decision(summary: str, *, agent: str | None = None,
                    rationale: str = "", task: str | None = None,
                    **extra) -> dict:
    agent = validate_agent(agent or current_agent())
    entry = {
        "t": round(time.time(), 3),
        "agent": agent,
        "summary": summary.strip(),
        "rationale": rationale.strip(),
        "task": task,
    }
    entry.update(extra)
    path = decisions_path(agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with file_lock(path, timeout=5.0):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
    rotate(agent)
    return entry


def read_decisions(agent: str | None = None, *, limit: int | None = None) -> list[dict]:
    agent = validate_agent(agent or current_agent())
    try:
        lines = decisions_path(agent).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if limit is not None:
        out = out[-limit:]
    return out


def rotate(agent: str | None = None) -> int:
    """Trim the decisions log if it exceeds :data:`MAX_DECISIONS`.

    Returns the number of entries dropped. Keeps the most recent
    :data:`ROTATE_KEEP` so the log stays useful but bounded.
    """
    agent = validate_agent(agent or current_agent())
    path = decisions_path(agent)
    with file_lock(path, timeout=5.0):
        entries = read_decisions(agent)
        if len(entries) <= MAX_DECISIONS:
            return 0
        kept = entries[-ROTATE_KEEP:]
        dropped = len(entries) - len(kept)
        body = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in kept)
        atomic_write_text(path, body)
        return dropped
