"""Gloss orchestration (W2): cache -> Nebius -> Claude -> passthrough.

Returns a frozen `GlossSequence` (§3.3). The terminal passthrough provider is
always available, so `to_gloss` never fails — it degrades.
"""

from __future__ import annotations

import logging

from asl_schemas import GlossSequence

from . import cache
from .base import GlossError, GlossProvider
from .claude import ClaudeProvider
from .nebius import NebiusProvider
from .passthrough import PassthroughProvider

log = logging.getLogger(__name__)


class GlossService:
    def __init__(
        self,
        providers: list[GlossProvider] | None = None,
        use_cache: bool = True,
    ):
        # Order matters: primary first, terminal passthrough last.
        self._providers = providers if providers is not None else [
            NebiusProvider(),
            ClaudeProvider(),
            PassthroughProvider(),
        ]
        self._use_cache = use_cache

    def to_gloss(self, english: str) -> GlossSequence:
        english = english.strip()

        # 1) Pre-verified demo script — never hits the network.
        if self._use_cache:
            cached = cache.lookup(english)
            if cached is not None:
                return GlossSequence(english=english, gloss=list(cached))

        # 2) Try each available provider in order; fall through on failure.
        for provider in self._providers:
            if not provider.available():
                continue
            try:
                tokens = provider.gloss(english)
                if tokens:
                    log.info("gloss via %s: %d tokens", provider.name, len(tokens))
                    return GlossSequence(english=english, gloss=tokens)
            except GlossError as exc:
                log.warning("gloss provider %s failed: %s", provider.name, exc)
                continue

        # Should be unreachable: passthrough is always available and total.
        return GlossSequence(english=english, gloss=[])
