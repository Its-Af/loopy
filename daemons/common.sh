#!/usr/bin/env bash
# common.sh — shared shell helpers sourced by every operator and daemon script.
#
#   source "$(dirname "$0")/../daemons/common.sh"
#
# Provides: project-root discovery, runtime paths, logging, python selection,
# roster expansion, and tmux helpers. Pure bash; no external deps beyond core
# utilities. Safe to source repeatedly.

# Resolve our own location so sourcing works from any CWD.
LOOPY_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# daemons/ -> framework dir is one up.
LOOPY_FRAMEWORK_DIR="$(cd "$LOOPY_COMMON_DIR/.." && pwd)"

# --- project root + runtime ------------------------------------------------
loopy_project_root() {
  if [[ -n "${LOOPY_PROJECT_ROOT:-}" ]]; then
    printf '%s\n' "$LOOPY_PROJECT_ROOT"
    return 0
  fi
  # When vendored as loopy/, start the search ABOVE the framework dir so the
  # host repo is found — never the submodule itself (whose loopy/.git is a
  # gitlink file). Accept .git as a file or dir (host may be a worktree/submodule).
  local d
  if [[ "$(basename "$LOOPY_FRAMEWORK_DIR")" == "loopy" ]]; then
    d="$(dirname "$LOOPY_FRAMEWORK_DIR")"
  else
    d="$LOOPY_FRAMEWORK_DIR"
  fi
  while [[ "$d" != "/" ]]; do
    if [[ -d "$d/.loopy" || -e "$d/.git" ]]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  # Fall back to the framework's parent.
  dirname "$LOOPY_FRAMEWORK_DIR"
}

LOOPY_ROOT="$(loopy_project_root)"
LOOPY_RUNTIME="$LOOPY_ROOT/.loopy"
LOOPY_CONFIG="$LOOPY_RUNTIME/config.md"
LOOPY_TODO="$LOOPY_ROOT/#TODO"
LOOPY_TOOL="$LOOPY_FRAMEWORK_DIR/scripts/agent-tool.py"
# Honour the LOOPY_BUS_SOCK override (used for deep project paths that would
# blow the ~104-char AF_UNIX limit). Keep this in lockstep with
# tools/project_root.py:bus_socket_path().
LOOPY_BUS_SOCK_PATH="${LOOPY_BUS_SOCK:-$LOOPY_RUNTIME/bus.sock}"

# --- python ----------------------------------------------------------------
loopy_python() {
  if [[ -n "${LOOPY_PYTHON:-}" ]]; then echo "$LOOPY_PYTHON";
  elif [[ -x "$LOOPY_ROOT/.venv/bin/python" ]]; then echo "$LOOPY_ROOT/.venv/bin/python";
  elif command -v python3 >/dev/null 2>&1; then echo python3;
  else echo python; fi
}
PY="$(loopy_python)"

# --- logging ---------------------------------------------------------------
_loopy_ts() { date "+%H:%M:%S"; }
log()  { printf '\033[0;36m[loopy %s]\033[0m %s\n'  "$(_loopy_ts)" "$*"; }
ok()   { printf '\033[0;32m[loopy %s]\033[0m %s\n'  "$(_loopy_ts)" "$*"; }
warn() { printf '\033[0;33m[loopy %s] WARN\033[0m %s\n' "$(_loopy_ts)" "$*" >&2; }
err()  { printf '\033[0;31m[loopy %s] ERROR\033[0m %s\n' "$(_loopy_ts)" "$*" >&2; }
die()  { err "$*"; exit 1; }

# --- tmux ------------------------------------------------------------------
LOOPY_TMUX="${LOOPY_TMUX:-tmux}"
LOOPY_SESSION="${LOOPY_SESSION:-loopy}"
loopy_have_tmux() { command -v "$LOOPY_TMUX" >/dev/null 2>&1; }
loopy_session_exists() { loopy_have_tmux && "$LOOPY_TMUX" has-session -t "$LOOPY_SESSION" 2>/dev/null; }
# Window name for an agent id (tmux dislikes '.').
loopy_window_name() { echo "${1/./-}"; }
loopy_pane_target() { echo "$LOOPY_SESSION:$(loopy_window_name "$1")"; }

# --- claude CLI ------------------------------------------------------------
# Prefer an explicit override, then a global `claude`, then the copy npm
# installs into the framework's node_modules (optionalDependency).
loopy_claude_bin() {
  if [[ -n "${LOOPY_CLAUDE_BIN:-}" ]]; then echo "$LOOPY_CLAUDE_BIN";
  elif command -v claude >/dev/null 2>&1; then echo claude;
  elif [[ -x "$LOOPY_FRAMEWORK_DIR/node_modules/.bin/claude" ]]; then
    echo "$LOOPY_FRAMEWORK_DIR/node_modules/.bin/claude";
  else echo claude; fi
}
LOOPY_CLAUDE="$(loopy_claude_bin)"
loopy_have_claude() { command -v "$LOOPY_CLAUDE" >/dev/null 2>&1 || [[ -x "$LOOPY_CLAUDE" ]]; }

# The exact command each agent pane/process runs. Single source of truth so
# every launcher (tmux, headless, background, docker) stays in sync. Override
# wholesale with LOOPY_AGENT_CMD (use ${ROLE} as a placeholder).
loopy_agent_cmd() {
  local role="$1" interval="${LOOPY_LOOP_INTERVAL:-5m}"
  if [[ -n "${LOOPY_AGENT_CMD:-}" ]]; then
    printf '%s' "${LOOPY_AGENT_CMD//\$\{ROLE\}/$role}"
    return 0
  fi
  local prompt="Read loopy/agents/${role}.md, loopy/protocol/PROTOCOL.md, and the host-repo context in .loopy/project-context.md (also read ./CLAUDE.md and ./README* if they exist). Run your STARTUP, then begin: /loop ${interval} /wizard Read loopy/agents/${role}.md then execute your LOOP steps."
  printf '%s --dangerously-skip-permissions "%s"' "$LOOPY_CLAUDE" "$prompt"
}

# --- roster ----------------------------------------------------------------
# Expand the configured roster to a flat list of agent ids, one per line.
# Falls back to the framework default if no config is present.
loopy_roster() {
  "$LOOPY_FRAMEWORK_DIR/tools/roster.sh"
}

# --- misc ------------------------------------------------------------------
loopy_require_runtime() {
  [[ -d "$LOOPY_RUNTIME" ]] || die ".loopy/ not found — run loopy/operator/init.sh first"
}

# Ensure the host repo's .gitignore excludes the runtime — crucial because
# .loopy/keys.env can hold an API key. No-op if the host isn't a git repo.
# Note the `\#TODO` escaping: a bare leading '#' is a gitignore comment.
loopy_ensure_gitignore() {
  command -v git >/dev/null 2>&1 && git -C "$LOOPY_ROOT" rev-parse >/dev/null 2>&1 || return 0
  local gi="$LOOPY_ROOT/.gitignore"
  if [[ ! -f "$gi" ]] || ! grep -qxF ".loopy/" "$gi" 2>/dev/null; then
    {
      echo ""
      echo "# Loopy runtime state (holds credentials in .loopy/keys.env) — never commit"
      echo ".loopy/"
      echo "\\#TODO"
    } >> "$gi"
  fi
}
