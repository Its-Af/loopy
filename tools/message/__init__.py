"""Inbox messaging subsystem (see :mod:`tools.message.inbox`)."""

from __future__ import annotations

from tools.message.inbox import (
    Message,
    SanitizeResult,
    SendResult,
    inbox_count,
    prune_shared,
    read_inbox,
    sanitize,
    send_message,
)

__all__ = [
    "Message",
    "SanitizeResult",
    "SendResult",
    "send_message",
    "read_inbox",
    "sanitize",
    "inbox_count",
    "prune_shared",
]
