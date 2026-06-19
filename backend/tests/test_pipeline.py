"""W2->W3->W4 pipeline tests (hermetic: passthrough gloss + stub clips)."""

from __future__ import annotations

import pytest
from asl_schemas import SMPLXSequence

from app.blend import concatenate  # noqa: F401  (ensures import wiring is sane)
from app.gloss import GlossService, PassthroughProvider
from app.lookup import DictionaryLookup
from app.pipeline import SignPipeline, UnmatchedError
from app.stub_dictionary import build_stub_clips


def _pipeline() -> SignPipeline:
    # Cached demo gloss + offline passthrough; no network.
    gloss = GlossService(providers=[PassthroughProvider()])
    lookup = DictionaryLookup(build_stub_clips())
    return SignPipeline(gloss, lookup, transition_frames=4)


def test_demo_line_signs_to_sequence():
    seq = _pipeline().sign("My name is Jade.")  # cached -> MY NAME fs:J fs:A fs:D fs:E
    assert isinstance(seq, SMPLXSequence)
    assert seq.model == "SMPLX_NEUTRAL"
    assert len(seq.frames) > 0
    # meta is clip-aligned: source_gloss uses clip glosses (letters resolve fs:J -> "J")
    assert seq.meta.source_gloss == ["MY", "NAME", "J", "A", "D", "E"]
    assert seq.meta.clip_ids and len(seq.meta.clip_ids) == 6


def test_clip_frame_spans_align_and_bound():
    seq = _pipeline().sign("How are you today?")  # HOW YOU TODAY -> 3 clips
    spans = seq.meta.clip_frame_spans
    assert spans is not None
    # one span per clip, aligned with clip_ids
    assert len(spans) == len(seq.meta.clip_ids) == 3
    n = len(seq.frames)
    for start, end in spans:
        assert 0 <= start < end <= n          # within bounds, non-empty
    # spans are ordered and non-overlapping (transition frames sit between them)
    for i in range(len(spans) - 1):
        assert spans[i][1] <= spans[i + 1][0]


def test_v1_words_only_lines_sign():
    pipe = _pipeline()
    for line in ["Hello.", "How are you today?", "I can sign.", "I am happy."]:
        seq = pipe.sign(line)
        assert len(seq.frames) > 0 and seq.meta.clip_frame_spans


def test_all_five_demo_lines_sign():
    pipe = _pipeline()
    for line in [
        "Hello.",
        "How are you doing today?",
        "My name is Jade.",
        "I don't speak sign language, but my AI does.",
        "I'm happy to communicate.",
    ]:
        seq = pipe.sign(line)
        assert len(seq.frames) > 0


def test_zero_match_raises_unmatched():
    with pytest.raises(UnmatchedError) as exc:
        _pipeline().sign("xylophone zebra quokka")  # no stub clips for these
    assert exc.value.unmatched  # populated
