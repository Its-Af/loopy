#!/usr/bin/env bash
# start.sh — launch (or relaunch) a single agent into the tmux session.
#
#   loopy/operator/start.sh producers.2
#
# Useful for bringing back an agent the watchdog couldn't, or adding one
# ad hoc. Creates the session if it doesn't exist yet.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

agent="${1:-}"
[[ -z "$agent" ]] && die "usage: start.sh <agent-id>   e.g. producers.2"
loopy_have_tmux || die "tmux is required for start.sh"
loopy_require_runtime

# Validate the agent id against the framework's rules.
"$PY" "$LOOPY_TOOL" --json read-state --agent "$agent" >/dev/null 2>&1 || \
  "$PY" -c "import sys; sys.path.insert(0,'$LOOPY_FRAMEWORK_DIR'); \
from tools.validation import validate_agent; validate_agent('$agent')" \
  || die "invalid agent id: $agent"

role="${agent%%.*}"
win="$(loopy_window_name "$agent")"
cmd="$(loopy_agent_cmd "$role")"

if ! loopy_session_exists; then
  "$LOOPY_TMUX" new-session -d -s "$LOOPY_SESSION" -n "$win" -c "$LOOPY_ROOT"
elif "$LOOPY_TMUX" list-windows -t "$LOOPY_SESSION" -F '#W' | grep -qx "$win"; then
  warn "window for $agent exists; killing and relaunching"
  "$LOOPY_TMUX" kill-window -t "$(loopy_pane_target "$agent")" 2>/dev/null || true
  "$LOOPY_TMUX" new-window -t "$LOOPY_SESSION" -n "$win" -c "$LOOPY_ROOT"
else
  "$LOOPY_TMUX" new-window -t "$LOOPY_SESSION" -n "$win" -c "$LOOPY_ROOT"
fi

target="$(loopy_pane_target "$agent")"
"$LOOPY_TMUX" send-keys -t "$target" \
  "export LOOPY_AGENT_ID=$agent LOOPY_PROJECT_ROOT=$LOOPY_ROOT" Enter
"$LOOPY_TMUX" send-keys -t "$target" "$cmd" Enter
"$LOOPY_FRAMEWORK_DIR/operator/_write-panes.sh"
ok "started $agent -> $target"
