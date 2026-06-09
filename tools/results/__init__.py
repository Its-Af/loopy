"""Subagent results channel (see :mod:`tools.results.core`)."""

from __future__ import annotations

from tools.results.core import (
    Result,
    get_result,
    pending_count,
    post_result,
    read_results,
    reserve_result_path,
)

__all__ = [
    "Result",
    "post_result",
    "read_results",
    "reserve_result_path",
    "pending_count",
    "get_result",
]
