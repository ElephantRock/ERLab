"""BATCH-137 / TASK-02 — Startup security warnings.

Tests:
  TEST-137-02-01  Startup warns when JWT secret is default AND auth_enabled=True
  TEST-137-02-02  Startup does NOT warn when JWT secret is custom AND auth_enabled=True
  TEST-137-02-03  Startup warns when no LLM API key configured and lmstudio_enabled=False
  TEST-137-02-04  Startup does NOT warn when LM Studio enabled and no cloud key
"""

import asyncio
import logging
import logging.handlers
from unittest.mock import MagicMock, patch

import pytest


def _make_settings(**overrides):
    """Build a lightweight settings-like mock with sensible defaults."""
    defaults = dict(
        debug=False,
        auth_enabled=False,
        jwt_secret="dev-secret-change-in-production",
        openai_api_key=None,
        anthropic_api_key=None,
        gemini_api_key=None,
        lmstudio_enabled=False,
        semantic_scholar_api_key=None,
        sentry_dsn="",
        sentry_environment="test",
        sentry_traces_sample_rate=0.0,
        rate_limit_enabled=False,
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


def _run_startup(settings_mock):
    """Run startup() with all external dependencies patched out."""
    from backend.api.app import startup
    import backend.api.app as app_mod

    with (
        patch("backend.config.get_settings", return_value=settings_mock),
        patch("backend.db.database.init_db"),
        patch("backend.logging_config.configure_logging"),
        patch("backend.monitoring.sentry.init_sentry"),
        patch.object(app_mod, "_get_limiter", return_value=None),
    ):
        asyncio.get_event_loop().run_until_complete(startup())


def _capture_warnings():
    """Context manager that captures log warnings from backend.api.app logger."""
    handler = logging.handlers.MemoryHandler(capacity=200)
    handler.setLevel(logging.WARNING)
    logger = logging.getLogger("backend.api.app")
    logger.addHandler(handler)
    original_level = logger.level
    logger.setLevel(logging.WARNING)
    return handler, logger, original_level


class TestJwtDefaultSecretWarning:
    """TEST-137-02-01: Startup warns when JWT secret is default AND auth_enabled=True."""

    def test_warns_on_default_jwt_with_auth_enabled(self) -> None:
        handler, logger, original_level = _capture_warnings()
        try:
            settings = _make_settings(
                auth_enabled=True,
                jwt_secret="dev-secret-change-in-production",
            )
            _run_startup(settings)
            msgs = [r.getMessage() for r in handler.buffer]
            jwt_msgs = [m for m in msgs if "JWT secret" in m]
            assert len(jwt_msgs) >= 1, (
                f"Expected a warning about JWT secret, but got: {msgs}"
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)


class TestJwtCustomSecretNoWarning:
    """TEST-137-02-02: Startup does NOT warn when JWT secret is custom AND auth_enabled=True."""

    def test_no_warn_on_custom_jwt(self) -> None:
        handler, logger, original_level = _capture_warnings()
        try:
            settings = _make_settings(
                auth_enabled=True,
                jwt_secret="a-real-production-secret-32chars!!",
                openai_api_key="sk-test",
            )
            _run_startup(settings)
            msgs = [r.getMessage() for r in handler.buffer]
            jwt_msgs = [m for m in msgs if "JWT secret" in m]
            assert len(jwt_msgs) == 0, (
                f"Expected no JWT secret warning, but got: {jwt_msgs}"
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)


class TestNoApiKeyWarning:
    """TEST-137-02-03: Startup warns when no LLM API key configured and lmstudio_enabled=False."""

    def test_warns_no_api_key_no_lmstudio(self) -> None:
        handler, logger, original_level = _capture_warnings()
        try:
            settings = _make_settings(
                auth_enabled=False,
                lmstudio_enabled=False,
                openai_api_key=None,
                anthropic_api_key=None,
                gemini_api_key=None,
            )
            _run_startup(settings)
            msgs = [r.getMessage() for r in handler.buffer]
            api_msgs = [m for m in msgs if "No LLM API key" in m]
            assert len(api_msgs) >= 1, (
                f"Expected a warning about no LLM API key, but got: {msgs}"
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)


class TestLmstudioEnabledNoWarning:
    """TEST-137-02-04: Startup does NOT warn when LM Studio enabled and no cloud key."""

    def test_no_warn_lmstudio_enabled(self) -> None:
        handler, logger, original_level = _capture_warnings()
        try:
            settings = _make_settings(
                auth_enabled=False,
                lmstudio_enabled=True,
                openai_api_key=None,
                anthropic_api_key=None,
                gemini_api_key=None,
            )
            _run_startup(settings)
            msgs = [r.getMessage() for r in handler.buffer]
            api_msgs = [m for m in msgs if "No LLM API key" in m]
            assert len(api_msgs) == 0, (
                f"Expected no 'No LLM API key' warning when LM Studio enabled, but got: {api_msgs}"
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)
