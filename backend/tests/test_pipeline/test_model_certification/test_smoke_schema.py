"""Phase C tests: Smoke Test + Schema Eval."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.model_certification.schema_eval import (
    run_schema_eval,
)
from backend.pipeline.model_certification.smoke_test import (
    run_smoke_test,
)


def _make_provider(response_text: str):
    """Create a mock provider that returns the given text."""
    provider = AsyncMock()
    resp = MagicMock()
    resp.text = response_text
    provider.complete = AsyncMock(return_value=resp)
    return provider


class TestSmokeTest:
    @pytest.mark.asyncio
    async def test_smoke_test_passes_on_valid_json_response(self):
        provider = _make_provider('{"status":"ok"}')
        result = await run_smoke_test(provider, "test-model")
        assert result.passed is True
        assert result.parsed_json == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_smoke_test_passes_with_markdown_fences(self):
        provider = _make_provider('```json\n{"status":"ok"}\n```')
        result = await run_smoke_test(provider, "test-model")
        assert result.passed is True
        assert result.parsed_json == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_smoke_test_fails_on_empty_response(self):
        provider = _make_provider("")
        result = await run_smoke_test(provider, "test-model")
        assert result.passed is False
        assert "Empty" in result.error

    @pytest.mark.asyncio
    async def test_smoke_test_fails_on_non_json_response(self):
        provider = _make_provider("I am doing well, thanks!")
        result = await run_smoke_test(provider, "test-model")
        assert result.passed is False
        assert "JSON parse error" in result.error

    @pytest.mark.asyncio
    async def test_smoke_test_fails_on_timeout(self):
        provider = AsyncMock()
        provider.complete = AsyncMock(side_effect=TimeoutError("timed out"))
        result = await run_smoke_test(provider, "test-model", timeout=5.0)
        assert result.passed is False
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_smoke_test_fails_on_missing_status_field(self):
        provider = _make_provider('{"hello":"world"}')
        result = await run_smoke_test(provider, "test-model")
        assert result.passed is False
        assert "Missing required field" in result.error


class TestSchemaEval:
    @pytest.mark.asyncio
    async def test_schema_eval_rates_valid_json_correctly(self, tmp_path):
        # Create a simple schema
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        (schema_dir / "test.schema.json").write_text(json.dumps({
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }))

        provider = _make_provider('{"name":"test"}')
        result = await run_schema_eval(
            provider, "test-model", schema_dir, cases_per_schema=3
        )
        assert result.total_cases == 3
        assert result.raw_json_valid_rate == 1.0
        assert result.schema_valid_rate == 1.0

    @pytest.mark.asyncio
    async def test_schema_eval_detects_markdown_contamination(self, tmp_path):
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        (schema_dir / "test.schema.json").write_text(json.dumps({
            "type": "object",
            "properties": {"x": {"type": "number"}},
            "required": ["x"],
        }))

        provider = _make_provider('```json\n{"x":1}\n```')
        result = await run_schema_eval(
            provider, "test-model", schema_dir, cases_per_schema=2
        )
        assert result.markdown_contamination_rate == 1.0
        assert result.recoverable_json_rate == 1.0
        assert result.repair_attempted_count == 2

    @pytest.mark.asyncio
    async def test_schema_eval_detects_truncation(self, tmp_path):
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        (schema_dir / "test.schema.json").write_text(json.dumps({
            "type": "object",
            "properties": {"x": {"type": "number"}},
            "required": ["x"],
        }))

        provider = _make_provider('{"x":')  # truncated JSON
        result = await run_schema_eval(
            provider, "test-model", schema_dir, cases_per_schema=2
        )
        assert result.raw_json_valid_rate == 0.0
        assert result.truncation_rate > 0

    @pytest.mark.asyncio
    async def test_schema_eval_tracks_per_schema_breakdown(self, tmp_path):
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        (schema_dir / "a.schema.json").write_text(json.dumps({
            "type": "object",
            "properties": {"v": {"type": "number"}},
            "required": ["v"],
        }))
        (schema_dir / "b.schema.json").write_text(json.dumps({
            "type": "object",
            "properties": {"w": {"type": "string"}},
            "required": ["w"],
        }))

        provider = _make_provider('{"v":42}')  # only matches schema a
        result = await run_schema_eval(
            provider, "test-model", schema_dir, cases_per_schema=2
        )
        assert "a" in result.per_schema
        assert "b" in result.per_schema
        assert result.per_schema["a"]["raw_json_valid_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_schema_eval_distinguishes_raw_vs_repair_assisted(self, tmp_path):
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        (schema_dir / "test.schema.json").write_text(json.dumps({
            "type": "object",
            "properties": {"v": {"type": "number"}},
            "required": ["v"],
        }))

        # Response has markdown fences but valid JSON inside
        provider = _make_provider('```json\n{"v":42}\n```')
        result = await run_schema_eval(
            provider, "test-model", schema_dir, cases_per_schema=3
        )
        # Raw valid should be 0 (starts with ```) but recoverable should be 1.0
        assert result.raw_json_valid_rate == 0.0
        assert result.recoverable_json_rate == 1.0
        assert result.repair_attempted_count == 3
        assert result.repair_success_rate == 1.0

    @pytest.mark.asyncio
    async def test_schema_eval_repair_adjusted_metrics(self, tmp_path):
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        (schema_dir / "test.schema.json").write_text(json.dumps({
            "type": "object",
            "properties": {"v": {"type": "number"}},
            "required": ["v"],
        }))

        # All responses have fences and valid JSON after stripping
        provider = _make_provider('```json\n{"v":1}\n```')
        result = await run_schema_eval(
            provider, "test-model", schema_dir, cases_per_schema=5
        )
        assert result.schema_valid_after_repair_rate == 1.0
        assert result.repair_success_rate == 1.0

    @pytest.mark.asyncio
    async def test_schema_eval_empty_directory(self, tmp_path):
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        provider = _make_provider("anything")
        result = await run_schema_eval(provider, "test-model", schema_dir)
        assert result.total_cases == 0
        assert result.raw_json_valid_rate == 0.0
