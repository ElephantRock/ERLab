"""Tests for BATCH-189: Effort Probing for Model Selection.

AIV §13: Tests verify behavior (effort level resolved correctly)."""

import asyncio

from backend.pipeline.monitoring.effort_probe import (
    get_effective_effort,
    probe_effort,
)


class TestProbeEffort:
    """probe_effort resolves effort levels correctly."""

    def test_01_local_model_no_thinking(self):
        """Local qwen model has no extended thinking."""
        async def _run():
            result = await probe_effort("qwen/qwen3-4b-2507", "high")
            assert result.effective_effort is None
            assert result.model_id == "qwen/qwen3-4b-2507"
        asyncio.run(_run())

    def test_02_cloud_model_supports_high(self):
        """glm-5.1 supports high effort."""
        async def _run():
            result = await probe_effort("glm-5.1", "high")
            assert result.effective_effort == "high"
        asyncio.run(_run())

    def test_03_effort_cascade(self):
        """If preferred effort not supported, falls back to highest supported."""
        async def _run():
            # glm-5.1 doesn't support "max"
            result = await probe_effort("glm-5.1", "max")
            assert result.effective_effort == "high"  # highest supported
            assert "fell back" in result.note
        asyncio.run(_run())

    def test_04_effort_off(self):
        """effort=None means thinking off."""
        async def _run():
            result = await probe_effort("glm-5.1", None)
            assert result.effective_effort is None
            assert "off" in result.note.lower()
        asyncio.run(_run())

    def test_05_unknown_model_no_thinking(self):
        """Unknown models default to no thinking."""
        async def _run():
            result = await probe_effort("unknown-model-v99", "high")
            assert result.effective_effort is None
        asyncio.run(_run())

    def test_06_result_has_timing(self):
        """Result includes elapsed_ms."""
        async def _run():
            result = await probe_effort("qwen/qwen3-4b-2507", "low")
            assert result.elapsed_ms >= 0
        asyncio.run(_run())


class TestGetEffectiveEffort:
    """Synchronous helper resolves effort correctly."""

    def test_07_local_model_none(self):
        assert get_effective_effort("qwen/qwen3-4b-2507", "high") is None

    def test_08_cloud_model_match(self):
        assert get_effective_effort("glm-5.1", "high") == "high"

    def test_09_off_returns_none(self):
        assert get_effective_effort("glm-5.1", None) is None

    def test_10_unknown_returns_none(self):
        assert get_effective_effort("nonexistent", "high") is None
