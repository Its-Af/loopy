"""Inbox functional behaviour: delivery, pop semantics, shared fan-out."""

from __future__ import annotations

from tools.message import inbox


def test_delivery_and_pop():
    r = inbox.send_message("execs", "producers.1", "done", notify=False)
    assert r.delivered and r.path.exists()
    msgs = inbox.read_inbox("execs")
    assert len(msgs) == 1
    assert msgs[0].sender == "producers.1"
    assert msgs[0].body == "done"
    assert not r.path.exists()                 # popped
    assert inbox.read_inbox("execs") == []      # idempotent drain


def test_peek_does_not_consume():
    inbox.send_message("execs", "producers.1", "hi", notify=False)
    assert len(inbox.read_inbox("execs", pop=False)) == 1
    assert len(inbox.read_inbox("execs", pop=False)) == 1   # still there
    assert len(inbox.read_inbox("execs")) == 1              # now consumed
    assert inbox.read_inbox("execs") == []


def test_messages_returned_in_time_order():
    for i in range(5):
        inbox.send_message("execs", "producers.1", f"m{i}", notify=False)
    bodies = [m.body for m in inbox.read_inbox("execs")]
    assert bodies == ["m0", "m1", "m2", "m3", "m4"]


def test_inbox_count():
    inbox.send_message("qas", "execs", "a", notify=False)
    inbox.send_message("qas", "execs", "b", notify=False)
    assert inbox.inbox_count("qas") == 2
    assert inbox.inbox_count("qas") == 2     # count must not consume


def test_shared_fan_out_with_seen_sets():
    inbox.send_message("producers", "execs", "standup", shared=True, notify=False)
    a = inbox.read_inbox("producers.1")
    b = inbox.read_inbox("producers.2")
    c = inbox.read_inbox("producers.3")
    assert len(a) == len(b) == len(c) == 1      # every instance receives it
    assert all(m.shared for m in a + b + c)
    # ... but each only once.
    assert inbox.read_inbox("producers.1") == []
    assert inbox.read_inbox("producers.2") == []


def test_private_and_shared_combined():
    inbox.send_message("producers.1", "execs", "just-you", notify=False)
    inbox.send_message("producers", "execs", "all-of-you", shared=True, notify=False)
    bodies = {m.body for m in inbox.read_inbox("producers.1")}
    assert bodies == {"just-you", "all-of-you"}
    # producers.2 only sees the shared one.
    assert {m.body for m in inbox.read_inbox("producers.2")} == {"all-of-you"}


def test_prune_shared_by_ttl():
    inbox.send_message("producers", "execs", "old", shared=True, notify=False)
    assert inbox.prune_shared("producers", ttl=-1) == 1   # everything is "old"
    assert inbox.read_inbox("producers.1") == []
