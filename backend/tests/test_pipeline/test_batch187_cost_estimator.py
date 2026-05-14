"""Tests for BATCH-187: Pre-Flight Cost & Time Estimation.

AIV §13 Test Integrity: Tests verify behavioral outcomes
(correct cost calculations, time estimates), not structure.
"""

import pytest

from backend.pipeline.monitoring.cost_estimator import (
    CostEstimate,
    estimate_run_cost,
    get_model_pricing,
    STRATEGY_STAGES,
)


class TestGetModelPricing:
    """get_model_pricing returns correct pricing."""

    def test_01_local_model_free(self):
        pricing = get_model_pricing("qwen/qwen3-4b-2507")
        assert pricing["input"] == 0.0
        assert pricing["output"] == 0.0
        assert "local" in pricing["label"]

    def test_02_cloud_model_priced(self):
        pricing = get_model_pricing("glm-5.1")
        assert pricing["input"] > 0.0
        assert pricing["output"] > 0.0

    def test_03_unknown_model_defaults_free(self):
        pricing = get_model_pricing("nonexistent-model-v99")
        assert pricing["input"] == 0.0
        assert pricing["output"] == 0.0

    def test_04_embedding_model_free(self):
        pricing = get_model_pricing("text-embedding-bge-m3")
        assert pricing["input"] == 0.0


class TestEstimateRunCost:
    """estimate_run_cost produces valid estimates."""

    def test_05_fast_scan_all_local_free(self):
        """fast_scan with default local models costs $0."""
        est = estimate_run_cost("fast_scan")
        assert isinstance(est, CostEstimate)
        assert est.stages == 7  # fast_scan has 7 stages
        assert est.local_cost_usd == 0.0
        assert est.estimated_time_seconds > 0

    def test_06_deep_research_has_cloud_cost(self):
        """deep_research uses cloud for generation stages."""
        est = estimate_run_cost("deep_research")
        assert est.stages == 17  # deep_research has 17 stages
        assert est.cloud_cost_usd > 0.0  # generation stages use cloud
        assert est.estimated_time_seconds > est_fast_scan_time()

    def test_07_all_strategies_valid(self):
        """All 4 strategies produce valid estimates."""
        for strategy in ["fast_scan", "deep_research", "academic_proposal", "literature_review"]:
            est = estimate_run_cost(strategy)
            assert est.stages > 0
            assert est.estimated_cost_usd >= 0.0
            assert est.estimated_time_seconds > 0
            assert len(est.breakdown) == est.stages

    def test_08_model_overrides(self):
        """Custom model overrides affect cost."""
        # All-local override
        est_local = estimate_run_cost("deep_research", model_overrides={
            "proposal_synthesis": "qwen/qwen3-4b-2507",
        })
        # Default (cloud for synthesis)
        est_default = estimate_run_cost("deep_research")
        # Local override should be cheaper or equal
        assert est_local.cloud_cost_usd <= est_default.cloud_cost_usd

    def test_09_breakdown_has_all_stages(self):
        """Breakdown contains one entry per stage."""
        est = estimate_run_cost("fast_scan")
        stage_names = [b["stage"] for b in est.breakdown]
        for expected in STRATEGY_STAGES["fast_scan"]:
            assert expected in stage_names

    def test_10_time_display_format(self):
        """time_display produces human-readable strings."""
        est = estimate_run_cost("fast_scan")
        display = est.time_display
        assert "min" in display or "s" in display
        assert "$" not in display  # time, not cost


def est_fast_scan_time() -> float:
    """Helper: get fast_scan estimated time for comparison."""
    return estimate_run_cost("fast_scan").estimated_time_seconds
