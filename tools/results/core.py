"""Subagent results — the return channel of the parent-as-coordinator pattern.

A parent agent must finish its loop in under a minute, so anything heavy (a
build, a test run, a deep code read) is handed to a *background subagent*. The
subagent can take as long as it needs; when done it drops a result file in
``.loopy/results/<parent>/``. On its next loop the parent pops these results
and acts on them. This file is that mailbox.

Results are ULID-named so they are time-ordered, and popped (deleted) once the
parent has consumed them — mirroring the private inbox semantics.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from tools.file.atomic_write import create_exclusive
from tools.identity import current_agent
from tools.project_root import runtime_dir
from tools.ulid import monotonic_ulid
from tools.validation import validate_agent, validate_ulid


def _results_dir(agent: str, *, create: bool = False) -> Path:
    d = runtime_dir() / "results" / validate_agent(agent)
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Result:
    id: str
    parent: str                  # the agent that will consume this result
    kind: str                    # e.g. "build", "test", "review", "implement"
    ok: bool = True
    summary: str = ""
    payload: Any = None
    subagent: str = ""           # free-form label of who produced it
    created_at: float = field(default_factory=time.time)
    path: Optional[str] = None

    def to_json(self) -> str:
        d = asdict(self)
        d.pop("path", None)
        return json.dumps(d, ensure_ascii=False, indent=2)

    @classmethod
    def from_path(cls, path: Path) -> Optional["Result"]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        known = {f for f in cls.__dataclass_fields__ if f != "path"}  # type: ignore[attr-defined]
        obj = cls(**{k: v for k, v in data.items() if k in known})
        obj.path = str(path)
        return obj


def post_result(parent: str, kind: str, *, ok: bool = True, summary: str = "",
                payload: Any = None, subagent: str = "") -> Result:
    """Write a result destined for *parent* to consume. Returns the Result."""
    parent = validate_agent(parent)
    result = Result(
        id=monotonic_ulid(),
        parent=parent,
        kind=kind.strip() or "generic",
        ok=ok,
        summary=summary.strip(),
        payload=payload,
        subagent=subagent.strip(),
    )
    d = _results_dir(parent, create=True)
    path = d / f"{result.id}.json"
    create_exclusive(path, result.to_json().encode("utf-8"))
    result.path = str(path)
    return result


def reserve_result_path(parent: str, kind: str = "generic") -> tuple[str, Path]:
    """Pre-allocate a result id + path to hand to a subagent before it runs.

    The subagent writes its JSON to this exact path on completion.
    """
    parent = validate_agent(parent)
    rid = monotonic_ulid()
    path = _results_dir(parent, create=True) / f"{rid}.json"
    return rid, path


def read_results(parent: str | None = None, *, consume: bool = True,
                 limit: int | None = None) -> list[Result]:
    """Pop completed results for *parent* (defaults to the current agent)."""
    parent = validate_agent(parent or current_agent())
    d = _results_dir(parent)
    if not d.is_dir():
        return []
    out: list[Result] = []
    for path in sorted(d.iterdir()):
        if not path.name.endswith(".json"):
            continue
        if limit is not None and len(out) >= limit:
            break
        result = Result.from_path(path)
        if result is None:
            continue
        out.append(result)
        if consume:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
    return out


def pending_count(parent: str | None = None) -> int:
    parent = validate_agent(parent or current_agent())
    d = _results_dir(parent)
    if not d.is_dir():
        return 0
    return sum(1 for p in d.iterdir() if p.name.endswith(".json"))


def get_result(parent: str, result_id: str) -> Optional[Result]:
    parent = validate_agent(parent)
    path = _results_dir(parent) / f"{validate_ulid(result_id)}.json"
    return Result.from_path(path) if path.exists() else None
