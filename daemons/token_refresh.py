#!/usr/bin/env python3
"""Slack OAuth token refresh (optional).

Slack rotating bot tokens expire; this exchanges a stored refresh token for a
fresh access token via ``oauth.v2.access`` and writes it back to
``.loopy/slack/tokens.json``. Run periodically (cron / launchd) when using token
rotation. Standard library only; a no-op without the required configuration.

Required env: ``SLACK_CLIENT_ID``, ``SLACK_CLIENT_SECRET``, and either
``SLACK_REFRESH_TOKEN`` or a previously-written tokens.json holding one.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

_FW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _FW not in sys.path:
    sys.path.insert(0, _FW)

from tools.project_root import runtime_dir  # noqa: E402

SLACK_API = "https://slack.com/api"


def _tokens_path() -> str:
    d = os.path.join(str(runtime_dir()), "slack")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "tokens.json")


def _load() -> dict:
    try:
        with open(_tokens_path()) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    path = _tokens_path()
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def refresh() -> bool:
    client_id = os.environ.get("SLACK_CLIENT_ID")
    client_secret = os.environ.get("SLACK_CLIENT_SECRET")
    stored = _load()
    refresh_token = os.environ.get("SLACK_REFRESH_TOKEN") or stored.get("refresh_token")
    if not (client_id and client_secret and refresh_token):
        print("loopy-token: refresh not configured — skipping")
        return False

    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode("utf-8")
    req = urllib.request.Request(f"{SLACK_API}/oauth.v2.access", data=data,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"loopy-token: refresh request failed: {exc}", file=sys.stderr)
        return False

    if not body.get("ok"):
        print(f"loopy-token: refresh rejected: {body.get('error')}", file=sys.stderr)
        return False

    new = {
        "access_token": body.get("access_token"),
        "refresh_token": body.get("refresh_token", refresh_token),
        "expires_in": body.get("expires_in"),
        "refreshed_at": time.time(),
    }
    _save(new)
    print("loopy-token: access token refreshed")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if refresh() else 1)
