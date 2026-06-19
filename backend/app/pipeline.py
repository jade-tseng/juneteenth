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
        # concatenate sets meta.source_gloss / clip_ids / clip_frame_spans all
        # aligned 1:1 with the matched clips — leave them intact (don't overwrite
        # source_gloss with the raw tokens, which include fs:/synonym/unmatched
        # forms that wouldn't line up with clip_frame_spans for caption sync).
        return concatenate(result.clips, transition_frames=self._transition_frames)
