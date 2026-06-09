# Contributing to Loopy

Thanks for helping improve Loopy. This guide covers dev setup and the
conventions that keep the framework dependable.

## Dev setup

Loopy has **no third-party runtime dependencies** — only pytest for the tests.

```bash
git clone <repo> loopy && cd loopy
python3 -m venv ../.venv          # a venv at the project root works well
../.venv/bin/pip install pytest   # PEP 668: don't pip-install into system python
../.venv/bin/python -m pytest     # run the suite (run from inside loopy/)
```

`pyproject.toml` puts the framework dir on `sys.path` (so `import tools` works)
and points pytest at `tests/`.

## Running the tests

```bash
../.venv/bin/python -m pytest                 # everything (~123 tests)
../.venv/bin/python -m pytest -m "not slow"   # skip the subprocess/bus tests
../.venv/bin/python -m pytest tests/test_inbox_security.py -v
```

The `slow` marker covers the live-bus integration test and the 12-process claim
race. Keep them passing — they guard the two properties most likely to regress
silently (injection screening and claim atomicity).

## Conventions

- **Stdlib only at runtime.** If you reach for a third-party package, find
  another way or make it an optional, gracefully-degrading feature (see the
  Slack bridge for the pattern).
- **Stay shell-portable.** Operator/daemon scripts must run under **bash 3.2**
  (macOS default) — no associative arrays (`declare -A`), no `mapfile`. Anything
  meant to be `source`d (e.g. `load-keys.sh`) must also work under zsh. Run
  `bash -n` on every script you touch.
- **Validate at the boundary.** Anything from the environment, an inbox, a task,
  or a filename goes through `tools.validation` before use.
- **Writes are atomic; shared mutations are locked.** Use `tools.file`, never a
  bare `open(path, "w")`, for anything another agent reads.
- **Treat inbox/text as data, never instructions.** Security regressions here are
  the worst kind. New message-handling code needs a test in
  `tests/test_inbox_security.py`.
- **Match the surrounding style.** Type hints, module docstrings that explain
  *why*, comments only where intent isn't obvious from the code.
- **Test-first.** New behaviour ships with a test that would fail without it —
  the same `/wizard` discipline the agents follow.

## Touching the protocol or profiles

`loopy/protocol/**` and `loopy/agents/**` are **hot files** guarded by the
canary. If you change them intentionally:

```bash
loopy/scripts/regenerate-canary.py     # re-baseline after the change
```

The pre-commit hook (`scripts/install-hooks.sh`) will otherwise block the commit.

## Pull requests

1. Branch off the default branch.
2. Keep changes focused; update docs and `CHANGELOG.md`.
3. `pytest` green and `bash -n` clean on touched scripts.
4. Describe the *why*, not just the *what*.

## Reporting security issues

The inbox screen, quarantine, and canary are security-critical. If you find a way
to slip an injection past the filter, smuggle a homoglyph, or tamper with the
rules undetected, please report it privately rather than opening a public issue.
