"""Temporal decay for citation and claim confidence scores (B159).

Older citations decay in confidence over time, reflecting the reality
that research relevance diminishes. New citations get a freshness boost.
"""
from __future__ import annotations

import math
from datetime import datetime


def decay_factor(age_days: float, half_life: float = 365.0) -> float:
    """Exponential decay factor based on citation age.

    Args:
        age_days: Days since publication.
        half_life: Days for confidence to halve. Default 365 (1 year).

    Returns:
        Decay factor in [0.0, 1.0]. 1.0 = brand new, ~0.5 = 1 year old.

    Examples:
        >>> decay_factor(0)     # brand new
        1.0
        >>> round(decay_factor(365), 2)  # 1 year old
        0.5
        >>> round(decay_factor(730), 2)  # 2 years old
        0.25
    """
    if age_days <= 0:
        return 1.0
    if half_life <= 0:
        return 1.0
    return math.exp(-0.693 * age_days / half_life)  # ln(2) ≈ 0.693


def apply_decay(confidence: float, year: int | None, reference_year: int | None = None) -> float:
    """Apply temporal decay to a confidence score based on publication year.

    Args:
        confidence: Original confidence (0.0-1.0).
        year: Publication year of the cited work.
        reference_year: Current year for computing age. Defaults to now.

    Returns:
        Decayed confidence, clamped to [0.0, 1.0].
    """
    if year is None or confidence <= 0:
        return confidence

    ref = reference_year or datetime.utcnow().year
    age_days = max(0, (ref - year) * 365.25)
    decay = decay_factor(age_days, half_life=365.0 * 3)  # 3-year half-life for research
    return max(0.0, min(1.0, confidence * decay))
