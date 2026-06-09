"""The ``#TODO`` index projection."""

from __future__ import annotations

from tools.task import crud
from tools.task.index import regenerate, render_index
from tools.project_root import todo_path


def test_render_groups_by_priority():
    crud.create_task("urgent", priority="P0")
    crud.create_task("later", priority="P3")
    out = render_index()
    assert "## P0" in out and "## P3" in out
    assert out.index("## P0") < out.index("## P3")   # P0 listed first


def test_done_tasks_in_done_section():
    t = crud.create_task("finish me", priority="P1")
    crud.claim_task(t.id, "producers.1")
    crud.complete_task(t.id, "producers.1")
    out = render_index()
    assert "Done" in out
    assert t.id in out
    assert "## P1" not in out      # no active P1 tasks remain


def test_regenerate_writes_todo_file():
    crud.create_task("something")
    path = regenerate()
    assert path == todo_path()
    assert path.exists()
    assert path.read_text().startswith("# #TODO")


def test_empty_index_is_valid():
    out = render_index()
    assert "0 open" in out
