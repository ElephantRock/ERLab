"""Contradiction detection package."""

from backend.pipeline.claims.contradiction.models import ContradictionCandidate
from backend.pipeline.claims.contradiction.detector import ContradictionDetector

__all__ = ["ContradictionCandidate", "ContradictionDetector"]
