"""Error classification for resilience retry decisions.

Two-pass classification:
1. Exception type/category attribute (litellm, openai, anthropic exceptions)
2. HTTP status code fallback
"""

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

# Exception type/category → retry strategy (checked before status code)
_RETRYABLE_TYPES = frozenset({
    "rate_limit", "timeout", "server_error",
    "connection_error", "api_connection_error",
    "service_unavailable_error", "context_window_exceeded",
    "overloaded_error",
})
_NON_RETRYABLE_TYPES = frozenset({
    "auth_error", "invalid_request_error",
    "invalid_api_key", "model_not_found",
    "context_length_exceeded",
})


def _classify_by_type(exc: Exception) -> RetryDecision | None:
    """Classify using exception type/category attributes (litellm pattern)."""
    exc_type = getattr(exc, "type", None) or ""
    exc_category = getattr(exc, "category", None) or ""
    # litellm exceptions expose llm_provider attribute
    is_llm_exc = hasattr(exc, "llm_provider") or hasattr(exc, "model")

    if not exc_type and not exc_category:
        return None

    candidates = {exc_type.lower(), exc_category.lower()}
    if candidates & {"rate_limit", "ratelimiterror"}:
        return RetryDecision.COOLDOWN
    if candidates & _RETRYABLE_TYPES:
        return RetryDecision.RETRY
    if candidates & _NON_RETRYABLE_TYPES:
        return RetryDecision.NO_RETRY
    if is_llm_exc and candidates & {"authenticationerror", "permissiondeniederror"}:
        return RetryDecision.NO_RETRY
    return None


def classify_status(status_code: int) -> RetryDecision:
    if status_code in _COOLDOWN:
        return RetryDecision.COOLDOWN
    if status_code in _NO_RETRY:
        return RetryDecision.NO_RETRY
    if status_code in _RETRYABLE:
        return RetryDecision.RETRY
    return RetryDecision.NO_RETRY


def classify_exception(exc: Exception) -> RetryDecision:
    """Classify an exception into a retry decision.

    Two-pass: first by exception type/category, then by HTTP status code.
    """
    type_decision = _classify_by_type(exc)
    if type_decision is not None:
        return type_decision
    status = extract_status_code(exc)
    if status is not None:
        return classify_status(status)
    # Non-HTTP errors (connection, timeout) — retry with backoff
    return RetryDecision.RETRY


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
