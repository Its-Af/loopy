#!/usr/bin/env bash
# launch-procs.sh — run the squad as background processes (no tmux required).
#
# The fallback launcher for machines without tmux. Each agent runs under
# agent-wrapper.sh via nohup, logging to .loopy/logs/<agent>.log, with its pid
# in .loopy/procs/<agent>.pid. Instant bus wakes degrade to the 5-minute loop
# (there's no pane to send-keys to), but the squad still runs. Stop with
# `loopy stop`.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

[[ -d "$LOOPY_RUNTIME" ]] || "$LOOPY_FRAMEWORK_DIR/operator/init.sh"
"$PY" "$LOOPY_FRAMEWORK_DIR/scripts/scan-project.py" >/dev/null 2>&1 || true
mkdir -p "$LOOPY_RUNTIME/procs" "$LOOPY_RUNTIME/logs"

loopy_have_claude || warn "claude CLI not found — agents will fail to start. Run 'loopy doctor'."

log "starting message bus"
"$LOOPY_FRAMEWORK_DIR/daemons/start-bus.sh"

started=0
while read -r agent; do
  [[ -z "$agent" ]] && continue
  pidf="$LOOPY_RUNTIME/procs/${agent}.pid"
  if [[ -f "$pidf" ]] && kill -0 "$(cat "$pidf" 2>/dev/null)" 2>/dev/null; then
    log "$agent already running (pid $(cat "$pidf"))"
    continue
  fi
  LOOPY_AGENT_ID="$agent" LOOPY_PROJECT_ROOT="$LOOPY_ROOT" \
    nohup "$LOOPY_FRAMEWORK_DIR/scripts/agent-wrapper.sh" \
    >> "$LOOPY_RUNTIME/logs/${agent}.log" 2>&1 &
  echo $! > "$pidf"
  started=$((started + 1))
  log "launched $agent (pid $!) -> .loopy/logs/${agent}.log"
done < <(loopy_roster)

ok "squad running in background ($started agents). \
Watch: loopy/bin/loopy logs    Status: loopy/bin/loopy status    Stop: loopy/bin/loopy stop"
