"""Token helpers shared by every gloss provider.

A gloss token is either a lexical gloss (``HELLO``) or a fingerspell directive
(``fs:J``), per §3.3. These helpers normalize/validate tokens and expand proper
nouns to fingerspell letters.
"""

from __future__ import annotations

import json
import re

# Lexical gloss: uppercase letters/digits, may contain ' or - (e.g. DON'T, SELF-).
_LEXICAL = re.compile(r"^[A-Z][A-Z0-9'\-]*$")
_FS = re.compile(r"^fs:[A-Z]$")

# Articles + copula/auxiliaries dropped by the passthrough fallback (§4.2).
STOPWORDS = frozenset(
    {
        "a", "an", "the",
        "is", "am", "are", "was", "were", "be", "been", "being",
        "do", "does", "did", "to", "of",
    }
)


def is_valid_token(tok: str) -> bool:
    return bool(_FS.match(tok) or _LEXICAL.match(tok))


def fingerspell(word: str) -> list[str]:
    """Expand a word to per-letter fingerspell directives: 'Jade' -> fs:J fs:A …"""
    return [f"fs:{ch}" for ch in word.upper() if ch.isalpha()]


def normalize_token(raw: str) -> str | None:
    """Coerce one model-emitted token to canonical form, or None if unusable.

    Accepts case-insensitive ``fs:`` prefixes and strips stray punctuation so a
    slightly-off LLM output still yields valid tokens instead of being discarded.
    """
    tok = raw.strip().strip(",;\"'`[]()")
    if not tok:
        return None
    if tok.lower().startswith("fs:"):
        letter = tok[3:].strip().upper()
        return f"fs:{letter}" if len(letter) == 1 and letter.isalpha() else None
    up = tok.upper()
    return up if _LEXICAL.match(up) else None


def parse_gloss_tokens(text: str) -> list[str]:
    """Extract a clean token list from raw model output.

    Handles a JSON array (``["MY","NAME"]``) or plain whitespace/comma-separated
    text. Invalid tokens are dropped; returns ``[]`` if nothing usable, which the
    service treats as a provider failure and falls through.
    """
    text = text.strip()
    raw_tokens: list[str] = []

    # Prefer a JSON array if the model returned one (possibly fenced).
    fenced = re.search(r"\[.*\]", text, re.DOTALL)
    if fenced:
        try:
            parsed = json.loads(fenced.group(0))
            if isinstance(parsed, list):
                raw_tokens = [str(t) for t in parsed]
        except (json.JSONDecodeError, ValueError):
            raw_tokens = []

    if not raw_tokens:
        # Strip code fences / labels, then split on whitespace and commas.
        text = re.sub(r"```[a-zA-Z]*", "", text).replace("`", "")
        raw_tokens = re.split(r"[\s,]+", text)

    out: list[str] = []
    for raw in raw_tokens:
        tok = normalize_token(raw)
        if tok:
            out.append(tok)
    return out
