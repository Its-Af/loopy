#!/usr/bin/env bash
# launch-headless.sh — run the squad without an interactive tmux attach.
#
# Same as launch-all.sh but never attaches: starts the bus, creates the
# detached tmux session, launches every agent, and starts the headless
# watchdog in the background. Intended for servers, CI, and `forever.sh`.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

loopy_have_tmux || die "tmux is required (even headless, agents run in panes)"
[[ -d "$LOOPY_RUNTIME" ]] || "$LOOPY_FRAMEWORK_DIR/operator/init.sh"

if loopy_session_exists; then
  ok "session '$LOOPY_SESSION' already running (headless)"
  exit 0
fi

"$PY" "$LOOPY_FRAMEWORK_DIR/scripts/scan-project.py" >/dev/null 2>&1 || true
"$LOOPY_FRAMEWORK_DIR/daemons/start-bus.sh"

first=1
while read -r agent; do
  [[ -z "$agent" ]] && continue
  role="${agent%%.*}"
  win="$(loopy_window_name "$agent")"
  cmd="$(loopy_agent_cmd "$role")"
  if [[ "$first" == 1 ]]; then
    "$LOOPY_TMUX" new-session -d -s "$LOOPY_SESSION" -n "$win" -c "$LOOPY_ROOT"; first=0
  else
    "$LOOPY_TMUX" new-window -t "$LOOPY_SESSION" -n "$win" -c "$LOOPY_ROOT"
  fi
  t="$(loopy_pane_target "$agent")"
  "$LOOPY_TMUX" send-keys -t "$t" "export LOOPY_AGENT_ID=$agent LOOPY_PROJECT_ROOT=$LOOPY_ROOT; source loopy/tools/load-keys.sh >/dev/null 2>&1 || true" Enter
  "$LOOPY_TMUX" send-keys -t "$t" "$cmd" Enter
  log "launched $agent (headless)"
done < <(loopy_roster)

"$LOOPY_FRAMEWORK_DIR/operator/_write-panes.sh"
nohup "$LOOPY_FRAMEWORK_DIR/operator/watchdog-headless.sh" \
  >>"$LOOPY_RUNTIME/logs/watchdog.log" 2>&1 &
ok "squad running headless in session '$LOOPY_SESSION'. Status: operator/status.sh"
