#!/usr/bin/env python3
"""Capture the integrity manifest of protocol + agent hot files.

Run once when the squad starts (and after any *authorised* change to the
protocol or profiles) to (re)establish the trusted baseline that
`verify-canary.py` checks against each round.
"""

import os
import sys

_FW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FW not in sys.path:
    sys.path.insert(0, _FW)

from tools.canary import write_manifest  # noqa: E402


def main() -> int:
    path = write_manifest()
    import json
    data = json.loads(path.read_text())
    print(f"canary baseline written: {path} ({len(data['files'])} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
