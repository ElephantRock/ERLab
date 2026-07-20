"""P1.2: Canonical ranking contracts.

Frozen dataclasses for ranking input, output, policy, and evidence.
No ranking policy may mutate the candidate or its provenance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


# ── Ranking surfaces ─────────────────────────────────────────────────

SURFACE_DISCOVERY = "discovery_ranking"
SURFACE_RETRIEVAL = "retrieval_ranking"

# ── Dispositions ─────────────────────────────────────────────────────

DISPOSITION_SELECTED = "selected"
DISPOSITION_EXCLUDED_RANK = "excluded_by_rank"
DISPOSITION_EXCLUDED_INVALID = "excluded_invalid_score"
DISPOSITION_DUPLICATE = "duplicate_near"

# ── Ranking schema version ───────────────────────────────────────────

RANKING_SCHEMA_V1 = "ranking_v1"


@dataclass(frozen=True)
class RankingCandidate:
    """Immutable ranking input candidate. No mutation permitted."""

    candidate_id: str
    target_kind: str  # "paper" | "chunk" | "evidence"
    canonical_text_hash: str

    lexical_input_score: float | None = None
    semantic_input_score: float | None = None

    discovery_source_count: int | None = None
    discovery_query_count: int | None = None
    upstream_rank: int | None = None

    metadata: Mapping[str, object] = field(default_factory=dict, hash=False)


@dataclass(frozen=True)
class RankingRequest:
    """One ranking operation request."""

    ranking_surface: str  # discovery_ranking | retrieval_ranking
    ranking_intent: str
    query_text: str
    candidates: tuple[RankingCandidate, ...]
    ranking_policy_id: str
    final_limit: int
    configuration_snapshot_id: str | None = None


@dataclass(frozen=True)
class RankedCandidate:
    """One ranked output candidate with complete score evidence."""

    candidate_id: str
    input_position: int
    hybrid_score: float
    final_score: float
    final_rank: int
    tie_break_key: str
    disposition: str

    component_scores: Mapping[str, float] = field(default_factory=dict, hash=False)
    reranker_score: float | None = None


@dataclass(frozen=True)
class RankingResult:
    """Complete ranking output for one request."""

    request: RankingRequest
    ranked: tuple[RankedCandidate, ...]
    policy_id: str
    policy_version: str
    fallback_used: str | None = None  # None if no fallback


@dataclass(frozen=True)
class RankingPolicyContract:
    """Versioned policy contract."""

    policy_id: str
    policy_version: str
    supported_surfaces: tuple[str, ...]
    supported_intents: tuple[str, ...]

    required_features: tuple[str, ...]
    score_transform_versions: Mapping[str, str] = field(default_factory=dict, hash=False)
    fusion_policy: str = "rrf"
    reranker_policy: str = "none"
    missing_feature_policy: str = "neutral_zero"
    tie_break_policy: str = "score_desc_hybrid_desc_semantic_desc_id_asc"


# ── Score validation ─────────────────────────────────────────────────


class RankingValidationError(Exception):
    """Raised when ranking output fails validation."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def validate_ranked_candidate(rc: RankedCandidate) -> list[str]:
    """Validate a ranked candidate. Returns list of error strings (empty = valid)."""
    errors: list[str] = []

    if math.isnan(rc.hybrid_score):
        errors.append(f"{rc.candidate_id}: hybrid_score is NaN")
    if math.isnan(rc.final_score):
        errors.append(f"{rc.candidate_id}: final_score is NaN")
    if math.isinf(rc.hybrid_score):
        errors.append(f"{rc.candidate_id}: hybrid_score is infinite")
    if math.isinf(rc.final_score):
        errors.append(f"{rc.candidate_id}: final_score is infinite")

    if rc.reranker_score is not None:
        if math.isnan(rc.reranker_score):
            errors.append(f"{rc.candidate_id}: reranker_score is NaN")
        if math.isinf(rc.reranker_score):
            errors.append(f"{rc.candidate_id}: reranker_score is infinite")

    for name, score in rc.component_scores.items():
        if score is not None and (math.isnan(score) or math.isinf(score)):
            errors.append(f"{rc.candidate_id}: component {name} is NaN/inf")

    return errors


def validate_ranking_result(result: RankingResult) -> list[str]:
    """Validate a complete ranking result."""
    errors: list[str] = []

    # Check no duplicate candidate IDs
    ids = [r.candidate_id for r in result.ranked]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_candidate_ids")

    # Check all candidates from request appear in output
    request_ids = {c.candidate_id for c in result.request.candidates}
    output_ids = {r.candidate_id for r in result.ranked}
    missing = request_ids - output_ids
    if missing:
        errors.append(f"missing_candidates: {missing}")

    extra = output_ids - request_ids
    if extra:
        errors.append(f"extra_candidates: {extra}")

    # Check each candidate
    for rc in result.ranked:
        errors.extend(validate_ranked_candidate(rc))

    # Check final ranks for selected candidates are contiguous starting at 1
    selected = [r for r in result.ranked if r.disposition == DISPOSITION_SELECTED]
    selected_ranks = sorted(r.final_rank for r in selected)
    if selected_ranks:
        expected = list(range(1, len(selected_ranks) + 1))
        if selected_ranks != expected:
            errors.append(f"non_contiguous_selected_ranks: {selected_ranks}")

    return errors


# ── Tie-break key computation ────────────────────────────────────────


def compute_tie_break_key(
    candidate_id: str,
    final_score: float,
    hybrid_score: float,
    semantic_score: float | None = None,
) -> str:
    """Compute a deterministic tie-break key.

    Order: final_score desc → hybrid desc → semantic desc → candidate_id asc

    Uses zero-padded score values so string comparison produces the
    correct descending order. Format: 10-digit integer part + 10-digit
    decimal, guaranteed to sort correctly for scores in [0, 1).
    """
    sem = semantic_score if semantic_score is not None else 0.0

    def _fmt(score: float) -> str:
        # Convert to a string that sorts descending when read as ascending.
        # For scores in [0, 1): "1.0000000000" - f"{score:.10f}" gives
        # lexicographic descending when the values are themselves descending.
        # We use complement: (1.0 - score) formatted to fixed width.
        clamped = max(0.0, min(1.0, score))
        return f"{1.0 - clamped:.10f}"

    return f"{_fmt(final_score)}_{_fmt(hybrid_score)}_{_fmt(sem)}_{candidate_id}"
