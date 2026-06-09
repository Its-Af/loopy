"""Latency metrics.

The framework's central health invariant is "a parent loop completes in under
60 seconds". To know whether that holds we time loops (and other operations)
and append samples to ``.loopy/metrics/latency.jsonl``. The watchdog and
``status.sh`` summarise these to spot an agent whose loops are creeping toward
the budget — usually the first sign it is doing heavy work inline instead of
delegating to a subagent.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from tools.file.locking import file_lock
from tools.identity import current_agent
from tools.project_root import runtime_dir

#: Soft budget for a parent loop, in milliseconds.
LOOP_BUDGET_MS = 60_000
MAX_SAMPLES = 2000              # ring-buffer cap on the metrics file


def _metrics_path() -> Path:
    d = runtime_dir() / "metrics"
    d.mkdir(parents=True, exist_ok=True)
    return d / "latency.jsonl"


def record(kind: str, ms: float, *, agent: str | None = None, **fields) -> None:
    """Append one latency sample."""
    agent = agent or current_agent(required=False) or "?"
    entry = {"t": round(time.time(), 3), "agent": agent, "kind": kind,
             "ms": round(ms, 2)}
    entry.update(fields)
    path = _metrics_path()
    with file_lock(path, timeout=2.0):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        _trim(path)


def _trim(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    if len(lines) > MAX_SAMPLES:
        from tools.file.atomic_write import atomic_write_text
        atomic_write_text(path, "\n".join(lines[-MAX_SAMPLES:]) + "\n")


@contextmanager
def measure(kind: str, *, agent: str | None = None, **fields) -> Iterator[None]:
    """Time the wrapped block and record the result.

    Usage::

        with measure("loop"):
            run_one_loop()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        record(kind, (time.perf_counter() - start) * 1000.0, agent=agent, **fields)


@dataclass
class Stats:
    kind: str
    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float
    over_budget: int

    def as_dict(self) -> dict:
        return {
            "kind": self.kind, "count": self.count, "mean_ms": self.mean_ms,
            "p50_ms": self.p50_ms, "p95_ms": self.p95_ms, "max_ms": self.max_ms,
            "over_budget": self.over_budget,
        }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[k]


def summarize(kind: str = "loop", *, agent: str | None = None,
              budget_ms: float = LOOP_BUDGET_MS) -> Optional[Stats]:
    """Summarise recorded samples for *kind* (optionally filtered by agent)."""
    path = _metrics_path()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    vals: list[float] = []
    for line in lines:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("kind") != kind:
            continue
        if agent and e.get("agent") != agent:
            continue
        vals.append(float(e.get("ms", 0)))
    if not vals:
        return None
    return Stats(
        kind=kind,
        count=len(vals),
        mean_ms=round(sum(vals) / len(vals), 2),
        p50_ms=round(_percentile(vals, 50), 2),
        p95_ms=round(_percentile(vals, 95), 2),
        max_ms=round(max(vals), 2),
        over_budget=sum(1 for v in vals if v > budget_ms),
    )
