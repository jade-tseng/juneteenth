"""Gloss step (W2): English -> GlossSequence (§3.3).

Provider chain: cached demo script -> Nebius (primary) -> Claude (fallback)
-> deterministic passthrough (always available).
"""

from .base import GlossError, GlossProvider
from .claude import ClaudeProvider
from .nebius import NebiusProvider
from .passthrough import PassthroughProvider
from .service import GlossService

__all__ = [
    "GlossService",
    "GlossProvider",
    "GlossError",
    "NebiusProvider",
    "ClaudeProvider",
    "PassthroughProvider",
]
