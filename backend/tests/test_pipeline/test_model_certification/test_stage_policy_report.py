"""Phase E+G tests: Stage Policy, Report, Runner."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.model_certification.report import CapabilityReport
from backend.pipeline.model_certification.stage_policy import (
    decide_all_stages,
    decide_stage_eligibility,
)
from backend.pipeline.model_certification.stage_report import (
    StageEligibilityDecisionV2,
    StageScoreCard,
    compute_latency_percentiles,
    extend_report_with_stage_eval,
)


def _make_scorecard(stage="query_generation", **overrides):
    defaults = dict(
        stage=stage,
        cases_run=3,
        cases_passed=2,
        aggregate_score=0.85,
        schema_valid_rate=0.95,
        metrics={"query_relevance": 0.85, "query_diversity": 0.80},
    )
    defaults.update(overrides)
    return StageScoreCard(**defaults)


class TestStagePolicy:
    def test_blocks_paper_synthesis_on_citation_fabrication(self):
        card = _make_scorecard(
            "paper_synthesis",
            metrics={"section_completeness": 0.95, "citation_grounding": 0.80},
            grounding_metrics={"citation_fabrication_rate": 0.05, "unsupported_claim_rate": 0.10},
        )
        decision = decide_stage_eligibility("paper_synthesis", card)
        assert decision.eligibility == "not_approved"
        assert any("fabrication" in f.lower() for f in decision.hard_failures)

    def test_approves_query_generation_at_threshold(self):
        card = _make_scorecard(
            "query_generation",
            metrics={"schema_valid_rate": 0.95, "query_relevance": 0.85},
        )
        decision = decide_stage_eligibility("query_generation", card)
        # Should be at least limited_use
        assert decision.eligibility in ("approved", "limited_use")

    def test_limited_use_below_threshold(self):
        card = _make_scorecard(
            "query_generation",
            metrics={"schema_valid_rate": 0.80, "query_relevance": 0.60},
            aggregate_score=0.60,
        )
        decision = decide_stage_eligibility("query_generation", card)
        assert decision.eligibility in ("limited_use", "repair_only", "not_approved")

    def test_hard_failure_override(self):
        card = _make_scorecard(
            "evidence_table",
            grounding_metrics={"citation_fabrication_rate": 0.10, "unsupported_claim_rate": 0.05},
        )
        decision = decide_stage_eligibility("evidence_table", card)
        assert decision.eligibility == "not_approved"

    def test_fallback_to_defaults(self):
        card = _make_scorecard("unknown_stage", metrics={})
        decision = decide_stage_eligibility("unknown_stage", card)
        assert decision.eligibility == "not_approved"

    def test_ignores_stages_without_scorecards(self):
        decisions = decide_all_stages({})
        assert len(decisions) == 0

    def test_caps_paper_synthesis_at_limited_use_in_v02(self):
        """paper_synthesis cannot be fully approved in v0.2."""
        card = _make_scorecard(
            "paper_synthesis",
            metrics={
                "section_completeness": 0.95,
                "citation_grounding": 0.85,
            },
            grounding_metrics={
                "citation_fabrication_rate": 0.00,
                "unsupported_claim_rate": 0.05,
            },
        )
        decision = decide_stage_eligibility("paper_synthesis", card)
        assert decision.eligibility in ("limited_use", "repair_only", "not_approved")
        assert decision.eligibility != "approved"

    def test_caps_proposal_synthesis_at_limited_use_in_v02(self):
        """proposal_synthesis cannot be fully approved in v0.2."""
        card = _make_scorecard(
            "proposal_synthesis",
            metrics={
                "method_specificity": 0.90,
                "feasibility_clarity": 0.90,
            },
        )
        decision = decide_stage_eligibility("proposal_synthesis", card)
        assert decision.eligibility != "approved"


class TestStageReport:
    def test_stage_score_card_serialization(self):
        card = _make_scorecard()
        d = card.to_dict()
        assert d["stage"] == "query_generation"
        assert d["cases_run"] == 3

    def test_capability_report_v2_includes_stage_eval(self):
        report = CapabilityReport(model_id="test")
        card = _make_scorecard()
        decision = StageEligibilityDecisionV2(
            stage="query_generation",
            eligibility="approved",
            reason="All gates passed",
        )
        extend_report_with_stage_eval(report, {"query_generation": card}, {"query_generation": decision})
        assert report.stage_eval is not None
        assert report.stage_eligibility_v2 is not None
        assert report.eval_version == "0.2"

    def test_capability_report_v1_backward_compatible(self):
        """v0.1 report deserializes without v0.2 fields."""
        report = CapabilityReport(
            model_id="test",
            status="approved_for_limited_use",
            stage_eligibility={"draft": "approved"},
        )
        yaml_str = report.to_yaml()
        loaded = CapabilityReport.from_yaml(yaml_str)
        assert loaded.model_id == "test"
        assert loaded.stage_eligibility == {"draft": "approved"}
        assert loaded.stage_eval is None  # v0.1 doesn't have stage_eval

    def test_stage_report_serializes_to_capability_report(self):
        report = CapabilityReport(model_id="test")
        card = _make_scorecard("repair", metrics={"json_repair_success": 0.90})
        extend_report_with_stage_eval(report, {"repair": card}, {})
        d = report.to_dict()
        assert "repair" in d["stage_eval"]

    def test_stage_score_card_latency_percentiles(self):
        latencies = [0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0]
        p50, p95 = compute_latency_percentiles(latencies)
        assert p50 > 0
        assert p95 >= p50

    def test_stage_score_card_aggregate_score(self):
        card = _make_scorecard(aggregate_score=0.75)
        assert card.aggregate_score == 0.75

    def test_v2_stage_eligibility_supersedes_v1_without_deleting_v1(self):
        """v0.2 eligibility is added alongside v0.1, never replaces."""
        report = CapabilityReport(
            model_id="test",
            stage_eligibility={"draft": "approved", "repair": "approved"},
        )
        v2_decision = StageEligibilityDecisionV2(
            stage="repair", eligibility="limited_use", reason="Measured lower"
        )
        extend_report_with_stage_eval(
            report,
            {"repair": _make_scorecard("repair")},
            {"repair": v2_decision},
        )
        # v0.1 field preserved
        assert report.stage_eligibility == {"draft": "approved", "repair": "approved"}
        # v0.2 field added
        assert report.stage_eligibility_v2 is not None
        assert "repair" in report.stage_eligibility_v2

    def test_v1_report_deserializes_without_v2_fields(self):
        report = CapabilityReport(
            model_id="test",
            eval_version="0.1",
            stage_eligibility={"draft": "approved"},
        )
        yaml_str = report.to_yaml()
        loaded = CapabilityReport.from_yaml(yaml_str)
        assert loaded.eval_version == "0.1"
        assert loaded.stage_eval is None


class TestStageRunner:
    @pytest.mark.asyncio
    async def test_stage_runner_records_latency_tokens_errors(self, tmp_path):
        from backend.pipeline.model_certification.eval_case import StageEvalCase
        from backend.pipeline.model_certification.stage_runner import StageEvalRunner

        provider = AsyncMock()
        resp = MagicMock()
        resp.text = '{"queries": ["test query"]}'
        provider.complete = AsyncMock(return_value=resp)

        runner = StageEvalRunner(provider, "test-model", eval_dir=str(tmp_path))
        case = StageEvalCase(
            case_id="qg-001", stage="query_generation",
            prompt_template="Generate queries", output_token_budget=4096,
        )
        result = await runner.run_case(case)
        assert result.latency_seconds >= 0
        assert result.output_tokens >= 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_stage_runner_handles_provider_failure(self):
        from backend.pipeline.model_certification.eval_case import StageEvalCase
        from backend.pipeline.model_certification.stage_runner import StageEvalRunner

        provider = AsyncMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("provider down"))

        runner = StageEvalRunner(provider, "test-model")
        case = StageEvalCase(
            case_id="qg-001", stage="query_generation",
            prompt_template="Generate queries", output_token_budget=4096,
        )
        result = await runner.run_case(case)
        assert result.error is not None
        assert "provider down" in result.error

    @pytest.mark.asyncio
    async def test_stage_runner_schema_check_when_schema_provided(self):
        from backend.pipeline.model_certification.eval_case import StageEvalCase
        from backend.pipeline.model_certification.stage_runner import StageEvalRunner

        provider = AsyncMock()
        resp = MagicMock()
        resp.text = 'not json at all'
        provider.complete = AsyncMock(return_value=resp)

        runner = StageEvalRunner(provider, "test-model")
        case = StageEvalCase(
            case_id="qg-001", stage="query_generation",
            prompt_template="Generate queries", output_token_budget=4096,
        )
        result = await runner.run_case(case)
        assert result.passed_schema is False

    @pytest.mark.asyncio
    async def test_stage_runner_empty_case_set_returns_empty(self, tmp_path):
        from backend.pipeline.model_certification.stage_runner import StageEvalRunner
        provider = AsyncMock()
        runner = StageEvalRunner(provider, "test-model", eval_dir=str(tmp_path))
        results = await runner.run_stage("nonexistent_stage")
        assert results == []

    @pytest.mark.asyncio
    async def test_stage_runner_marks_case_failed_on_token_budget_violation(self):
        from backend.pipeline.model_certification.eval_case import StageEvalCase
        from backend.pipeline.model_certification.stage_runner import StageEvalRunner

        provider = AsyncMock()
        # Return very long text that exceeds budget
        resp = MagicMock()
        resp.text = "word " * 5000  # ~5000 words → ~6500 tokens
        provider.complete = AsyncMock(return_value=resp)

        runner = StageEvalRunner(provider, "test-model")
        case = StageEvalCase(
            case_id="qg-001", stage="query_generation",
            prompt_template="Generate queries", output_token_budget=100,  # very tight budget
        )
        result = await runner.run_case(case)
        assert result.token_budget_violation is True
        assert "Token budget violated" in result.failures
