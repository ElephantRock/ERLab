"""BATCH-138 / TASK-02 — Verify externalized compaction fallback model.

Tests:
  TEST-138-02-01: config has compaction_fallback_model field with correct default
  TEST-138-02-02: window manager reads fallback from settings
"""

from unittest.mock import MagicMock, patch

from backend.config import Settings


class TestCompactionFallbackModel:
    """TEST-138-02-01 — config has compaction_fallback_model field."""

    def test_default_value(self) -> None:
        s = Settings()
        assert s.compaction_fallback_model == "gpt-4o"

    def test_override(self) -> None:
        s = Settings(compaction_fallback_model="gpt-4o-mini")
        assert s.compaction_fallback_model == "gpt-4o-mini"


class TestWindowManagerFallback:
    """TEST-138-02-02 — window manager reads fallback from settings."""

    def test_fallback_function_reads_settings(self) -> None:
        from backend.pipeline.compaction.window_manager import _get_fallback_model

        # Default
        assert _get_fallback_model() == "gpt-4o"

    def test_fallback_function_respects_settings_override(self) -> None:
        from backend.pipeline.compaction.window_manager import _get_fallback_model

        with patch("backend.config.get_settings") as mock_gs:
            mock_gs.return_value.compaction_fallback_model = "claude-3.5-sonnet"
            assert _get_fallback_model() == "claude-3.5-sonnet"

    def test_window_manager_uses_fallback_when_no_model(self) -> None:
        """WindowManager.check_and_compress uses _get_fallback_model when
        neither model_name nor provider.default_model is set."""
        from backend.pipeline.compaction.window_manager import ContextWindowManager

        provider = MagicMock(spec=[])
        # provider has no default_model attribute
        mgr = ContextWindowManager(provider=provider, trigger_fraction=0.85)

        messages = [{"role": "user", "content": "short"}]
        # Should not raise — uses fallback model from settings
        result = mgr.check_and_compress(messages)
        assert isinstance(result, list)

    def test_window_manager_uses_fallback_in_usage_report(self) -> None:
        """WindowManager.get_usage_report uses _get_fallback_model."""
        from backend.pipeline.compaction.window_manager import ContextWindowManager

        provider = MagicMock(spec=[])
        mgr = ContextWindowManager(provider=provider)

        messages = [{"role": "user", "content": "hello world"}]
        report = mgr.get_usage_report(messages)
        assert "current_tokens" in report
        assert "context_size" in report
