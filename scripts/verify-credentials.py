#!/usr/bin/env python3
"""Verify Anthropic credentials are present AND actually work.

Does a free ``GET /v1/models`` (lists models — no token cost) using whatever
auth is in the environment:

* ``ANTHROPIC_API_KEY``      -> ``x-api-key`` header
* ``ANTHROPIC_AUTH_TOKEN``   -> ``Authorization: Bearer`` header

Exit codes (so callers can branch precisely):
  0  credentials present and accepted (200)
  1  credentials present but REJECTED (401/403) — wrong/expired key
  2  no credentials to check, OR couldn't reach the API (network) — "unknown"

Never prints the secret. Honors ``ANTHROPIC_BASE_URL`` for proxies/gateways.
"""

import json
import os
import sys
import urllib.error
import urllib.request

VERSION = "2023-06-01"


def main() -> int:
    as_json = "--json" in sys.argv[1:]
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")

    headers = {"anthropic-version": VERSION}
    if api_key:
        headers["x-api-key"] = api_key
        method = "api-key"
    elif auth_token:
        headers["authorization"] = f"Bearer {auth_token}"
        method = "auth-token"
    else:
        out = {"status": "no-credentials", "ok": False}
        print(json.dumps(out) if as_json else "no credentials in environment")
        return 2

    req = urllib.request.Request(f"{base}/v1/models", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            ok = resp.status == 200
            out = {"status": "valid" if ok else f"http-{resp.status}",
                   "ok": ok, "auth": method}
            print(json.dumps(out) if as_json else f"credentials valid ({method})")
            return 0 if ok else 1
    except urllib.error.HTTPError as exc:
        rejected = exc.code in (401, 403)
        out = {"status": f"http-{exc.code}", "ok": False, "auth": method,
               "rejected": rejected}
        if as_json:
            print(json.dumps(out))
        else:
            print(f"credentials REJECTED (HTTP {exc.code})" if rejected
                  else f"unexpected response (HTTP {exc.code})")
        return 1 if rejected else 2
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        out = {"status": "unreachable", "ok": False, "error": str(exc)}
        print(json.dumps(out) if as_json
              else f"could not reach {base} (offline?) — skipping live check")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
