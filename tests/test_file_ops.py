"""Atomic writes, advisory locks, and intent locks."""

from __future__ import annotations

import threading
import time

import pytest

from tools.file.atomic_write import (
    atomic_write_bytes,
    atomic_write_text,
    create_exclusive,
)
from tools.file.intent_lock import (
    declare_intent,
    is_available,
    read_intent,
    release_intent,
)
from tools.file.locking import LockTimeout, file_lock


def test_atomic_write_overwrites_cleanly(tmp_path):
    p = tmp_path / "sub" / "f.txt"
    atomic_write_text(p, "one")
    assert p.read_text() == "one"
    atomic_write_text(p, "two")
    assert p.read_text() == "two"
    # No leftover temp files in the directory.
    assert [x.name for x in p.parent.iterdir()] == ["f.txt"]


def test_atomic_write_bytes(tmp_path):
    p = tmp_path / "f.bin"
    atomic_write_bytes(p, b"\x00\x01\x02")
    assert p.read_bytes() == b"\x00\x01\x02"


def test_create_exclusive_is_create_iff_absent(tmp_path):
    p = tmp_path / "once.txt"
    assert create_exclusive(p, b"first") is True
    assert create_exclusive(p, b"second") is False
    assert p.read_bytes() == b"first"


def test_file_lock_is_mutually_exclusive(tmp_path):
    target = tmp_path / "resource"
    target.write_text("x")
    order = []

    def worker(tag):
        with file_lock(target, timeout=5):
            order.append(f"{tag}-enter")
            time.sleep(0.2)
            order.append(f"{tag}-exit")

    with file_lock(target):
        t = threading.Thread(target=worker, args=("B",))
        t.start()
        time.sleep(0.2)
        order.append("A-holds")
    t.join()
    # B must not enter until A has released.
    assert order[0] == "A-holds"
    assert order[1:] == ["B-enter", "B-exit"]


def test_file_lock_timeout(tmp_path):
    target = tmp_path / "resource"

    def hold():
        with file_lock(target):
            time.sleep(0.5)

    t = threading.Thread(target=hold)
    t.start()
    time.sleep(0.1)
    with pytest.raises(LockTimeout):
        with file_lock(target, timeout=0):  # non-blocking attempt
            pass
    t.join()


def test_intent_lock_excludes_others():
    assert declare_intent("/repo/a.py", "producers.1") is not None
    assert declare_intent("/repo/a.py", "producers.2") is None      # taken
    assert declare_intent("/repo/a.py", "producers.1") is not None  # own refresh
    assert read_intent("/repo/a.py").owner == "producers.1"
    assert is_available("/repo/a.py", "producers.1") is True
    assert is_available("/repo/a.py", "producers.2") is False


def test_intent_release_only_by_owner():
    declare_intent("/repo/b.py", "producers.1")
    assert release_intent("/repo/b.py", "producers.2") is False
    assert release_intent("/repo/b.py", "producers.1") is True
    assert read_intent("/repo/b.py") is None


def test_intent_expires(monkeypatch):
    declare_intent("/repo/c.py", "producers.1", ttl=0.05)
    time.sleep(0.1)
    assert read_intent("/repo/c.py") is None       # expired -> treated as free
    assert declare_intent("/repo/c.py", "producers.2") is not None
