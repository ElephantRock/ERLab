"""Tests for BATCH-52 TASK-02: Sentry error monitoring integration."""

import importlib
import sys
from unittest.mock import patch

import pytest


def test_sentry_init_returns_false_when_dsn_empty():
    """Sentry init returns False when DSN is empty string."""
    from backend.monitoring.sentry import init_sentry

    # Reset module state
    import backend.monitoring.sentry as sentry_mod
    sentry_mod._initialized = False

    result = init_sentry(dsn="")
    assert result is False
    assert sentry_mod._initialized is False


def test_sentry_init_returns_false_when_sentry_sdk_not_importable():
    """Sentry init returns False when sentry-sdk cannot be imported."""
    from backend.monitoring.sentry import init_sentry

    # Reset module state
    import backend.monitoring.sentry as sentry_mod
    sentry_mod._initialized = False

    with patch.dict(sys.modules, {"sentry_sdk": None, "sentry_sdk.integrations.fastapi": None}):
        # Force re-import to trigger ImportError path
        result = init_sentry(dsn="https://example@sentry.io/123", environment="test")
        assert result is False


def test_sentry_is_initialized_reflects_state():
    """is_sentry_initialized() reflects initialization state."""
    from backend.monitoring import sentry as sentry_mod

    # Reset
    sentry_mod._initialized = False
    assert sentry_mod.is_sentry_initialized() is False

    # Simulate initialized
    sentry_mod._initialized = True
    assert sentry_mod.is_sentry_initialized() is True

    # Clean up
    sentry_mod._initialized = False
