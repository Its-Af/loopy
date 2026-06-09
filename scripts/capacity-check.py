#!/usr/bin/env python3
"""Subagent spawn gate — LOOP step 6.

Prints ``CLEAR`` (exit 0) when it is safe to spawn a background subagent, or
``WAIT: <reason>`` (exit 3) when the system is under pressure. Agents call this
before spawning::

    if python3 loopy/scripts/capacity-check.py >/dev/null; then
        # spawn subagent
    fi

See :mod:`tools.capacity` for the policy.
"""

import os
import sys

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FRAMEWORK_DIR not in sys.path:
    sys.path.insert(0, _FRAMEWORK_DIR)

from tools.capacity import check  # noqa: E402
from tools.identity import current_agent  # noqa: E402


def main() -> int:
    as_json = "--json" in sys.argv[1:]
    agent = current_agent(required=False)
    cap = check(agent)
    if as_json:
        import json
        print(json.dumps(cap.as_dict()))
    else:
        print(cap.verdict if cap.clear else f"{cap.verdict}: {cap.reason}")
    return 0 if cap.clear else 3


if __name__ == "__main__":
    raise SystemExit(main())
