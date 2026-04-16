"""Tests for budget and resource management."""

from backend.pipeline.autonomy.budget import (
    BudgetPolicy,
    PlanVerifier,
    SimpleBudget,
)


class TestSimpleBudget:
    def test_initial_policy_is_continue(self):
        budget = SimpleBudget(max_tokens=500000, max_cost_usd=10.0, max_seconds=600)
        budget.start()
        assert budget.check_policy() == BudgetPolicy.CONTINUE

    def test_stop_on_token_limit(self):
        budget = SimpleBudget(max_tokens=1000, max_cost_usd=100.0, max_seconds=600)
        budget.start()
        budget.record("stage1", tokens=1000)
        assert budget.check_policy() == BudgetPolicy.STOP

    def test_stop_on_cost_limit(self):
        budget = SimpleBudget(max_tokens=100000, max_cost_usd=1.0, max_seconds=600)
        budget.start()
        budget.record("stage1", tokens=100, cost_usd=1.0)
        assert budget.check_policy() == BudgetPolicy.STOP

    def test_replan_at_80_percent(self):
        budget = SimpleBudget(max_tokens=1000, max_cost_usd=100.0, max_seconds=600)
        budget.start()
        budget.record("stage1", tokens=800)
        assert budget.check_policy() == BudgetPolicy.REPLAN

    def test_accumulates_multiple_stages(self):
        budget = SimpleBudget(max_tokens=10000, max_cost_usd=10.0, max_seconds=600)
        budget.start()
        budget.record("stage1", tokens=1000, cost_usd=0.5)
        budget.record("stage2", tokens=2000, cost_usd=1.0)

        snap = budget.snapshot()
        assert snap.total_tokens == 3000
        assert abs(snap.total_cost_usd - 1.5) < 0.01

    def test_accumulates_same_stage(self):
        budget = SimpleBudget(max_tokens=10000, max_cost_usd=10.0, max_seconds=600)
        budget.start()
        budget.record("generation", tokens=1000, cost_usd=0.5)
        budget.record("generation", tokens=500, cost_usd=0.3)

        snap = budget.snapshot()
        assert snap.by_stage["generation"].token_count == 1500
        assert abs(snap.by_stage["generation"].estimated_cost_usd - 0.8) < 0.01


class TestPlanVerifier:
    def test_estimate_cost_default(self):
        verifier = PlanVerifier()
        estimate = verifier.estimate_cost({"generation_rounds": 2, "ideas_per_round": 3})
        assert estimate.total_tokens > 0
        assert estimate.total_cost_usd > 0

    def test_estimate_scales_with_rounds(self):
        verifier = PlanVerifier()
        small = verifier.estimate_cost({"generation_rounds": 1, "ideas_per_round": 3})
        large = verifier.estimate_cost({"generation_rounds": 5, "ideas_per_round": 3})
        assert large.total_tokens > small.total_tokens

    def test_validate_fits_budget(self):
        verifier = PlanVerifier()
        budget = SimpleBudget(max_tokens=500000, max_cost_usd=10.0)
        budget.start()
        valid, msg = verifier.validate({"generation_rounds": 2, "ideas_per_round": 3}, budget)
        assert valid is True

    def test_validate_exceeds_budget(self):
        verifier = PlanVerifier()
        budget = SimpleBudget(max_tokens=100, max_cost_usd=0.01)
        budget.start()
        budget.record("prior", tokens=50, cost_usd=0.005)
        valid, msg = verifier.validate({"generation_rounds": 2, "ideas_per_round": 3}, budget)
        assert valid is False
