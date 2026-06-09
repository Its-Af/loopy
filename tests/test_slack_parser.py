"""Slack message parsing (pure, no network)."""

from __future__ import annotations

from daemons.slack_parser import (
    SlackMessage,
    is_for_squad,
    mentioned_users,
    parse_event,
)


def test_parse_basic_message():
    msg = parse_event({"event": {"type": "message", "channel": "C123",
                                  "user": "U1", "text": "hi", "ts": "1.0"}})
    assert msg and msg.user == "U1" and msg.text == "hi"
    assert not msg.is_dm


def test_dm_detected():
    msg = parse_event({"event": {"type": "message", "channel": "D999",
                                  "user": "U1", "text": "yo", "ts": "1.0"}})
    assert msg.is_dm


def test_bot_and_subtype_messages_ignored():
    assert parse_event({"event": {"type": "message", "bot_id": "B1",
                                   "text": "x"}}) is None
    assert parse_event({"event": {"type": "message", "subtype": "message_changed",
                                   "text": "x"}}) is None
    assert parse_event({"event": {"type": "reaction_added"}}) is None


def test_clean_text_strips_mentions():
    msg = SlackMessage("C1", "U1", "<@UBOT> please deploy", "1.0", False)
    assert msg.clean_text == "please deploy"


def test_is_for_squad_dm_always():
    dm = SlackMessage("D1", "U1", "anything", "1.0", True)
    assert is_for_squad(dm, "UBOT")


def test_is_for_squad_channel_needs_mention():
    plain = SlackMessage("C1", "U1", "just chatting", "1.0", False)
    mention = SlackMessage("C1", "U1", "hey <@UBOT> status?", "1.0", False)
    assert not is_for_squad(plain, "UBOT")
    assert is_for_squad(mention, "UBOT")


def test_mentioned_users():
    assert mentioned_users("<@U1> and <@U2> ping") == ["U1", "U2"]
