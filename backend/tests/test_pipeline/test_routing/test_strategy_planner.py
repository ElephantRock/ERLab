"""Phase D tests: StrategyPlanner."""

import pytest

from backend.pipeline.routing.stage_contract import StageContract
from backend.pipeline.routing.certified_lookup import CertifiedModelCandidate
from backend.pipeline.routing.strategy_planner import StrategyPlanner


def _make_contract(**overrides):
    defaults = dict(
        stage="paper_synthesis",
        task_type="generation",
        risk_level="high",
        input_tokens_estimate=8000,
        output_tokens_requested=12000,
        allowed_strategies=["section_wise", "map_reduce"],
        fallback_strategy="section_wise",
    )
    defaults.update(overrides)
    return StageContract(**defaults)


def _make_candidate(**overrides):
    defaults = dict(
        model_id="qwen3-4b",
        provider="lmstudio",
        allowed_stages=["paper_synthesis"],
        safe_context_window=16384,
        safe_output_tokens=4096,
    )
    defaults.update(overrides)
    return CertifiedModelCandidate(**defaults)


class TestStrategyPlanner:
    def test_planner_selects_single_call_by_default(self):
        planner = StrategyPlanner()
        contract = _make_contract(
            stage="query_generation",
            input_tokens_estimate=1500,
            output_tokens_requested=2048,
            allowed_strategies=["single_call"],
        )
        candidate = _make_candidate(safe_context_window=8192)
        plan = planner.plan(contract, candidate)
        assert plan.strategy == "single_call"
        assert plan.fits_context is True

    def test_planner_selects_section_wise_when_single_call_too_large(self):
        planner = StrategyPlanner()
        contract = _make_contract(
            stage="paper_synthesis",
            input_tokens_estimate=12000,
            output_tokens_requested=8000,
            allowed_strategies=["single_call", "section_wise"],
        )
        # section_wise: 12000*0.35=4200 + 8000*0.40=3200 = 7400*1.15=8510
        candidate = _make_candidate(safe_context_window=12000)
        plan = planner.plan(contract, candidate)
        assert plan.strategy == "section_wise"
        assert plan.fits_context is True

    def test_planner_selects_compressed_review_for_large_review(self):
        planner = StrategyPlanner()
        contract = _make_contract(
            stage="adversarial_review",
            input_tokens_estimate=12000,
            output_tokens_requested=6000,
            allowed_strategies=["compressed_review_packet", "section_wise_review"],
        )
        # compressed: 12000*0.50=6000 + 6000*0.60=3600 = 9600*1.15=11040
        # section_wise_review: 12000*0.40=4800 + 6000*0.50=3000 = 7800*1.15=8970
        candidate = _make_candidate(safe_context_window=12000)
        plan = planner.plan(contract, candidate)
        assert plan.strategy == "compressed_review_packet"
        assert plan.fits_context is True

    def test_planner_selects_closed_set_audit_for_citation_audit(self):
        planner = StrategyPlanner()
        contract = _make_contract(
            stage="citation_audit",
            input_tokens_estimate=4000,
            output_tokens_requested=4096,
            allowed_strategies=["closed_set_audit"],
        )
        candidate = _make_candidate(safe_context_window=8192)
        plan = planner.plan(contract, candidate)
        assert plan.strategy == "closed_set_audit"

    def test_planner_flags_degraded_when_nothing_fits(self):
        planner = StrategyPlanner()
        contract = _make_contract(
            input_tokens_estimate=50000,
            output_tokens_requested=20000,
            allowed_strategies=["single_call"],
        )
        candidate = _make_candidate(safe_context_window=4096)
        plan = planner.plan(contract, candidate)
        assert plan.strategy == "skip_with_degraded_result"
        assert plan.fits_context is False

    def test_planner_respects_contract_allowed_strategies(self):
        planner = StrategyPlanner()
        contract = _make_contract(
            allowed_strategies=["closed_set_audit"],  # only this
        )
        candidate = _make_candidate(safe_context_window=16384)
        plan = planner.plan(contract, candidate)
        assert plan.strategy == "closed_set_audit"

    def test_planner_warns_on_tight_fit(self):
        planner = StrategyPlanner()
        contract = _make_contract(
            input_tokens_estimate=5000,
            output_tokens_requested=4096,
            allowed_strategies=["single_call"],
        )
        candidate = _make_candidate(safe_context_window=11000)  # barely fits
        plan = planner.plan(contract, candidate)
        assert plan.strategy == "single_call"
        assert len(plan.warnings) > 0

    def test_planner_estimates_tokens_for_each_strategy(self):
        planner = StrategyPlanner()
        contract = _make_contract(
            input_tokens_estimate=10000,
            output_tokens_requested=8000,
        )
        candidate = _make_candidate(safe_context_window=32768)

        plan = planner.plan(contract, candidate)
        assert plan.estimated_input_tokens > 0
        assert plan.estimated_output_tokens > 0

    def test_strategy_plan_allows_section_wise_candidate_that_single_call_would_reject(self):
        """A candidate that can't do single_call may succeed with section_wise."""
        planner = StrategyPlanner()
        contract = _make_contract(
            input_tokens_estimate=15000,
            output_tokens_requested=10000,
            allowed_strategies=["single_call", "section_wise"],
        )
        # Context of 12k: single_call needs ~28k → fails, section_wise needs ~7k → passes
        candidate = _make_candidate(safe_context_window=12000)
        plan = planner.plan(contract, candidate)
        assert plan.strategy == "section_wise"
        assert plan.fits_context is True

    def test_plan_all_returns_plans_for_all_candidates(self):
        planner = StrategyPlanner()
        contract = _make_contract(input_tokens_estimate=2000, output_tokens_requested=2048)
        c1 = _make_candidate(model_id="model-a", safe_context_window=8192)
        c2 = _make_candidate(model_id="model-b", safe_context_window=4096)
        results = planner.plan_all(contract, [c1, c2])
        assert len(results) == 2
        models = [c.model_id for c, p in results]
        assert "model-a" in models
        assert "model-b" in models
