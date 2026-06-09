"""Filesystem primitives: atomic writes, advisory locks, intent locks."""

from __future__ import annotations

from tools.file.atomic_write import (
    atomic_write_bytes,
    atomic_write_text,
    create_exclusive,
)
from tools.file.intent_lock import (
    Intent,
    declare_intent,
    is_available,
    read_intent,
    release_intent,
)
from tools.file.locking import LockTimeout, file_lock

__all__ = [
    "atomic_write_bytes",
    "atomic_write_text",
    "create_exclusive",
    "file_lock",
    "LockTimeout",
    "Intent",
    "declare_intent",
    "release_intent",
    "read_intent",
    "is_available",
]
