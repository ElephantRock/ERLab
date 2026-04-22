"""Budget enforcement for cost-aware routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.providers.provider_factory import CostTracker


class BudgetManager:
    def __init__(
        self,
        max_cost_usd: float = float("inf"),
        max_tokens: int = 0,
        per_provider_limits: dict[str, float] | None = None,
    ) -> None:
        self._max_cost_usd = max_cost_usd
        self._max_tokens = max_tokens
        self._per_provider = per_provider_limits or {}

    def check(self, cost_tracker: CostTracker) -> bool:
        """Return True if within all budget limits."""
        if not self._within_global(cost_tracker):
            return False
        for provider in self._per_provider:
            if self.provider_exceeded(provider, cost_tracker):
                return False
        return True

    def _within_global(self, cost_tracker: CostTracker) -> bool:
        summary = cost_tracker.summary()
        if self._max_cost_usd > 0 and summary["total_cost_usd"] >= self._max_cost_usd:
            return False
        if self._max_tokens > 0 and summary["total_tokens"] >= self._max_tokens:
            return False
        return True

    def provider_exceeded(self, provider: str, cost_tracker: CostTracker) -> bool:
        limit = self._per_provider.get(provider)
        if limit is None:
            return False
        by_prov = cost_tracker.by_provider()
        spent = by_prov.get(provider, {}).get("cost_usd", 0.0)
        return spent >= limit

    def provider_remaining(self, provider: str, cost_tracker: CostTracker) -> float:
        limit = self._per_provider.get(provider, float("inf"))
        by_prov = cost_tracker.by_provider()
        spent = by_prov.get(provider, {}).get("cost_usd", 0.0)
        return max(0.0, limit - spent)

    def remaining(self, cost_tracker: CostTracker) -> dict[str, float]:
        summary = cost_tracker.summary()
        result: dict[str, float] = {}
        if self._max_cost_usd > 0 and self._max_cost_usd < float("inf"):
            result["cost_usd"] = max(0.0, self._max_cost_usd - summary["total_cost_usd"])
        if self._max_tokens > 0:
            result["tokens"] = max(0, self._max_tokens - summary["total_tokens"])
        for prov in self._per_provider:
            result[f"provider:{prov}"] = self.provider_remaining(prov, cost_tracker)
        return result
