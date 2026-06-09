"""Slack writer / token-refresh / poller — no real network (urllib mocked)."""

from __future__ import annotations

import io
import json

import pytest

from daemons import slack_poller, slack_writer, token_refresh


class _FakeResp:
    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mock_urlopen(monkeypatch, module, payload, capture=None):
    def fake(req, timeout=10):
        if capture is not None:
            capture.append(req)
        return _FakeResp(payload)
    monkeypatch.setattr(module.urllib.request, "urlopen", fake)


# --- writer ----------------------------------------------------------------
def test_post_message_noop_without_token(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    assert slack_writer.post_message("C1", "hi") is False
    assert slack_writer.auth_test() is None


def test_post_message_success(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    _mock_urlopen(monkeypatch, slack_writer, {"ok": True})
    assert slack_writer.post_message("C1", "hello", thread_ts="1.0") is True


def test_post_message_api_error(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    _mock_urlopen(monkeypatch, slack_writer, {"ok": False, "error": "channel_not_found"})
    assert slack_writer.post_message("C1", "hello") is False


# --- token refresh ---------------------------------------------------------
def test_refresh_noop_without_config(monkeypatch):
    for v in ("SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_REFRESH_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    assert token_refresh.refresh() is False


def test_refresh_success_writes_tokens(monkeypatch):
    monkeypatch.setenv("SLACK_CLIENT_ID", "cid")
    monkeypatch.setenv("SLACK_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SLACK_REFRESH_TOKEN", "rt-old")
    _mock_urlopen(monkeypatch, token_refresh,
                  {"ok": True, "access_token": "xoxb-new",
                   "refresh_token": "rt-new", "expires_in": 43200})
    assert token_refresh.refresh() is True
    saved = json.loads(open(token_refresh._tokens_path()).read())
    assert saved["access_token"] == "xoxb-new" and saved["refresh_token"] == "rt-new"


# --- poller ----------------------------------------------------------------
def test_poller_inactive_without_token(monkeypatch, capsys):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    assert slack_poller.main() == 0
    assert "inactive" in capsys.readouterr().out


def test_drain_outbox_posts_and_clears(monkeypatch):
    import os
    sent = []
    monkeypatch.setattr(slack_poller, "post_message",
                        lambda ch, txt, thread_ts=None: (sent.append((ch, txt)), True)[1])
    out_dir = os.path.join(slack_poller._slack_dir(), "outbox")
    with open(os.path.join(out_dir, "1.json"), "w") as fh:
        json.dump({"channel": "C1", "text": "queued reply"}, fh)
    slack_poller._drain_outbox()
    assert sent == [("C1", "queued reply")]
    assert os.listdir(out_dir) == []           # delivered -> removed


def test_drain_outbox_keeps_on_failure(monkeypatch):
    import os
    monkeypatch.setattr(slack_poller, "post_message",
                        lambda *a, **k: False)
    out_dir = os.path.join(slack_poller._slack_dir(), "outbox")
    with open(os.path.join(out_dir, "2.json"), "w") as fh:
        json.dump({"channel": "C1", "text": "retry me"}, fh)
    slack_poller._drain_outbox()
    assert os.listdir(out_dir) == ["2.json"]    # not delivered -> retained


def test_drain_outbox_drops_malformed(monkeypatch):
    import os
    out_dir = os.path.join(slack_poller._slack_dir(), "outbox")
    with open(os.path.join(out_dir, "bad.json"), "w") as fh:
        fh.write("{not json")
    slack_poller._drain_outbox()
    assert os.listdir(out_dir) == []            # malformed -> dropped
