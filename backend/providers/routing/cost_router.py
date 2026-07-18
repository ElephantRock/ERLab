"""CostAwareRouter — strategy-based provider selection with budget enforcement."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from backend.providers.base import LLMProvider
from backend.providers.routing.budget_manager import BudgetManager
from backend.providers.routing.latency_tracker import LatencyTracker
from backend.providers.routing.strategy import RoutingStrategy, sort_providers

if TYPE_CHECKING:
    from backend.providers.provider_factory import CostTracker, ProviderRegistry

logger = logging.getLogger(__name__)


class CostAwareRouter:
    def __init__(
        self,
        registry: ProviderRegistry,
        cost_tracker: CostTracker,
        strategy: RoutingStrategy = RoutingStrategy.CHEAPEST,
        routing_config: dict[str, dict] | None = None,
        fallback_chain: list[str] | None = None,
        budget_manager: BudgetManager | None = None,
        latency_tracker: LatencyTracker | None = None,
        quality_ranking: dict[str, int] | None = None,
    ) -> None:
        self._registry = registry
        self._cost_tracker = cost_tracker
        self._strategy = strategy
        self._routing = routing_config or {}
        self._fallback_chain = fallback_chain or []
        self._budget = budget_manager
        self._latency = latency_tracker or LatencyTracker()
        self._quality_ranking = quality_ranking
        self._provider_cache: dict[str, LLMProvider] = {}

    def get_provider(self, stage: str, run_id: str | None = None) -> LLMProvider:
        candidates = self._get_candidates(stage)
        candidates = self._filter_by_budget(candidates)
        candidates = self._filter_by_health(candidates)

        if not candidates:
            logger.warning("No healthy candidates for stage '%s' — using default", stage)
            return self._registry.create()

        ordered = sort_providers(
            candidates,
            self._strategy,
            self._cost_tracker,
            self._latency,
            self._quality_ranking,
        )
        chosen = ordered[0]
        logger.debug("Stage '%s' routed to '%s' (strategy=%s)", stage, chosen, self._strategy.value)
        return self._get_or_create(chosen, self._routing.get(stage, {}))

    async def get_provider_with_health_check(
        self, stage: str, run_id: str | None = None
    ) -> LLMProvider:
        from backend.providers.resilience.circuit_breaker import (
            CircuitOpenError,
            _breakers,
        )

        candidates = self._get_candidates(stage)
        candidates = self._filter_by_budget(candidates)

        for name in candidates:
            breaker = _breakers.get(name)
            if breaker is not None:
                # check() is a raising guard, not a boolean predicate:
                # it returns None when closed and raises CircuitOpenError
                # when open. Treat the raise as "skip this candidate".
                try:
                    breaker.check()
                except CircuitOpenError:
                    continue
            provider = self._get_or_create(name, self._routing.get(stage, {}))
            try:
                if await provider.health_check():
                    return provider
            except Exception:
                continue

        logger.warning("No healthy provider for stage '%s'", stage)
        return self._registry.create()

    def record_latency(self, provider: str, duration_ms: float) -> None:
        self._latency.record(provider, duration_ms)

    def _get_candidates(self, stage: str) -> list[str]:
        config = self._routing.get(stage)
        if config and "provider" in config:
            primary = config["provider"]
            return [primary] + [f for f in self._fallback_chain if f != primary]
        if self._fallback_chain:
            return list(self._fallback_chain)
        return [self._registry._providers.keys().__iter__().__next__()] if self._registry._providers else []

    def _filter_by_budget(self, candidates: list[str]) -> list[str]:
        if self._budget is None:
            return candidates
        return [n for n in candidates if not self._budget.provider_exceeded(n, self._cost_tracker)]

    def _filter_by_health(self, candidates: list[str]) -> list[str]:
        from backend.providers.resilience.circuit_breaker import (
            CircuitOpenError,
            _breakers,
        )

        healthy = []
        for name in candidates:
            breaker = _breakers.get(name)
            if breaker is None:
                healthy.append(name)
            else:
                # check() is a raising guard, not a boolean predicate:
                # it returns None when closed and raises CircuitOpenError
                # when open. Treat the raise as "exclude this candidate".
                try:
                    breaker.check()
                    healthy.append(name)
                except CircuitOpenError:
                    continue
        return healthy if healthy else candidates

    def _get_or_create(self, name: str, config: dict) -> LLMProvider:
        model = config.get("model", "")
        cache_key = f"{name}:{model}"
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]
        provider = self._registry.create(name)
        self._provider_cache[cache_key] = provider
        return provider
