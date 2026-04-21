"""Retry with exponential backoff and jitter.

Classifies errors by HTTP status code and applies appropriate delay strategy:
- 429 (rate limit): cooldown delay (longer)
- 401/403 (auth): no retry — trigger key rotation
- 408/5xx (transient): exponential backoff with jitter
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from backend.providers.resilience.circuit_breaker import CircuitBreaker
from backend.providers.resilience.errors import (
    CircuitOpenError,
    RetryDecision,
    classify_status,
    extract_status_code,
)

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 0.1
    cooldown_delay: float = 30.0


def _compute_delay(
    attempt: int,
    config: RetryConfig,
    decision: RetryDecision,
) -> float:
    if decision == RetryDecision.COOLDOWN:
        base = config.cooldown_delay
    else:
        base = min(config.base_delay * (2 ** attempt), config.max_delay)
    jitter_range = base * config.jitter
    return base + random.uniform(-jitter_range, jitter_range)


async def retry_with_backoff(
    fn: Callable[[], Awaitable[Any]],
    config: RetryConfig,
    circuit_breaker: CircuitBreaker,
    *,
    on_retry: Callable[[int, Exception, RetryDecision], Awaitable[None]] | None = None,
    on_auth_failure: Callable[[], Awaitable[None]] | None = None,
) -> Any:
    """Execute fn with retry, backoff, and circuit breaker integration.

    Args:
        fn: Async callable to execute.
        config: Retry timing configuration.
        circuit_breaker: Circuit breaker to record success/failure.
        on_retry: Called before each retry with (attempt, exception, decision).
        on_auth_failure: Called on 401/403 before raising.

    Returns:
        The return value of fn.

    Raises:
        CircuitOpenError: If the circuit breaker is open.
        The last exception if all retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(config.max_retries + 1):
        if not await circuit_breaker.allow_request():
            raise CircuitOpenError("Circuit breaker is open — fast-fail")

        try:
            result = await fn()
            await circuit_breaker.record_success()
            return result
        except Exception as exc:
            last_exc = exc
            status = extract_status_code(exc)
            if status is None:
                # Non-HTTP error (connection, timeout) — retry with backoff
                decision = RetryDecision.RETRY
            else:
                decision = classify_status(status)

            if decision == RetryDecision.NO_RETRY:
                await circuit_breaker.record_failure()
                if on_auth_failure:
                    await on_auth_failure()
                raise

            await circuit_breaker.record_failure()

            if attempt >= config.max_retries:
                raise

            if on_retry:
                await on_retry(attempt, exc, decision)

            delay = _compute_delay(attempt, config, decision)
            logger.info(
                "Retry %d/%d after %.1fs (status=%s, decision=%s): %s",
                attempt + 1,
                config.max_retries,
                delay,
                status,
                decision.value,
                exc,
            )
            await asyncio.sleep(delay)

    raise last_exc  # pragma: no cover
