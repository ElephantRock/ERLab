"""Tests for RoutingStrategy and sort_providers."""

from backend.providers.provider_factory import CostTracker
from backend.providers.routing.latency_tracker import LatencyTracker
from backend.providers.routing.strategy import RoutingStrategy, sort_providers


class TestRoutingStrategy:
    def test_config_returns_as_is(self):
        ct = CostTracker()
        result = sort_providers(["openai", "anthropic"], RoutingStrategy.CONFIG, ct)
        assert result == ["openai", "anthropic"]

    def test_cheapest_sorts_by_cost(self):
        ct = CostTracker()
        result = sort_providers(
            ["openai", "anthropic", "gemini"],
            RoutingStrategy.CHEAPEST,
            ct,
        )
        # gemini: avg 0.003125, openai: avg 0.00625, anthropic: avg 0.009
        assert result[0] == "gemini"

    def test_balanced_sorts_with_latency(self):
        ct = CostTracker()
        lt = LatencyTracker()
        lt.record("openai", 100.0)
        lt.record("anthropic", 500.0)
        result = sort_providers(
            ["openai", "anthropic"],
            RoutingStrategy.BALANCED,
            ct,
            latency_tracker=lt,
        )
        assert result[0] == "openai"  # cheaper + faster

    def test_quality_first_uses_ranking(self):
        ct = CostTracker()
        ranking = {"anthropic": 1, "openai": 2, "gemini": 3}
        result = sort_providers(
            ["gemini", "openai", "anthropic"],
            RoutingStrategy.QUALITY_FIRST,
            ct,
            quality_ranking=ranking,
        )
        assert result[0] == "anthropic"

    def test_empty_candidates(self):
        ct = CostTracker()
        assert sort_providers([], RoutingStrategy.CHEAPEST, ct) == []

    def test_unknown_provider_uses_litellm_default(self):
        ct = CostTracker()
        result = sort_providers(["unknown"], RoutingStrategy.CHEAPEST, ct)
        assert len(result) == 1
