"""``#TODO`` index generation.

The ``#TODO`` file at the project root is the at-a-glance board humans and
agents skim every loop. It is a *projection* — never edited by hand — rebuilt
from the JSON task store whenever a task changes. Grouping is by priority then
state, with recently-completed work listed at the bottom for context.
"""

from __future__ import annotations

import time
from pathlib import Path

from tools.file.atomic_write import atomic_write_text
from tools.project_root import todo_path
from tools.task.crud import Task, list_tasks
from tools.validation.constants import TASK_PRIORITIES

_PRIORITY_ORDER = ["P0", "P1", "P2", "P3"]
_STATE_GLYPH = {
    "OPEN": " ", "REOPENED": "!", "CLAIMED": "~", "IN_PROGRESS": "~",
    "BLOCKED": "x", "REVIEW": "?", "DONE": "x",
}
_DONE_RECENT = 15  # how many completed tasks to show


def _format_task(task: Task) -> str:
    glyph = _STATE_GLYPH.get(task.state, " ")
    owner = f" @{task.owner}" if task.owner else ""
    tags = f" [{', '.join(task.tags)}]" if task.tags else ""
    blocked = f" ⛔{len(task.blocked_by)}" if task.blocked_by else ""
    return (
        f"- [{glyph}] `{task.id}` **{task.state}**{owner} — {task.title}"
        f"{tags}{blocked}"
    )


def render_index(tasks: list[Task] | None = None) -> str:
    tasks = list_tasks() if tasks is None else tasks
    active = [t for t in tasks if not t.is_done]
    done = [t for t in tasks if t.is_done]
    done.sort(key=lambda t: t.updated_at, reverse=True)

    lines: list[str] = [
        "# #TODO",
        "",
        f"_Generated {time.strftime('%Y-%m-%d %H:%M:%S')} — projection of "
        f".loopy/tasks/. Do not edit by hand; use `agent-tool.py task ...`._",
        "",
        f"**{len(active)} open · {len(done)} done**",
        "",
    ]

    for prio in _PRIORITY_ORDER:
        bucket = [t for t in active if t.priority == prio]
        if not bucket:
            continue
        # Open work first within a priority, then in-progress, then blocked.
        bucket.sort(key=lambda t: (t.owner is not None, t.state, t.created_at))
        lines.append(f"## {prio}  ({len(bucket)})")
        lines.extend(_format_task(t) for t in bucket)
        lines.append("")

    untagged_prio = [t for t in active if t.priority not in TASK_PRIORITIES]
    if untagged_prio:
        lines.append("## (no priority)")
        lines.extend(_format_task(t) for t in untagged_prio)
        lines.append("")

    if done:
        lines.append(f"## Done — most recent {min(len(done), _DONE_RECENT)}")
        for t in done[:_DONE_RECENT]:
            who = f" ({t.owner})" if t.owner else ""
            lines.append(f"- [x] `{t.id}` ~~{t.title}~~{who}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def regenerate(path: Path | None = None) -> Path:
    """Rewrite the ``#TODO`` index from the current task store."""
    target = path or todo_path()
    atomic_write_text(target, render_index())
    return target
