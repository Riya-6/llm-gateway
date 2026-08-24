import pytest

from app.domains.generation.providers.base import GenerationError, ProviderResponse
from app.domains.generation.retry import call_with_retry


class _FakeProvider:
    name = "fake"

    def __init__(self, fail_times: int = 0, always_fail: bool = False) -> None:
        self.fail_times = fail_times
        self.always_fail = always_fail
        self.call_count = 0

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        self.call_count += 1
        if self.always_fail or self.call_count <= self.fail_times:
            raise GenerationError(f"fake failed on attempt {self.call_count}")
        return ProviderResponse(provider=self.name, model=model, content="ok", tokens_used=1, latency_ms=1)


def test_no_jitter_matches_exact_exponential_sequence() -> None:
    provider = _FakeProvider(fail_times=3)
    sleeps: list[float] = []

    result = call_with_retry(
        provider, "prompt", "model",
        max_attempts=4, base_backoff_seconds=0.1, max_backoff_seconds=10.0,
        jitter=False, sleep_fn=sleeps.append,
    )

    assert result.content == "ok"
    assert provider.call_count == 4
    assert sleeps == [0.1, 0.2, 0.4]


def test_backoff_caps_at_max_backoff_seconds() -> None:
    provider = _FakeProvider(fail_times=3)
    sleeps: list[float] = []

    call_with_retry(
        provider, "prompt", "model",
        max_attempts=4, base_backoff_seconds=1.0, max_backoff_seconds=2.0,
        jitter=False, sleep_fn=sleeps.append,
    )

    assert sleeps == [1.0, 2.0, 2.0]


def test_jitter_scales_delay_by_random_fn() -> None:
    provider = _FakeProvider(fail_times=2)
    sleeps: list[float] = []

    call_with_retry(
        provider, "prompt", "model",
        max_attempts=3, base_backoff_seconds=0.1, max_backoff_seconds=10.0,
        jitter=True, sleep_fn=sleeps.append, random_fn=lambda: 0.5,
    )

    assert sleeps == [0.05, 0.1]


def test_default_max_attempts_is_one_no_retry() -> None:
    provider = _FakeProvider(always_fail=True)
    sleeps: list[float] = []

    with pytest.raises(GenerationError):
        call_with_retry(provider, "prompt", "model", sleep_fn=sleeps.append)

    assert provider.call_count == 1
    assert sleeps == []


def test_exhausts_attempts_and_reraises_original_error() -> None:
    provider = _FakeProvider(always_fail=True)
    sleeps: list[float] = []

    with pytest.raises(GenerationError):
        call_with_retry(
            provider, "prompt", "model",
            max_attempts=3, base_backoff_seconds=0.1, jitter=False, sleep_fn=sleeps.append,
        )

    assert provider.call_count == 3
    assert len(sleeps) == 2
