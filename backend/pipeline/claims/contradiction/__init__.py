"""Contradiction detection package."""

from backend.pipeline.claims.contradiction.detector import ContradictionDetector
from backend.pipeline.claims.contradiction.models import ContradictionCandidate

__all__ = ["ContradictionCandidate", "ContradictionDetector"]
