"""High-level notification helpers.

Thin convenience layer that combines the durable channel (an inbox message)
with the instant channel (a bus wake), plus an optional best-effort desktop
notification for the human operator. Agents usually call
:func:`tools.message.send_message` directly; this exists for the common
"tell someone and nudge them now" idiom and for operator scripts.
"""

from __future__ import annotations

import platform
import shutil
import subprocess

from tools.identity import current_agent
from tools.message import send_message
from tools.message.inbox import SendResult


def notify_agent(target: str, body: str, *, sender: str | None = None,
                 shared: bool = False) -> SendResult:
    """Durably message *target* and ring its doorbell (send_message wakes too)."""
    sender = sender or current_agent(required=False) or "alfred"
    return send_message(target, sender, body, shared=shared, notify=True)


def desktop(title: str, message: str) -> bool:
    """Best-effort OS desktop notification for the human. Never raises."""
    try:
        system = platform.system()
        if system == "Darwin" and shutil.which("osascript"):
            safe_t = title.replace('"', "'")
            safe_m = message.replace('"', "'")
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{safe_m}" with title "{safe_t}"'],
                check=False, timeout=5,
            )
            return True
        if system == "Linux" and shutil.which("notify-send"):
            subprocess.run(["notify-send", title, message], check=False, timeout=5)
            return True
    except Exception:
        pass
    return False


__all__ = ["notify_agent", "desktop"]
