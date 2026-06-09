#!/usr/bin/env python3
"""Entry point for the Loopy agent CLI.

This thin shim exists so agents and operator scripts can invoke a stable path —
``python3 loopy/scripts/agent-tool.py <command>`` — regardless of where the
framework is checked out. It puts the framework directory (``loopy/``) on
``sys.path`` so ``tools.*`` imports resolve, then hands off to
:func:`tools.cli.main`.
"""

import os
import sys

# loopy/scripts/agent-tool.py -> framework dir is two levels up.
_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRAMEWORK_DIR not in sys.path:
    sys.path.insert(0, _FRAMEWORK_DIR)

from tools.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
