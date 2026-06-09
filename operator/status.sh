#!/usr/bin/env bash
# status.sh — health dashboard for the squad.
#
# Combines agent heartbeats, the task board, loop latency, and bus health into
# one screen. Pass --watch to refresh every few seconds.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

render() {
  printf '\033[1m═══ Loopy status — %s ═══\033[0m\n' "$(date '+%H:%M:%S')"
  printf 'project: %s\n\n' "$LOOPY_ROOT"

  if [[ ! -d "$LOOPY_RUNTIME" ]]; then
    warn "no .loopy/ runtime — run init.sh"; return
  fi

  # Agents + tasks via the CLI (authoritative).
  "$PY" "$LOOPY_TOOL" status || true
  echo

  # tmux panes.
  if loopy_session_exists; then
    printf '\033[1mtmux windows:\033[0m '
    "$LOOPY_TMUX" list-windows -t "$LOOPY_SESSION" -F '#W' | tr '\n' ' '; echo
  else
    printf 'tmux session: \033[0;33mnot running\033[0m\n'
  fi

  # Bus.
  if [[ -f "$LOOPY_RUNTIME/bus-status.json" ]]; then
    printf '\033[1mbus:\033[0m '
    "$PY" - "$LOOPY_RUNTIME/bus-status.json" <<'PY'
import json,sys,time
d=json.load(open(sys.argv[1]))
age=time.time()-d.get("updated_at",0)
print(f"pid {d.get('pid')} · up {d.get('uptime_s')}s · wakes {d.get('wakes_sent')} "
      f"(debounced {d.get('wakes_debounced')}) · auth-fails {d.get('auth_failures')} "
      f"· status {age:.0f}s old")
PY
  else
    printf 'bus: \033[0;33mno status file\033[0m\n'
  fi

  # Quarantine warning.
  qn=$(find "$LOOPY_RUNTIME/quarantine" -type f 2>/dev/null | wc -l | tr -d ' ')
  [[ "${qn:-0}" -gt 0 ]] && printf '\033[0;31m⚠ %s quarantined message(s)\033[0m\n' "$qn"
}

if [[ "${1:-}" == "--watch" ]]; then
  while true; do clear; render; sleep "${2:-3}"; done
else
  render
fi
