"""Subagent spawn gate.

Running too many Claude Code instances at once is the single most common way to
crash the machine (memory exhaustion, fork-bomb-like CPU contention). Before a
parent spawns a background subagent it consults this gate, which returns
``CLEAR`` only when the system has headroom. The check is cheap and dependency
-free so it can run on every loop.

Signals considered:

* number of live ``claude`` processes vs a configured ceiling;
* number of background subagents this agent already has in flight (tracked by
  pending result files);
* 1-minute load average per CPU.

The ceiling and thresholds come from the environment (set by the operator) with
conservative defaults.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from tools.results.core import pending_count

# Defaults are intentionally conservative; the operator raises them on big hosts.
DEFAULT_MAX_CLAUDE = int(os.environ.get("LOOPY_MAX_CLAUDE_PROCS", "12"))
DEFAULT_MAX_INFLIGHT = int(os.environ.get("LOOPY_MAX_INFLIGHT", "2"))
DEFAULT_MAX_LOAD_PER_CPU = float(os.environ.get("LOOPY_MAX_LOAD_PER_CPU", "2.5"))


@dataclass
class Capacity:
    clear: bool
    reason: str
    claude_procs: int
    inflight: int
    load1: float
    cpus: int

    @property
    def verdict(self) -> str:
        return "CLEAR" if self.clear else "WAIT"

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict, "clear": self.clear, "reason": self.reason,
            "claude_procs": self.claude_procs, "inflight": self.inflight,
            "load1": round(self.load1, 2), "cpus": self.cpus,
        }


def _count_claude_processes() -> int:
    """Best-effort count of running ``claude`` CLI processes."""
    pgrep = shutil.which("pgrep")
    if pgrep:
        try:
            out = subprocess.run(
                [pgrep, "-f", "claude"], capture_output=True, text=True, timeout=5
            )
            if out.returncode in (0, 1):
                return len([ln for ln in out.stdout.splitlines() if ln.strip()])
        except (subprocess.SubprocessError, OSError):
            pass
    # Fallback: parse ps.
    try:
        out = subprocess.run(["ps", "-axo", "comm"], capture_output=True,
                             text=True, timeout=5)
        return sum(1 for ln in out.stdout.splitlines() if "claude" in ln.lower())
    except (subprocess.SubprocessError, OSError):
        return 0


def check(agent: str | None = None, *, max_claude: int = DEFAULT_MAX_CLAUDE,
          max_inflight: int = DEFAULT_MAX_INFLIGHT,
          max_load_per_cpu: float = DEFAULT_MAX_LOAD_PER_CPU) -> Capacity:
    """Decide whether it is safe to spawn another subagent right now."""
    try:
        cpus = os.cpu_count() or 1
    except NotImplementedError:  # pragma: no cover
        cpus = 1
    try:
        load1 = os.getloadavg()[0]
    except (OSError, AttributeError):  # pragma: no cover - unsupported platform
        load1 = 0.0

    procs = _count_claude_processes()
    try:
        inflight = pending_count(agent) if agent else 0
    except Exception:
        inflight = 0

    if procs > max_claude:
        return Capacity(False, f"too many claude procs ({procs}>{max_claude})",
                        procs, inflight, load1, cpus)
    if inflight >= max_inflight:
        return Capacity(False, f"already {inflight} subagents in flight",
                        procs, inflight, load1, cpus)
    if load1 > max_load_per_cpu * cpus:
        return Capacity(False,
                        f"load too high ({load1:.1f}>{max_load_per_cpu}×{cpus})",
                        procs, inflight, load1, cpus)
    return Capacity(True, "headroom available", procs, inflight, load1, cpus)
