"""Async circuit breaker with closed/open/half-open states.

Adapted from RAG-Anything's CircuitBreaker (threading.Lock version).
Uses asyncio.Lock for async-safe operation.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum

from backend.providers.resilience.errors import CircuitOpenError


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-provider circuit breaker with three states.

    Closed: requests pass through. Failures are counted.
    Open: all requests fail immediately. After reset_timeout, transitions to half-open.
    Half-open: allows limited requests through to test recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._half_open_max_calls = half_open_max_calls
        self._state = _State.CLOSED
        self._failure_count = 0
        self._half_open_successes = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state.value

    async def allow_request(self) -> bool:
        """Check if a request is allowed. Raises CircuitOpenError if open."""
        async with self._lock:
            if self._state == _State.CLOSED:
                return True
            if self._state == _State.OPEN:
                if time.monotonic() - self._last_failure_time >= self._reset_timeout:
                    self._state = _State.HALF_OPEN
                    self._half_open_successes = 0
                    return True
                return False
            # HALF_OPEN: allow up to half_open_max_calls
            return self._half_open_successes < self._half_open_max_calls

    async def record_success(self) -> None:
        async with self._lock:
            if self._state == _State.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self._half_open_max_calls:
                    self._state = _State.CLOSED
                    self._failure_count = 0
            else:
                self._failure_count = 0

    async def record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == _State.HALF_OPEN:
                self._state = _State.OPEN
            elif self._failure_count >= self._failure_threshold:
                self._state = _State.OPEN

    def check(self) -> None:
        """Synchronous check — raises CircuitOpenError if open."""
        if self._state == _State.OPEN:
            if time.monotonic() - self._last_failure_time < self._reset_timeout:
                raise CircuitOpenError(
                    f"Circuit open (failures={self._failure_count})"
                )


# Module-level registry: one breaker per provider name
_breakers: dict[str, CircuitBreaker] = {}
