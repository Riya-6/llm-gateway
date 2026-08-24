import time
from typing import Callable


class CircuitBreaker:
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
        if self.state == "open":
            if self._now() - self._opened_at >= self.recovery_timeout_seconds:
                self.state = "half_open"
                return True
            return False
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self.state = "closed"
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self.state == "half_open" or self._consecutive_failures >= self.failure_threshold:
            self.state = "open"
            self._opened_at = self._now()
