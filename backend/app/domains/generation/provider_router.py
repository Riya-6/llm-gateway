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
    """Multi-provider router: failure-based fallback (generate) plus
    cost/latency-aware selection for normal operation (select_provider).

    TODO (you): implement both. See docs/stages/phase4-generation.md,
    Stages 6 and 7.
    """

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
        """Stage 6 — failure-handling path.

        TODO (you): walk self.routes in order. Skip a route entirely if
        breaker.allow_request() is False. Otherwise call_with_retry against
        it; on success, breaker.record_success() and return immediately. On
        GenerationError, breaker.record_failure() and move to the next
        route. If every route was skipped, raise
        AllProvidersUnavailableError. If at least one route was tried but
        all failed, re-raise the last GenerationError.
        """
        raise NotImplementedError

    def select_provider(
        self,
        stats: dict[str, ProviderStats],
        scoring: ScoringStrategy,
    ) -> ProviderRoute:
        """Stage 7 — normal-operation path.

        TODO (you): among self.routes whose breaker.allow_request() is True,
        return the one with the highest scoring(stats[route.provider.name]).
        A tripped-open route must never be selected even if its stats would
        otherwise score highest. Populating/updating `stats` over time
        (e.g. an EMA of recent_latency_ms) is also yours — this method just
        picks, given whatever stats it's handed.
        """
        raise NotImplementedError
