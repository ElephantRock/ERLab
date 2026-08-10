"""Curation package — rule-based paper filtering and ranking."""

from backend.pipeline.curation.engine import CurationEngine
from backend.pipeline.curation.models import CurationRule

__all__ = ["CurationRule", "CurationEngine"]
