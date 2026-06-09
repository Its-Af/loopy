"""Atomic file writes.

Multiple agents read shared state concurrently. A half-written file must never
be observable, so every write goes to a uniquely-named temporary file in the
*same directory* (to guarantee an atomic ``rename`` on the same filesystem),
is flushed to disk, and is then ``os.replace``-d over the target. Readers
either see the old file or the new file — never a torn one.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

Pathish = Union[str, os.PathLike]


def atomic_write_bytes(path: Pathish, data: bytes, *, mode: int = 0o644,
                       fsync: bool = True) -> None:
    """Atomically write *data* to *path*."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp name in the same directory keeps the final rename atomic.
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{os.urandom(4).hex()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            if fsync:
                os.fsync(fh.fileno())
        os.replace(tmp, path)
        if fsync:
            _fsync_dir(path.parent)
    except BaseException:
        # Best-effort cleanup of the temp file on any failure.
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def atomic_write_text(path: Pathish, text: str, *, encoding: str = "utf-8",
                      mode: int = 0o644, fsync: bool = True) -> None:
    """Atomically write *text* to *path*."""
    atomic_write_bytes(path, text.encode(encoding), mode=mode, fsync=fsync)


def _fsync_dir(directory: Path) -> None:
    """fsync a directory so the rename is durable across a crash."""
    try:
        dfd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dfd)
    except OSError:
        pass  # Some filesystems disallow directory fsync; ignore.
    finally:
        os.close(dfd)


def create_exclusive(path: Pathish, data: bytes, *, mode: int = 0o644) -> bool:
    """Create *path* with *data* only if it does not already exist.

    Returns True on creation, False if the file already existed. This is the
    primitive behind atomic inbox delivery and task claiming — the ``O_EXCL``
    flag makes "create iff absent" a single uninterruptible syscall.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError:
        return False
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
    finally:
        _fsync_dir(path.parent)
    return True
