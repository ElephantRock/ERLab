"""Provider-level retry with exponential backoff for 429/503 errors."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if exception is a 429 or 503 error."""
    exc_str = str(exc).lower()
    # Check for status_code attribute (common in SDK exceptions)
    status = getattr(exc, 'status_code', None)
    if status in (429, 503):
        return True
    # Check for HTTPStatusError or similar
    if hasattr(exc, 'response'):
        resp = getattr(exc, 'response', None)
        if resp is not None:
            code = getattr(resp, 'status_code', None)
            if code in (429, 503):
                return True
    # Fallback: check string
    if "429" in exc_str or "rate" in exc_str or "503" in exc_str or "overloaded" in exc_str:
        return True
    return False


async def retry_llm_call(
    coro_factory: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> tuple[Any, int]:
    """Execute an async LLM call with retry on 429/503.

    Args:
        coro_factory: A callable that returns the coroutine to await.
                     Must be a factory (callable) not a coroutine, so we can retry.
        max_retries: Maximum number of retries (0 = no retry).
        base_delay: Base delay in seconds for exponential backoff.

    Returns:
        Tuple of (result, retries_used).

    Raises:
        The original exception if all retries are exhausted.
    """
    retries_used = 0

    for attempt in range(max_retries + 1):
        try:
            result = await coro_factory()
            return result, retries_used
        except Exception as exc:
            if not _is_rate_limit_error(exc):
                raise  # Not a rate limit error — propagate immediately
            if attempt >= max_retries:
                raise  # Exhausted retries — propagate original exception
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "LLM rate limited (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1, max_retries + 1, delay, exc,
            )
            retries_used += 1
            await asyncio.sleep(delay)

    raise RuntimeError("Unreachable")  # type: ignore
