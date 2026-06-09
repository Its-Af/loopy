#!/usr/bin/env bash
# init.sh — create the .loopy/ runtime directory for this project.
#
# Idempotent: safe to run repeatedly. Creates the runtime tree, seeds
# config.md from the sample, and (optionally) the host .claude/settings.json
# from the reference. Never overwrites an existing config without --force.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

log "initialising Loopy runtime at $LOOPY_RUNTIME"

# Runtime subdirectories (mirrors protocol/structure.md).
for d in inbox quarantine wake state tasks memory results metrics intents \
         locks bus/tokens logs; do
  mkdir -p "$LOOPY_RUNTIME/$d"
done
chmod 700 "$LOOPY_RUNTIME/bus" "$LOOPY_RUNTIME/bus/tokens" 2>/dev/null || true

# Seed config.md from the sample at the framework/project root.
sample=""
for cand in "$LOOPY_ROOT/config.sample.md" "$LOOPY_FRAMEWORK_DIR/config.sample.md"; do
  [[ -f "$cand" ]] && { sample="$cand"; break; }
done
if [[ -n "$sample" ]]; then
  if [[ ! -f "$LOOPY_CONFIG" || "$FORCE" == 1 ]]; then
    cp "$sample" "$LOOPY_CONFIG"
    ok "wrote $LOOPY_CONFIG"
  else
    log "config.md exists; leaving it (use --force to overwrite)"
  fi
else
  warn "no config.sample.md found; skipping config seed"
fi

# Seed the host harness settings if absent.
ref="$LOOPY_ROOT/settings.reference.json"
[[ -f "$ref" ]] || ref="$LOOPY_FRAMEWORK_DIR/settings.reference.json"
settings="$LOOPY_ROOT/.claude/settings.json"
if [[ -f "$ref" && ! -f "$settings" ]]; then
  mkdir -p "$(dirname "$settings")"
  cp "$ref" "$settings"
  ok "seeded $settings from reference"
fi

# Empty #TODO so the board exists from minute one.
if [[ ! -f "$LOOPY_TODO" ]]; then
  "$PY" "$LOOPY_TOOL" regen-todo >/dev/null 2>&1 || printf '# #TODO\n\n_empty_\n' > "$LOOPY_TODO"
fi

# Scan the host repo so the squad has its context from the first loop.
if "$PY" "$LOOPY_FRAMEWORK_DIR/scripts/scan-project.py" 2>/dev/null; then
  :
else
  warn "host-repo scan skipped"
fi

# Record the roster we'll launch, for visibility.
log "roster (host root: $LOOPY_ROOT):"
loopy_roster | sed 's/^/  - /'

ok "init complete. Next: loopy/bin/loopy start"
