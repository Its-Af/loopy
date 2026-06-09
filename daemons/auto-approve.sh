#!/usr/bin/env bash
# auto-approve.sh — "YOLO" mode: auto-confirm Claude Code permission prompts.
#
#   ⚠️  DANGER. This removes the human from the approval loop. Only use in a
#   disposable sandbox / container where the agents cannot do real harm. Prefer
#   a tight .claude/settings.json allow-list instead.
#
# Watches each agent pane for a permission prompt and sends the approval key.
# Enabled only when config has `auto_approve: on` or LOOPY_AUTO_APPROVE=1.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

enabled=0
[[ "${LOOPY_AUTO_APPROVE:-}" == "1" ]] && enabled=1
grep -qiE '^\s*-?\s*auto_approve\s*:\s*on' "$LOOPY_CONFIG" 2>/dev/null && enabled=1
if [[ "$enabled" != 1 ]]; then
  log "auto-approve disabled (set auto_approve: on or LOOPY_AUTO_APPROVE=1)"; exit 0
fi
loopy_have_tmux || die "auto-approve needs tmux"

warn "YOLO auto-approve ENABLED — agents will not ask permission. Sandbox only!"
PIDFILE="$LOOPY_RUNTIME/auto-approve.pid"
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

INTERVAL="${LOOPY_APPROVE_INTERVAL:-2}"
# Prompt fragments Claude Code shows when asking to run something.
PROMPT_RE='Do you want to|Allow this|permission|Proceed\?|❯ 1\. Yes'

while true; do
  if loopy_session_exists; then
    while read -r agent; do
      [[ -z "$agent" ]] && continue
      target="$(loopy_pane_target "$agent")"
      pane="$("$LOOPY_TMUX" capture-pane -p -t "$target" 2>/dev/null | tail -25 || true)"
      if grep -qiE "$PROMPT_RE" <<<"$pane"; then
        # Choose option 1 (Yes) and submit.
        "$LOOPY_TMUX" send-keys -t "$target" "1" Enter 2>/dev/null || true
        log "auto-approved a prompt for $agent"
      fi
    done < <(loopy_roster)
  fi
  sleep "$INTERVAL"
done
