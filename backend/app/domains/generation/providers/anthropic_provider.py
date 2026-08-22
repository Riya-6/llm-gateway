import time

import httpx

from app.domains.generation.providers.base import (
    GenerationError,
    ProviderResponse,
    ProviderTimeoutError,
)

_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, timeout_seconds: float = 30.0, max_tokens: int = 1024) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        started = time.monotonic()
        try:
            response = httpx.post(
                _MESSAGES_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": _ANTHROPIC_VERSION,
                },
                json={
                    "model": model,
                    "max_tokens": self._max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"anthropic timed out after {self._timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise GenerationError(f"anthropic request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)

        if response.status_code >= 400:
            raise GenerationError(f"anthropic returned {response.status_code}: {response.text}")

        body = response.json()
        content = body["content"][0]["text"]
        usage = body.get("usage", {})
        tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

        return ProviderResponse(
            provider=self.name,
            model=model,
            content=content,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
