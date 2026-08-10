"""Claim extraction package — structured claim decomposition from research papers."""

from backend.pipeline.claims.extractor import ClaimExtractor
from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.store import ClaimStore

__all__ = ["Claim", "ClaimType", "ClaimExtractor", "ClaimStore"]
