import time
from typing import Callable


class CircuitBreaker:
    """Per-provider closed/open/half-open circuit breaker.

    TODO (you): implement this. See docs/stages/phase4-generation.md, Stage 4
    for the exact state machine test_p4_stage04_circuit_breaker.py checks:
      - Starts "closed"; allow_request() is True.
      - record_failure() increments a consecutive-failure counter; at
        failure_threshold, trips to "open" and records now_fn() as the
        open time.
      - While "open", allow_request() is False unless
        recovery_timeout_seconds has elapsed since it opened — then it
        moves to "half_open" and this call returns True.
      - While "half_open": record_success() -> back to "closed", counter
        reset. record_failure() -> back to "open", timer restarts.
      - record_success() while "closed" just resets the counter.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        now_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._now = now_fn
        self.state = "closed"
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    def allow_request(self) -> bool:
        raise NotImplementedError

    def record_success(self) -> None:
        raise NotImplementedError

    def record_failure(self) -> None:
        raise NotImplementedError
