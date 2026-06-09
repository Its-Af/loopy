"""Host-repo context scanner."""

from __future__ import annotations

from tools.project_scan import context_path, render, scan, write_context


def _make_host(tmp_path):
    host = tmp_path / "acme-api"
    (host / "src").mkdir(parents=True)
    (host / "tests").mkdir()
    (host / "node_modules" / "left-pad").mkdir(parents=True)   # must be ignored
    (host / "loopy" / "tools").mkdir(parents=True)             # framework, ignored
    (host / "package.json").write_text('{"name":"acme-api"}')
    (host / "pyproject.toml").write_text("[project]\nname='acme'")
    (host / "README.md").write_text("# Acme API\n\nA todo service.\n")
    (host / "CLAUDE.md").write_text("Always run tests before committing.")
    (host / "src" / "app.ts").write_text("export const x = 1")
    (host / "src" / "util.py").write_text("def f(): return 1")
    (host / "node_modules" / "left-pad" / "index.js").write_text("//noise")
    (host / "loopy" / "tools" / "x.py").write_text("# framework noise")
    return host


def test_scan_detects_stack_and_excludes_noise(tmp_path):
    info = scan(_make_host(tmp_path))
    assert info["name"] == "acme-api"
    assert "Python" in " ".join(info["manifests"])
    assert any("JavaScript" in m for m in info["manifests"])
    # Languages come from the host's own files, not node_modules or loopy/.
    assert "TypeScript" in info["languages"]
    assert "src" in info["top_dirs"] and "tests" in info["top_dirs"]
    assert "node_modules" not in info["top_dirs"]
    assert "loopy" not in info["top_dirs"]
    # node_modules/left-pad/index.js must not inflate the JS count beyond src.
    assert info["file_count"] < 10        # noise dirs pruned


def test_scan_captures_readme_and_claude(tmp_path):
    info = scan(_make_host(tmp_path))
    assert "Acme API" in info["readme"]
    assert "run tests" in info["claude_md"]


def test_render_has_expected_sections(tmp_path):
    md = render(scan(_make_host(tmp_path)))
    assert md.startswith("# Host project context")
    assert "Top-level directories" in md
    assert "README (excerpt)" in md
    assert "CLAUDE.md" in md


def test_write_context_writes_into_runtime(isolated_runtime):
    # Uses the conftest isolated project as the host.
    path = write_context()
    assert path == context_path()
    assert path.exists()
    assert path.read_text().startswith("# Host project context")
