"""GlossProvider abstraction (§4.2)."""

from __future__ import annotations

import abc


class GlossError(RuntimeError):
    """Raised by a provider when it cannot produce usable gloss tokens."""


class GlossProvider(abc.ABC):
    """Turns an English string into a list of gloss tokens.

    Implementations raise GlossError on any failure (network, timeout, auth,
    empty/invalid output) so the service can fall through to the next provider.
    """

    name: str = "provider"

    @abc.abstractmethod
    def available(self) -> bool:
        """True if the provider is configured (e.g. its API key is present)."""

    @abc.abstractmethod
    def gloss(self, english: str) -> list[str]:
        """Return validated gloss tokens, or raise GlossError."""
