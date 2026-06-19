"""Sign pipeline: text -> SMPLXSequence, chaining W2 -> W3 -> W4."""

from __future__ import annotations

from asl_schemas import SMPLXSequence

from .blend import concatenate
from .gloss import GlossService
from .lookup import DictionaryLookup


class UnmatchedError(Exception):
    """No gloss token resolved to a clip — maps to HTTP 422 (§3.5)."""

    def __init__(self, unmatched: list[str]):
        self.unmatched = unmatched
        super().__init__(f"no clips matched: {unmatched}")


class SignPipeline:
    def __init__(
        self,
        gloss: GlossService,
        lookup: DictionaryLookup,
        transition_frames: int = 6,
    ):
        self._gloss = gloss
        self._lookup = lookup
        self._transition_frames = transition_frames

    def sign(self, text: str) -> SMPLXSequence:
        gloss_seq = self._gloss.to_gloss(text)
        result = self._lookup.resolve(gloss_seq)
        if not result.matched_any:
            # zero matches -> 422 (partial matches still blend what resolved)
            raise UnmatchedError(result.unmatched)
        seq = concatenate(result.clips, transition_frames=self._transition_frames)
        # carry the original English + any unmatched tokens for the client/UI
        seq.meta.source_gloss = gloss_seq.gloss
        return seq
