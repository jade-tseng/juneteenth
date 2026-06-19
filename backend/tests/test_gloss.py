"""W2 acceptance tests: cached script lines, passthrough fallback, fs: expansion."""

from __future__ import annotations

import pytest
from asl_schemas import GlossSequence

from app.gloss import GlossService, PassthroughProvider
from app.gloss.base import GlossError, GlossProvider
from app.gloss.tokens import fingerspell, parse_gloss_tokens


# --- the 5 demo script lines (§5), served from the verified cache -------------
DEMO_CASES = [
    ("Hello.", ["HELLO"]),
    ("How are you doing today?", ["HOW", "YOU", "TODAY"]),
    ("My name is Jade.", ["MY", "NAME", "fs:J", "fs:A", "fs:D", "fs:E"]),
    (
        "I don't speak sign language, but my AI does.",
        ["ME", "SIGN", "NOT", "BUT", "MY", "fs:A", "fs:I", "CAN"],
    ),
    ("I'm happy to communicate.", ["ME", "HAPPY", "COMMUNICATE"]),
]


@pytest.mark.parametrize("english,expected", DEMO_CASES)
def test_demo_script_cached(english, expected):
    # No providers at all — cache must satisfy every demo line.
    svc = GlossService(providers=[])
    result = svc.to_gloss(english)
    assert isinstance(result, GlossSequence)
    assert result.gloss == expected


def test_cache_resilient_to_punctuation_and_case():
    svc = GlossService(providers=[])
    assert svc.to_gloss("HELLO!!!").gloss == ["HELLO"]
    assert svc.to_gloss("  my name is jade  ").gloss[:2] == ["MY", "NAME"]


# --- passthrough works with both LLM providers disabled -----------------------
def test_passthrough_when_providers_unavailable():
    # Cache off, only passthrough available -> deterministic word-by-word.
    svc = GlossService(providers=[PassthroughProvider()], use_cache=False)
    result = svc.to_gloss("the cat is happy")
    # articles/copula dropped, content words uppercased
    assert result.gloss == ["CAT", "HAPPY"]


def test_passthrough_fingerspells_proper_nouns():
    pt = PassthroughProvider()
    # Mid-sentence capitalized proper noun -> fingerspelled
    assert pt.gloss("my name is Jade") == ["MY", "NAME"] + fingerspell("Jade")
    # Acronym -> fingerspelled
    assert pt.gloss("my AI signs") == ["MY"] + fingerspell("AI") + ["SIGNS"]


# --- provider fall-through order ----------------------------------------------
class _BoomProvider(GlossProvider):
    name = "boom"

    def available(self) -> bool:
        return True

    def gloss(self, english: str) -> list[str]:
        raise GlossError("boom")


class _StubProvider(GlossProvider):
    name = "stub"

    def available(self) -> bool:
        return True

    def gloss(self, english: str) -> list[str]:
        return ["STUB"]


def test_falls_through_failing_provider_to_next():
    svc = GlossService(providers=[_BoomProvider(), _StubProvider()], use_cache=False)
    assert svc.to_gloss("anything").gloss == ["STUB"]


def test_primary_used_when_it_succeeds():
    svc = GlossService(providers=[_StubProvider(), _BoomProvider()], use_cache=False)
    assert svc.to_gloss("anything").gloss == ["STUB"]


# --- token parsing / fs: expansion -------------------------------------------
def test_fingerspell_expansion():
    assert fingerspell("Jade") == ["fs:J", "fs:A", "fs:D", "fs:E"]
    assert fingerspell("AI") == ["fs:A", "fs:I"]


def test_parse_gloss_tokens_space_separated():
    assert parse_gloss_tokens("MY NAME fs:J fs:A") == ["MY", "NAME", "fs:J", "fs:A"]


def test_parse_gloss_tokens_json_array():
    assert parse_gloss_tokens('["HELLO", "you"]') == ["HELLO", "YOU"]


def test_parse_gloss_tokens_drops_invalid():
    # lowercase fs normalized; junk dropped; nothing valid -> []
    assert parse_gloss_tokens("FS:j !!! ??") == ["fs:J"]
    assert parse_gloss_tokens("...") == []
