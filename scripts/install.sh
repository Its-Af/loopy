#!/usr/bin/env bash
# install.sh — one-command setup for Loopy in a host repo.
#
#   loopy/bin/loopy install        # or: npm install (runs this via postinstall)
#   loopy/bin/loopy install --dev  # also create a venv + install pytest
#
# Loopy's runtime needs no packages (Python stdlib only); "install" therefore
# means: verify prerequisites, create the .loopy/ runtime, scan the host repo,
# and install git hooks. The Claude Code CLI is the one external tool — npm
# install pulls it (optionalDependency); otherwise we point you at it.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

FROM_NPM=0; DEV=0
for arg in "$@"; do
  case "$arg" in
    --from-npm) FROM_NPM=1 ;;
    --dev) DEV=1 ;;
  esac
done

log "installing Loopy into host repo: $LOOPY_ROOT"

# 1. Hard requirement: Python 3.10+.
if ! command -v "$PY" >/dev/null 2>&1 \
   || ! "$PY" -c 'import sys;raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
  err "Python 3.10+ is required. Install it and re-run."
  # When invoked from npm postinstall, don't hard-fail the whole npm install.
  [[ "$FROM_NPM" == 1 ]] && exit 0 || exit 1
fi
ok "Python OK ($("$PY" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])'))"

# 2. Create the runtime + seed config/settings + scan the host repo.
bash "$LOOPY_FRAMEWORK_DIR/operator/init.sh"

# 3. Install git hooks (protocol integrity) if the host is a git repo.
if command -v git >/dev/null 2>&1 && git -C "$LOOPY_ROOT" rev-parse >/dev/null 2>&1; then
  bash "$LOOPY_FRAMEWORK_DIR/scripts/install-hooks.sh" 2>/dev/null \
    && ok "git hooks installed" || warn "could not install git hooks"
fi

# 4. Optional dev setup: a venv with pytest for running the suite.
if [[ "$DEV" == 1 ]]; then
  venv="$LOOPY_FRAMEWORK_DIR/.venv"
  if [[ ! -x "$venv/bin/python" ]]; then
    log "creating dev venv at $venv"
    "$PY" -m venv "$venv" && "$venv/bin/pip" install -q --upgrade pip pytest
  fi
  ok "dev venv ready — run: loopy test"
fi

echo
# 5. Readiness report.
bash "$LOOPY_FRAMEWORK_DIR/scripts/doctor.sh" || true

echo
ok "install complete."
if [[ "$FROM_NPM" == 1 ]]; then
  log "start the squad with:  ./node_modules/.bin/loopy start   (or: npx loopy start)"
else
  log "start the squad with:  loopy/bin/loopy start"
fi
