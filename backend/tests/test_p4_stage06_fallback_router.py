import pytest

from app.domains.generation.circuit_breaker import CircuitBreaker
from app.domains.generation.providers.base import GenerationError, ProviderResponse
from app.domains.generation.provider_router import (
    AllProvidersUnavailableError,
    ProviderRoute,
    ProviderRouter,
)


class _FakeProvider:
    def __init__(self, name: str, always_fail: bool = False) -> None:
        self.name = name
        self.always_fail = always_fail
        self.call_count = 0

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        self.call_count += 1
        if self.always_fail:
            raise GenerationError(f"{self.name} failed")
        return ProviderResponse(provider=self.name, model=model, content="ok", tokens_used=1, latency_ms=1)


def test_falls_back_to_secondary_when_primary_fails() -> None:
    primary = _FakeProvider("primary", always_fail=True)
    secondary = _FakeProvider("secondary")
    router = ProviderRouter([
        ProviderRoute(provider=primary, breaker=CircuitBreaker()),
        ProviderRoute(provider=secondary, breaker=CircuitBreaker()),
    ])

    result = router.generate("prompt", "mock-model")

    assert result.provider == "secondary"
    assert primary.call_count == 1


def test_all_providers_unavailable_raises_without_calling_providers() -> None:
    primary = _FakeProvider("primary")
    secondary = _FakeProvider("secondary")
    primary_breaker = CircuitBreaker(failure_threshold=1)
    secondary_breaker = CircuitBreaker(failure_threshold=1)
    primary_breaker.record_failure()
    secondary_breaker.record_failure()

    router = ProviderRouter([
        ProviderRoute(provider=primary, breaker=primary_breaker),
        ProviderRoute(provider=secondary, breaker=secondary_breaker),
    ])

    with pytest.raises(AllProvidersUnavailableError):
        router.generate("prompt", "mock-model")

    assert primary.call_count == 0
    assert secondary.call_count == 0


def test_tripped_primary_is_skipped_on_next_call() -> None:
    primary = _FakeProvider("primary", always_fail=True)
    secondary = _FakeProvider("secondary")
    router = ProviderRouter([
        ProviderRoute(provider=primary, breaker=CircuitBreaker(failure_threshold=1)),
        ProviderRoute(provider=secondary, breaker=CircuitBreaker(failure_threshold=1)),
    ])

    router.generate("prompt", "mock-model")
    assert primary.call_count == 1

    router.generate("prompt", "mock-model")
    assert primary.call_count == 1
    assert secondary.call_count == 2


def test_raises_last_error_when_all_tried_providers_fail() -> None:
    primary = _FakeProvider("primary", always_fail=True)
    secondary = _FakeProvider("secondary", always_fail=True)
    router = ProviderRouter([
        ProviderRoute(provider=primary, breaker=CircuitBreaker(failure_threshold=10)),
        ProviderRoute(provider=secondary, breaker=CircuitBreaker(failure_threshold=10)),
    ])

    with pytest.raises(GenerationError):
        router.generate("prompt", "mock-model")

    assert primary.call_count == 1
    assert secondary.call_count == 1
