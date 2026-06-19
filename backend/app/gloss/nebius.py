"""Primary gloss provider: Nebius (OpenAI-compatible). §4.2."""

from __future__ import annotations

import os

from .base import GlossError, GlossProvider
from .prompt import SYSTEM_PROMPT, user_prompt
from .tokens import parse_gloss_tokens

# Confirm current base URL + model from Nebius docs; older studio URL may resolve.
DEFAULT_BASE_URL = "https://api.studio.nebius.com/v1/"
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"


class NebiusProvider(GlossProvider):
    name = "nebius"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 8.0,
    ):
        self._api_key = api_key or os.getenv("NEBIUS_API_KEY")
        self._base_url = base_url or os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL)
        self._model = model or os.getenv("NEBIUS_MODEL", DEFAULT_MODEL)
        self._timeout = timeout
        self._client = None

    def available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI  # lazy import; keeps cold start cheap

            self._client = OpenAI(
                api_key=self._api_key, base_url=self._base_url, timeout=self._timeout
            )
        return self._client

    def gloss(self, english: str) -> list[str]:
        if not self.available():
            raise GlossError("nebius: NEBIUS_API_KEY not set")
        try:
            resp = self._get_client().chat.completions.create(
                model=self._model,
                temperature=0,
                max_tokens=128,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt(english)},
                ],
            )
            content = (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # network/timeout/auth/SDK -> fall through
            raise GlossError(f"nebius: {exc}") from exc

        tokens = parse_gloss_tokens(content)
        if not tokens:
            raise GlossError(f"nebius: no valid tokens in {content!r}")
        return tokens
