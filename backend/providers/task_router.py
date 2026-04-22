"""Task-aware model routing — resolves pipeline stages to LLM providers.

Routes different pipeline stages to different providers/models for
quality/cost/latency optimization. Falls back through a chain on failure.

Reference: LobeHub RouterRuntime with priority routing + fallback.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.providers.base import LLMProvider

if TYPE_CHECKING:
    from backend.providers.provider_factory import CostTracker, ProviderRegistry

logger = logging.getLogger(__name__)


class TaskRouter:
    """Resolves pipeline stage to an LLM provider, with fallback chain."""

    def __init__(
        self,
        registry: ProviderRegistry,
        cost_tracker: CostTracker | None = None,
        routing_config: dict[str, dict] | None = None,
        fallback_chain: list[str] | None = None,
    ):
        self._registry = registry
        self._cost_tracker = cost_tracker
        self._routing = routing_config or {}
        self._fallback_chain = fallback_chain or []
        self._provider_cache: dict[str, LLMProvider] = {}

    def get_provider(
        self,
        stage: str,
        run_id: str | None = None,
    ) -> LLMProvider:
        """Get the provider for a given stage. Falls back on failure."""
        config = self._routing.get(stage)

        if config:
            provider_name = config.get("provider", "")
            try:
                return self._get_or_create(provider_name, config)
            except Exception as e:
                logger.warning(
                    "Primary provider '%s' for stage '%s' failed: %s",
                    provider_name, stage, e,
                )

        # Try fallback chain
        for fallback_name in self._fallback_chain:
            try:
                return self._get_or_create(fallback_name, {})
            except Exception:
                continue

        # Ultimate fallback: default provider from registry
        return self._registry.create()

    async def get_provider_with_health_check(
        self, stage: str, run_id: str | None = None
    ) -> LLMProvider:
        """Get provider, verifying health, with automatic failover."""
        provider = self.get_provider(stage, run_id)

        # Check circuit breaker state before health check
        provider_name = provider.provider_name
        try:
            from backend.providers.resilience.circuit_breaker import _breakers

            breaker = _breakers.get(provider_name)
            if breaker and not await breaker.allow_request():
                logger.warning(
                    "Circuit open for '%s' (stage '%s'), trying fallback",
                    provider_name,
                    stage,
                )
                for fallback_name in self._fallback_chain:
                    try:
                        fb_breaker = _breakers.get(fallback_name)
                        if fb_breaker and not await fb_breaker.allow_request():
                            continue
                        fallback = self._get_or_create(fallback_name, {})
                        if await fallback.health_check():
                            return fallback
                    except Exception:
                        continue
                return provider
        except ImportError:
            pass

        is_healthy = await provider.health_check()
        if not is_healthy:
            logger.warning(
                "Provider for stage '%s' unhealthy, trying fallback",
                stage,
            )
            for fallback_name in self._fallback_chain:
                try:
                    fallback = self._get_or_create(fallback_name, {})
                    if await fallback.health_check():
                        return fallback
                except Exception:
                    continue
        return provider

    def _get_or_create(self, name: str, config: dict) -> LLMProvider:
        cache_key = f"{name}:{config.get('model', '')}"
        if cache_key in self._provider_cache:
            return self._provider_cache[cache_key]

        provider = self._registry.create(name)
        self._provider_cache[cache_key] = provider
        return provider


def create_router(
    registry: ProviderRegistry,
    cost_tracker: CostTracker | None = None,
    settings: Any = None,
) -> TaskRouter | CostAwareRouter:
    """Create the appropriate router based on settings.

    Returns CostAwareRouter if cost_routing_enabled, otherwise TaskRouter.
    """
    if getattr(settings, "cost_routing_enabled", False):
        from backend.providers.routing import BudgetManager, CostAwareRouter, LatencyTracker, RoutingStrategy

        strategy = RoutingStrategy(getattr(settings, "cost_routing_strategy", "cheapest"))
        per_provider = getattr(settings, "cost_routing_per_provider_limits", {})
        window = getattr(settings, "cost_routing_latency_window", 100)
        max_cost = getattr(settings, "budget_max_cost_usd", 10.0)
        max_tokens = getattr(settings, "budget_max_tokens", 0)

        budget = BudgetManager(
            max_cost_usd=max_cost,
            max_tokens=max_tokens,
            per_provider_limits=per_provider or None,
        )
        return CostAwareRouter(
            registry=registry,
            cost_tracker=cost_tracker or registry.cost_tracker,
            strategy=strategy,
            routing_config=getattr(settings, "model_routing", {}),
            fallback_chain=getattr(settings, "model_fallback_chain", []),
            budget_manager=budget,
            latency_tracker=LatencyTracker(window_size=window),
        )

    return TaskRouter(
        registry=registry,
        cost_tracker=cost_tracker,
        routing_config=getattr(settings, "model_routing", {}),
        fallback_chain=getattr(settings, "model_fallback_chain", []),
    )


# Lazy import to avoid circular dependency
if TYPE_CHECKING:
    from typing import Any
    from backend.providers.routing.cost_router import CostAwareRouter
