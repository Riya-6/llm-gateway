import time

import httpx

from app.domains.generation.providers.base import (
    GenerationError,
    ProviderResponse,
    ProviderTimeoutError,
)


class OllamaProvider:
    """Local model inference via Ollama (https://ollama.com).

    Structurally identical to the hosted providers — same Provider protocol,
    same httpx-based call — but free to run repeatedly and with a genuinely
    different latency profile (local GPU/CPU inference vs. a network round
    trip to a hosted API), which is the point of including it: it gives the
    router something real to route against on cost/latency grounds, not just
    on failure.

    Requires Ollama running locally (`ollama serve`, default port 11434) with
    the requested model already pulled (`ollama pull <model>`) — this class
    doesn't pull models on your behalf.
    """

    name = "ollama"

    def __init__(self, base_url: str = "http://127.0.0.1:11434", timeout_seconds: float = 60.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        started = time.monotonic()
        try:
            response = httpx.post(
                f"{self._base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(f"ollama timed out after {self._timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise GenerationError(f"ollama request failed: {exc}") from exc

        latency_ms = int((time.monotonic() - started) * 1000)

        if response.status_code >= 400:
            raise GenerationError(f"ollama returned {response.status_code}: {response.text}")

        body = response.json()
        content = body["response"]
        tokens_used = body.get("prompt_eval_count", 0) + body.get("eval_count", 0)

        return ProviderResponse(
            provider=self.name,
            model=model,
            content=content,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
