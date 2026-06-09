#!/usr/bin/env bash
# install-hooks.sh — install git hooks that protect the squad's integrity.
#
# Adds a pre-commit hook running hot-files-check.sh, so an accidental edit to
# the protocol/profiles (or canary drift) blocks the commit until acknowledged.
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../daemons/common.sh"

command -v git >/dev/null 2>&1 || die "git not found"
git -C "$LOOPY_ROOT" rev-parse >/dev/null 2>&1 || die "not a git repo: $LOOPY_ROOT"

hooks_dir="$(git -C "$LOOPY_ROOT" rev-parse --git-path hooks)"
mkdir -p "$hooks_dir"
hook="$hooks_dir/pre-commit"

cat > "$hook" <<'HOOK'
#!/usr/bin/env bash
# Loopy pre-commit hook — verify protocol/profile integrity.
set -euo pipefail
here="$(git rev-parse --show-toplevel)"
if [[ -x "$here/loopy/scripts/hot-files-check.sh" ]]; then
  "$here/loopy/scripts/hot-files-check.sh" || {
    echo "Commit blocked by Loopy hot-files check."
    echo "If the protocol/profile change is intentional, re-run:"
    echo "  loopy/scripts/regenerate-canary.py   then   git add -A && commit"
    exit 1
  }
fi
HOOK
chmod +x "$hook"
ok "installed pre-commit hook -> $hook"
