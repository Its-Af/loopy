#!/usr/bin/env python3
"""Slack bridge daemon — connect the human's Slack to alfred.

Two directions, both best-effort and entirely optional:

* **Inbound** — polls a Slack channel/DM; new human messages addressed to the
  squad are delivered to alfred's inbox (fenced as untrusted text, screened for
  injection like any other message).
* **Outbound** — alfred (or any agent) queues a reply by dropping a JSON file in
  ``.loopy/slack/outbox/`` (``{"channel": "...", "text": "..."}``); the bridge
  posts it to Slack.

Inert unless ``SLACK_BOT_TOKEN`` (and ``SLACK_CHANNEL`` for inbound) are set, so
it is safe to launch always. Standard library only.
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

from daemons.slack_parser import is_for_squad, parse_event  # noqa: E402
from daemons.slack_writer import auth_test, post_message  # noqa: E402
from tools.message import send_message  # noqa: E402
from tools.project_root import runtime_dir  # noqa: E402

POLL_INTERVAL = float(os.environ.get("LOOPY_SLACK_POLL", "5"))
SLACK_API = "https://slack.com/api"


def _slack_dir() -> str:
    d = os.path.join(str(runtime_dir()), "slack")
    os.makedirs(os.path.join(d, "outbox"), exist_ok=True)
    return d


def _cursor_path() -> str:
    return os.path.join(_slack_dir(), "cursor")


def _read_cursor() -> str:
    try:
        with open(_cursor_path()) as fh:
            return fh.read().strip()
    except FileNotFoundError:
        return ""


def _write_cursor(ts: str) -> None:
    with open(_cursor_path(), "w") as fh:
        fh.write(ts)


def _history(channel: str, oldest: str, token: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {"channel": channel, "oldest": oldest, "limit": "50"} if oldest
        else {"channel": channel, "limit": "20"}
    )
    req = urllib.request.Request(
        f"{SLACK_API}/conversations.history?{params}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("messages", []) if body.get("ok") else []
    except Exception:
        return []


def _drain_outbox() -> None:
    out = os.path.join(_slack_dir(), "outbox")
    for name in sorted(os.listdir(out)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(out, name)
        try:
            with open(path) as fh:
                msg = json.load(fh)
            if post_message(msg["channel"], msg["text"],
                            thread_ts=msg.get("thread_ts")):
                os.unlink(path)        # delivered
        except (OSError, json.JSONDecodeError, KeyError):
            os.unlink(path)             # malformed; drop it


def main() -> int:
    token = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_CHANNEL")
    if not token:
        print("loopy-slack: SLACK_BOT_TOKEN unset — Slack bridge inactive")
        return 0
    identity = auth_test()
    bot_user = identity.get("user_id") if identity else None
    print(f"loopy-slack: bridge up (bot={bot_user}, channel={channel or 'outbound-only'})",
          flush=True)

    while True:
        # Outbound: always drain queued replies.
        try:
            _drain_outbox()
        except OSError:
            pass

        # Inbound: only if a channel is configured.
        if channel:
            cursor = _read_cursor()
            msgs = _history(channel, cursor, token)
            # conversations.history returns newest-first; process oldest-first.
            for raw in sorted(msgs, key=lambda m: m.get("ts", "")):
                if cursor and raw.get("ts", "") <= cursor:
                    continue
                parsed = parse_event({"event": {**raw, "type": "message",
                                                 "channel": channel}})
                if parsed and is_for_squad(parsed, bot_user):
                    body = f"[human via Slack <{parsed.user}>] {parsed.clean_text}"
                    send_message("alfred", "alfred", body[:2000])
                if raw.get("ts"):
                    _write_cursor(raw["ts"])

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
