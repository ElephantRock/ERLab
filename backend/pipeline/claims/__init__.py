"""Claim extraction engine for decomposing paper text into typed claims."""

from backend.pipeline.claims.extractor import ClaimExtractor
from backend.pipeline.claims.models import Claim, ClaimType

__all__ = [
    "Claim",
    "ClaimType",
    "ClaimExtractor",
]
