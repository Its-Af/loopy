"""Project-root and runtime-directory discovery.

Loopy is designed to live as a git submodule named ``loopy/`` inside a host
project. All mutable runtime state lives in a sibling ``.loopy/`` directory at
the project root, so that the framework checkout itself stays clean.

This module locates both directories deterministically from anywhere in the
tree, with an environment-variable escape hatch for tests and containers.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

#: Name of the mutable runtime-state directory.
RUNTIME_DIRNAME = ".loopy"
#: Name of the framework submodule directory.
FRAMEWORK_DIRNAME = "loopy"


def _framework_dir() -> Path:
    """Absolute path to the framework checkout (the ``loopy/`` directory)."""
    # This file is loopy/tools/project_root.py -> framework dir is parents[1].
    return Path(__file__).resolve().parents[1]


def _is_project_root(path: Path) -> bool:
    """True if *path* looks like a host project root.

    A root either already has a ``.loopy/`` runtime directory, or is a git
    checkout. We accept ``.git`` as a *file* too: a submodule or linked worktree
    stores ``.git`` as a gitlink file rather than a directory.
    """
    if (path / RUNTIME_DIRNAME).is_dir():
        return True
    git = path / ".git"
    return git.is_dir() or git.is_file()


@lru_cache(maxsize=None)
def find_project_root(start: str | os.PathLike[str] | None = None) -> Path:
    """Return the host project's root directory.

    Resolution order:

    1. ``LOOPY_PROJECT_ROOT`` environment variable, if set.
    2. Walk upward looking for a ``.loopy/`` runtime dir or a git checkout.
    3. Fall back to the parent of the framework directory.

    When Loopy is vendored as ``loopy/`` (the intended submodule layout) the
    search starts *above* the framework directory, so the host repo — not the
    submodule itself — is found. This matters specifically for submodules: a
    submodule's own ``loopy/.git`` is a gitlink file that would otherwise make
    the framework dir masquerade as the project root.
    """
    env = os.environ.get("LOOPY_PROJECT_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    fw = _framework_dir()
    if start is not None:
        origin = Path(start).resolve()
        if origin.is_file():
            origin = origin.parent
    elif fw.name == FRAMEWORK_DIRNAME:
        # Vendored: the host root is an ancestor of loopy/, never loopy/ itself.
        origin = fw.parent
    else:
        # Standalone / dev checkout (not named "loopy"): it can be its own root.
        origin = fw

    for candidate in (origin, *origin.parents):
        if candidate == fw:
            continue  # never treat the framework dir as the host root
        if _is_project_root(candidate):
            return candidate

    # Nothing found: assume the framework sits directly under the project root.
    return fw.parent if fw.name == FRAMEWORK_DIRNAME else fw


def runtime_dir(start: str | os.PathLike[str] | None = None) -> Path:
    """Absolute path to the ``.loopy/`` runtime-state directory."""
    return find_project_root(start) / RUNTIME_DIRNAME


# Backwards-compatible alias used throughout the codebase.
loopy_dir = runtime_dir


def runtime_subdir(*parts: str, create: bool = False) -> Path:
    """Return a path inside ``.loopy/``, optionally creating it.

    Example::

        runtime_subdir("inbox", "producers.1", create=True)
    """
    path = runtime_dir().joinpath(*parts)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def bus_socket_path() -> Path:
    """Absolute path to the message-bus Unix domain socket."""
    env = os.environ.get("LOOPY_BUS_SOCK")
    if env:
        return Path(env).expanduser()
    return runtime_dir() / "bus.sock"


def todo_path() -> Path:
    """Absolute path to the generated ``#TODO`` index at the project root."""
    env = os.environ.get("LOOPY_TODO_PATH")
    if env:
        return Path(env).expanduser()
    return find_project_root() / "#TODO"


def reset_cache() -> None:
    """Clear the memoised project root (used by tests that move CWD around)."""
    find_project_root.cache_clear()


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    print("project_root:", find_project_root())
    print("runtime_dir :", runtime_dir())
    print("bus_socket  :", bus_socket_path())
