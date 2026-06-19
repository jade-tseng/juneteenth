"""Pre-verified gloss for the fixed demo script (§5).

The live demo must never depend on a flaky LLM call, so the five script lines
are hand-verified here and served from cache. Keys are normalized (lowercased,
stripped of surrounding punctuation/space) so minor STT/transcript variation
still hits. The LLM path still handles arbitrary input.
"""

from __future__ import annotations

import re

# english (verified gloss) — straight from the §5 table, spot-checked.
DEMO_GLOSS: dict[str, list[str]] = {
    "hello": ["HELLO"],
    "how are you doing today": ["HOW", "YOU", "TODAY"],
    "my name is jade": ["MY", "NAME", "fs:J", "fs:A", "fs:D", "fs:E"],
    "i don't speak sign language but my ai does": [
        "ME", "SIGN", "NOT", "BUT", "MY", "fs:A", "fs:I", "CAN",
    ],
    "i'm happy to communicate": ["ME", "HAPPY", "COMMUNICATE"],
}


def normalize_key(english: str) -> str:
    """Lowercase, drop punctuation except the apostrophe, collapse whitespace."""
    s = english.lower().strip()
    s = re.sub(r"[^a-z0-9'\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


# Pre-normalize so lookups are O(1) and resilient to trailing punctuation.
_NORMALIZED = {normalize_key(k): v for k, v in DEMO_GLOSS.items()}


def lookup(english: str) -> list[str] | None:
    return _NORMALIZED.get(normalize_key(english))
