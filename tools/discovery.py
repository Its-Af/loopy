"""Dynamic tool discovery.

Rather than maintain a hand-written list of "what can an agent do", this module
introspects the live CLI parser and the messaging/task/state subsystems to
produce a catalog at runtime. The registry MCP server and ``tools/REGISTRY.md``
generation both read from here, so the catalog can never drift from the code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Capability:
    name: str
    kind: str          # "cli" | "subsystem"
    summary: str

    def as_dict(self) -> dict:
        return {"name": self.name, "kind": self.kind, "summary": self.summary}


def cli_commands() -> list[Capability]:
    """Every `agent-tool.py` subcommand, with its help text."""
    from tools.cli import build_parser
    parser = build_parser()
    out: list[Capability] = []
    # Find the subparsers action and walk its choices.
    for action in parser._actions:  # noqa: SLF001 - argparse has no public API
        if hasattr(action, "choices") and action.choices:
            for name, sub in action.choices.items():
                help_text = (sub.description or sub.format_usage()).strip()
                out.append(Capability(name, "cli", help_text.splitlines()[0]))
            break
    return sorted(out, key=lambda c: c.name)


def subsystems() -> list[Capability]:
    """The Python building blocks an agent (or its subagent) can import."""
    return [
        Capability("tools.message", "subsystem",
                   "send/read inbox messages with injection screening"),
        Capability("tools.task", "subsystem",
                   "create/claim/complete tasks; regenerate #TODO"),
        Capability("tools.state", "subsystem", "read/write agent heartbeats"),
        Capability("tools.memory", "subsystem", "briefings + decision log"),
        Capability("tools.results", "subsystem", "post/collect subagent results"),
        Capability("tools.metrics", "subsystem", "record/summarise loop latency"),
        Capability("tools.capacity", "subsystem", "subagent spawn gate"),
        Capability("tools.file", "subsystem",
                   "atomic writes, flock, intent locks"),
        Capability("tools.canary", "subsystem", "protocol integrity manifest"),
    ]


def catalog() -> dict:
    """Full capability catalog: CLI commands + importable subsystems."""
    return {
        "cli": [c.as_dict() for c in cli_commands()],
        "subsystems": [c.as_dict() for c in subsystems()],
    }


def describe(name: str) -> dict | None:
    for cap in cli_commands() + subsystems():
        if cap.name == name:
            return cap.as_dict()
    return None
