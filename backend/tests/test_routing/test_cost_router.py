"""Tests for CostAwareRouter — strategy routing, budget filtering, health checks."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from backend.providers.base import CostEvent, LLMProvider
from backend.providers.provider_factory import CostTracker
from backend.providers.routing.budget_manager import BudgetManager
from backend.providers.routing.cost_router import CostAwareRouter
from backend.providers.routing.latency_tracker import LatencyTracker
from backend.providers.routing.strategy import RoutingStrategy


class FakeProvider(LLMProvider):
    def __init__(self, name: str = "fake"):
        self._name = name
        self._cost_callback = None

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def default_model(self) -> str:
        return "fake-model"

    async def complete(self, messages, temperature=0.7, max_tokens=4096):
        return "ok"

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        yield "ok"

    async def structured_output(self, messages, schema, temperature=0.3):
        return {}

    async def embed(self, texts):
        return []


class FakeRegistry:
    def __init__(self, providers: dict[str, FakeProvider] | None = None):
        self._providers = {"openai": FakeProvider, "anthropic": FakeProvider, "gemini": FakeProvider}
        self._instances = providers or {}
        self._cost_tracker = None

    def create(self, name=None, settings=None):
        return self._instances.get(name, FakeProvider(name))

    @property
    def cost_tracker(self):
        return self._cost_tracker


def _tracker_with_events(events):
    ct = CostTracker()
    for provider, cost in events:
        ct.record(CostEvent(
            provider=provider, model="test",
            input_tokens=50, output_tokens=50,
            cost_usd=cost, timestamp=datetime.now(timezone.utc),
        ))
    return ct


class TestCostAwareRouter:
    def test_cheapest_strategy(self):
        registry = FakeRegistry()
        ct = CostTracker()
        router = CostAwareRouter(
            registry=registry, cost_tracker=ct,
            strategy=RoutingStrategy.CHEAPEST,
            fallback_chain=["openai", "anthropic", "gemini"],
        )
        provider = router.get_provider("test_stage")
        # gemini is cheapest per DEFAULT_COSTS
        assert provider.provider_name == "gemini"

    def test_config_strategy_uses_routing(self):
        registry = FakeRegistry()
        ct = CostTracker()
        router = CostAwareRouter(
            registry=registry, cost_tracker=ct,
            strategy=RoutingStrategy.CONFIG,
            routing_config={"my_stage": {"provider": "anthropic"}},
        )
        provider = router.get_provider("my_stage")
        assert provider.provider_name == "anthropic"

    def test_budget_filters_provider(self):
        registry = FakeRegistry()
        ct = _tracker_with_events([("gemini", 999.0)])
        budget = BudgetManager(per_provider_limits={"gemini": 1.0})
        router = CostAwareRouter(
            registry=registry, cost_tracker=ct,
            strategy=RoutingStrategy.CHEAPEST,
            fallback_chain=["gemini", "openai"],
            budget_manager=budget,
        )
        provider = router.get_provider("test_stage")
        assert provider.provider_name == "openai"

    def test_record_latency(self):
        registry = FakeRegistry()
        ct = CostTracker()
        lt = LatencyTracker()
        router = CostAwareRouter(
            registry=registry, cost_tracker=ct,
            latency_tracker=lt,
            fallback_chain=["openai"],
        )
        router.record_latency("openai", 150.0)
        assert lt.avg_latency("openai") == 150.0

    def test_no_candidates_returns_default(self):
        registry = FakeRegistry()
        ct = CostTracker()
        router = CostAwareRouter(
            registry=registry, cost_tracker=ct,
            fallback_chain=[],
        )
        # No routing config, no fallback — returns default
        provider = router.get_provider("unknown")
        assert provider is not None

    @pytest.mark.anyio
    async def test_health_check_failover(self):
        registry = FakeRegistry()
        ct = CostTracker()
        router = CostAwareRouter(
            registry=registry, cost_tracker=ct,
            routing_config={"stage": {"provider": "openai"}},
            fallback_chain=["anthropic"],
        )
        # Both providers are FakeProviders, health_check returns True by default
        provider = await router.get_provider_with_health_check("stage")
        assert provider.provider_name == "openai"
