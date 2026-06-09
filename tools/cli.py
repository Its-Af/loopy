"""``agent-tool.py`` — the one CLI every agent and operator script drives.

Agent LOOP steps are written as plain shell calls into this tool, e.g.::

    python3 loopy/scripts/agent-tool.py write-state "implementing login"
    python3 loopy/scripts/agent-tool.py read-inbox
    python3 loopy/scripts/agent-tool.py task claim 01ABC...

Every command prints a concise human-readable summary by default, or strict
JSON with ``--json`` for machine consumption. Commands that act "as me" infer
the agent from ``LOOPY_AGENT_ID``; pass ``--agent`` to override. Exit codes are
meaningful so shell scripts can branch on them (notably ``capacity`` and
``briefing-stale``).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from tools import __version__
from tools.validation import ValidationError


# --------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------
class Ctx:
    def __init__(self, as_json: bool) -> None:
        self.as_json = as_json

    def emit(self, human: str, data: Any = None) -> None:
        if self.as_json:
            print(json.dumps(data if data is not None else {"message": human},
                              ensure_ascii=False, default=str))
        else:
            print(human)


def _read_body(arg: str | None) -> str:
    """Body comes from the positional arg, or stdin when omitted/``-``."""
    if arg is None or arg == "-":
        return sys.stdin.read()
    return arg


# --------------------------------------------------------------------------
# Command implementations
# --------------------------------------------------------------------------
def cmd_write_state(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.state import write_state
    s = write_state(a.status, agent=a.agent, task=a.task, detail=a.detail or "")
    ctx.emit(f"state[{s.agent}] loop={s.loop} :: {s.status}", s.__dict__)
    return 0


def cmd_read_state(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.state import all_states, read_state
    if a.all:
        states = all_states()
        if ctx.as_json:
            ctx.emit("", [s.__dict__ for s in states])
        else:
            for s in states:
                flag = " STALE" if s.stale else ""
                ctx.emit(f"{s.agent:<14} {s.status:<30} loop={s.loop}{flag}")
        return 0
    s = read_state(a.agent)
    if s is None:
        ctx.emit("(no state)", None)
        return 1
    ctx.emit(f"{s.agent}: {s.status} (loop {s.loop})", s.__dict__)
    return 0


def cmd_status(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.state import all_states
    from tools.task import list_tasks
    from tools.metrics import summarize
    states = all_states()
    tasks = list_tasks()
    open_tasks = [t for t in tasks if not t.is_done]
    loop_stats = summarize("loop")
    data = {
        "agents": [s.__dict__ for s in states],
        "agents_total": len(states),
        "agents_stale": sum(1 for s in states if s.stale),
        "tasks_open": len(open_tasks),
        "tasks_done": len(tasks) - len(open_tasks),
        "loop_p95_ms": loop_stats.p95_ms if loop_stats else None,
    }
    if ctx.as_json:
        ctx.emit("", data)
    else:
        ctx.emit(f"agents: {len(states)} ({data['agents_stale']} stale) | "
                 f"tasks: {len(open_tasks)} open, {data['tasks_done']} done | "
                 f"loop p95: {data['loop_p95_ms']}ms")
        for s in states:
            ctx.emit(f"  {'⚠' if s.stale else '•'} {s.agent:<14} {s.status}")
    return 0


def cmd_read_inbox(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.identity import current_agent
    from tools.message import read_inbox
    agent = a.agent or current_agent()
    msgs = read_inbox(agent, include_shared=not a.no_shared, pop=not a.peek)
    if ctx.as_json:
        ctx.emit("", [{"id": m.id, "from": m.sender, "shared": m.shared,
                        "ts_us": m.timestamp_us, "body": m.body} for m in msgs])
    else:
        if not msgs:
            ctx.emit("(inbox empty)")
        for m in msgs:
            tag = "[shared] " if m.shared else ""
            ctx.emit(f"── from {m.sender} {tag}─────────────\n{m.body}\n")
    return 0


def cmd_send_message(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.identity import current_agent
    from tools.message import send_message
    sender = a.sender or current_agent()
    body = _read_body(a.body)
    r = send_message(a.target, sender, body, shared=a.shared, notify=not a.quiet)
    if r.delivered:
        ctx.emit(f"delivered to {a.target}", {"delivered": True, "path": str(r.path)})
        return 0
    ctx.emit(f"NOT delivered ({r.reason})",
             {"delivered": False, "reason": r.reason,
              "quarantined": r.quarantined, "findings": r.findings})
    return 2


def cmd_read_results(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.results import read_results
    rs = read_results(a.agent, consume=not a.peek)
    if ctx.as_json:
        ctx.emit("", [{"id": r.id, "kind": r.kind, "ok": r.ok,
                        "summary": r.summary, "subagent": r.subagent,
                        "payload": r.payload} for r in rs])
    else:
        if not rs:
            ctx.emit("(no results)")
        for r in rs:
            mark = "✓" if r.ok else "✗"
            ctx.emit(f"{mark} [{r.kind}] {r.summary} ({r.subagent or '?'})")
    return 0


def cmd_post_result(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.results import post_result
    r = post_result(a.parent, a.kind, ok=not a.fail, summary=a.summary or "",
                    subagent=a.subagent or "")
    ctx.emit(f"posted result {r.id} -> {a.parent}", {"id": r.id})
    return 0


# --- tasks -----------------------------------------------------------------
def cmd_task(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools import task as T
    from tools.identity import current_agent
    sub = a.task_cmd

    if sub == "create":
        t = T.create_task(a.title, description=a.desc or "", priority=a.priority,
                          created_by=a.by or current_agent(), tags=a.tag or [],
                          blocked_by=a.blocked_by or [])
        _maybe_regen(a)
        ctx.emit(f"created {t.id} [{t.priority}] {t.title}", {"id": t.id})
        return 0

    if sub == "list":
        tasks = T.list_tasks(state=a.state, owner=a.owner,
                             include_done=not a.open)
        if ctx.as_json:
            ctx.emit("", [t.__dict__ for t in tasks])
        else:
            if not tasks:
                ctx.emit("(no tasks)")
            for t in tasks:
                owner = f" @{t.owner}" if t.owner else ""
                ctx.emit(f"{t.id} [{t.priority}] {t.state:<11}{owner}  {t.title}")
        return 0

    if sub == "show":
        try:
            t = T.read_task(a.id)
        except KeyError:
            ctx.emit("no such task", None)
            return 1
        ctx.emit(json.dumps(t.__dict__, indent=2, default=str), t.__dict__)
        return 0

    if sub == "claim":
        owner = a.owner or current_agent()
        t = T.claim_task(a.id, owner)
        if t is None:
            ctx.emit("claim FAILED (taken, blocked, or not open)",
                     {"claimed": False})
            return 2
        ctx.emit(f"claimed {t.id} by {owner}", {"claimed": True, "id": t.id})
        return 0

    if sub == "release":
        owner = a.owner or current_agent()
        t = T.release_task(a.id, owner, reason=a.reason or "")
        _maybe_regen(a)
        ctx.emit(f"released {t.id}", {"id": t.id, "state": t.state})
        return 0

    if sub == "update":
        owner = a.by or current_agent()
        t = T.update_task(a.id, actor=owner, state=a.state, priority=a.priority,
                          note=a.note)
        _maybe_regen(a)
        ctx.emit(f"updated {t.id} -> {t.state}", {"id": t.id, "state": t.state})
        return 0

    if sub == "done":
        owner = a.owner or current_agent()
        t = T.complete_task(a.id, owner, note=a.note or "")
        _maybe_regen(a)
        ctx.emit(f"completed {t.id}", {"id": t.id})
        return 0

    if sub == "reopen":
        actor = a.by or current_agent()
        t = T.reopen_task(a.id, actor, reason=a.reason)
        _maybe_regen(a)
        ctx.emit(f"reopened {t.id}", {"id": t.id})
        return 0

    ctx.emit("unknown task subcommand", None)
    return 1


def _maybe_regen(a: argparse.Namespace) -> None:
    if getattr(a, "no_regen", False):
        return
    try:
        from tools.task import regenerate_index
        regenerate_index()
    except Exception:
        pass


def cmd_regen_todo(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.task import regenerate_index
    p = regenerate_index()
    ctx.emit(f"regenerated {p}", {"path": str(p)})
    return 0


# --- memory ----------------------------------------------------------------
def cmd_read_briefing(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.memory import read_briefing
    b = read_briefing(a.agent)
    if b is None:
        ctx.emit("(no briefing)", None)
        return 1
    ctx.emit(b.text, {"text": b.text, "age_s": round(b.age), "stale": b.stale})
    return 0


def cmd_write_briefing(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.memory import write_briefing
    write_briefing(_read_body(a.text), agent=a.agent)
    ctx.emit("briefing updated", {"ok": True})
    return 0


def cmd_briefing_stale(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.memory import briefing_stale
    stale = briefing_stale(a.agent)
    ctx.emit("STALE" if stale else "fresh", {"stale": stale})
    return 0 if stale else 1  # exit 0 when stale so `if ...; then rewrite` works


def cmd_record_decision(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.memory import record_decision
    record_decision(a.summary, agent=a.agent, rationale=a.rationale or "",
                    task=a.task)
    ctx.emit("decision recorded", {"ok": True})
    return 0


# --- bus -------------------------------------------------------------------
def cmd_notify(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.message.notify_quick import wake
    ok = wake(a.target, shared=a.shared)
    ctx.emit("woke " + a.target if ok else "bus unavailable", {"woke": ok})
    return 0 if ok else 1


def cmd_broadcast(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.message.notify_quick import broadcast
    ok = broadcast()
    ctx.emit("broadcast sent" if ok else "bus unavailable", {"ok": ok})
    return 0 if ok else 1


# --- metrics / capacity ----------------------------------------------------
def cmd_metrics(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.metrics import summarize
    st = summarize(a.kind, agent=a.agent)
    if st is None:
        ctx.emit("(no samples)", None)
        return 1
    ctx.emit(f"{st.kind}: n={st.count} p50={st.p50_ms}ms p95={st.p95_ms}ms "
             f"max={st.max_ms}ms over_budget={st.over_budget}", st.as_dict())
    return 0


def cmd_capacity(a: argparse.Namespace, ctx: Ctx) -> int:
    from tools.capacity import check
    from tools.identity import current_agent
    cap = check(a.agent or current_agent(required=False))
    ctx.emit(f"{cap.verdict}: {cap.reason}", cap.as_dict())
    return 0 if cap.clear else 3  # exit 3 == WAIT, so scripts can gate on it


# --------------------------------------------------------------------------
# Argument parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent-tool.py",
                                description="Loopy agent coordination CLI")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--version", action="version", version=f"loopy {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_agent(sp):
        sp.add_argument("--agent", help="override LOOPY_AGENT_ID")

    sp = sub.add_parser("write-state", help="update my status line (LOOP step 1)")
    sp.add_argument("status")
    sp.add_argument("--task"); sp.add_argument("--detail")
    add_agent(sp); sp.set_defaults(func=cmd_write_state)

    sp = sub.add_parser("read-state", help="read an agent's state")
    sp.add_argument("--all", action="store_true"); add_agent(sp)
    sp.set_defaults(func=cmd_read_state)

    sp = sub.add_parser("status", help="health dashboard summary")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("read-inbox", help="pop my inbox (LOOP step 3)")
    sp.add_argument("--no-shared", action="store_true")
    sp.add_argument("--peek", action="store_true", help="do not consume")
    add_agent(sp); sp.set_defaults(func=cmd_read_inbox)

    sp = sub.add_parser("send-message", help="send a message to another agent")
    sp.add_argument("target"); sp.add_argument("body", nargs="?")
    sp.add_argument("--from", dest="sender"); sp.add_argument("--shared", action="store_true")
    sp.add_argument("--quiet", action="store_true", help="do not ring the bus")
    sp.set_defaults(func=cmd_send_message)

    sp = sub.add_parser("read-results", help="pop subagent results (LOOP step 4)")
    sp.add_argument("--peek", action="store_true"); add_agent(sp)
    sp.set_defaults(func=cmd_read_results)

    sp = sub.add_parser("post-result", help="write a result for a parent agent")
    sp.add_argument("parent"); sp.add_argument("kind")
    sp.add_argument("--summary"); sp.add_argument("--subagent")
    sp.add_argument("--fail", action="store_true")
    sp.set_defaults(func=cmd_post_result)

    # task group
    tp = sub.add_parser("task", help="task store operations")
    tsub = tp.add_subparsers(dest="task_cmd", required=True)
    tp.add_argument("--no-regen", action="store_true",
                    help="skip #TODO regeneration")

    c = tsub.add_parser("create"); c.add_argument("title")
    c.add_argument("--desc"); c.add_argument("--priority", default="P2")
    c.add_argument("--by"); c.add_argument("--tag", action="append")
    c.add_argument("--blocked-by", action="append")
    c = tsub.add_parser("list")
    c.add_argument("--state"); c.add_argument("--owner")
    c.add_argument("--open", action="store_true", help="hide done tasks")
    c = tsub.add_parser("show"); c.add_argument("id")
    c = tsub.add_parser("claim"); c.add_argument("id"); c.add_argument("--owner")
    c = tsub.add_parser("release"); c.add_argument("id")
    c.add_argument("--owner"); c.add_argument("--reason")
    c = tsub.add_parser("update"); c.add_argument("id")
    c.add_argument("--state"); c.add_argument("--priority")
    c.add_argument("--note"); c.add_argument("--by")
    c = tsub.add_parser("done"); c.add_argument("id")
    c.add_argument("--owner"); c.add_argument("--note")
    c = tsub.add_parser("reopen"); c.add_argument("id")
    c.add_argument("--reason", required=True); c.add_argument("--by")
    tp.set_defaults(func=cmd_task)

    sp = sub.add_parser("regen-todo", help="rebuild the #TODO index")
    sp.set_defaults(func=cmd_regen_todo)

    sp = sub.add_parser("read-briefing"); add_agent(sp)
    sp.set_defaults(func=cmd_read_briefing)
    sp = sub.add_parser("write-briefing"); sp.add_argument("text", nargs="?")
    add_agent(sp); sp.set_defaults(func=cmd_write_briefing)
    sp = sub.add_parser("briefing-stale", help="exit 0 if briefing needs rewrite")
    add_agent(sp); sp.set_defaults(func=cmd_briefing_stale)
    sp = sub.add_parser("record-decision"); sp.add_argument("summary")
    sp.add_argument("--rationale"); sp.add_argument("--task"); add_agent(sp)
    sp.set_defaults(func=cmd_record_decision)

    sp = sub.add_parser("notify", help="ring an agent's bus doorbell")
    sp.add_argument("target"); sp.add_argument("--shared", action="store_true")
    sp.set_defaults(func=cmd_notify)
    sp = sub.add_parser("broadcast"); sp.set_defaults(func=cmd_broadcast)

    sp = sub.add_parser("metrics"); sp.add_argument("--kind", default="loop")
    add_agent(sp); sp.set_defaults(func=cmd_metrics)

    sp = sub.add_parser("capacity", help="subagent spawn gate (CLEAR/WAIT)")
    add_agent(sp); sp.set_defaults(func=cmd_capacity)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ctx = Ctx(getattr(args, "json", False))
    try:
        return args.func(args, ctx)
    except ValidationError as exc:
        ctx.emit(f"error: {exc}", {"error": str(exc)})
        return 64  # EX_USAGE
    except KeyError as exc:
        ctx.emit(f"not found: {exc}", {"error": str(exc)})
        return 65
    except BrokenPipeError:  # pragma: no cover
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
