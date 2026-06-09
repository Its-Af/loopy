#!/usr/bin/env bash
# setup-ide.sh — drop a VS Code workspace that surfaces the squad's runtime.
#
# Writes .vscode/loopy.code-workspace and a tasks.json with one-click commands
# for launch / status / stop. Non-destructive: won't clobber existing files.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

mkdir -p "$LOOPY_ROOT/.vscode"
WS="$LOOPY_ROOT/.vscode/loopy.code-workspace"
TASKS="$LOOPY_ROOT/.vscode/tasks.json"

if [[ ! -f "$WS" ]]; then
cat > "$WS" <<JSON
{
  "folders": [
    { "name": "project", "path": ".." },
    { "name": "loopy (framework)", "path": "../loopy" },
    { "name": ".loopy (runtime)", "path": "../.loopy" }
  ],
  "settings": {
    "files.watcherExclude": { "**/.loopy/locks/**": true },
    "terminal.integrated.cwd": "\${workspaceFolder}"
  }
}
JSON
  ok "wrote $WS"
else log "$WS exists; leaving it"; fi

if [[ ! -f "$TASKS" ]]; then
cat > "$TASKS" <<JSON
{
  "version": "2.0.0",
  "tasks": [
    { "label": "Loopy: launch", "type": "shell",
      "command": "loopy/operator/launch-all.sh" },
    { "label": "Loopy: status", "type": "shell",
      "command": "loopy/operator/status.sh" },
    { "label": "Loopy: stop",   "type": "shell",
      "command": "loopy/operator/stop-all.sh --force" }
  ]
}
JSON
  ok "wrote $TASKS"
else log "$TASKS exists; leaving it"; fi

ok "VS Code setup complete. Open $WS, or run tasks via ⇧⌘P → 'Run Task'."
