import random
import time
from dataclasses import dataclass
from typing import Callable

from app.domains.generation.circuit_breaker import CircuitBreaker
from app.domains.generation.providers.base import GenerationError, Provider, ProviderResponse
from app.domains.generation.providers.scoring import ProviderStats, ScoringStrategy
from app.domains.generation.retry import call_with_retry


class AllProvidersUnavailableError(Exception):
    """Raised when every provider's circuit breaker is currently open."""


@dataclass
class ProviderRoute:
    provider: Provider
    breaker: CircuitBreaker


class ProviderRouter:

    name = "router"

    def __init__(self, routes: list[ProviderRoute]) -> None:
        self.routes = routes

    def generate(
        self,
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
        attempted = False
        for route in self.routes:
            if not route.breaker.allow_request():
                continue
            attempted = True
            try:
                result = call_with_retry(
                    route.provider, prompt, model,
                    max_attempts=max_attempts, base_backoff_seconds=base_backoff_seconds,
                    max_backoff_seconds=max_backoff_seconds, jitter=jitter,
                    sleep_fn=sleep_fn, random_fn=random_fn,
                )
                route.breaker.record_success()
                return result
            except GenerationError as exc:
                route.breaker.record_failure()
                last_error = exc
                continue

        if not attempted:
            raise AllProvidersUnavailableError("All providers are currently unavailable")
        assert last_error is not None
        raise last_error

    def select_provider(
        self,
        stats: dict[str, ProviderStats],
        scoring: ScoringStrategy,
    ) -> ProviderRoute:
        available = [route for route in self.routes if route.breaker.allow_request()]
        if not available:
            raise AllProvidersUnavailableError("All providers are currently unavailable")
        return max(available, key=lambda route: scoring(stats[route.provider.name]))
