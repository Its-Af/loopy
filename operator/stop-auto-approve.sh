#!/usr/bin/env bash
# stop-auto-approve.sh — stop the YOLO auto-approver daemon.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"
PIDFILE="$LOOPY_RUNTIME/auto-approve.pid"
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  kill "$(cat "$PIDFILE")" 2>/dev/null || true
  rm -f "$PIDFILE"
  ok "auto-approver stopped"
else
  log "auto-approver not running"
fi
