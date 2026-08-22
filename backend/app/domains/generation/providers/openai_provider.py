import time

import httpx

from app.domains.generation.providers.base import (
    GenerationError,
    ProviderResponse,
    ProviderTimeoutError,
)

_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, timeout_seconds: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        started = time.monotonic()
        try:
            response = httpx.post(
                _CHAT_COMPLETIONS_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"openai timed out after {self._timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise GenerationError(f"openai request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)

        if response.status_code >= 400:
            raise GenerationError(f"openai returned {response.status_code}: {response.text}")

        body = response.json()
        content = body["choices"][0]["message"]["content"]
        tokens_used = body.get("usage", {}).get("total_tokens", 0)

        return ProviderResponse(
            provider=self.name,
            model=model,
            content=content,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
