#!/usr/bin/env bash
# watchdog.sh — keep the squad alive.
#
# Every WATCH_INTERVAL seconds: ensure the bus is up, and ensure every roster
# agent still has a live tmux window. Respawn dead agents with *exponential
# backoff* so a pane that crashes on startup can't become a respawn storm
# (a fork bomb). Backoff per-agent resets after a sustained healthy period.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

WATCH_INTERVAL="${LOOPY_WATCH_INTERVAL:-30}"
MAX_BACKOFF="${LOOPY_WATCH_MAX_BACKOFF:-600}"   # cap at 10 min
PIDFILE="$LOOPY_RUNTIME/watchdog.pid"
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

# Per-agent backoff state. macOS bash 3.2 has no associative arrays, so we keep
# state in dynamically-named scalars (bk_<agent>, nt_<agent>) via eval.
_san() { local s="${1//[^a-zA-Z0-9]/_}"; echo "$s"; }
get_bk() { eval "echo \${bk_$(_san "$1"):-0}"; }
set_bk() { eval "bk_$(_san "$1")=$2"; }
get_nt() { eval "echo \${nt_$(_san "$1"):-0}"; }
set_nt() { eval "nt_$(_san "$1")=$2"; }

log "watchdog up (interval ${WATCH_INTERVAL}s, pid $$)"

alive() { # is there a tmux window for this agent?
  loopy_session_exists && \
    "$LOOPY_TMUX" list-windows -t "$LOOPY_SESSION" -F '#W' 2>/dev/null \
    | grep -qx "$(loopy_window_name "$1")"
}

while true; do
  # 1. Bus health.
  if [[ ! -S "$LOOPY_BUS_SOCK_PATH" ]]; then
    warn "bus socket missing — restarting"
    "$LOOPY_FRAMEWORK_DIR/daemons/start-bus.sh" || true
  fi

  # 2. Agent health, with backoff.
  now="$(date +%s)"
  while read -r agent; do
    [[ -z "$agent" ]] && continue
    if alive "$agent"; then
      # Healthy: decay backoff toward zero.
      set_bk "$agent" 0
      continue
    fi
    bt="$(get_nt "$agent")"
    if (( now < bt )); then continue; fi      # still backing off
    cur="$(get_bk "$agent")"
    if (( cur == 0 )); then cur=5; else cur=$(( cur * 2 )); fi
    (( cur > MAX_BACKOFF )) && cur="$MAX_BACKOFF"
    set_bk "$agent" "$cur"
    set_nt "$agent" $(( now + cur ))
    warn "agent $agent is down — respawning (next backoff ${cur}s)"
    "$LOOPY_FRAMEWORK_DIR/operator/start.sh" "$agent" || \
      err "respawn of $agent failed"
  done < <(loopy_roster)

  sleep "$WATCH_INTERVAL"
done
