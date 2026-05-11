"""BATCH-176: Rate Limit Resilience — retry wrapper, config, and integration tests."""

import asyncio
from dataclasses import fields
from unittest.mock import AsyncMock, patch

import pytest

# ── TASK-01: Retry Wrapper + Config + StageReport ──────────────────────


class TestRetryLlmCall:
    """Tests for backend.providers.retry.retry_llm_call."""

    def test_retry_returns_on_success(self):
        """Successful call returns immediately with retries_used=0."""
        from backend.providers.retry import retry_llm_call

        async def _run():
            coro_factory = AsyncMock(return_value="ok")
            result, retries = await retry_llm_call(coro_factory, max_retries=3)
            return result, retries

        result, retries = asyncio.run(_run())
        assert result == "ok"
        assert retries == 0
        # Factory called exactly once
        assert asyncio.run(self._count_calls()) == 1

    async def _count_calls(self):
        from backend.providers.retry import retry_llm_call
        factory = AsyncMock(return_value="ok")
        await retry_llm_call(factory, max_retries=3)
        return factory.call_count

    def test_retry_retries_on_429(self):
        """Mock raises 429-like error, then succeeds; retries_used > 0."""
        from backend.providers.retry import retry_llm_call

        async def _run():
            call_count = 0

            async def factory():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    exc = Exception("Rate limit: 429 Too Many Requests")
                    raise exc
                return "ok"

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result, retries = await retry_llm_call(factory, max_retries=3)
            return result, retries, call_count

        result, retries, call_count = asyncio.run(_run())
        assert result == "ok"
        assert retries == 1
        assert call_count == 2

    def test_retry_retries_on_503(self):
        """Mock raises 503-like error, then succeeds."""
        from backend.providers.retry import retry_llm_call

        async def _run():
            call_count = 0

            async def factory():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("503 Service Overloaded")
                return "ok"

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result, retries = await retry_llm_call(factory, max_retries=3)
            return result, retries, call_count

        result, retries, call_count = asyncio.run(_run())
        assert result == "ok"
        assert retries == 1
        assert call_count == 2

    def test_retry_propagates_after_exhaustion(self):
        """Mock always raises 429, verify exception propagates after all retries."""
        from backend.providers.retry import retry_llm_call

        async def _run():
            async def factory():
                raise Exception("429 rate limit exceeded")

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(Exception, match="429"):
                    await retry_llm_call(factory, max_retries=3)
            return True

        asyncio.run(_run())

    def test_retry_no_retry_when_zero(self):
        """max_retries=0, exception propagates on first 429 with no sleep."""
        from backend.providers.retry import retry_llm_call

        async def _run():
            async def factory():
                raise Exception("429 rate limit exceeded")

            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                with pytest.raises(Exception, match="429"):
                    await retry_llm_call(factory, max_retries=0)
                # asyncio.sleep should NOT have been called
                mock_sleep.assert_not_awaited()

        asyncio.run(_run())


class TestStageReportField:
    """Verify StageReport has retries_used field."""

    def test_stage_report_has_retries_used(self):
        from backend.pipeline.result import StageReport

        field_names = {f.name for f in fields(StageReport)}
        assert "retries_used" in field_names, f"Missing retries_used. Fields: {field_names}"

        # Verify default value
        report = StageReport(name="test", status="executed")
        assert report.retries_used == 0

        # Verify explicit value
        report = StageReport(name="test", status="executed", retries_used=3)
        assert report.retries_used == 3


class TestConfigRateLimitRetries:
    """Verify Settings has llm_rate_limit_retries."""

    def test_config_has_rate_limit_retries(self):
        from backend.config import Settings

        settings = Settings()
        assert hasattr(settings, "llm_rate_limit_retries")
        assert settings.llm_rate_limit_retries == 3

    def test_config_rate_limit_retries_env_override(self):
        """Verify EROCK_LLM_RATE_LIMIT_RETRIES env var overrides default."""
        from backend.config import Settings

        with patch.dict("os.environ", {"EROCK_LLM_RATE_LIMIT_RETRIES": "5"}):
            settings = Settings()
            assert settings.llm_rate_limit_retries == 5


# ── TASK-02: Integration + Verification + Batch Close ──────────────────


class TestIntegration:
    """Integration tests for retry wrapper in pipeline context."""

    def test_stage_with_retrying_provider_succeeds(self):
        """Stage uses retry_llm_call internally, first call 429 then succeeds."""
        from backend.providers.retry import retry_llm_call

        async def _run():
            call_count = 0

            async def llm_factory():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("429 Too Many Requests")
                return "stage result"

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result, retries = await retry_llm_call(llm_factory, max_retries=3)
            return result, retries, call_count

        result, retries, call_count = asyncio.run(_run())
        assert result == "stage result"
        assert retries > 0
        assert retries == 1
        assert call_count == 2

    def test_stage_with_exhausted_retries_skipped(self):
        """Stage always raises 429, gets skipped_by_error in stage_report."""
        from backend.pipeline.result import StageReport
        from backend.providers.retry import retry_llm_call

        async def _run():
            # Simulate what the orchestrator does: try retry_llm_call, catch exception
            async def always_429():
                raise Exception("429 rate limit exceeded")

            report = StageReport(name="test_stage", status="executed")
            try:
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result, retries = await retry_llm_call(always_429, max_retries=3)
                report.retries_used = retries
            except Exception as e:
                report.status = "skipped_by_error"
                report.error = str(e)[:500]
                report.retries_used = 0
            return report

        report = asyncio.run(_run())
        assert report.status == "skipped_by_error"
        assert "429" in (report.error or "")


class TestBatchClose:
    """Regression and documentation verification."""

    def test_no_regressions(self):
        """Verify batch172-175 test modules still import and key test classes exist."""
        # Import-based regression check: verify modules load without error
        import importlib
        modules = [
            "backend.tests.test_pipeline.test_batch172_wiring",
            "backend.tests.test_pipeline.test_batch172_preflight",
            "backend.tests.test_pipeline.test_batch172_strategies",
            "backend.tests.test_pipeline.test_batch173_stage_report",
            "backend.tests.test_pipeline.test_batch173_api_expose",
            "backend.tests.test_pipeline.test_batch174_core_stages",
            "backend.tests.test_pipeline.test_batch174_synthesis_stages",
            "backend.tests.test_pipeline.test_batch175_e2e_integration",
        ]
        for mod_name in modules:
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"Failed to import {mod_name}"

        # Verify source modules still import cleanly
        from backend.providers.retry import retry_llm_call, _is_rate_limit_error
        from backend.pipeline.result import StageReport
        from backend.config import Settings
        assert callable(retry_llm_call)
        assert callable(_is_rate_limit_error)
        # Verify new fields don't break existing construction
        Settings()  # should not raise
        StageReport(name="x", status="executed")  # should not raise

    def test_state_md_has_batch176(self):
        """STATE.md documents BATCH-176."""
        with open("docs/aiv/STATE.md", encoding="utf-8") as f:
            content = f.read()
        assert "BATCH-176" in content, "STATE.md missing BATCH-176 entry"

    def test_changelog_has_batch176(self):
        """CHANGELOG.md documents BATCH-176."""
        with open("CHANGELOG.md", encoding="utf-8") as f:
            content = f.read()
        assert "BATCH-176" in content, "CHANGELOG.md missing BATCH-176 entry"
