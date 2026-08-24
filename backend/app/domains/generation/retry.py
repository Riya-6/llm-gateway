import random
import time
from typing import Callable

from app.domains.generation.providers.base import GenerationError, Provider, ProviderResponse


def call_with_retry(
    provider: Provider,
    prompt: str,
    model: str,
    *,
    max_attempts: int = 1,
    base_backoff_seconds: float = 0.1,
    max_backoff_seconds: float = 10.0,
    jitter: bool = True,
    sleep_fn: Callable[[float], None] = time.sleep,
    random_fn: Callable[[], float] = random.random,
) -> ProviderResponse:
    
    last_error: GenerationError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return provider.generate(prompt, model)
        except GenerationError as exc:
            last_error = exc
            if attempt < max_attempts:
                delay = min(max_backoff_seconds, base_backoff_seconds * (2 ** (attempt - 1)))
                if jitter:
                    delay = random_fn() * delay
                sleep_fn(delay)
    assert last_error is not None
    raise last_error
