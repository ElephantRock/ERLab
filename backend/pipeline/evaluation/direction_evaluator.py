"""Phase 8 / D3 — structural metric-direction evaluation.

Computes improvement from persisted observed values and declared metric
directions — never from language-model interpretation of paper text.

The evaluator answers two questions:

1. **Is the comparison better than the baseline?** (structural comparison)
2. **Does a textual claim correctly interpret the direction?** (claim checking)

Direction rules:
    higher_better: comparison > baseline → improvement
    lower_better:  comparison < baseline → improvement
    neutral:       no comparison possible

The evaluator blocks claims such as:
    model_rmse = 0.12, baseline_rmse = 0.15
    paper says "the model reduced error"  ← CORRECT (lower is better, 0.12 < 0.15)
    paper says "the model improved accuracy"  ← INCORRECT (RMSE is not accuracy)

    model_rmse = 0.20, baseline_rmse = 0.15
    paper says "the model reduced error"  ← INCORRECT (0.20 > 0.15, error increased)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ComparisonOutcome(Enum):
    IMPROVEMENT = "improvement"
    DEGRADATION = "degradation"
    TIE = "tie"


@dataclass
class MetricComparison:
    """Result of comparing a comparison-model metric against a baseline metric."""

    metric_name: str
    baseline_value: float
    comparison_value: float
    direction: str  # higher_better | lower_better | neutral
    outcome: ComparisonOutcome
    delta: float  # comparison - baseline (raw)
    relative_delta: float  # (comparison - baseline) / baseline, or 0.0 if baseline=0
    is_improvement: bool

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "comparison_value": self.comparison_value,
            "direction": self.direction,
            "outcome": self.outcome.value,
            "delta": self.delta,
            "relative_delta": self.relative_delta,
            "is_improvement": self.is_improvement,
        }


def evaluate_metric_comparison(
    metric_name: str,
    baseline_value: float,
    comparison_value: float,
    direction: str,
    tie_tolerance: float = 1e-9,
) -> MetricComparison:
    """Structurally compare a comparison-model metric against a baseline.

    The direction determines what counts as improvement:
        higher_better: comparison > baseline + tolerance → improvement
        lower_better:  comparison < baseline - tolerance → improvement

    Returns a MetricComparison with the computed outcome.
    """
    delta = comparison_value - baseline_value
    if abs(baseline_value) > tie_tolerance:
        relative_delta = delta / abs(baseline_value)
    else:
        relative_delta = 0.0

    if direction == "higher_better":
        if delta > tie_tolerance:
            outcome = ComparisonOutcome.IMPROVEMENT
        elif delta < -tie_tolerance:
            outcome = ComparisonOutcome.DEGRADATION
        else:
            outcome = ComparisonOutcome.TIE
    elif direction == "lower_better":
        if delta < -tie_tolerance:
            outcome = ComparisonOutcome.IMPROVEMENT
        elif delta > tie_tolerance:
            outcome = ComparisonOutcome.DEGRADATION
        else:
            outcome = ComparisonOutcome.TIE
    else:
        # neutral: no direction → no improvement determination possible
        outcome = ComparisonOutcome.TIE

    is_improvement = outcome == ComparisonOutcome.IMPROVEMENT

    return MetricComparison(
        metric_name=metric_name,
        baseline_value=baseline_value,
        comparison_value=comparison_value,
        direction=direction,
        outcome=outcome,
        delta=delta,
        relative_delta=relative_delta,
        is_improvement=is_improvement,
    )


@dataclass
class ClaimCheck:
    """Result of checking whether a textual claim correctly interprets
    persisted metric values and directions."""

    claim_text: str
    is_correct: bool
    reason: str
    comparison: MetricComparison | None = None


def check_claim_direction(
    claim_text: str,
    comparison: MetricComparison,
) -> ClaimCheck:
    """Check whether a textual claim about a metric comparison correctly
    interprets the persisted direction.

    This is the structural guard that blocks inverted interpretations even
    when both numbers are correctly cited.

    Examples:
        rmse: lower_better, comparison=0.12 < baseline=0.15
            claim "reduced error" → CORRECT
            claim "improved accuracy" → INCORRECT (RMSE is not accuracy)
            claim "increased error" → INCORRECT (error decreased)

        accuracy: higher_better, comparison=0.90 > baseline=0.80
            claim "improved accuracy" → CORRECT
            claim "reduced accuracy" → INCORRECT (accuracy increased)
    """
    text = claim_text.lower()

    # ── Detect claim polarity from language ──────────────────────────
    # "Improvement" language: claims the model is better
    improvement_words = [
        "improve", "improved", "improvement", "outperform", "outperforms",
        "better", "superior", "exceed", "exceeds", "surpass", "gains",
        "boost", "enhance", "enhanced", "reduce error", "reduces error",
        "reduced error", "lower error", "lower rmse", "lower mae",
        "lower loss", "decrease error", "decreased error", "fewer errors",
    ]
    # "Degradation" language: claims the model is worse
    degradation_words = [
        "worse", "inferior", "underperform", "underperforms",
        "increased error", "increase error", "higher rmse", "higher mae",
        "higher loss", "more error", "degraded", "degradation",
    ]

    claims_improvement = any(w in text for w in improvement_words)
    claims_degradation = any(w in text for w in degradation_words)

    # ── Cross-check against structural outcome ───────────────────────
    if comparison.outcome == ComparisonOutcome.IMPROVEMENT:
        if claims_degradation and not claims_improvement:
            return ClaimCheck(
                claim_text=claim_text,
                is_correct=False,
                reason=(
                    f"Claim uses degradation language but {comparison.metric_name} "
                    f"structurally improved (comparison={comparison.comparison_value}, "
                    f"baseline={comparison.baseline_value}, direction={comparison.direction})"
                ),
                comparison=comparison,
            )
        return ClaimCheck(
            claim_text=claim_text,
            is_correct=True,
            reason="Claim is consistent with structural improvement",
            comparison=comparison,
        )

    if comparison.outcome == ComparisonOutcome.DEGRADATION:
        if claims_improvement and not claims_degradation:
            return ClaimCheck(
                claim_text=claim_text,
                is_correct=False,
                reason=(
                    f"Claim uses improvement language but {comparison.metric_name} "
                    f"structurally degraded (comparison={comparison.comparison_value}, "
                    f"baseline={comparison.baseline_value}, direction={comparison.direction})"
                ),
                comparison=comparison,
            )
        return ClaimCheck(
            claim_text=claim_text,
            is_correct=True,
            reason="Claim is consistent with structural degradation",
            comparison=comparison,
        )

    # TIE
    return ClaimCheck(
        claim_text=claim_text,
        is_correct=True,
        reason="Metric comparison is a tie; no directional claim to invalidate",
        comparison=comparison,
    )
