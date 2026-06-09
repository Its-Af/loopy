#!/usr/bin/env bash
# _write-panes.sh — (re)generate .loopy/panes.json from the roster.
#
# Maps each agent id to its tmux pane target so the bus broker can route wakes.
# Called by launch-all.sh / start.sh after windows are created.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

out="$LOOPY_RUNTIME/panes.json"
tmp="$out.tmp.$$"
{
  printf '{\n'
  first=1
  while read -r agent; do
    [[ -z "$agent" ]] && continue
    if [[ "$first" == 1 ]]; then first=0; else printf ',\n'; fi
    printf '  "%s": "%s"' "$agent" "$(loopy_pane_target "$agent")"
  done < <(loopy_roster)
  printf '\n}\n'
} > "$tmp"
mv -f "$tmp" "$out"
log "wrote pane map -> $out"
