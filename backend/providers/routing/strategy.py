"""Routing strategies for cost-aware provider selection."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.providers.provider_factory import CostTracker
    from backend.providers.routing.latency_tracker import LatencyTracker


class RoutingStrategy(str, Enum):
    CONFIG = "config"
    CHEAPEST = "cheapest"
    BALANCED = "balanced"
    QUALITY_FIRST = "quality"


def sort_providers(
    candidates: list[str],
    strategy: RoutingStrategy,
    cost_tracker: CostTracker,
    latency_tracker: LatencyTracker | None = None,
    quality_ranking: dict[str, int] | None = None,
) -> list[str]:
    """Sort candidate providers according to the given strategy.

    Returns providers ordered from best to worst for the strategy.
    """
    if not candidates:
        return []
    if strategy == RoutingStrategy.CONFIG:
        return list(candidates)

    from backend.providers.provider_factory import CostTracker as CT

    costs = CT.DEFAULT_COSTS

    def _avg_cost(name: str) -> float:
        rates = costs.get(name, costs.get("litellm", {"input": 0.0025, "output": 0.01}))
        return (rates["input"] + rates["output"]) / 2

    def _avg_latency(name: str) -> float:
        if latency_tracker is None:
            return 0.0
        return latency_tracker.avg_latency(name)

    if strategy == RoutingStrategy.CHEAPEST:
        return sorted(candidates, key=_avg_cost)

    if strategy == RoutingStrategy.BALANCED:
        # Normalize cost and latency to [0, 1] range, then weighted sum
        cost_vals = {n: _avg_cost(n) for n in candidates}
        lat_vals = {n: _avg_latency(n) for n in candidates}
        max_cost = max(cost_vals.values()) or 1.0
        max_lat = max(lat_vals.values()) or 1.0

        def _balanced(name: str) -> float:
            cost_norm = cost_vals[name] / max_cost
            lat_norm = lat_vals[name] / max_lat if max_lat > 0 else 0.0
            return 0.6 * cost_norm + 0.4 * lat_norm

        return sorted(candidates, key=_balanced)

    if strategy == RoutingStrategy.QUALITY_FIRST:
        ranks = quality_ranking or {}
        default_rank = max(ranks.values(), default=0) + 1
        return sorted(candidates, key=lambda n: ranks.get(n, default_rank))

    return list(candidates)
