"""Project goal — the squad's single standing instruction.

The "## Project goal" section of ``.loopy/config.md`` is what the human wants
built. Alfred (the human's interface) keeps it current as the user clarifies or
changes direction; execs reads it to steer priorities. This module reads and
rewrites just that section, atomically, leaving the roster/settings the user
edited untouched.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from tools.file.atomic_write import atomic_write_text
from tools.file.locking import file_lock
from tools.project_root import runtime_dir
from tools.time import iso

_HEADING = "## Project goal"
_HEADING_RE = re.compile(r"^##\s+project\s+goal\b.*$", re.IGNORECASE)
_NEXT_SECTION_RE = re.compile(r"^##\s+")
_STAMP_RE = re.compile(r"^<!--\s*goal updated:.*-->\s*$")

# Shown when no goal has been set yet (also the sample's placeholder intent).
_PLACEHOLDER = (
    "Describe what you want the squad to build or maintain. This is the human's "
    "standing instruction; agents read it to orient."
)


def config_path() -> Path:
    return runtime_dir() / "config.md"


def _split_sections(text: str) -> tuple[list[str], int, int]:
    """Return (lines, goal_body_start, goal_body_end) indices.

    goal_body spans the lines *after* the heading up to (excluding) the next
    ``## `` heading or EOF. If there is no goal heading, both indices are -1.
    """
    lines = text.splitlines()
    start = -1
    for i, line in enumerate(lines):
        if _HEADING_RE.match(line):
            start = i
            break
    if start == -1:
        return lines, -1, -1
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _NEXT_SECTION_RE.match(lines[j]):
            end = j
            break
    return lines, start + 1, end


def read_goal() -> str:
    """Return the current project goal text (without markdown decoration).

    Empty string if no goal is set (or only the placeholder remains).
    """
    try:
        text = config_path().read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    lines, body_start, body_end = _split_sections(text)
    if body_start == -1:
        return ""
    collected: list[str] = []
    for line in lines[body_start:body_end]:
        if _STAMP_RE.match(line):
            continue
        stripped = line.strip()
        if stripped.startswith(">"):
            collected.append(stripped[1:].strip())
        elif stripped:
            collected.append(stripped)
        else:
            collected.append("")
    goal = "\n".join(collected).strip()
    if not goal or goal.startswith(_PLACEHOLDER[:30]):
        return ""
    return goal


def _render_section(goal: str, by: str) -> list[str]:
    body = [f"> {ln}" if ln else ">" for ln in goal.splitlines()] or ["> (none)"]
    return [_HEADING, "", *body, "", f"<!-- goal updated: {iso()} by {by} -->"]


def set_goal(goal: str, *, by: str = "alfred") -> str:
    """Replace the project-goal section with *goal*. Returns the stored text.

    Creates a minimal config.md if none exists yet (roster then falls back to
    framework defaults). Concurrency-safe via a lock on the config file.
    """
    goal = goal.strip()
    if not goal:
        raise ValueError("goal must not be empty")
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with file_lock(path, timeout=10.0):
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = "# Loopy Squad Configuration\n"
        lines, body_start, body_end = _split_sections(text)
        section = _render_section(goal, by)

        if body_start == -1:
            # No goal section yet — append one.
            new_lines = lines + ([""] if (lines and lines[-1].strip()) else []) + section
        else:
            heading_idx = body_start - 1
            new_lines = lines[:heading_idx] + section + lines[body_end:]
        atomic_write_text(path, "\n".join(new_lines).rstrip() + "\n")
    return goal


def goal_summary() -> str:
    """One-line human summary for status output."""
    g = read_goal()
    if not g:
        return "(no project goal set — tell alfred what to build)"
    first = g.splitlines()[0]
    return first if len(first) <= 100 else first[:97] + "…"
