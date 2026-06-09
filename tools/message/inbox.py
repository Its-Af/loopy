"""File-based inbox: atomic delivery, sanitisation, quarantine, rate limiting.

Design goals, in priority order:

1. **Safety.** Untrusted text never reaches an agent's context unscreened.
   Every body is Unicode-normalised, de-confusable-d, control-stripped and
   scanned for prompt-injection signatures. A hit quarantines the message
   rather than delivering it. Delivered bodies are additionally fenced so the
   reader can tell quoted data from its own instructions.
2. **Atomicity.** Delivery is a single ``O_CREAT|O_EXCL`` write of a uniquely
   named file, so a reader never sees a partial message and two senders never
   collide.
3. **Liveness.** Per-sender rate limiting caps a noisy or runaway peer.

Two inbox flavours exist. A *private* inbox (``inbox/<agent>/``) is drained by
exactly one reader, which deletes each message as it pops it. A *shared* inbox
(``inbox/<role>.shared/``) fans a message out to every instance of a role; each
instance tracks what it has already seen in its own seen-set instead of
deleting, so siblings still receive the message.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tools.file.atomic_write import create_exclusive
from tools.file.locking import file_lock
from tools.project_root import runtime_dir
from tools.validation import ValidationError, validate_agent
from tools.message import constants as C


# --------------------------------------------------------------------------
# Sanitisation
# --------------------------------------------------------------------------
@dataclass
class SanitizeResult:
    text: str
    findings: list[str] = field(default_factory=list)
    truncated: bool = False

    @property
    def blocked(self) -> bool:
        return bool(self.findings)


def _strip_codepoints(text: str) -> str:
    if not any(c in C.STRIP_CODEPOINTS for c in text):
        return text
    return "".join(c for c in text if c not in C.STRIP_CODEPOINTS)


def _defang_confusables(text: str) -> str:
    if text.isascii():
        return text
    return "".join(C.CONFUSABLES.get(c, c) for c in text)


def sanitize(body: str) -> SanitizeResult:
    """Normalise and screen *body*.

    Always returns cleaned text (NFKC, de-confusabled, control-stripped,
    size-capped). ``findings`` lists the names of any injection signatures that
    matched; when non-empty the caller should quarantine rather than deliver.
    """
    if not isinstance(body, str):
        raise ValidationError("message body must be a string")

    # 1. Canonical Unicode form folds fullwidth/compatibility variants.
    text = unicodedata.normalize("NFKC", body)
    # 2. Map look-alike homoglyphs NFKC leaves alone (Cyrillic/Greek).
    text = _defang_confusables(text)
    # 3. Remove control + zero-width + bidi-override codepoints.
    text = _strip_codepoints(text)

    # 4. Enforce the byte cap (encode/cut/decode so we never split a codepoint).
    truncated = False
    encoded = text.encode("utf-8")
    if len(encoded) > C.MAX_MESSAGE_BYTES:
        text = encoded[: C.MAX_MESSAGE_BYTES].decode("utf-8", "ignore")
        truncated = True

    # 5. Screen for injection. Scan line-anchored patterns per line.
    findings: list[str] = []
    for pat in C.INJECTION_PATTERNS:
        if pat.search(text):
            findings.append(pat.pattern)

    return SanitizeResult(text=text, findings=findings, truncated=truncated)


def fence(body: str) -> str:
    """Wrap a delivered body in untrusted-data sentinels for the reader."""
    return f"{C.DATA_FENCE_OPEN}\n{body}\n{C.DATA_FENCE_CLOSE}"


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def _inbox_dir(agent: str, *, create: bool = False) -> Path:
    p = runtime_dir() / "inbox" / agent
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def _shared_dir(role: str, *, create: bool = False) -> Path:
    p = runtime_dir() / "inbox" / f"{role}.shared"
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def _quarantine_dir(agent: str, *, create: bool = False) -> Path:
    p = runtime_dir() / "quarantine" / agent
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def _seen_path(agent: str) -> Path:
    return runtime_dir() / "inbox" / f"{agent}.seen"


def _ratelimit_path(sender: str) -> Path:
    return runtime_dir() / "inbox" / ".ratelimit" / f"{sender}.json"


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------
def _check_and_record_rate(sender: str, now: float | None = None) -> bool:
    """Return True if *sender* is within its send budget, recording the send."""
    now = time.time() if now is None else now
    path = _ratelimit_path(sender)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path, timeout=5.0):
        try:
            stamps = json.loads(path.read_text())
            if not isinstance(stamps, list):
                stamps = []
        except (FileNotFoundError, json.JSONDecodeError):
            stamps = []
        # Drop anything outside the sliding window.
        stamps = [t for t in stamps if isinstance(t, (int, float))
                  and now - t < C.RATE_LIMIT_WINDOW]
        if len(stamps) >= C.RATE_LIMIT_COUNT:
            return False
        stamps.append(now)
        from tools.file.atomic_write import atomic_write_text
        atomic_write_text(path, json.dumps(stamps))
        return True


# --------------------------------------------------------------------------
# Message model
# --------------------------------------------------------------------------
@dataclass
class Message:
    id: str
    sender: str
    target: str
    timestamp_us: int
    body: str
    path: Path
    shared: bool = False

    @property
    def timestamp(self) -> float:
        return self.timestamp_us / 1_000_000


@dataclass
class SendResult:
    delivered: bool
    path: Optional[Path] = None
    quarantined: bool = False
    reason: str = ""
    findings: list[str] = field(default_factory=list)


def _make_filename(sender: str, ts_us: int) -> str:
    nonce = os.urandom(C.NONCE_BYTES).hex()
    return f"{ts_us:016d}-{nonce}-{sender}{C.MESSAGE_SUFFIX}"


def _render(sender: str, target: str, ts_us: int, body: str) -> str:
    header = (
        f"---\nfrom: {sender}\nto: {target}\nts_us: {ts_us}\n---\n"
    )
    return header + fence(body) + "\n"


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------
def send_message(target: str, sender: str, body: str, *, shared: bool = False,
                 notify: bool = True) -> SendResult:
    """Deliver *body* from *sender* to *target* (or *target*'s shared inbox).

    Returns a :class:`SendResult`. On an injection hit the raw message is
    written to the target's quarantine and ``delivered`` is ``False``.
    """
    target = validate_agent(target)
    sender = validate_agent(sender)

    if not _check_and_record_rate(sender):
        return SendResult(False, reason="rate-limited", quarantined=False)

    result = sanitize(body)
    ts_us = int(time.time() * 1_000_000)
    filename = _make_filename(sender, ts_us)

    if result.blocked:
        qdir = _quarantine_dir(target, create=True)
        payload = json.dumps(
            {
                "from": sender, "to": target, "ts_us": ts_us,
                "findings": result.findings, "raw": body[:C.MAX_MESSAGE_BYTES],
            },
            ensure_ascii=False,
        ).encode("utf-8")
        create_exclusive(qdir / (filename + ".json"), payload)
        return SendResult(False, quarantined=True, reason="injection-detected",
                          findings=result.findings)

    if shared:
        role = validate_agent(target).split(".")[0]
        dest_dir = _shared_dir(role, create=True)
    else:
        dest_dir = _inbox_dir(target, create=True)

    rendered = _render(sender, target, ts_us, result.text).encode("utf-8")
    dest = dest_dir / filename
    if not create_exclusive(dest, rendered):
        # Astronomically unlikely nonce collision — retry once.
        dest = dest_dir / _make_filename(sender, ts_us)
        create_exclusive(dest, rendered)

    if notify:
        _best_effort_notify(target, shared)

    return SendResult(True, path=dest, findings=result.findings)


def _best_effort_notify(target: str, shared: bool) -> None:
    try:
        from tools.message.notify_quick import wake
        wake(target, shared=shared)
    except Exception:
        # The bus is optional; agents still poll their inbox every loop.
        pass


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def _parse_message(path: Path, *, shared: bool) -> Optional[Message]:
    m = C.FILENAME_RE.match(path.name)
    if not m:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return None
    body = raw
    if raw.startswith("---\n"):
        _, _, rest = raw.partition("---\n")
        _, sep, after = rest.partition("---\n")
        if sep:
            body = after
    body = body.strip()
    if body.startswith(C.DATA_FENCE_OPEN):
        body = body[len(C.DATA_FENCE_OPEN):].lstrip("\n")
    if body.endswith(C.DATA_FENCE_CLOSE):
        body = body[: -len(C.DATA_FENCE_CLOSE)].rstrip("\n")
    return Message(
        id=path.name,
        sender=m.group("sender"),
        target="",
        timestamp_us=int(m.group("ts")),
        body=body,
        path=path,
        shared=shared,
    )


def _load_seen(agent: str) -> set[str]:
    try:
        return set(_seen_path(agent).read_text().split())
    except FileNotFoundError:
        return set()


def read_inbox(agent: str, *, include_shared: bool = True,
               limit: int | None = None, pop: bool = True) -> list[Message]:
    """Return pending messages for *agent*, oldest first.

    Private messages are *popped* (deleted) when ``pop`` is True. Shared
    messages are never deleted; instead each is recorded in the agent's
    seen-set so siblings still receive it and this agent won't see it twice.
    """
    agent = validate_agent(agent)
    role = agent.split(".")[0]
    messages: list[Message] = []

    # 1. Private inbox — drain and delete.
    pdir = _inbox_dir(agent)
    if pdir.is_dir():
        for path in sorted(pdir.iterdir()):
            if limit is not None and len(messages) >= limit:
                break
            msg = _parse_message(path, shared=False)
            if msg is None:
                continue
            messages.append(msg)
            if pop:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass

    # 2. Shared inbox — read once via the seen-set.
    if include_shared:
        sdir = _shared_dir(role)
        if sdir.is_dir():
            seen = _load_seen(agent)
            newly_seen: list[str] = []
            for path in sorted(sdir.iterdir()):
                if limit is not None and len(messages) >= limit:
                    break
                if path.name in seen or not C.FILENAME_RE.match(path.name):
                    continue
                msg = _parse_message(path, shared=True)
                if msg is None:
                    continue
                messages.append(msg)
                newly_seen.append(path.name)
            if newly_seen and pop:
                _mark_seen(agent, newly_seen)

    messages.sort(key=lambda m: m.timestamp_us)
    return messages


def _mark_seen(agent: str, ids: list[str]) -> None:
    path = _seen_path(agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path, timeout=5.0):
        existing = _load_seen(agent)
        existing.update(ids)
        from tools.file.atomic_write import atomic_write_text
        atomic_write_text(path, "\n".join(sorted(existing)) + "\n")


def prune_shared(role: str, *, ttl: int = C.SHARED_MESSAGE_TTL) -> int:
    """Delete shared-inbox messages older than *ttl* seconds. Returns count."""
    sdir = _shared_dir(role)
    if not sdir.is_dir():
        return 0
    cutoff_us = int((time.time() - ttl) * 1_000_000)
    removed = 0
    for path in sdir.iterdir():
        m = C.FILENAME_RE.match(path.name)
        if m and int(m.group("ts")) < cutoff_us:
            try:
                path.unlink()
                removed += 1
            except FileNotFoundError:
                pass
    return removed


def inbox_count(agent: str, *, include_shared: bool = True) -> int:
    """Cheap count of pending messages without consuming them."""
    return len(read_inbox(agent, include_shared=include_shared, pop=False))
