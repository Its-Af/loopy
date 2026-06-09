"""Latency metrics (see :mod:`tools.metrics.latency`)."""

from __future__ import annotations

from tools.metrics.latency import (
    LOOP_BUDGET_MS,
    Stats,
    measure,
    record,
    summarize,
)

__all__ = ["LOOP_BUDGET_MS", "Stats", "measure", "record", "summarize"]
