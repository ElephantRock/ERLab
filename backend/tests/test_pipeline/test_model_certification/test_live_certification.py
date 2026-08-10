"""Phase F: Live integration tests for model certification.

These tests require LM Studio to be running at 100.64.0.1:1234.
They are skipped by default — use --live flag or set EROCK_LMSTUDIO_BASE_URL.
"""

import os
from pathlib import Path

import pytest

from backend.pipeline.model_certification.manifest import CandidateModelManifest
from backend.pipeline.model_certification.registries import ProductionModelRegistry
from backend.pipeline.model_certification.runner import CertificationRunner

# Skip all tests in this module unless LM Studio is available
pytestmark = pytest.mark.skipif(
    os.environ.get("EROCK_RUN_LIVE_TESTS") != "1",
    reason="Live tests require EROCK_RUN_LIVE_TESTS=1 and LM Studio at 100.64.0.1:1234",
)

_LMSTUDIO_URL = os.environ.get("EROCK_LMSTUDIO_BASE_URL", "http://100.64.0.1:1234/v1")


@pytest.fixture
def qwen_manifest():
    return CandidateModelManifest(
        model_id="qwen/qwen3-4b-2507",
        provider="lmstudio",
        source="local",
        model_family="qwen",
        parameter_count="4b",
        advertised_context_window=8192,
        advertised_max_output_tokens=4096,
        supports_json_mode=False,
        supports_tool_calling=False,
        supports_streaming=True,
    )


@pytest.fixture
def provider():
    from backend.providers.openai_provider import OpenAIProvider
    return OpenAIProvider(
        base_url=_LMSTUDIO_URL,
        model="qwen/qwen3-4b-2507",
        api_key="lm-studio",
        max_tokens=4096,
    )


@pytest.mark.live
@pytest.mark.requires_lmstudio
@pytest.mark.asyncio
async def test_live_certification_qwen3_4b(qwen_manifest, provider, tmp_path):
    """Full live certification of qwen3-4b-2507 against LM Studio."""
    schema_dir = Path(__file__).parent.parent.parent / "pipeline" / "model_certification" / "config" / "schemas"
    reports_dir = tmp_path / "reports"

    runner = CertificationRunner(
        provider=provider,
        schema_dir=schema_dir,
        reports_dir=reports_dir,
        lmstudio_base_url=_LMSTUDIO_URL.replace("/v1", ""),
    )

    report = await runner.certify(qwen_manifest, cases_per_schema=3)

    # Basic assertions
    assert report.model_id == "qwen/qwen3-4b-2507"
    assert report.status in (
        "approved_for_production",
        "approved_for_limited_use",
        "approved_for_repair_only",
        "requires_manual_review",
    )
    assert report.safe_context_window > 0
    assert report.smoke_test is not None
    assert report.smoke_test.get("passed") is True, f"Smoke test failed: {report.smoke_test}"
    assert report.schema_eval is not None

    # Report file written
    report_files = list((reports_dir / "qwen/qwen3-4b-2507").glob("*.yaml"))
    assert len(report_files) >= 1

    print("\nLive certification result:")
    print(f"  Status: {report.status}")
    print(f"  Safe context: {report.safe_context_window}")
    print(f"  Schema valid rate: {report.schema_eval.get('schema_valid_rate', 'N/A')}")
    print(f"  Raw JSON rate: {report.schema_eval.get('raw_json_valid_rate', 'N/A')}")
    print(f"  Promotion allowed: {report.promotion_allowed}")


@pytest.mark.live
@pytest.mark.requires_lmstudio
@pytest.mark.asyncio
async def test_production_registry_unchanged_after_non_auto_promote(
    qwen_manifest, provider, tmp_path,
):
    """Verify production registry is NOT modified when auto_promote=false."""
    schema_dir = Path(__file__).parent.parent.parent / "pipeline" / "model_certification" / "config" / "schemas"
    reports_dir = tmp_path / "reports"
    prod_path = tmp_path / "prod.yaml"
    prod_registry = ProductionModelRegistry(path=prod_path)

    runner = CertificationRunner(
        provider=provider,
        schema_dir=schema_dir,
        reports_dir=reports_dir,
        production_registry=prod_registry,
        lmstudio_base_url=_LMSTUDIO_URL.replace("/v1", ""),
    )

    report = await runner.certify(qwen_manifest, auto_promote=False)

    # Production registry should be empty
    assert len(prod_registry.list_models()) == 0
