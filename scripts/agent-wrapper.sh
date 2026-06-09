#!/usr/bin/env bash
# agent-wrapper.sh — run one agent's loop with crash recovery.
#
#   LOOPY_AGENT_ID=producers.1 loopy/scripts/agent-wrapper.sh
#
# Runs the agent command; if it exits non-zero, restarts it with exponential
# backoff (capped), logging each restart. This is the inner resilience layer —
# the watchdog handles whole-pane death, this handles the agent process itself
# dying inside a live pane.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

agent="${LOOPY_AGENT_ID:-${1:-}}"
[[ -z "$agent" ]] && die "set LOOPY_AGENT_ID (or pass it as \$1)"
role="${agent%%.*}"

# Agents must run from the host repo root so their relative reads resolve
# (./CLAUDE.md, loopy/agents/<role>.md, .loopy/project-context.md). tmux sets
# this via `new-window -c`; in background mode we must do it ourselves.
cd "$LOOPY_ROOT" 2>/dev/null || true
export LOOPY_PROJECT_ROOT="$LOOPY_ROOT"
LOG="$LOOPY_RUNTIME/logs/${agent}.log"
mkdir -p "$LOOPY_RUNTIME/logs"

cmd="$(loopy_agent_cmd "$role")"

backoff=2; MAX=300
while true; do
  log "starting $agent" | tee -a "$LOG"
  start=$(date +%s)
  bash -lc "$cmd" 2>&1 | tee -a "$LOG" || true
  ran=$(( $(date +%s) - start ))
  # If it ran a healthy while, reset backoff; else grow it.
  if (( ran > 120 )); then backoff=2; else backoff=$(( backoff * 2 )); fi
  (( backoff > MAX )) && backoff=$MAX
  warn "$agent exited after ${ran}s — restarting in ${backoff}s" | tee -a "$LOG"
  sleep "$backoff"
done
