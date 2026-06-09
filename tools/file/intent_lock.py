"""Intent locks — cooperative, TTL'd "I'm about to touch this" markers.

A hard ``flock`` is the wrong tool when an agent will spend minutes editing a
source file: holding a kernel lock for the whole edit blocks everyone and dies
badly if the agent crashes. Instead an agent *declares intent* on a path. The
declaration is a small JSON file under ``.loopy/intents/`` carrying the owner
and an expiry. Other agents check for a live intent before claiming the same
file and back off if one exists. Intents auto-expire, so a crashed agent never
wedges a file forever.

This is advisory coordination, not mutual exclusion — it prevents two agents
from *choosing* the same file, which is the conflict that actually happens in
practice.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tools.file.atomic_write import atomic_write_text, create_exclusive
from tools.file.locking import file_lock
from tools.project_root import find_project_root, runtime_dir

DEFAULT_TTL = 900  # 15 minutes — long enough for a real edit, short enough to heal


def _intents_dir() -> Path:
    d = runtime_dir() / "intents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key_for(target_path: str | os.PathLike) -> str:
    """Stable, collision-resistant key for an arbitrary target path."""
    try:
        rel = Path(target_path).resolve().relative_to(find_project_root())
        canonical = str(rel)
    except (ValueError, OSError):
        canonical = str(Path(target_path))
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return digest


@dataclass(frozen=True)
class Intent:
    target: str
    owner: str
    expires_at: float
    reason: str = ""

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at

    def to_json(self) -> str:
        return json.dumps(
            {
                "target": self.target,
                "owner": self.owner,
                "expires_at": self.expires_at,
                "reason": self.reason,
            }
        )


def _path_for_key(key: str) -> Path:
    return _intents_dir() / f"{key}.json"


def read_intent(target_path: str | os.PathLike) -> Optional[Intent]:
    """Return the live intent for *target_path*, or None if absent/expired."""
    path = _path_for_key(_key_for(target_path))
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    intent = Intent(
        target=data.get("target", str(target_path)),
        owner=data.get("owner", "?"),
        expires_at=float(data.get("expires_at", 0)),
        reason=data.get("reason", ""),
    )
    if intent.expired:
        # Opportunistically clean up the stale marker.
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return None
    return intent


def declare_intent(target_path: str | os.PathLike, owner: str, *,
                   ttl: float = DEFAULT_TTL, reason: str = "") -> Optional[Intent]:
    """Try to claim intent on *target_path* for *owner*.

    Returns the held :class:`Intent` on success, or ``None`` if another live
    agent already holds it. Re-declaring your own intent refreshes the TTL.
    """
    key = _key_for(target_path)
    path = _path_for_key(key)
    intent = Intent(str(target_path), owner, time.time() + ttl, reason)

    # Serialise the check-and-set so two agents can't both win the race.
    with file_lock(path, timeout=5.0):
        existing = read_intent(target_path)
        if existing is not None and existing.owner != owner:
            return None
        atomic_write_text(path, intent.to_json())
    return intent


def release_intent(target_path: str | os.PathLike, owner: str) -> bool:
    """Release an intent if held by *owner*. Returns True if removed."""
    path = _path_for_key(_key_for(target_path))
    with file_lock(path, timeout=5.0):
        existing = read_intent(target_path)
        if existing is None:
            return False
        if existing.owner != owner:
            return False
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False


def is_available(target_path: str | os.PathLike, owner: str) -> bool:
    """True if *owner* may take *target_path* (free or already theirs)."""
    existing = read_intent(target_path)
    return existing is None or existing.owner == owner
