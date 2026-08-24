from app.domains.generation.circuit_breaker import CircuitBreaker


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_stays_closed_below_failure_threshold() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=10, now_fn=clock)

    breaker.record_failure()
    breaker.record_failure()

    assert breaker.state == "closed"
    assert breaker.allow_request() is True


def test_trips_open_at_failure_threshold_and_blocks_requests() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=10, now_fn=clock)

    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()

    assert breaker.state == "open"
    assert breaker.allow_request() is False


def test_moves_to_half_open_after_recovery_timeout() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=10, now_fn=clock)

    breaker.record_failure()
    assert breaker.state == "open"
    assert breaker.allow_request() is False

    clock.advance(10)
    assert breaker.allow_request() is True
    assert breaker.state == "half_open"


def test_success_in_half_open_closes_breaker() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=10, now_fn=clock)

    breaker.record_failure()
    clock.advance(10)
    breaker.allow_request()

    breaker.record_success()

    assert breaker.state == "closed"
    assert breaker.allow_request() is True


def test_failure_in_half_open_reopens_breaker() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=10, now_fn=clock)

    breaker.record_failure()
    clock.advance(10)
    breaker.allow_request()

    breaker.record_failure()

    assert breaker.state == "open"
    assert breaker.allow_request() is False
