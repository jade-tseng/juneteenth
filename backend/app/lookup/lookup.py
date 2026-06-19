"""Dictionary lookup (W3, §4.3): GlossSequence -> ordered SMPLXClip[].

Resolves each token (lexical gloss or `fs:<letter>` fingerspell) to a clip from
the dictionary, applying a small synonym map, and reports unmatched tokens. The
API layer turns a zero-match result into a 422 (§3.5).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from asl_schemas import GlossSequence, SMPLXClip

from .store import ClipStore

# Canonical synonyms: token -> a gloss that exists in the dictionary (§4.3, ME↔I).
SYNONYMS: dict[str, str] = {
    "I": "ME",
    "MINE": "MY",
    "HI": "HELLO",
    "HELLO_THERE": "HELLO",
}


@dataclass
class LookupResult:
    clips: list[SMPLXClip] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)

    @property
    def matched_any(self) -> bool:
        return bool(self.clips)


class DictionaryLookup:
    # Extractors that produce non-real placeholder motion. With
    # EXCLUDE_PLACEHOLDER_CLIPS=1 these are never matched, so unrecognized speech
    # falls through to the caller's default sign rather than signing synthetic
    # gestures. Off by default (keeps stub-based tests and pre-real-data builds
    # working); the demo/prod backend sets the env var.
    _PLACEHOLDER_EXTRACTORS = {"synthetic-placeholder", "stub", "synthetic", "poc-stub"}

    def __init__(self, clips: list[SMPLXClip]):
        # Index lexical clips by uppercase gloss, letter clips by single letter.
        self._lexical: dict[str, SMPLXClip] = {}
        self._letters: dict[str, SMPLXClip] = {}
        exclude_placeholders = os.getenv("EXCLUDE_PLACEHOLDER_CLIPS") == "1"
        for clip in clips:
            extractor = (clip.source.extractor or "").lower() if clip.source else ""
            if exclude_placeholders and extractor in self._PLACEHOLDER_EXTRACTORS:
                continue  # only real ASL is recognized; rest → caller's default
            if clip.kind == "letter":
                self._letters[clip.gloss.upper()] = clip
            else:
                self._lexical[clip.gloss.upper()] = clip

    @classmethod
    def from_store(cls, store: ClipStore) -> "DictionaryLookup":
        return cls(store.load_all())

    def _resolve_token(self, token: str) -> SMPLXClip | None:
        if token.lower().startswith("fs:"):
            letter = token[3:].strip().upper()
            return self._letters.get(letter)
        key = token.upper()
        clip = self._lexical.get(key)
        if clip is None:
            # synonym fallback (ME↔I, etc.)
            canonical = SYNONYMS.get(key)
            if canonical is not None:
                clip = self._lexical.get(canonical)
        return clip

    def resolve(self, gloss: GlossSequence) -> LookupResult:
        result = LookupResult()
        for token in gloss.gloss:
            clip = self._resolve_token(token)
            if clip is None:
                result.unmatched.append(token)
            else:
                result.clips.append(clip)
        return result
