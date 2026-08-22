import time

import httpx

from app.domains.generation.providers.base import (
    GenerationError,
    ProviderResponse,
    ProviderTimeoutError,
)


class MockHTTPProvider:
    name = "mock"

    def __init__(self, base_url: str = "http://localhost:9100", timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        started = time.monotonic()
        try:
            response = httpx.post(
                f"{self._base_url}/v1/generate",
                json={"model": model, "prompt": prompt},
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"mock provider timed out after {self._timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise GenerationError(f"mock provider request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)

        if response.status_code >= 400:
            raise GenerationError(f"mock provider returned {response.status_code}: {response.text}")

        body = response.json()
        return ProviderResponse(
            provider=self.name,
            model=model,
            content=body["content"],
            tokens_used=body["tokens_used"],
            latency_ms=latency_ms,
        )
