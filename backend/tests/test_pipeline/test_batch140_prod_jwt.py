"""BATCH-140/TASK-02: Production JWT enforcement tests.

Tests:
  TEST-140-02-01: Production + default JWT raises error
  TEST-140-02-02: Production + custom JWT starts fine
  TEST-140-02-03: Development + default JWT only warns
"""

from unittest.mock import patch

import pytest

from backend.config import Settings


class TestBatch140ProdJwt:
    """BATCH-140/TASK-02: Production JWT enforcement."""

    @pytest.fixture(autouse=True)
    def _reset_limiter(self):
        """Reset module-level limiter between tests."""
        import backend.api.app as app_mod

        app_mod._limiter = None
        yield
        app_mod._limiter = None

    def _run_startup(self, settings: Settings):
        """Run startup() with all side-effecting imports patched out."""
        with (
            patch("backend.db.database.init_db"),
            patch("backend.config.get_settings", return_value=settings),
            patch("backend.logging_config.configure_logging"),
            patch("backend.monitoring.sentry.init_sentry"),
            patch("backend.api.app._get_limiter"),
        ):
            import asyncio

            from backend.api.app import startup

            asyncio.get_event_loop().run_until_complete(startup())

    def test_production_default_jwt_raises(self):
        """TEST-140-02-01: Production + default JWT raises RuntimeError."""
        settings = Settings(
            _env_file=None,
            env="production",
            jwt_secret="dev-secret-change-in-production",
        )
        with pytest.raises(RuntimeError, match="Insecure JWT secret"):
            self._run_startup(settings)

    def test_production_custom_jwt_starts(self):
        """TEST-140-02-02: Production + custom JWT starts without error."""
        settings = Settings(
            _env_file=None,
            env="production",
            jwt_secret="a-real-secret-not-default",
        )
        self._run_startup(settings)  # should not raise

    def test_development_default_jwt_warns(self):
        """TEST-140-02-03: Development + default JWT warns but does not raise."""
        settings = Settings(
            _env_file=None,
            env="development",
            auth_enabled=True,
            jwt_secret="dev-secret-change-in-production",
        )
        self._run_startup(settings)  # should not raise
