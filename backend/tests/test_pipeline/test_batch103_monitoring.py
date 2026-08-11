"""Tests for BATCH-103 — Pipeline Monitoring Service.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

from backend.pipeline.monitoring.pipeline_monitoring import (
    PipelineMonitoringService,
    PreflightResult,
)


def test_103_01_preflight_returns_result():
    """Preflight returns PreflightResult."""
    svc = PipelineMonitoringService()
    result = svc.preflight(domain="AI/NLP", strategy="deep_research")
    assert isinstance(result, PreflightResult)
    assert result.ready is True


def test_103_01_preflight_has_plan():
    """Preflight includes execution plan."""
    svc = PipelineMonitoringService()
    result = svc.preflight(domain="AI")
    assert result.execution_plan is not None
    assert len(result.execution_plan.stages) == 9


def test_103_01_preflight_has_estimates():
    """Preflight includes time and token estimates."""
    svc = PipelineMonitoringService()
    result = svc.preflight(domain="AI")
    assert result.estimated_time_s > 0
    assert result.estimated_tokens > 0


def test_103_01_preflight_no_domain_not_ready():
    """Preflight with no domain returns not ready."""
    svc = PipelineMonitoringService()
    result = svc.preflight(domain="")
    assert result.ready is False
    assert any("domain" in w.lower() for w in result.warnings)


def test_103_02_record_token_usage():
    """Token usage is recorded."""
    svc = PipelineMonitoringService()
    svc.record_token_usage("gpt-4o", 1000, 500, stage="gap_analysis")
    report = svc.cost_report()
    assert report.total_input_tokens == 1000
    assert report.total_output_tokens == 500


def test_103_02_cost_report_aggregates():
    """Cost report aggregates multiple usages."""
    svc = PipelineMonitoringService()
    svc.record_token_usage("gpt-4o", 1000, 500, stage="gap_analysis")
    svc.record_token_usage("gpt-4o", 2000, 1000, stage="synthesis")
    report = svc.cost_report()
    assert report.total_input_tokens == 3000
    assert len(report.by_stage) == 2


def test_103_03_preflight_fast_scan():
    """Preflight with fast_scan strategy halves estimates."""
    svc = PipelineMonitoringService()
    deep = svc.preflight(domain="AI", strategy="deep_research")
    fast = svc.preflight(domain="AI", strategy="fast_scan")
    assert fast.estimated_time_s < deep.estimated_time_s


def test_103_03_cost_tracker_accessible():
    """cost_tracker property returns CostTracker."""
    from backend.pipeline.monitoring.cost_tracker import CostTracker
    svc = PipelineMonitoringService()
    assert isinstance(svc.cost_tracker, CostTracker)
