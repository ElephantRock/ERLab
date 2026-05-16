"""DegradedResult — explicit marker for failed/low-confidence outputs.

Replaces the pattern where failed quality checks silently become score=1.00
or other fake-perfect values. A degraded result is honest about its uncertainty.

Usage:
    # Before (dangerous):
    if not reflection_result:
        return 1.00  # lies about quality

    # After (honest):
    if not reflection_result:
        return DegradedResult(
            value=0.5,
            reason="reflection LLM call failed",
            requires_review=True,
        )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DegradedResult:
    """A result that is explicitly degraded or uncertain.

    Attributes:
        value: The fallback value (neutral, not fake-perfect).
        confidence: 0.0 — this is a degraded result.
        reason: Why the result is degraded.
        requires_review: Whether human review is needed.
        original_error: The error that caused degradation, if any.
    """

    value: Any
    confidence: float = 0.0
    reason: str = ""
    requires_review: bool = True
    original_error: str | None = None

    @property
    def is_degraded(self) -> bool:
        return True

    def to_dict(self) -> dict:
        """Serialize for logging/API response."""
        return {
            "value": self.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "requires_review": self.requires_review,
            "degraded": True,
            "original_error": self.original_error,
        }


def degraded_score(
    default: float = 0.5,
    reason: str = "",
    error: str | None = None,
) -> DegradedResult:
    """Shorthand for creating a degraded score result."""
    return DegradedResult(
        value=default,
        confidence=0.0,
        reason=reason or "LLM call failed, using neutral default",
        requires_review=True,
        original_error=error,
    )


def degraded_pass(
    reason: str = "",
    error: str | None = None,
) -> DegradedResult:
    """Shorthand for a degraded pass result (reflection, quality gate).

    Replaces the pattern: `if failed: return score=1.00, passed=True`
    """
    return DegradedResult(
        value=True,
        confidence=0.0,
        reason=reason or "Quality check failed, auto-passing with degraded confidence",
        requires_review=True,
        original_error=error,
    )
