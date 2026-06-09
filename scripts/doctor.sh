#!/usr/bin/env bash
# doctor.sh — report whether this machine is ready to run Loopy.
#
# Exit 0 if the one hard requirement (Python 3.10+) is met; non-zero otherwise.
# tmux / claude / credentials are reported as warnings — Loopy degrades without
# them (background mode, manual launch) but runs best with all three.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

green="\033[0;32m"; red="\033[0;31m"; yellow="\033[0;33m"; dim="\033[0;90m"; off="\033[0m"
pass() { printf "  ${green}✓${off} %s\n" "$*"; }
fail() { printf "  ${red}✗${off} %s\n" "$*"; }
warn_() { printf "  ${yellow}⚠${off} %s\n" "$*"; }
note() { printf "    ${dim}%s${off}\n" "$*"; }

printf "\033[1mLoopy doctor\033[0m\n"
printf "host repo : %s\n" "$LOOPY_ROOT"
printf "framework : %s\n\n" "$LOOPY_FRAMEWORK_DIR"

hard_ok=0

# --- Python (hard requirement) ---
if command -v "$PY" >/dev/null 2>&1; then
  pyver="$("$PY" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null)"
  if "$PY" -c 'import sys;raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
    pass "Python $pyver ($PY)"
  else
    fail "Python $pyver is too old — need 3.10+"; hard_ok=1
  fi
else
  fail "Python 3 not found — install Python 3.10+"; hard_ok=1
fi

# --- tmux (soft) ---
if loopy_have_tmux; then
  pass "tmux ($("$LOOPY_TMUX" -V 2>/dev/null))"
else
  warn_ "tmux not found — 'loopy start' will use background process mode"
  note "install: brew install tmux   |   apt-get install tmux"
fi

# --- claude CLI (soft) ---
if loopy_have_claude; then
  pass "claude CLI ($LOOPY_CLAUDE)"
else
  warn_ "claude CLI not found — agents can't launch until it's installed"
  note "global: npm i -g @anthropic-ai/claude-code   |   local: 'npm install' in loopy/"
fi

# --- credentials (soft) ---
if [[ -n "${ANTHROPIC_API_KEY:-}${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
  pass "Anthropic credentials present in environment"
elif [[ -f "$LOOPY_ROOT/.loopy/keys.env" || -f "$LOOPY_ROOT/.env" ]]; then
  warn_ "credentials not in env, but a keys file exists — source loopy/tools/load-keys.sh"
else
  warn_ "no ANTHROPIC_API_KEY found — set it, or put it in .loopy/keys.env"
fi

# --- node/npm (soft, only needed for the npm install path) ---
if command -v npm >/dev/null 2>&1; then
  pass "npm ($(npm -v 2>/dev/null))"
else
  warn_ "npm not found — use 'make install' or 'loopy install' instead of npm"
fi

# --- runtime + git state (info) ---
[[ -d "$LOOPY_RUNTIME" ]] && pass ".loopy/ runtime initialised" \
  || warn_ ".loopy/ not initialised yet — run 'loopy install' or 'loopy init'"
if command -v git >/dev/null 2>&1 && git -C "$LOOPY_ROOT" rev-parse >/dev/null 2>&1; then
  pass "host is a git repo ($(git -C "$LOOPY_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null))"
else
  warn_ "host is not a git repo — agents work, but git-aware features are limited"
fi

# --- pytest (dev, info) ---
pytest_ok=0
"$PY" -c "import pytest" 2>/dev/null && pytest_ok=1
if (( pytest_ok == 0 )) && [[ -x "$LOOPY_FRAMEWORK_DIR/.venv/bin/python" ]]; then
  "$LOOPY_FRAMEWORK_DIR/.venv/bin/python" -c "import pytest" 2>/dev/null && pytest_ok=1
fi
if (( pytest_ok )); then
  pass "pytest available (can run 'loopy test')"
else
  note "pytest not installed (dev only) — 'loopy install --dev' to add it"
fi

echo
if (( hard_ok == 0 )); then
  printf "${green}Ready.${off} Next: loopy/bin/loopy start\n"
else
  printf "${red}Not ready${off} — install Python 3.10+ and re-run 'loopy doctor'.\n"
fi
exit $hard_ok
