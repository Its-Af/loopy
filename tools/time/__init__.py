"""Small time helpers shared across the framework.

Centralised so every module formats and compares time the same way (UTC,
microsecond epochs for ids, human strings for humans).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone


def now_us() -> int:
    """Current time as integer microseconds since the epoch."""
    return int(time.time() * 1_000_000)


def now_ms() -> int:
    return int(time.time() * 1000)


def iso(ts: float | None = None) -> str:
    """ISO-8601 UTC timestamp, e.g. ``2026-06-08T18:50:00Z``."""
    dt = datetime.fromtimestamp(ts if ts is not None else time.time(), timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def humanize(seconds: float) -> str:
    """Render a duration compactly: ``45s``, ``12m``, ``3h``, ``2d``."""
    seconds = max(0, int(seconds))
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"


def age_str(ts: float) -> str:
    """Human age of a timestamp relative to now (e.g. ``3m ago``)."""
    return f"{humanize(time.time() - ts)} ago"


__all__ = ["now_us", "now_ms", "iso", "humanize", "age_str"]
