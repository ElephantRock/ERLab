"""Simple Claim Corroboration Checker.

Checks if a new claim's values are corroborated by existing claims in the DB.
20-line implementation that catches outlier claims without statistical infrastructure.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def check_corroboration(
    claim_metric: str,
    claim_dataset: str,
    claim_value: float,
    known_claims: list[dict],
    tolerance: float = 0.05,
    min_corroborations: int = 2,
) -> str | None:
    """Check if other papers report similar values for the same metric+dataset.

    Args:
        claim_metric: e.g. "accuracy", "F1", "BLEU"
        claim_dataset: e.g. "SQuAD", "ImageNet"
        claim_value: numeric value of the new claim
        known_claims: list of dicts with keys: metric, dataset, value
        tolerance: max relative difference to consider "similar" (default 5%)
        min_corroborations: how many similar claims needed to flag outliers

    Returns:
        Warning string if claim appears to be an outlier, None otherwise.
    """
    similar = [
        k for k in known_claims
        if k.get("metric", "").lower() == claim_metric.lower()
        and k.get("dataset", "").lower() == claim_dataset.lower()
    ]

    if len(similar) < min_corroborations:
        return None  # Not enough data to corroborate

    # Check if claim value is close to any known values
    for k in similar:
        known_val = k.get("value", 0)
        if known_val == 0:
            continue
        rel_diff = abs(claim_value - known_val) / abs(known_val)
        if rel_diff <= tolerance:
            return None  # Claim is within expected range

    # All known values differ by more than tolerance → outlier
    avg_known = sum(k.get("value", 0) for k in similar) / len(similar)
    if avg_known == 0:
        return None

    rel_diff = abs(claim_value - avg_known) / abs(avg_known)
    return (
        f"Claim ({claim_value:.4f}) differs {rel_diff:.0%} from "
        f"{len(similar)} corroborated reports (~{avg_known:.4f}) "
        f"for {claim_metric}/{claim_dataset}"
    )
