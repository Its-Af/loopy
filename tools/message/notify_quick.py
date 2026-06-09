"""Bus wake client — the "ring the doorbell" half of the message bus.

When an agent delivers an inbox message it also sends a tiny wake frame over
the Unix-domain message bus so the recipient's pane is nudged *now* instead of
on its next 5-minute tick. This module is the client; ``daemons/bus_broker.py``
is the server. Both import the wire-protocol constants defined here so they can
never drift out of sync.

Everything here is best-effort: if the bus is down the wake is simply lost and
the recipient picks the message up on its regular loop. Liveness never depends
on the bus.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

from tools.identity import current_role, role_slug
from tools.project_root import bus_socket_path, runtime_dir
from tools.validation import split_agent, validate_agent
from tools.validation.constants import ROLE_INDEX

# --- Wire protocol (shared with the broker) --------------------------------
PROTOCOL_VERSION = 1
WILDCARD = 0xFF                # role or instance value meaning "all"

OP_UNICAST = b"W"             # W + role(1) + instance(1)
OP_MULTICAST = b"M"          # M + count(1) + role_index * count
AUTH_OK = 0x01

CONNECT_TIMEOUT = 0.5         # seconds — never block an agent loop on the bus


def _token_path(role: str) -> Path:
    return runtime_dir() / "bus" / "tokens" / f"{role}.token"


def load_token(role: str) -> str | None:
    """Read the per-role auth token written by the broker at startup."""
    env = os.environ.get("LOOPY_BUS_TOKEN")
    if env:
        return env
    try:
        return _token_path(role).read_text().strip()
    except FileNotFoundError:
        return None


def _send_frame(sender_role: str, frame: bytes) -> bool:
    sock_path = bus_socket_path()
    if not Path(sock_path).exists():
        return False
    token = load_token(sender_role)
    if not token:
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(CONNECT_TIMEOUT)
            s.connect(str(sock_path))
            s.sendall(f"{sender_role}:{token}\n".encode())
            ack = s.recv(3)
            if len(ack) < 1 or ack[0] != AUTH_OK:
                return False
            s.sendall(frame)
            return True
    except (OSError, socket.timeout):
        return False


def _sender_role() -> str:
    # Fall back to "alfred" identity when no agent context is set (e.g. a CLI
    # invocation from the operator); alfred has a token like any other role.
    return current_role(required=False) or "alfred"


def wake(target: str, *, shared: bool = False) -> bool:
    """Wake *target*. With ``shared=True`` wake every instance of its role."""
    target = validate_agent(target)
    role, instance = split_agent(target)
    role_idx = ROLE_INDEX[role]
    inst_byte = WILDCARD if (shared or instance is None) else instance
    frame = OP_UNICAST + bytes([role_idx & 0xFF, inst_byte & 0xFF])
    return _send_frame(_sender_role(), frame)


def wake_roles(roles: list[str]) -> bool:
    """Multicast a wake to all instances of each role in *roles*."""
    if not roles:
        return False
    indices = bytes(ROLE_INDEX[validate_agent(r).split(".")[0]] for r in roles)
    frame = OP_MULTICAST + bytes([len(indices) & 0xFF]) + indices
    return _send_frame(_sender_role(), frame)


def broadcast() -> bool:
    """Wake every agent on the bus."""
    frame = OP_UNICAST + bytes([WILDCARD, WILDCARD])
    return _send_frame(_sender_role(), frame)


if __name__ == "__main__":  # pragma: no cover
    import sys
    tgt = sys.argv[1] if len(sys.argv) > 1 else "alfred"
    print("woke" if wake(tgt) else "bus unavailable", tgt)
