"""W3 acceptance: token->clip mapping incl. fs:, unmatched reporting, 0-match."""

from __future__ import annotations

from asl_schemas import GlossSequence
from conftest import clip

from app.lookup import DictionaryLookup, LocalClipStore


def _dict() -> DictionaryLookup:
    return DictionaryLookup([
        clip("HELLO", "lexical"),
        clip("MY", "lexical"),
        clip("NAME", "lexical"),
        clip("ME", "lexical"),
        clip("J", "letter"),
        clip("A", "letter"),
        clip("D", "letter"),
        clip("E", "letter"),
    ])


def test_maps_lexical_and_fingerspell_tokens():
    g = GlossSequence(english="my name is jade",
                      gloss=["MY", "NAME", "fs:J", "fs:A", "fs:D", "fs:E"])
    res = _dict().resolve(g)
    assert res.unmatched == []
    assert [c.gloss for c in res.clips] == ["MY", "NAME", "J", "A", "D", "E"]
    assert res.matched_any


def test_reports_unmatched_but_keeps_matches():
    g = GlossSequence(english="x", gloss=["HELLO", "BANANA", "fs:Z"])
    res = _dict().resolve(g)
    assert [c.gloss for c in res.clips] == ["HELLO"]
    assert res.unmatched == ["BANANA", "fs:Z"]


def test_synonym_me_i():
    g = GlossSequence(english="i", gloss=["I"])  # I -> ME via synonym map
    res = _dict().resolve(g)
    assert [c.gloss for c in res.clips] == ["ME"]


def test_zero_match():
    g = GlossSequence(english="x", gloss=["NOPE", "fs:Q"])
    res = _dict().resolve(g)
    assert not res.matched_any
    assert res.unmatched == ["NOPE", "fs:Q"]


def test_local_store_roundtrip(tmp_path):
    (tmp_path / "hello.json").write_text(clip("HELLO").model_dump_json())
    (tmp_path / "j.json").write_text(clip("J", "letter").model_dump_json())
    lookup = DictionaryLookup.from_store(LocalClipStore(tmp_path))
    res = lookup.resolve(GlossSequence(english="hello", gloss=["HELLO", "fs:J"]))
    assert [c.gloss for c in res.clips] == ["HELLO", "J"]
