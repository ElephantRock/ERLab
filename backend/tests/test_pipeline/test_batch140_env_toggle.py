"""BATCH-140/TASK-01: EROCK_ENV toggle and CORS hardening tests.

Tests:
  TEST-140-01-01: Default env is "development"
  TEST-140-01-02: is_production is False by default
  TEST-140-01-03: effective_cors_origins returns ["*"] in dev mode
  TEST-140-01-04: effective_cors_origins returns [] in prod with default cors
  TEST-140-01-05: effective_cors_origins returns configured value in prod
  TEST-140-01-06: effective_debug returns False in production
  TEST-140-01-07: effective_debug returns settings.debug in development
"""

from backend.config import Settings


class TestBatch140EnvToggle:
    """BATCH-140/TASK-01: EROCK_ENV toggle and CORS hardening."""

    def test_default_env_is_development(self):
        """TEST-140-01-01: Default env is 'development'."""
        s = Settings(_env_file=None)
        assert s.env == "development"

    def test_is_production_false_by_default(self):
        """TEST-140-01-02: is_production is False by default."""
        s = Settings(_env_file=None)
        assert s.is_production is False

    def test_effective_cors_dev_returns_wildcard(self):
        """TEST-140-01-03: effective_cors_origins returns ["*"] in dev mode."""
        s = Settings(_env_file=None)
        assert s.effective_cors_origins == ["*"]

    def test_effective_cors_prod_with_default_is_empty(self):
        """TEST-140-01-04: effective_cors_origins returns [] in production when cors_origins=["*"]."""
        s = Settings(_env_file=None, env="production", cors_origins=["*"])
        assert s.effective_cors_origins == []

    def test_effective_cors_prod_with_explicit_origins(self):
        """TEST-140-01-05: effective_cors_origins returns configured value in production."""
        s = Settings(
            _env_file=None,
            env="production",
            cors_origins=["https://example.com"],
        )
        assert s.effective_cors_origins == ["https://example.com"]

    def test_effective_debug_forced_off_in_production(self):
        """TEST-140-01-06: effective_debug returns False in production regardless of debug."""
        s = Settings(_env_file=None, env="production", debug=True)
        assert s.effective_debug is False

    def test_effective_debug_respects_setting_in_dev(self):
        """TEST-140-01-07: effective_debug returns settings.debug in development."""
        s = Settings(_env_file=None, env="development", debug=True)
        assert s.effective_debug is True
