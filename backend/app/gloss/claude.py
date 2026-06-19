"""Fallback gloss provider: Anthropic Claude API. §4.2.

Triggered when Nebius errors/times out/returns invalid output. Uses the
Anthropic SDK (Messages API). Model defaults to claude-opus-4-8 and is
overridable via ANTHROPIC_MODEL.
"""

from __future__ import annotations

import os

from .base import GlossError, GlossProvider
from .prompt import SYSTEM_PROMPT, user_prompt
from .tokens import parse_gloss_tokens

# Default to the latest Opus; override with ANTHROPIC_MODEL (e.g. a cheaper
# Haiku) if cost matters for the fallback path.
DEFAULT_MODEL = "claude-opus-4-8"


class ClaudeProvider(GlossProvider):
    name = "claude"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 12.0,
    ):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        self._timeout = timeout
        self._client = None

    def available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            import anthropic  # lazy import; keeps cold start cheap

            self._client = anthropic.Anthropic(
                api_key=self._api_key, timeout=self._timeout
            )
        return self._client

    def gloss(self, english: str) -> list[str]:
        if not self.available():
            raise GlossError("claude: ANTHROPIC_API_KEY not set")
        try:
            # NOTE: do NOT pass temperature — it is removed on Opus 4.8 (400).
            resp = self._get_client().messages.create(
                model=self._model,
                max_tokens=256,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt(english)}],
            )
        except Exception as exc:  # network/timeout/auth/SDK -> fall through
            raise GlossError(f"claude: {exc}") from exc

        # Check stop_reason before reading content (refusal -> empty/partial).
        if getattr(resp, "stop_reason", None) == "refusal":
            raise GlossError("claude: request refused")

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()

        tokens = parse_gloss_tokens(text)
        if not tokens:
            raise GlossError(f"claude: no valid tokens in {text!r}")
        return tokens
