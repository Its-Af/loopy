#!/usr/bin/env python3
"""Verify protocol + agent hot files against the trusted canary manifest.

Exit 0 and print ``canary OK`` when nothing has drifted. Exit 1 and list the
changed/added/removed files otherwise — a non-zero exit means the rules may
have been tampered with; the caller (execs/securities) should halt and
investigate. ``--json`` prints a machine-readable report.
"""

import os
import sys

_FW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FW not in sys.path:
    sys.path.insert(0, _FW)

from tools.canary import verify  # noqa: E402


def main() -> int:
    as_json = "--json" in sys.argv[1:]
    result = verify()
    if as_json:
        import json
        print(json.dumps(result.as_dict()))
    elif result.ok:
        print("canary OK")
    else:
        print("CANARY FAILED — hot files changed since baseline:")
        for line in result.drift:
            print(f"  {line}")
        print("If this change was authorised, re-run regenerate-canary.py.")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
