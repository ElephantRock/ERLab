"""Phase E tests: Runner + CLI."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipeline.model_certification.manifest import CandidateModelManifest
from backend.pipeline.model_certification.registries import ProductionModelRegistry
from backend.pipeline.model_certification.runner import CertificationRunner


def _make_manifest(**overrides) -> CandidateModelManifest:
    defaults = dict(
        model_id="test-model",
        provider="lmstudio",
        source="local",
        model_family="qwen",
        advertised_context_window=8192,
        advertised_max_output_tokens=4096,
    )
    defaults.update(overrides)
    return CandidateModelManifest(**defaults)


def _make_passing_provider():
    """Provider that returns valid JSON for all prompts."""
    provider = AsyncMock()
    resp = MagicMock()
    resp.text = '{"status":"ok"}'
    provider.complete = AsyncMock(return_value=resp)
    return provider


def _make_failing_provider():
    """Provider that returns garbage."""
    provider = AsyncMock()
    resp = MagicMock()
    resp.text = "I cannot do that"
    provider.complete = AsyncMock(return_value=resp)
    return provider


def _make_schema_dir(tmp_path) -> Path:
    """Create a temporary schema directory with one simple schema."""
    d = tmp_path / "schemas"
    d.mkdir()
    (d / "test.schema.json").write_text(json.dumps({
        "type": "object",
        "properties": {"status": {"type": "string"}},
        "required": ["status"],
    }))
    return d


class TestRunner:
    @pytest.mark.asyncio
    async def test_runner_certify_full_pass(self, tmp_path):
        schema_dir = _make_schema_dir(tmp_path)
        reports_dir = tmp_path / "reports"
        provider = _make_passing_provider()

        async def fake_probe(*args, **kwargs):
            from backend.pipeline.model_certification.hardware_probe import HardwareFitResult
            return HardwareFitResult(
                hardware_id="test-model",
                engine="lmstudio",
                load_success=True,
                model_loaded=True,
                context_window_reported=8192,
                safe_context_window=6553,
                safe_output_tokens=1638,
                stable=True,
            )

        with patch("backend.pipeline.model_certification.runner.probe_model", side_effect=fake_probe):
            runner = CertificationRunner(
                provider=provider,
                schema_dir=schema_dir,
                reports_dir=reports_dir,
            )
            manifest = _make_manifest()
            report = await runner.certify(manifest, cases_per_schema=2)

        assert report.model_id == "test-model"
        assert report.status in ("approved_for_production", "approved_for_limited_use")
        assert report.safe_context_window > 0
        assert report.promotion_allowed is True
        # Report file should exist
        assert (reports_dir / "test-model").exists()

    @pytest.mark.asyncio
    async def test_runner_certify_smoke_failure_stops_early(self, tmp_path):
        schema_dir = _make_schema_dir(tmp_path)
        reports_dir = tmp_path / "reports"
        provider = _make_failing_provider()

        async def fake_probe(*args, **kwargs):
            from backend.pipeline.model_certification.hardware_probe import HardwareFitResult
            return HardwareFitResult(
                hardware_id="test-model",
                engine="lmstudio",
                load_success=True,
                model_loaded=True,
                context_window_reported=8192,
                stable=True,
            )

        with patch("backend.pipeline.model_certification.runner.probe_model", side_effect=fake_probe):
            runner = CertificationRunner(
                provider=provider,
                schema_dir=schema_dir,
                reports_dir=reports_dir,
            )
            manifest = _make_manifest()
            report = await runner.certify(manifest)

        assert report.status == "rejected"
        assert report.known_failure_modes
        # Schema eval should NOT have run
        assert report.schema_eval is None

    @pytest.mark.asyncio
    async def test_runner_writes_report_even_when_rejected(self, tmp_path):
        schema_dir = _make_schema_dir(tmp_path)
        reports_dir = tmp_path / "reports"
        provider = _make_failing_provider()

        async def fake_probe(*args, **kwargs):
            from backend.pipeline.model_certification.hardware_probe import HardwareFitResult
            return HardwareFitResult(
                hardware_id="test-model",
                engine="lmstudio",
                load_success=True,
                model_loaded=True,
                context_window_reported=8192,
                stable=True,
            )

        with patch("backend.pipeline.model_certification.runner.probe_model", side_effect=fake_probe):
            runner = CertificationRunner(
                provider=provider,
                schema_dir=schema_dir,
                reports_dir=reports_dir,
            )
            report = await runner.certify(_make_manifest())

        # Report was written
        report_files = list((reports_dir / "test-model").glob("*.yaml"))
        assert len(report_files) == 1
        content = report_files[0].read_text()
        assert "rejected" in content

    @pytest.mark.asyncio
    async def test_runner_auto_promote_only_when_promotion_allowed(self, tmp_path):
        schema_dir = _make_schema_dir(tmp_path)
        reports_dir = tmp_path / "reports"
        prod_path = tmp_path / "prod.yaml"
        prod_registry = ProductionModelRegistry(path=prod_path)
        provider = _make_passing_provider()

        async def fake_probe(*args, **kwargs):
            from backend.pipeline.model_certification.hardware_probe import HardwareFitResult
            return HardwareFitResult(
                hardware_id="test-model",
                engine="lmstudio",
                load_success=True,
                model_loaded=True,
                context_window_reported=8192,
                safe_context_window=6553,
                safe_output_tokens=1638,
                stable=True,
            )

        with patch("backend.pipeline.model_certification.runner.probe_model", side_effect=fake_probe):
            runner = CertificationRunner(
                provider=provider,
                schema_dir=schema_dir,
                reports_dir=reports_dir,
                production_registry=prod_registry,
            )
            report = await runner.certify(
                _make_manifest(),
                auto_promote=True,
            )

        # Should have been promoted (passing provider → approved)
        entry = prod_registry.get("test-model")
        assert entry is not None

    @pytest.mark.asyncio
    async def test_runner_rejects_invalid_manifest(self, tmp_path):
        reports_dir = tmp_path / "reports"
        provider = _make_passing_provider()

        runner = CertificationRunner(
            provider=provider,
            reports_dir=reports_dir,
        )
        manifest = _make_manifest(model_id="")  # invalid
        report = await runner.certify(manifest)

        assert report.status == "rejected"
        assert any("Invalid manifest" in m for m in report.known_failure_modes)

    def test_cli_certify_produces_summary(self, tmp_path):
        """Test CLI summary output (synchronous — just tests import)."""
        from backend.pipeline.model_certification import cli
        assert hasattr(cli, "main")
        assert hasattr(cli, "_certify")
