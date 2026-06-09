#!/usr/bin/env bash
# chat.sh — talk to an agent from the command line.
#
#   loopy/operator/chat.sh alfred "what's the squad status?"
#   echo "deploy when green" | loopy/operator/chat.sh execs
#
# Delivers a message to the agent's inbox (as the human, via alfred's identity)
# and rings the bus so they pick it up promptly. The reply, if any, comes back
# as an inbox message to alfred — read it with: agent-tool.py read-inbox --agent alfred
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"
loopy_require_runtime

target="${1:-alfred}"
shift || true
body="${*:-}"
[[ -z "$body" ]] && body="$(cat)"     # read from stdin if no message given
[[ -z "$body" ]] && die "nothing to send"

# Send as alfred (the human's proxy). agent-tool send-message also wakes the bus.
"$PY" "$LOOPY_TOOL" send-message "$target" "$body" --from alfred
ok "delivered to $target. Replies arrive in alfred's inbox:"
echo "  $PY $LOOPY_TOOL read-inbox --agent alfred"
