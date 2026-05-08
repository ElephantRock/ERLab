"""Contradiction detection models."""

from __future__ import annotations

from dataclasses import dataclass

from backend.pipeline.claims.models import Claim


@dataclass
class ContradictionCandidate:
    """A candidate contradiction between two claims from different papers."""
    claim_a: Claim
    claim_b: Claim
    metric: str
    dataset: str
    value_a: str
    value_b: str
    is_genuine: bool | None = None  # None = not yet verified by LLM
    explanation: str = ""
