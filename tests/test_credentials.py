"""Credential preflight + verification (deterministic, no network).

`verify-credentials.py` short-circuits to exit 2 before any HTTP call when no
credentials are present, so these stay offline-safe. The interactive prompt
path (needs a TTY) isn't unit-tested here; the non-interactive branches are.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

FW = Path(__file__).resolve().parents[1]
VERIFY = FW / "scripts" / "verify-credentials.py"
PREFLIGHT = FW / "scripts" / "preflight-credentials.sh"
COMMON = FW / "daemons" / "common.sh"


def _run(cmd, env_extra, cwd=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("ANTHROPIC_")}        # clean credential slate
    env.update(env_extra)
    return subprocess.run(cmd, capture_output=True, text=True, env=env,
                          cwd=cwd, timeout=30)


# --- verify-credentials.py -------------------------------------------------
def test_verify_no_creds_exits_2(isolated_runtime):
    r = _run(["python3", str(VERIFY)], {"LOOPY_PROJECT_ROOT": str(isolated_runtime)})
    assert r.returncode == 2
    assert "no credentials" in r.stdout.lower()


def test_verify_no_creds_json(isolated_runtime):
    r = _run(["python3", str(VERIFY), "--json"],
             {"LOOPY_PROJECT_ROOT": str(isolated_runtime)})
    import json
    assert r.returncode == 2 and json.loads(r.stdout)["status"] == "no-credentials"


# --- preflight (non-interactive: stdin is a pipe, never a TTY here) ---------
def test_preflight_no_creds_warns_but_does_not_block(isolated_runtime):
    r = _run(["bash", str(PREFLIGHT)],
             {"LOOPY_PROJECT_ROOT": str(isolated_runtime), "HOME": str(isolated_runtime)})
    assert r.returncode == 0                          # never hard-blocks the launch
    assert "no Anthropic credentials" in (r.stdout + r.stderr)


def test_preflight_finds_stored_key(isolated_runtime):
    # Simulate a previously-stored key; offline verify -> exit 2 -> "present".
    keys = isolated_runtime / ".loopy" / "keys.env"
    keys.parent.mkdir(parents=True, exist_ok=True)
    keys.write_text("ANTHROPIC_API_KEY=sk-ant-fake-offline\n")
    r = _run(["bash", str(PREFLIGHT)],
             {"LOOPY_PROJECT_ROOT": str(isolated_runtime),
              "ANTHROPIC_BASE_URL": "http://127.0.0.1:9"})  # force unreachable, fast
    assert r.returncode == 0
    blob = r.stdout + r.stderr
    assert "no Anthropic credentials" not in blob       # it DID find the stored key


# --- loopy_ensure_gitignore (shell function) -------------------------------
def test_ensure_gitignore_protects_runtime(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=host, check=True)
    snippet = (f'source "{COMMON}"; loopy_ensure_gitignore')
    _run(["bash", "-c", snippet], {"LOOPY_PROJECT_ROOT": str(host)})
    gi = (host / ".gitignore").read_text()
    assert ".loopy/" in gi
    assert "\\#TODO" in gi                              # escaped so it's not a comment


def test_ensure_gitignore_idempotent(tmp_path):
    host = tmp_path / "host"
    host.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=host, check=True)
    snippet = f'source "{COMMON}"; loopy_ensure_gitignore; loopy_ensure_gitignore'
    _run(["bash", "-c", snippet], {"LOOPY_PROJECT_ROOT": str(host)})
    gi = (host / ".gitignore").read_text()
    # Count the exact pattern *line* (the comment also contains the substring).
    assert gi.splitlines().count(".loopy/") == 1        # added once, not twice
