"""ULID generation: format, sortability, monotonicity, timestamp extraction."""

from __future__ import annotations

import time

import pytest

from tools import ulid


def test_format_is_26_crockford_chars():
    u = ulid.new_ulid()
    assert len(u) == 26
    assert ulid.is_ulid(u)
    assert all(c in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for c in u)


def test_excludes_ambiguous_letters():
    # Crockford base32 never emits I, L, O or U.
    for _ in range(200):
        u = ulid.new_ulid()
        assert not (set(u) & set("ILOU"))


def test_timestamp_roundtrips():
    now_ms = int(time.time() * 1000)
    u = ulid.new_ulid(now_ms)
    assert ulid.timestamp_of(u) == now_ms


def test_lexical_sort_matches_time_order():
    earlier = ulid.new_ulid(1_000_000)
    later = ulid.new_ulid(2_000_000)
    assert earlier < later


def test_monotonic_is_strictly_increasing_and_unique():
    ids = [ulid.monotonic_ulid() for _ in range(5000)]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_is_ulid_rejects_bad_values():
    assert not ulid.is_ulid("")
    assert not ulid.is_ulid("too-short")
    assert not ulid.is_ulid("I" * 26)          # ambiguous char
    assert not ulid.is_ulid("8" + "0" * 25)    # time hi-bit overflow (>7)
    assert not ulid.is_ulid(12345)             # not a string


def test_timestamp_of_rejects_non_ulid():
    with pytest.raises(ValueError):
        ulid.timestamp_of("not-a-ulid")


def test_rejects_out_of_range_timestamp():
    with pytest.raises(ValueError):
        ulid.new_ulid(2 ** 48)  # exceeds 48-bit field
