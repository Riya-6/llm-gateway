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
    """Call `provider.generate`, retrying on GenerationError with exponential backoff.

    TODO (you): implement this. See docs/stages/phase4-generation.md, Stage 3
    for the exact contract test_p4_stage03_retry.py checks against:
      - Success at any attempt returns immediately, no further attempts/sleeping.
      - A failed attempt n (1-indexed) sleeps before retrying, UNLESS it was
        the final attempt (max_attempts) — then just re-raise instead.
      - Uncapped delay for attempt n: base_backoff_seconds * (2 ** (n - 1)),
        capped at max_backoff_seconds.
      - jitter=False: sleep exactly the capped delay.
      - jitter=True ("full jitter"): sleep random_fn() * capped_delay.
      - Re-raise the final attempt's original GenerationError, not a new one.
    """
    raise NotImplementedError
