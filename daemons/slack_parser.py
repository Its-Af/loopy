"""Slack message parsing — pure, network-free, testable.

Turns raw Slack event/message payloads into the small shape the bridge needs,
and decides whether a message is *for the squad* (a DM, or an @mention in a
channel). Kept dependency-free and side-effect-free so it can be unit-tested
without touching Slack.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MENTION_RE = re.compile(r"<@([A-Z0-9]+)>")


@dataclass
class SlackMessage:
    channel: str
    user: str
    text: str
    ts: str
    is_dm: bool

    @property
    def clean_text(self) -> str:
        """Text with mention tokens removed and whitespace collapsed."""
        return _MENTION_RE.sub("", self.text).strip()


def parse_event(payload: dict) -> SlackMessage | None:
    """Parse a Slack `message` event into a :class:`SlackMessage`, or None.

    Ignores bot messages, edits, joins, and other non-user noise so the bridge
    never echoes itself into a loop.
    """
    event = payload.get("event", payload)
    if event.get("type") != "message":
        return None
    if event.get("subtype"):            # edits, joins, bot_message, etc.
        return None
    if event.get("bot_id"):             # never act on bot output
        return None
    text = event.get("text") or ""
    channel = event.get("channel") or ""
    return SlackMessage(
        channel=channel,
        user=event.get("user") or "?",
        text=text,
        ts=event.get("ts") or "",
        is_dm=channel.startswith("D"),  # DM channel ids start with 'D'
    )


def is_for_squad(msg: SlackMessage, bot_user_id: str | None) -> bool:
    """True if the squad should act on this message.

    DMs always count. In a channel, only messages that @mention the bot do, so
    the squad doesn't react to every line of unrelated chatter.
    """
    if msg.is_dm:
        return True
    if bot_user_id:
        return bot_user_id in _MENTION_RE.findall(msg.text)
    return False


def mentioned_users(text: str) -> list[str]:
    return _MENTION_RE.findall(text)
