"""Sentry SDK integration for error monitoring (BATCH-52).

Initializes Sentry only when a DSN is configured.
When EROCK_SENTRY_DSN is empty (default), Sentry is completely disabled.
"""
import logging

logger = logging.getLogger(__name__)

_initialized = False


def init_sentry(dsn: str, environment: str = "production", traces_sample_rate: float = 0.1) -> bool:
    """Initialize Sentry SDK. Returns True if initialized, False if skipped."""
    global _initialized
    if not dsn:
        logger.info("Sentry DSN not configured — error monitoring disabled")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            integrations=[FastApiIntegration()],
            traces_sample_rate=traces_sample_rate,
        )
        _initialized = True
        logger.info("Sentry initialized (environment=%s)", environment)
        return True
    except ImportError:
        logger.warning("sentry-sdk not installed — error monitoring disabled")
        return False


def is_sentry_initialized() -> bool:
    return _initialized
