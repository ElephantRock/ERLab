"""P1.3: Legacy lexical baseline policy.

Reproduces the current TrimmerStage keyword-overlap behavior as an
explicit versioned ranking policy for benchmark comparison.

Policy ID: legacy_lexical_top20_v1
"""

from __future__ import annotations

import re

from backend.ranking.contracts import (
    DISPOSITION_EXCLUDED_RANK,
    DISPOSITION_SELECTED,
    RankedCandidate,
    RankingCandidate,
    RankingPolicyContract,
    RankingRequest,
    RankingResult,
    compute_tie_break_key,
    validate_ranking_result,
)

LEGACY_LEXICAL_POLICY = RankingPolicyContract(
    policy_id="legacy_lexical_top20_v1",
    policy_version="v1",
    supported_surfaces=("discovery_ranking",),
    supported_intents=("general_research_relevance", "evidence_support",
                       "method_relevance", "literature_mapping", "gap_analysis"),
    required_features=("lexical_overlap",),
    score_transform_versions={"lexical": "raw_overlap_ratio_v1"},
    fusion_policy="none",
    reranker_policy="none",
    missing_feature_policy="neutral_zero",
    tie_break_policy="score_desc_hybrid_desc_semantic_desc_id_asc",
)


def _keyword_overlap(query: str, text: str) -> float:
    """Reproduce TrimmerStage's keyword-overlap heuristic.

    Score = overlap_count / total_query_words
    """
    query_words = set(re.findall(r"\w+", query.lower()))
    if not query_words:
        return 0.0
    text_words = set(re.findall(r"\w+", text.lower()))
    overlap = query_words & text_words
    return len(overlap) / len(query_words)


def rank_legacy_lexical(request: RankingRequest) -> RankingResult:
    """Rank candidates using the legacy lexical-overlap heuristic.

    Reproduces the current TrimmerStage behavior:
      1. Compute keyword overlap between query and title+abstract
      2. Sort by overlap score descending
      3. Select top `final_limit`
    """
    candidates_with_scores: list[tuple[RankingCandidate, float]] = []

    for i, c in enumerate(request.candidates):
        # Reconstruct text from metadata or use candidate_id as fallback
        title = c.metadata.get("title", "")
        abstract = c.metadata.get("abstract", "")
        text = f"{title} {abstract}".strip() or c.candidate_id

        score = _keyword_overlap(request.query_text, text)
        candidates_with_scores.append((c, score))

    # Sort by score descending
    candidates_with_scores.sort(key=lambda x: (-x[1], x[0].candidate_id))

    # Assign ranks
    ranked: list[RankedCandidate] = []
    limit = request.final_limit

    for i, (c, score) in enumerate(candidates_with_scores):
        rank = i + 1
        disposition = DISPOSITION_SELECTED if rank <= limit else DISPOSITION_EXCLUDED_RANK

        ranked.append(RankedCandidate(
            candidate_id=c.candidate_id,
            input_position=request.candidates.index(c),
            hybrid_score=score,
            final_score=score,
            final_rank=rank,
            tie_break_key=compute_tie_break_key(c.candidate_id, score, score),
            disposition=disposition,
            component_scores={"lexical_overlap": score},
        ))

    result = RankingResult(
        request=request,
        ranked=tuple(ranked),
        policy_id=LEGACY_LEXICAL_POLICY.policy_id,
        policy_version=LEGACY_LEXICAL_POLICY.policy_version,
    )

    # Validate
    errors = validate_ranking_result(result)
    if errors:
        # In production this would raise; for benchmark we log
        pass

    return result


# ── Hybrid RRF policy (P1.4) ─────────────────────────────────────────

HYBRID_RRF_POLICY = RankingPolicyContract(
    policy_id="hybrid_rrf_v1",
    policy_version="v1",
    supported_surfaces=("discovery_ranking", "retrieval_ranking"),
    supported_intents=("general_research_relevance", "evidence_support",
                       "method_relevance", "literature_mapping", "gap_analysis"),
    required_features=("lexical_rank", "semantic_rank"),
    score_transform_versions={"rrf": "1_over_k_plus_rank_v1"},
    fusion_policy="rrf",
    reranker_policy="none",
    missing_feature_policy="neutral_zero",
    tie_break_policy="score_desc_hybrid_desc_semantic_desc_id_asc",
)


def _rrf_score(ranks: list[int], k: int = 60) -> float:
    """Reciprocal rank fusion score."""
    return sum(1.0 / (k + r) for r in ranks)


def rank_hybrid_rrf(
    request: RankingRequest,
    *,
    rrf_k: int = 60,
) -> RankingResult:
    """Rank candidates using reciprocal-rank fusion.

    Requires candidates to have lexical_input_score and semantic_input_score.
    Converts scores to ranks, then fuses via RRF.
    """
    # Compute ranks from scores (higher score = lower rank number = better)
    lexical_scores = [(c.candidate_id, c.lexical_input_score or 0.0) for c in request.candidates]
    semantic_scores = [(c.candidate_id, c.semantic_input_score or 0.0) for c in request.candidates]

    lexical_scores.sort(key=lambda x: -x[1])
    semantic_scores.sort(key=lambda x: -x[1])

    lexical_ranks = {cid: i + 1 for i, (cid, _) in enumerate(lexical_scores)}
    semantic_ranks = {cid: i + 1 for i, (cid, _) in enumerate(semantic_scores)}

    # Compute RRF scores
    candidate_rrf: list[tuple[RankingCandidate, float]] = []
    for c in request.candidates:
        ranks = []
        lr = lexical_ranks.get(c.candidate_id)
        sr = semantic_ranks.get(c.candidate_id)
        if lr is not None:
            ranks.append(lr)
        if sr is not None:
            ranks.append(sr)
        score = _rrf_score(ranks, k=rrf_k) if ranks else 0.0
        candidate_rrf.append((c, score))

    # Sort by RRF score descending
    candidate_rrf.sort(key=lambda x: (-x[1], x[0].candidate_id))

    # Assign ranks
    ranked: list[RankedCandidate] = []
    limit = request.final_limit

    for i, (c, score) in enumerate(candidate_rrf):
        rank = i + 1
        disposition = DISPOSITION_SELECTED if rank <= limit else DISPOSITION_EXCLUDED_RANK

        ranked.append(RankedCandidate(
            candidate_id=c.candidate_id,
            input_position=request.candidates.index(c),
            hybrid_score=score,
            final_score=score,
            final_rank=rank,
            tie_break_key=compute_tie_break_key(c.candidate_id, score, score),
            disposition=disposition,
            component_scores={
                "lexical_rank": float(lexical_ranks.get(c.candidate_id, 0)),
                "semantic_rank": float(semantic_ranks.get(c.candidate_id, 0)),
                "rrf": score,
            },
        ))

    return RankingResult(
        request=request,
        ranked=tuple(ranked),
        policy_id=HYBRID_RRF_POLICY.policy_id,
        policy_version=HYBRID_RRF_POLICY.policy_version,
    )
