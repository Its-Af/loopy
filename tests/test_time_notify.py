"""Time helpers and the notification convenience layer."""

from __future__ import annotations

import time

from tools import notify
from tools.time import age_str, humanize, iso, now_ms, now_us


# --- time ------------------------------------------------------------------
def test_now_us_and_ms_are_consistent():
    a = now_us()
    assert isinstance(a, int)
    assert abs(now_ms() - a // 1000) < 1000


def test_iso_format():
    assert iso(0) == "1970-01-01T00:00:00Z"
    assert iso(1_700_000_000).endswith("Z") and iso(1_700_000_000).startswith("2023-")


def test_humanize_units():
    assert humanize(0) == "0s"
    assert humanize(45) == "45s"
    assert humanize(90) == "1m"
    assert humanize(3700) == "1h"
    assert humanize(90000) == "1d"
    assert humanize(-5) == "0s"          # clamps negatives


def test_age_str():
    s = age_str(time.time() - 120)
    assert s.endswith("ago") and ("2m" in s or "1m" in s)


# --- notify ----------------------------------------------------------------
def test_notify_agent_delivers_and_returns_result():
    r = notify.notify_agent("execs", "deploy is green", sender="alfred")
    assert r.delivered
    from tools.message import read_inbox
    msgs = read_inbox("execs")
    assert msgs and msgs[0].body == "deploy is green"


def test_notify_agent_defaults_sender_to_current_agent():
    # conftest sets LOOPY_AGENT_ID=producers.1
    r = notify.notify_agent("qas", "ping")
    assert r.delivered
    from tools.message import read_inbox
    assert read_inbox("qas")[0].sender == "producers.1"


def test_desktop_is_best_effort(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        class R:  # noqa: D401 - dummy completed process
            returncode = 0
        return R()

    monkeypatch.setattr(notify.subprocess, "run", fake_run)
    monkeypatch.setattr(notify.shutil, "which", lambda _: "/usr/bin/osascript")
    monkeypatch.setattr(notify.platform, "system", lambda: "Darwin")
    assert notify.desktop("Loopy", 'say "hi"') is True
    assert calls and "osascript" in calls[0][0]


def test_desktop_never_raises(monkeypatch):
    def boom(*a, **k):
        raise OSError("no notifier")
    monkeypatch.setattr(notify.subprocess, "run", boom)
    monkeypatch.setattr(notify.shutil, "which", lambda _: "/x")
    monkeypatch.setattr(notify.platform, "system", lambda: "Linux")
    assert notify.desktop("t", "m") is False
