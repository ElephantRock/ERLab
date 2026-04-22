"""Tests for BudgetManager — global and per-provider limits."""

from datetime import datetime, timezone

from backend.providers.base import CostEvent
from backend.providers.provider_factory import CostTracker
from backend.providers.routing.budget_manager import BudgetManager


def _record(tracker: CostTracker, provider: str, cost_usd: float, tokens: int = 100):
    tracker.record(CostEvent(
        provider=provider,
        model="test",
        input_tokens=tokens // 2,
        output_tokens=tokens // 2,
        cost_usd=cost_usd,
        timestamp=datetime.now(timezone.utc),
    ))


class TestBudgetManager:
    def test_no_limits_always_ok(self, cost_tracker):
        bm = BudgetManager()
        _record(cost_tracker, "openai", 999.0)
        assert bm.check(cost_tracker) is True

    def test_global_cost_limit(self, cost_tracker):
        bm = BudgetManager(max_cost_usd=1.0)
        _record(cost_tracker, "openai", 0.5)
        assert bm.check(cost_tracker) is True
        _record(cost_tracker, "openai", 0.6)
        assert bm.check(cost_tracker) is False

    def test_global_token_limit(self, cost_tracker):
        bm = BudgetManager(max_tokens=100)
        _record(cost_tracker, "openai", 0.01, tokens=50)
        assert bm.check(cost_tracker) is True
        _record(cost_tracker, "openai", 0.01, tokens=60)
        assert bm.check(cost_tracker) is False

    def test_per_provider_limit(self, cost_tracker):
        bm = BudgetManager(per_provider_limits={"openai": 1.0, "anthropic": 2.0})
        _record(cost_tracker, "openai", 0.6)
        _record(cost_tracker, "openai", 0.5)
        assert bm.provider_exceeded("openai", cost_tracker) is True
        assert bm.provider_exceeded("anthropic", cost_tracker) is False

    def test_per_provider_remaining(self, cost_tracker):
        bm = BudgetManager(per_provider_limits={"openai": 1.0})
        _record(cost_tracker, "openai", 0.3)
        assert abs(bm.provider_remaining("openai", cost_tracker) - 0.7) < 0.01

    def test_per_provider_no_limit(self, cost_tracker):
        bm = BudgetManager()
        assert bm.provider_exceeded("openai", cost_tracker) is False

    def test_remaining(self, cost_tracker):
        bm = BudgetManager(max_cost_usd=10.0, per_provider_limits={"openai": 5.0})
        _record(cost_tracker, "openai", 2.0)
        rem = bm.remaining(cost_tracker)
        assert abs(rem["cost_usd"] - 8.0) < 0.01
        assert abs(rem["provider:openai"] - 3.0) < 0.01
