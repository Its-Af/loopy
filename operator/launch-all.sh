#!/usr/bin/env bash
# launch-all.sh — bring up the full squad in a tmux session.
#
# Creates one tmux window per agent in the roster, exports LOOPY_AGENT_ID into
# each, records the agent->pane map for the bus, starts the message bus and the
# watchdog. Re-running attaches to the existing session instead of duplicating.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

loopy_have_tmux || die "tmux is required for launch-all.sh (try launch-headless.sh instead)"
[[ -d "$LOOPY_RUNTIME" ]] || "$LOOPY_FRAMEWORK_DIR/operator/init.sh"

# Refresh the host-repo context the agents read at startup.
"$PY" "$LOOPY_FRAMEWORK_DIR/scripts/scan-project.py" >/dev/null 2>&1 || true

if loopy_session_exists; then
  log "session '$LOOPY_SESSION' already exists — attaching"
  exec "$LOOPY_TMUX" attach -t "$LOOPY_SESSION"
fi

log "starting message bus"
"$LOOPY_FRAMEWORK_DIR/daemons/start-bus.sh"

log "creating tmux session '$LOOPY_SESSION'"
first=1
while read -r agent; do
  [[ -z "$agent" ]] && continue
  role="${agent%%.*}"
  win="$(loopy_window_name "$agent")"
  cmd="$(loopy_agent_cmd "$role")"
  if [[ "$first" == 1 ]]; then
    "$LOOPY_TMUX" new-session -d -s "$LOOPY_SESSION" -n "$win" -c "$LOOPY_ROOT"
    first=0
  else
    "$LOOPY_TMUX" new-window -t "$LOOPY_SESSION" -n "$win" -c "$LOOPY_ROOT"
  fi
  "$LOOPY_TMUX" send-keys -t "$(loopy_pane_target "$agent")" \
    "export LOOPY_AGENT_ID=$agent LOOPY_PROJECT_ROOT=$LOOPY_ROOT" Enter
  "$LOOPY_TMUX" send-keys -t "$(loopy_pane_target "$agent")" "$cmd" Enter
  log "  launched $agent -> $(loopy_pane_target "$agent")"
done < <(loopy_roster)

# Record the pane map so the bus can route wakes.
"$LOOPY_FRAMEWORK_DIR/operator/_write-panes.sh"

log "starting watchdog"
LOOPY_DETACH=1 "$LOOPY_FRAMEWORK_DIR/daemons/watchdog.sh" &

ok "squad up. Attach with: loopy/operator/attach.sh   (detach: Ctrl-b d)"
"$LOOPY_TMUX" attach -t "$LOOPY_SESSION"
