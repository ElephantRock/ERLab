"""Async circuit breaker with closed/open/half-open states.

Adapted from RAG-Anything's CircuitBreaker (threading.Lock version).
Uses asyncio.Lock for async-safe operation.
Enhanced with percentage-based cooldown and exponential backoff for
OPEN→HALF_OPEN transitions.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from enum import Enum

from backend.providers.resilience.errors import CircuitOpenError

_MAX_COOLDOWN_SECONDS = 300.0  # 5 min cap on exponential cooldown
_COOLDOWN_WINDOW_SECONDS = 60.0  # sliding window for failure-rate calculation


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-provider circuit breaker with three states.

    Closed: requests pass through. Failures are counted.
    Open: all requests fail immediately. After reset_timeout, transitions to half-open.
    Half-open: allows limited requests through to test recovery.

    Enhanced with percentage-based cooldown: when the failure rate within a
    sliding window exceeds cooldown_percent, the OPEN→HALF_OPEN timeout grows
    exponentially (capped at 5 min) to back off from unreliable providers.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        half_open_max_calls: int = 1,
        cooldown_percent: float = 0.1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._half_open_max_calls = half_open_max_calls
        self._cooldown_percent = cooldown_percent
        self._state = _State.CLOSED
        self._failure_count = 0
        self._total_count = 0
        self._half_open_successes = 0
        self._last_failure_time: float = 0.0
        self._consecutive_opens: int = 0
        self._failure_timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    def _effective_timeout(self) -> float:
        """Compute current OPEN→HALF_OPEN timeout with exponential backoff.

        If the failure rate within the sliding window exceeds cooldown_percent,
        the timeout grows exponentially based on consecutive opens.
        """
        now = time.monotonic()
        window_start = now - _COOLDOWN_WINDOW_SECONDS
        while self._failure_timestamps and self._failure_timestamps[0] < window_start:
            self._failure_timestamps.popleft()

        if self._total_count > 0 and self._total_count >= self._failure_threshold:
            failure_rate = len(self._failure_timestamps) / self._total_count
        else:
            failure_rate = 0.0

        if failure_rate > self._cooldown_percent and self._consecutive_opens > 1:
            backoff = self._reset_timeout * (2 ** self._consecutive_opens)
            return min(backoff, _MAX_COOLDOWN_SECONDS)
        return self._reset_timeout

    @property
    def state(self) -> str:
        return self._state.value

    async def allow_request(self) -> bool:
        """Check if a request is allowed. Raises CircuitOpenError if open."""
        async with self._lock:
            if self._state == _State.CLOSED:
                return True
            if self._state == _State.OPEN:
                timeout = self._effective_timeout()
                if time.monotonic() - self._last_failure_time >= timeout:
                    self._state = _State.HALF_OPEN
                    self._half_open_successes = 0
                    return True
                return False
            # HALF_OPEN: allow up to half_open_max_calls
            return self._half_open_successes < self._half_open_max_calls

    async def record_success(self) -> None:
        async with self._lock:
            self._total_count += 1
            if self._state == _State.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self._half_open_max_calls:
                    self._state = _State.CLOSED
                    self._failure_count = 0
                    self._consecutive_opens = 0
            else:
                self._failure_count = 0
                self._consecutive_opens = 0

    async def record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._total_count += 1
            self._last_failure_time = time.monotonic()
            self._failure_timestamps.append(self._last_failure_time)
            if self._state == _State.HALF_OPEN or self._failure_count >= self._failure_threshold:
                self._consecutive_opens += 1
                self._state = _State.OPEN

    def check(self) -> None:
        """Synchronous check — raises CircuitOpenError if open."""
        if self._state == _State.OPEN:
            timeout = self._effective_timeout()
            if time.monotonic() - self._last_failure_time < timeout:
                raise CircuitOpenError(
                    f"Circuit open (failures={self._failure_count})"
                )


# Module-level registry: one breaker per provider name
_breakers: dict[str, CircuitBreaker] = {}
