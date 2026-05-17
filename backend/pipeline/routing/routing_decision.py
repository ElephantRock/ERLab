"""Routing decision dataclass — full auditable routing output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoutingDecision:
    """Complete routing decision for a single stage execution.

    This is the primary output of SmartRouter.route().
    Every field is populated so routing is fully auditable.
    """

    stage: str
    model_id: str
    provider: str
    eligibility: str              # approved | limited_use | repair_only | not_approved
    strategy: str
    confidence: float             # 0.0–1.0, from ranking formula
    reason: str
    hard_gates_passed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    alternative_candidates: int = 0
    degraded: bool = False
    eval_version: str = "0.2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "model_id": self.model_id,
            "provider": self.provider,
            "eligibility": self.eligibility,
            "strategy": self.strategy,
            "confidence": round(self.confidence, 3),
            "reason": self.reason,
            "hard_gates_passed": self.hard_gates_passed,
            "warnings": self.warnings,
            "alternative_candidates": self.alternative_candidates,
            "degraded": self.degraded,
            "eval_version": self.eval_version,
        }

    @classmethod
    def degraded_decision(cls, stage: str, reason: str) -> RoutingDecision:
        """Create a degraded (no safe candidate) decision."""
        return cls(
            stage=stage,
            model_id="",
            provider="",
            eligibility="not_approved",
            strategy="skip_with_degraded_result",
            confidence=0.0,
            reason=reason,
            degraded=True,
        )
