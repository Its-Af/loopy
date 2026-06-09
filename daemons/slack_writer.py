"""Slack reply writer — post messages back to Slack via the Web API.

Uses only urllib (stdlib). Reads ``SLACK_BOT_TOKEN`` from the environment; if it
is absent every call is a graceful no-op so the bridge can run "half-wired"
during setup without raising.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

SLACK_API = "https://slack.com/api"


def _token() -> str | None:
    return os.environ.get("SLACK_BOT_TOKEN")


def post_message(channel: str, text: str, *, thread_ts: str | None = None) -> bool:
    """Post *text* to *channel*. Returns True on success, False otherwise."""
    token = _token()
    if not token:
        return False
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{SLACK_API}/chat.postMessage", data=data, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return bool(body.get("ok"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return False


def auth_test() -> dict | None:
    """Return the bot's identity (auth.test), or None if unconfigured/failing."""
    token = _token()
    if not token:
        return None
    req = urllib.request.Request(
        f"{SLACK_API}/auth.test", method="POST",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body if body.get("ok") else None
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None
