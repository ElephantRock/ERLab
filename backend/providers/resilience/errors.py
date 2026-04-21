"""Error classification for resilience retry decisions."""

from __future__ import annotations

from enum import Enum


class RetryDecision(Enum):
    RETRY = "retry"
    COOLDOWN = "cooldown"
    NO_RETRY = "no_retry"
    CIRCUIT_OPEN = "circuit_open"


class ResilienceError(Exception):
    """Base for all resilience-layer errors."""


class CircuitOpenError(ResilienceError):
    """Provider circuit is open — fast-fail."""


class AllKeysUnhealthyError(ResilienceError):
    """All keys in the vault are marked unhealthy."""


# Status code → retry strategy mapping
_RETRYABLE = {408, 500, 502, 503, 504}
_COOLDOWN = {429}
_NO_RETRY = {401, 403}


def classify_status(status_code: int) -> RetryDecision:
    if status_code in _COOLDOWN:
        return RetryDecision.COOLDOWN
    if status_code in _NO_RETRY:
        return RetryDecision.NO_RETRY
    if status_code in _RETRYABLE:
        return RetryDecision.RETRY
    return RetryDecision.NO_RETRY


def extract_status_code(exc: Exception) -> int | None:
    """Try to extract an HTTP status code from common exception types."""
    # httpx.HTTPStatusError
    if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
        return exc.response.status_code
    # openai.APIStatusError / anthropic.APIStatusError
    if hasattr(exc, "status_code"):
        return exc.status_code
    # google.api_core.exceptions
    if hasattr(exc, "code") and isinstance(exc.code, int):
        return exc.code
    return None
