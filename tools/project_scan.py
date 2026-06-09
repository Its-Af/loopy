"""Host-repo context scanner.

When Loopy is added to a project, the squad needs to understand *what it has
been dropped into*. This module inspects the host repository — languages,
manifests, top-level layout, README/CLAUDE.md, git remote — and renders a
compact ``.loopy/project-context.md`` that every agent reads at startup. It is
the bridge for "once added, it has the context of the entire repo".

Deliberately excludes the framework itself (``loopy/``), the runtime
(``.loopy/``), and dependency/build noise, so the picture is the *host's*, not
Loopy's. Standard library only; bounded so it stays fast on large repos.
"""

from __future__ import annotations

import subprocess
from collections import Counter
from pathlib import Path

from tools.file.atomic_write import atomic_write_text
from tools.project_root import find_project_root, runtime_dir

# Directories never descended into (noise, deps, the framework + runtime).
_SKIP_DIRS = {
    ".git", ".loopy", "loopy", "node_modules", ".venv", "venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build", ".next",
    "target", ".idea", ".vscode", ".gradle", "vendor", ".tox", "coverage",
    ".terraform", ".cache",
}

# Manifest file -> ecosystem label.
_MANIFESTS = {
    "package.json": "JavaScript/TypeScript (npm)",
    "pnpm-lock.yaml": "JavaScript (pnpm)",
    "yarn.lock": "JavaScript (yarn)",
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "requirements.txt": "Python",
    "Pipfile": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "build.gradle.kts": "Kotlin (Gradle)",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "mix.exs": "Elixir",
    "pubspec.yaml": "Dart/Flutter",
    "CMakeLists.txt": "C/C++ (CMake)",
    "Makefile": "Make",
    "Dockerfile": "Docker",
}

_EXT_LANG = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust",
    ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP",
    ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".cs": "C#",
    ".swift": "Swift", ".m": "Objective-C", ".scala": "Scala", ".ex": "Elixir",
    ".sh": "Shell", ".dart": "Dart", ".vue": "Vue", ".sql": "SQL",
}

_README_NAMES = ("README.md", "README.rst", "README.txt", "README")
_MAX_FILES = 20000          # walk budget
_README_LINES = 40
_CLAUDE_LINES = 60


def _git(root: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _read_excerpt(path: Path, max_lines: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    excerpt = "\n".join(lines[:max_lines]).strip()
    if len(lines) > max_lines:
        excerpt += "\n…(truncated)"
    return excerpt


def scan(root: Path | None = None) -> dict:
    """Return a structured snapshot of the host repository."""
    root = Path(root) if root else find_project_root()
    manifests: list[str] = []
    ext_counter: Counter[str] = Counter()
    files_seen = 0

    for path in root.rglob("*"):
        # Prune skip dirs cheaply by checking the path's parts.
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.is_dir():
            continue
        files_seen += 1
        if files_seen > _MAX_FILES:
            break
        name = path.name
        if name in _MANIFESTS and path.parent == root:
            manifests.append(_MANIFESTS[name])
        elif name in _MANIFESTS and len(path.relative_to(root).parts) <= 2:
            manifests.append(_MANIFESTS[name])
        ext = path.suffix.lower()
        if ext in _EXT_LANG:
            ext_counter[_EXT_LANG[ext]] += 1

    # Top-level layout (host's own dirs/files, framework + noise excluded).
    top_dirs, top_files = [], []
    for child in sorted(root.iterdir()):
        if child.name in _SKIP_DIRS or child.name.startswith("."):
            continue
        (top_dirs if child.is_dir() else top_files).append(child.name)

    readme = ""
    for cand in _README_NAMES:
        if (root / cand).is_file():
            readme = _read_excerpt(root / cand, _README_LINES)
            break
    claude_md = ""
    if (root / "CLAUDE.md").is_file():
        claude_md = _read_excerpt(root / "CLAUDE.md", _CLAUDE_LINES)

    return {
        "root": str(root),
        "name": root.name,
        "git_remote": _git(root, "remote", "get-url", "origin"),
        "git_branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"),
        "manifests": sorted(set(manifests)),
        "languages": [lang for lang, _ in ext_counter.most_common(6)],
        "language_counts": dict(ext_counter.most_common(6)),
        "top_dirs": top_dirs[:40],
        "top_files": top_files[:40],
        "file_count": files_seen,
        "readme": readme,
        "claude_md": claude_md,
        "truncated": files_seen > _MAX_FILES,
    }


def render(info: dict) -> str:
    """Render the scan as the markdown agents read at startup."""
    L: list[str] = [
        f"# Host project context — `{info['name']}`",
        "",
        "_Auto-generated by Loopy (`scripts/scan-project.py`). This is the repo "
        "the squad has been added to. Read it at startup to understand what "
        "you are working on. Re-generate after big structural changes._",
        "",
        f"- **Root:** `{info['root']}`",
    ]
    if info["git_remote"]:
        L.append(f"- **Git remote:** {info['git_remote']}")
    if info["git_branch"]:
        L.append(f"- **Branch:** {info['git_branch']}")
    if info["manifests"]:
        L.append(f"- **Stack:** {', '.join(info['manifests'])}")
    if info["languages"]:
        counts = ", ".join(f"{lang} ({info['language_counts'][lang]})"
                           for lang in info["languages"])
        L.append(f"- **Languages (by file count):** {counts}")
    L.append(f"- **Files scanned:** {info['file_count']}"
             + (" (truncated)" if info["truncated"] else ""))
    L.append("")

    if info["top_dirs"]:
        L.append("## Top-level directories")
        L.extend(f"- `{d}/`" for d in info["top_dirs"])
        L.append("")
    if info["top_files"]:
        L.append("## Top-level files")
        L.append(", ".join(f"`{f}`" for f in info["top_files"]))
        L.append("")
    if info["readme"]:
        L.append("## README (excerpt)")
        L.append("```")
        L.append(info["readme"])
        L.append("```")
        L.append("")
    if info["claude_md"]:
        L.append("## CLAUDE.md (host instructions — excerpt)")
        L.append("```")
        L.append(info["claude_md"])
        L.append("```")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def context_path() -> Path:
    return runtime_dir() / "project-context.md"


def write_context(root: Path | None = None) -> Path:
    """Scan the host repo and write `.loopy/project-context.md`."""
    info = scan(root)
    path = context_path()
    atomic_write_text(path, render(info))
    return path
