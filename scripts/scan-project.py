#!/usr/bin/env python3
"""Scan the host repository and (re)write .loopy/project-context.md.

Run automatically by init/install; re-run by hand after a big restructure so the
squad's view of the host project stays current:

    python3 loopy/scripts/scan-project.py
"""

import os
import sys

_FW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FW not in sys.path:
    sys.path.insert(0, _FW)

from tools.project_scan import scan, write_context  # noqa: E402


def main() -> int:
    info = scan()
    path = write_context()
    langs = ", ".join(info["languages"]) or "none detected"
    print(f"scanned host repo '{info['name']}' "
          f"({info['file_count']} files, {langs}) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
