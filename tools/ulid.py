"""ULID generation — Universally Unique Lexicographically Sortable Identifier.

A ULID is 128 bits: a 48-bit millisecond timestamp followed by 80 bits of
randomness, encoded as 26 characters of Crockford's Base32. ULIDs sort
lexicographically in time order, which makes them ideal for naming task files,
result files and inbox messages so that a plain directory listing is also a
chronological listing.

Pure standard library; no third-party dependencies.

Reference: https://github.com/ulid/spec
"""

from __future__ import annotations

import os
import secrets
import threading
import time

# Crockford's Base32 alphabet (excludes I, L, O, U to avoid ambiguity).
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {c: i for i, c in enumerate(_ALPHABET)}

ULID_LEN = 26
_TIME_LEN = 10  # first 10 chars encode the 48-bit timestamp
_RAND_LEN = 16  # remaining 16 chars encode 80 bits of randomness

_TIME_MAX = (1 << 48) - 1

_lock = threading.Lock()
_last_ms = -1
_last_rand = 0


def _encode(value: int, length: int) -> str:
    """Encode an integer as a fixed-length Crockford Base32 string."""
    chars = []
    for _ in range(length):
        value, rem = divmod(value, 32)
        chars.append(_ALPHABET[rem])
    if value:
        raise ValueError("value too large for the requested encoding length")
    return "".join(reversed(chars))


def new_ulid(timestamp_ms: int | None = None) -> str:
    """Return a new ULID string.

    If *timestamp_ms* is omitted the current wall-clock time is used.
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    if not 0 <= timestamp_ms <= _TIME_MAX:
        raise ValueError(f"timestamp_ms out of range: {timestamp_ms}")
    rand = secrets.randbits(80)
    return _encode(timestamp_ms, _TIME_LEN) + _encode(rand, _RAND_LEN)


def monotonic_ulid() -> str:
    """Return a ULID guaranteed to be strictly increasing within this process.

    When called multiple times in the same millisecond the random component is
    incremented rather than regenerated, preserving sort order for bursts of
    IDs created faster than the clock resolution.
    """
    global _last_ms, _last_rand
    with _lock:
        now = int(time.time() * 1000)
        if now > _last_ms:
            _last_ms = now
            _last_rand = secrets.randbits(80)
        else:
            # Same (or backwards) clock tick: bump the randomness.
            _last_rand += 1
            if _last_rand >= (1 << 80):
                # Overflow: wait for the next millisecond.
                while now <= _last_ms:
                    now = int(time.time() * 1000)
                _last_ms = now
                _last_rand = secrets.randbits(80)
        return _encode(_last_ms, _TIME_LEN) + _encode(_last_rand, _RAND_LEN)


def is_ulid(value: str) -> bool:
    """Return True if *value* is a syntactically valid ULID."""
    if not isinstance(value, str) or len(value) != ULID_LEN:
        return False
    up = value.upper()
    if any(c not in _DECODE for c in up):
        return False
    # The most-significant time character cannot exceed 7 (48-bit limit).
    return up[0] in "01234567"


def timestamp_of(ulid: str) -> int:
    """Extract the millisecond timestamp from a ULID."""
    if not is_ulid(ulid):
        raise ValueError(f"not a valid ULID: {ulid!r}")
    value = 0
    for c in ulid.upper()[:_TIME_LEN]:
        value = value * 32 + _DECODE[c]
    return value


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    print(new_ulid())
    if os.environ.get("LOOPY_ULID_DEMO"):
        for _ in range(3):
            print(monotonic_ulid())
