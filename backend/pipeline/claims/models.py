"""Claim data models for the claim extraction engine.

Defines ClaimType enum and Claim dataclass used to decompose paper
abstracts into typed, structured claims.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class ClaimType(Enum):
    """Sole authority for claim categorization (A-01)."""

    METHOD = "METHOD"
    RESULT = "RESULT"
    LIMITATION = "LIMITATION"
    FUTURE_WORK = "FUTURE_WORK"
    COMPARISON = "COMPARISON"


@dataclass
class Claim:
    """A typed claim extracted from a research paper.

    Every Claim must have source_paper_id tracing it to the originating
    paper (HB-02). Only ClaimExtractor may create Claim objects (A-03).
    """

    # ── Required fields ──────────────────────────────────────────
    claim_type: ClaimType
    title: str
    description: str
    source_paper_id: str

    # ── Identity ─────────────────────────────────────────────────
    claim_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    source_section: str = "abstract"
    confidence: float = 0.5  # extractor's confidence (A-02)

    # ── METHOD-specific fields ───────────────────────────────────
    method_name: str | None = None
    method_category: str | None = None  # architecture|training|loss|data|inference
    constraints: dict | None = None

    # ── RESULT-specific fields ───────────────────────────────────
    dataset: str | None = None
    metric: str | None = None
    value: str | None = None  # kept as string: "95.2%", "0.87", etc.
    baseline_method: str | None = None
    baseline_value: str | None = None

    # ── LIMITATION-specific fields ───────────────────────────────
    limitation_category: str | None = None  # scale|generalization|compute|data|fairness
    acknowledged: bool | None = None

    # ── FUTURE_WORK-specific fields ──────────────────────────────
    feasibility: str | None = None  # high|medium|low
    potential_impact: str | None = None  # high|medium|low

    # ── COMPARISON-specific fields ───────────────────────────────
    compared_to: str | None = None
    relationship: str | None = None  # improves_on|different|contradicts|complements
