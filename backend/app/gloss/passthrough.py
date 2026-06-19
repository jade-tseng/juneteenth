"""Hard fallback (§4.2): deterministic word-by-word gloss, no network.

Always available — this is the terminal provider that guarantees the service
returns *something* even when both LLM providers are down. Best-effort:
uppercase content words, strip punctuation, drop articles/copula, and expand
likely proper nouns to fingerspell letters.
"""

from __future__ import annotations

import re

from .base import GlossProvider
from .tokens import STOPWORDS, fingerspell

# Common contractions -> the content word we keep (drop the auxiliary/negation
# handled separately). Keeps "don't" -> DON'T readable rather than DON.
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def _looks_like_proper_noun(word: str, sentence_start: bool) -> bool:
    """Capitalized mid-sentence, or an all-caps acronym -> fingerspell it."""
    if word.isupper() and len(word) <= 4 and word.lower() not in STOPWORDS:
        return True  # acronym like AI, USA
    return word[:1].isupper() and not sentence_start


class PassthroughProvider(GlossProvider):
    name = "passthrough"

    def available(self) -> bool:
        return True

    def gloss(self, english: str) -> list[str]:
        tokens: list[str] = []
        # Track sentence starts so a leading capital isn't mistaken for a name.
        for sentence in re.split(r"(?<=[.!?])\s+", english.strip()):
            words = _WORD.findall(sentence)
            for i, word in enumerate(words):
                if word.lower() in STOPWORDS:
                    continue
                if _looks_like_proper_noun(word, sentence_start=(i == 0)):
                    tokens.extend(fingerspell(word))
                else:
                    tokens.append(word.upper())
        return tokens
