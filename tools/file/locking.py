"""Advisory file locking via ``fcntl.flock``.

macOS ships no ``flock(1)`` binary, so locking lives in Python where
``fcntl.flock`` is available on every Unix. Locks are *advisory* — they only
constrain processes that also take the lock — which is exactly the cooperative
model Loopy agents use. A dedicated ``<name>.lock`` sidecar file is locked
rather than the data file itself, so the lock survives atomic replaces of the
data file.
"""

from __future__ import annotations

import errno
import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Union

Pathish = Union[str, os.PathLike]


class LockTimeout(TimeoutError):
    """Raised when a lock cannot be acquired within the timeout."""


def lock_path_for(target: Pathish) -> Path:
    """Return the sidecar lock-file path for *target*."""
    target = Path(target)
    return target.with_name(f"{target.name}.lock")


@contextmanager
def file_lock(target: Pathish, *, exclusive: bool = True, timeout: float = 10.0,
              poll: float = 0.05) -> Iterator[Path]:
    """Acquire an advisory lock guarding *target*.

    Parameters
    ----------
    exclusive:
        ``True`` for a write lock (``LOCK_EX``), ``False`` for a shared read
        lock (``LOCK_SH``).
    timeout:
        Seconds to wait before raising :class:`LockTimeout`. ``0`` means a
        single non-blocking attempt.

    Yields the lock-file path while the lock is held.
    """
    lock_file = lock_path_for(target)
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    flag = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH

    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(fd, flag | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                    raise
                if timeout == 0 or time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not lock {lock_file} within {timeout}s"
                    ) from exc
                time.sleep(poll)
        # Record the holder for debugging; never relied upon for correctness.
        try:
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()} {time.time():.3f}\n".encode())
        except OSError:
            pass
        yield lock_file
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
