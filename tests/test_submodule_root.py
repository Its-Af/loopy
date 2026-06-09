"""Regression tests for host-repo root detection when vendored as a submodule.

The bug these guard against: a git submodule stores its ``.git`` as a *gitlink
file*, not a directory. If root detection matched that file, the framework dir
would masquerade as the project root and agents would lose sight of the host
repo. The host repo must always win.
"""

from __future__ import annotations

import pytest

from tools import project_root as pr


@pytest.fixture
def no_env(monkeypatch):
    monkeypatch.delenv("LOOPY_PROJECT_ROOT", raising=False)
    pr.reset_cache()
    yield
    pr.reset_cache()


def _make_submodule(tmp_path):
    """host/  (git repo, .git dir)  +  host/loopy/  (submodule, .git gitlink file)."""
    host = tmp_path / "host"
    (host / ".git").mkdir(parents=True)
    fw = host / "loopy"
    fw.mkdir()
    (fw / ".git").write_text("gitdir: ../.git/modules/loopy\n")
    return host, fw


def test_submodule_root_resolves_to_host_not_loopy(tmp_path, monkeypatch, no_env):
    host, fw = _make_submodule(tmp_path)
    monkeypatch.setattr(pr, "_framework_dir", lambda: fw)
    pr.reset_cache()
    assert pr.find_project_root() == host.resolve()      # not fw!
    assert pr.runtime_dir() == host.resolve() / ".loopy"


def test_submodule_root_when_host_not_yet_git(tmp_path, monkeypatch, no_env):
    # Host is a plain directory (no .git, no .loopy yet) with loopy vendored in.
    host = tmp_path / "plainhost"
    fw = host / "loopy"
    fw.mkdir(parents=True)
    (fw / ".git").write_text("gitdir: elsewhere\n")
    monkeypatch.setattr(pr, "_framework_dir", lambda: fw)
    pr.reset_cache()
    # Falls back to the parent of loopy/ — the host — never loopy/ itself.
    assert pr.find_project_root() == host.resolve()


def test_loopy_own_git_dir_does_not_hijack_root(tmp_path, monkeypatch, no_env):
    # After `git init loopy/` for standalone development, loopy/.git is a *dir*.
    # Vendored inside a git host, the host must still win.
    host, fw = _make_submodule(tmp_path)
    # Replace the gitlink file with a real .git dir (as if loopy were git-init'd).
    (fw / ".git").unlink()
    (fw / ".git").mkdir()
    monkeypatch.setattr(pr, "_framework_dir", lambda: fw)
    pr.reset_cache()
    assert pr.find_project_root() == host.resolve()


def test_deep_invocation_still_finds_host(tmp_path, monkeypatch, no_env):
    host, fw = _make_submodule(tmp_path)
    deep = host / "src" / "pkg" / "mod"
    deep.mkdir(parents=True)
    monkeypatch.setattr(pr, "_framework_dir", lambda: fw)
    pr.reset_cache()
    assert pr.find_project_root(deep) == host.resolve()
