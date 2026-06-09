"""Canary — tamper detection for the protocol and agent-profile hot files.

The rules an agent obeys live in `loopy/protocol/` and `loopy/agents/`. If an
injected instruction (or a buggy agent) rewrites those, the whole squad's
behaviour could be subverted silently. The canary is a manifest of SHA-256
hashes of every hot file, captured when the squad starts. `execs`/`securities`
re-verify it each round; any drift that wasn't an authorised change halts task
assignment and is surfaced to the human.

This is integrity detection, not access control — it catches changes after the
fact rather than preventing them, which is the right tool for a cooperative
multi-agent system where the files must remain editable for legitimate updates.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from tools.project_root import find_project_root, runtime_dir

# Framework dir = loopy/  (this file is loopy/tools/canary.py)
_FRAMEWORK_DIR = Path(__file__).resolve().parents[1]

#: Globs (relative to the framework dir) whose files are integrity-protected.
HOT_GLOBS = ("protocol/**/*.md", "agents/**/*.md")


def manifest_path() -> Path:
    return runtime_dir() / "canary.json"


def _hot_files() -> list[Path]:
    files: set[Path] = set()
    for glob in HOT_GLOBS:
        files.update(p for p in _FRAMEWORK_DIR.glob(glob) if p.is_file())
    return sorted(files)


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def compute_manifest() -> dict[str, str]:
    """Map each hot file (key relative to project root) to its SHA-256."""
    root = find_project_root()
    out: dict[str, str] = {}
    for path in _hot_files():
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        out[str(rel)] = _hash(path)
    return out


def write_manifest() -> Path:
    """Capture the current hot-file hashes to `.loopy/canary.json`."""
    from tools.file.atomic_write import atomic_write_text
    data = {"generated_at": time.time(), "files": compute_manifest()}
    path = manifest_path()
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True))
    return path


@dataclass
class CanaryResult:
    ok: bool
    modified: list[str]
    added: list[str]
    removed: list[str]

    @property
    def drift(self) -> list[str]:
        return (
            [f"MODIFIED {f}" for f in self.modified]
            + [f"ADDED {f}" for f in self.added]
            + [f"REMOVED {f}" for f in self.removed]
        )

    def as_dict(self) -> dict:
        return {"ok": self.ok, "modified": self.modified,
                "added": self.added, "removed": self.removed}


def verify() -> CanaryResult:
    """Compare current hot files against the stored manifest."""
    try:
        stored = json.loads(manifest_path().read_text()).get("files", {})
    except (FileNotFoundError, json.JSONDecodeError):
        # No manifest yet -> treat everything as "added" (i.e. not yet trusted).
        current = compute_manifest()
        return CanaryResult(False, [], sorted(current), [])

    current = compute_manifest()
    modified, added, removed = [], [], []
    for f, h in current.items():
        if f not in stored:
            added.append(f)
        elif stored[f] != h:
            modified.append(f)
    for f in stored:
        if f not in current:
            removed.append(f)
    ok = not (modified or added or removed)
    return CanaryResult(ok, sorted(modified), sorted(added), sorted(removed))
