"""Constants and threat patterns for the inbox subsystem.

Inbox messages are the one channel where text authored elsewhere — possibly
originating from an untrusted human or a compromised peer — flows into an
agent's context. Because that text will later be read by an LLM, the dangerous
payload is not a shell metacharacter but a *prompt injection*. The patterns and
limits here are the policy the sanitizer enforces.
"""

from __future__ import annotations

import re

# --- Size and rate limits --------------------------------------------------
MAX_MESSAGE_BYTES = 2048          # hard cap on a single message body
RATE_LIMIT_COUNT = 5              # max messages ...
RATE_LIMIT_WINDOW = 300          # ... per sender per 5 minutes
SHARED_MESSAGE_TTL = 6 * 3600     # shared-inbox messages pruned after 6h

# --- Filename format -------------------------------------------------------
# {epoch_microseconds}-{nonce}-{sender}.md  — lexically time-sortable.
NONCE_BYTES = 4
MESSAGE_SUFFIX = ".md"
FILENAME_RE = re.compile(
    r"^(?P<ts>\d{16,20})-(?P<nonce>[0-9a-f]{%d})-(?P<sender>[a-z][a-z0-9_]*(?:\.\d{1,2})?)\.md$"
    % (NONCE_BYTES * 2)
)

# --- Prompt-injection signatures ------------------------------------------
# Matched case-insensitively against NFKC-normalised text. A hit does not
# necessarily mean malice (an agent might legitimately quote one of these), so
# the sanitizer *neutralises* rather than silently dropping — see inbox.py.
INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(?:all\s+)?(?:previous|prior|above|the\s+following)\s+instructions",
        r"disregard\s+(?:all\s+)?(?:previous|prior|above)",
        r"forget\s+(?:everything|all|your)\s+(?:above|previous|instructions)",
        r"you\s+are\s+now\s+(?:a|an|the)\b",
        r"\bact\s+as\s+(?:a|an|if)\b",
        r"\bpretend\s+(?:to\s+be|you\s+are)\b",
        r"new\s+(?:system\s+)?(?:instructions?|prompt|rules?)\s*[:：]",
        r"^\s*system\s*[:：]",            # fake system turn
        r"^\s*assistant\s*[:：]",         # fake assistant turn
        r"^\s*human\s*[:：]",             # fake human turn
        r"^\s*developer\s*[:：]",
        r"<\|?im_(?:start|end)\|?>",       # chat-template tokens
        r"\[/?INST\]",                     # llama instruct tokens
        r"<<\s*SYS\s*>>",
        r"</?(?:function_calls?|invoke|tool_use|antml:)\b",  # tool-call injection
        r"begin\s+system\s+prompt",
        r"end\s+system\s+prompt",
        r"\bDAN\b\s+mode",
        r"developer\s+mode\s+enabled",
        r"override\s+(?:your\s+)?(?:safety|guard|instructions)",
    )
)

# Control characters to strip (everything below 0x20 except \t \n, plus DEL and
# the Unicode bidi/zero-width troublemakers that hide payloads visually).
_ALLOWED_CONTROL = {"\t", "\n"}
STRIP_CODEPOINTS = frozenset(
    [chr(c) for c in range(0x00, 0x20) if chr(c) not in _ALLOWED_CONTROL]
    + [chr(0x7F)]
    + [  # zero-width + bidi overrides commonly used to obfuscate text
        "​", "‌", "‍", "‎", "‏",
        "‪", "‫", "‬", "‭", "‮",
        "⁠", "⁦", "⁧", "⁨", "⁩",
        "﻿",
    ]
)

# Confusable homoglyphs that NFKC does *not* fold, mapped to their ASCII
# look-alikes. Without this, "ѕуѕtem:" (Cyrillic) would sail past the injection
# filter while reading identically to "system:".
CONFUSABLES: dict[str, str] = {
    # Cyrillic
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c",
    "у": "y", "х": "x", "і": "i", "ј": "j", "һ": "h",
    "Ѕ": "s", "ѕ": "s", "А": "A", "В": "B", "Е": "E",
    "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "Х": "X",
    # Greek
    "ο": "o", "α": "a", "ε": "e", "ρ": "p", "υ": "u",
    "Α": "A", "Β": "B", "Ε": "E", "Η": "H", "Ι": "I",
    "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P",
    "Τ": "T", "Χ": "X",
}

# Sentinel wrapper used to fence quoted untrusted content in the rendered
# inbox, so a downstream reader can tell data from instructions.
DATA_FENCE_OPEN = "⟦UNTRUSTED-MESSAGE⟧"
DATA_FENCE_CLOSE = "⟦END-UNTRUSTED-MESSAGE⟧"
