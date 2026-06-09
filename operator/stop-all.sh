#!/usr/bin/env bash
# stop-all.sh — stop every agent, the watchdog, and the message bus.
#
# Leaves all .loopy/ state intact (tasks, memory, inboxes). For a full reset,
# additionally `rm -rf .loopy` afterwards. Use --force to skip confirmation.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

if [[ "$FORCE" != 1 ]]; then
  read -r -p "Stop the entire Loopy squad? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { log "aborted"; exit 0; }
fi

# Watchdog.
if [[ -f "$LOOPY_RUNTIME/watchdog.pid" ]]; then
  kill "$(cat "$LOOPY_RUNTIME/watchdog.pid")" 2>/dev/null || true
  rm -f "$LOOPY_RUNTIME/watchdog.pid"
  log "stopped watchdog"
fi

# Auto-approver, if running.
"$LOOPY_FRAMEWORK_DIR/operator/stop-auto-approve.sh" 2>/dev/null || true

# tmux session.
if loopy_session_exists; then
  "$LOOPY_TMUX" kill-session -t "$LOOPY_SESSION"
  log "killed tmux session '$LOOPY_SESSION'"
fi

# Background process-mode agents (no-tmux launcher).
if [[ -d "$LOOPY_RUNTIME/procs" ]]; then
  stopped=0
  for pidf in "$LOOPY_RUNTIME/procs"/*.pid; do
    [[ -e "$pidf" ]] || continue
    pid="$(cat "$pidf" 2>/dev/null || true)"
    if [[ -n "$pid" ]]; then
      pkill -P "$pid" 2>/dev/null || true   # kill the agent (child of the wrapper)
      kill "$pid" 2>/dev/null || true        # kill the wrapper
      stopped=$((stopped + 1))
    fi
    rm -f "$pidf"
  done
  (( stopped > 0 )) && log "stopped $stopped background agent(s)"
fi

# Message bus (graceful SIGTERM so it cleans up its socket).
if [[ -f "$LOOPY_RUNTIME/bus.pid" ]]; then
  kill -TERM "$(cat "$LOOPY_RUNTIME/bus.pid")" 2>/dev/null || true
  rm -f "$LOOPY_RUNTIME/bus.pid"
  log "stopped message bus"
fi
rm -f "$LOOPY_BUS_SOCK_PATH"

ok "squad stopped. State preserved in $LOOPY_RUNTIME (rm -rf to reset)."
