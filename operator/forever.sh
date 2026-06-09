#!/usr/bin/env bash
# forever.sh — keep the squad running 24/7.
#
# A simple supervision loop: if the tmux session ever disappears, relaunch it
# headless. Intended to be the entry point a launchd/systemd unit calls (see
# install-daemon.sh), but also usable directly in a terminal.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

CHECK="${LOOPY_FOREVER_INTERVAL:-60}"
log "forever mode: supervising squad every ${CHECK}s (Ctrl-C to stop supervising)"
while true; do
  if ! loopy_session_exists; then
    warn "squad not running — launching headless"
    "$LOOPY_FRAMEWORK_DIR/operator/launch-headless.sh" || err "launch failed; retrying"
  fi
  # Keep the auto-approver running if configured.
  if grep -qiE '^\s*-?\s*auto_approve\s*:\s*on' "$LOOPY_CONFIG" 2>/dev/null \
     && [[ ! -f "$LOOPY_RUNTIME/auto-approve.pid" ]]; then
    nohup "$LOOPY_FRAMEWORK_DIR/daemons/auto-approve.sh" \
      >>"$LOOPY_RUNTIME/logs/auto-approve.log" 2>&1 &
  fi
  sleep "$CHECK"
done
