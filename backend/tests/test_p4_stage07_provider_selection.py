import pytest

from app.domains.generation.circuit_breaker import CircuitBreaker
from app.domains.generation.providers.base import ProviderResponse
from app.domains.generation.providers.scoring import ProviderStats
from app.domains.generation.provider_router import (
    AllProvidersUnavailableError,
    ProviderRoute,
    ProviderRouter,
)


class _FakeProvider:
    def __init__(self, name: str) -> None:
        self.name = name

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        return ProviderResponse(provider=self.name, model=model, content="ok", tokens_used=1, latency_ms=1)


def _lower_is_better_scoring(stats: ProviderStats) -> float:
    return -(stats.recent_latency_ms + stats.cost_per_1k_tokens * 1000)


def test_selects_the_highest_scoring_available_route() -> None:
    fast_cheap = ProviderRoute(provider=_FakeProvider("fast_cheap"), breaker=CircuitBreaker())
    slow_expensive = ProviderRoute(provider=_FakeProvider("slow_expensive"), breaker=CircuitBreaker())
    router = ProviderRouter([slow_expensive, fast_cheap])

    stats = {
        "fast_cheap": ProviderStats(provider_name="fast_cheap", recent_latency_ms=50.0, cost_per_1k_tokens=0.0),
        "slow_expensive": ProviderStats(provider_name="slow_expensive", recent_latency_ms=2000.0, cost_per_1k_tokens=0.03),
    }

    selected = router.select_provider(stats, _lower_is_better_scoring)

    assert selected.provider.name == "fast_cheap"


def test_tripped_breaker_is_excluded_even_if_it_would_score_highest() -> None:
    best_but_tripped = ProviderRoute(
        provider=_FakeProvider("best_but_tripped"),
        breaker=CircuitBreaker(failure_threshold=1),
    )
    best_but_tripped.breaker.record_failure()

    worse_but_available = ProviderRoute(provider=_FakeProvider("worse_but_available"), breaker=CircuitBreaker())
    router = ProviderRouter([best_but_tripped, worse_but_available])

    stats = {
        "best_but_tripped": ProviderStats(provider_name="best_but_tripped", recent_latency_ms=1.0, cost_per_1k_tokens=0.0),
        "worse_but_available": ProviderStats(provider_name="worse_but_available", recent_latency_ms=500.0, cost_per_1k_tokens=0.03),
    }

    selected = router.select_provider(stats, _lower_is_better_scoring)

    assert selected.provider.name == "worse_but_available"


def test_all_providers_unavailable_raises_instead_of_valueerror() -> None:
    primary = ProviderRoute(provider=_FakeProvider("primary"), breaker=CircuitBreaker(failure_threshold=1))
    secondary = ProviderRoute(provider=_FakeProvider("secondary"), breaker=CircuitBreaker(failure_threshold=1))
    primary.breaker.record_failure()
    secondary.breaker.record_failure()

    router = ProviderRouter([primary, secondary])
    stats = {
        "primary": ProviderStats(provider_name="primary", recent_latency_ms=1.0, cost_per_1k_tokens=0.0),
        "secondary": ProviderStats(provider_name="secondary", recent_latency_ms=1.0, cost_per_1k_tokens=0.0),
    }

    with pytest.raises(AllProvidersUnavailableError):
        router.select_provider(stats, _lower_is_better_scoring)
