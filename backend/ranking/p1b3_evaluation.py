"""P1B.3: Frozen policy evaluation against the governed embedding snapshot.

Evaluates the candidate ranking policies from Decision 2C against the frozen
v2 benchmark + frozen embedding snapshot:

    legacy_lexical_top20_v1   (keyword overlap — the production baseline)
    semantic_only_v1          (cosine similarity from snapshot vectors)
    hybrid_rrf_v1             (reciprocal rank fusion of lexical + semantic)
    hybrid_weighted_v1        (ONLY if weights frozen without held-out tuning)

Reports per the Gate 2 contract:
    - macro + per-case metrics (nDCG@5, nDCG@10, MRR@10, P@5, Recall@20)
    - paired bootstrap confidence intervals (vs legacy baseline)
    - per-slice breakdown (all 11 slice types)
    - per-domain and per-surface breakdown
    - latency per policy
    - exact-replay proof (run twice, confirm identical metrics)

Split discipline (frozen in Decision 3):
    - calibration + development: used for policy comparison + slice analysis
    - held_out: reported SEPARATELY, once, after selection. NOT used here
      for selection — only legacy baseline is reported on held_out as a
      reference; candidate policies are NOT evaluated on held_out until a
      production candidate is selected.

NO production policy is activated by this module. It only measures.
"""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backend.ranking.contracts import (
    RankingCandidate,
    RankingRequest,
    RankingResult,
)
from backend.ranking.embedding_snapshot import EmbeddingSnapshot
from backend.ranking.evaluation import (
    RankingMetrics,
    _mrr_at_k,
    _ndcg_at_k,
    _precision_at_k,
    _recall_at_k,
)
from backend.ranking.policies import (
    _keyword_overlap,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "docs" / "p1b_snapshot"

# Frozen RRF constant (matches the existing hybrid_rrf_v1 policy default).
# Per Decision 2C, this is frozen BEFORE any evaluation; not tuned on results.
FROZEN_RRF_K = 60

# Frozen final_limit (matches TrimmerStage's [:20] and the legacy policy).
FROZEN_FINAL_LIMIT = 20

# Frozen weights for the optional weighted policy — chosen a priori, NOT
# tuned on held-out. Equal weight (0.5/0.5) is the principled default when
# no tuning is permitted; we also report 0.7 lexical / 0.3 semantic and
# 0.3 lexical / 0.7 semantic as sensitivity, but ONLY 0.5/0.5 is a candidate.
FROZEN_WEIGHTED_LEXICAL = 0.5
FROZEN_WEIGHTED_SEMANTIC = 0.5


# ── Snapshot-backed semantic similarity ──────────────────────────────


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True)
class SnapshotSemanticScorer:
    """Computes query→candidate cosine similarity from frozen snapshot vectors."""

    snapshot: EmbeddingSnapshot

    def query_candidate_score(self, case_id: str, candidate_id: str) -> float | None:
        q = self.snapshot.get(case_id)
        c = self.snapshot.get(candidate_id)
        if q is None or c is None:
            return None
        if q.item_role != "query" or c.item_role != "candidate":
            return None
        return _cosine(q.vector, c.vector)


# ── Build RankingRequest from a frozen v2 case ──────────────────────


def _build_request(
    case,
    *,
    scorer: SnapshotSemanticScorer,
    include_semantic: bool,
    policy_id: str,
) -> RankingRequest:
    """Build a RankingRequest for one frozen v2 case.

    ``include_semantic`` controls whether semantic_input_score is populated
    (semantic_only and hybrid policies set True; legacy lexical sets False
    so the legacy policy reproduces pure keyword behavior).
    """
    candidates: list[RankingCandidate] = []
    for cand in case.candidates:
        title = cand.metadata.get("title", cand.title) if hasattr(cand, "metadata") else cand.title
        abstract = cand.abstract
        lex = _keyword_overlap(case.query_text, f"{cand.title} {cand.abstract}")
        sem = scorer.query_candidate_score(case.case_id, cand.candidate_id) if include_semantic else None
        candidates.append(RankingCandidate(
            candidate_id=cand.candidate_id,
            target_kind="paper",
            canonical_text_hash=cand.content_hash,
            lexical_input_score=lex,
            semantic_input_score=sem,
            metadata={"title": cand.title, "abstract": cand.abstract},
        ))
    return RankingRequest(
        ranking_surface=case.ranking_surface,
        ranking_intent=case.ranking_intent,
        query_text=case.query_text,
        candidates=tuple(candidates),
        ranking_policy_id=policy_id,
        final_limit=FROZEN_FINAL_LIMIT,
    )


# ── Semantic-only policy (P1B.3) ─────────────────────────────────────

SEMANTIC_ONLY_POLICY_ID = "semantic_only_v1"


def rank_semantic_only(request: RankingRequest) -> RankingResult:
    """Rank candidates purely by snapshot cosine similarity to the query.

    Requires semantic_input_score on every candidate. Missing semantic
    scores are treated as 0.0 (the missing_feature_policy='neutral_zero'
    from the contract).
    """
    scored = [(c, c.semantic_input_score or 0.0) for c in request.candidates]
    scored.sort(key=lambda x: (-x[1], x[0].candidate_id))

    ranked = []
    for i, (c, score) in enumerate(scored):
        rank = i + 1
        from backend.ranking.contracts import (
            DISPOSITION_EXCLUDED_RANK,
            DISPOSITION_SELECTED,
            RankedCandidate,
            compute_tie_break_key,
        )
        ranked.append(RankedCandidate(
            candidate_id=c.candidate_id,
            input_position=request.candidates.index(c),
            hybrid_score=score,
            final_score=score,
            final_rank=rank,
            tie_break_key=compute_tie_break_key(c.candidate_id, score, score, score),
            disposition=DISPOSITION_SELECTED if rank <= request.final_limit else DISPOSITION_EXCLUDED_RANK,
            component_scores={"semantic_cosine": score},
        ))
    from backend.ranking.contracts import RankingResult
    return RankingResult(
        request=request,
        ranked=tuple(ranked),
        policy_id=SEMANTIC_ONLY_POLICY_ID,
        policy_version="v1",
    )


# ── Hybrid weighted policy (optional, frozen weights) ────────────────

HYBRID_WEIGHTED_POLICY_ID = "hybrid_weighted_v1"


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def rank_hybrid_weighted(
    request: RankingRequest,
    *,
    lexical_weight: float = FROZEN_WEIGHTED_LEXICAL,
    semantic_weight: float = FROZEN_WEIGHTED_SEMANTIC,
) -> RankingResult:
    """Rank by frozen-weight fusion of min-max-normalized lexical + semantic.

    Weights are frozen a priori (0.5/0.5 by default) — NOT tuned on held-out.
    Per Decision 2C, this policy is only a candidate if the weights were
    frozen before any evaluation.
    """
    lex_raw = [c.lexical_input_score or 0.0 for c in request.candidates]
    sem_raw = [c.semantic_input_score or 0.0 for c in request.candidates]
    lex_n = _minmax(lex_raw)
    sem_n = _minmax(sem_raw)
    scored = []
    for i, c in enumerate(request.candidates):
        fused = lexical_weight * lex_n[i] + semantic_weight * sem_n[i]
        scored.append((c, fused))
    scored.sort(key=lambda x: (-x[1], x[0].candidate_id))

    from backend.ranking.contracts import (
        DISPOSITION_EXCLUDED_RANK,
        DISPOSITION_SELECTED,
        RankedCandidate,
        RankingResult,
        compute_tie_break_key,
    )
    ranked = []
    for i, (c, score) in enumerate(scored):
        rank = i + 1
        ranked.append(RankedCandidate(
            candidate_id=c.candidate_id,
            input_position=request.candidates.index(c),
            hybrid_score=score,
            final_score=score,
            final_rank=rank,
            tie_break_key=compute_tie_break_key(c.candidate_id, score, score),
            disposition=DISPOSITION_SELECTED if rank <= request.final_limit else DISPOSITION_EXCLUDED_RANK,
            component_scores={
                "lexical_norm": lex_n[i],
                "semantic_norm": sem_n[i],
                "weighted_fused": score,
            },
        ))
    return RankingResult(
        request=request,
        ranked=tuple(ranked),
        policy_id=HYBRID_WEIGHTED_POLICY_ID,
        policy_version="v1",
    )


# ── v2-aware evaluation ──────────────────────────────────────────────


def _grade_for(case, candidate_id: str) -> int:
    """Frozen adjudicated grade for a candidate in a frozen v2 case."""
    prov = case.judgments.get(candidate_id)
    return prov.final_grade() if prov else 0


def evaluate_v2(case, result: RankingResult) -> RankingMetrics:
    """Evaluate a ranking result against a frozen v2 case's adjudicated grades."""
    ranked_grades = [_grade_for(case, rc.candidate_id) for rc in result.ranked]
    all_grades = [_grade_for(case, c.candidate_id) for c in case.candidates]
    return RankingMetrics(
        case_id=case.case_id,
        ndcg_at_5=_ndcg_at_k(ranked_grades, 5),
        ndcg_at_10=_ndcg_at_k(ranked_grades, 10),
        mrr_at_10=_mrr_at_k(ranked_grades, 10),
        precision_at_5=_precision_at_k(ranked_grades, 5),
        recall_at_20=_recall_at_k(ranked_grades, 20, all_grades),
    )


# ── Paired bootstrap confidence interval ─────────────────────────────


def paired_bootstrap_ci(
    case_ids: list[str],
    policy_a_grades: dict[str, list[int]],  # case_id -> ranked grades
    policy_b_grades: dict[str, list[int]],
    metric_fn: Callable[[list[int], list[int]], float],  # (ranked, all) -> metric
    all_grades_by_case: dict[str, list[int]],
    *,
    n_bootstrap: int = 10000,
    seed: int = 20260721,
    alpha: float = 0.05,
) -> dict[str, float]:
    """Paired bootstrap CI on (policy_b - policy_a) per-case metric delta.

    Returns mean delta, lower bound, upper bound (95% CI by default), and
    the fraction of bootstrap samples where delta > 0.
    """
    rng = random.Random(seed)
    n = len(case_ids)
    if n == 0:
        return {"mean_delta": 0.0, "lower": 0.0, "upper": 0.0, "p_positive": 0.0, "n": 0}

    a_metrics = [
        metric_fn(policy_a_grades[cid], all_grades_by_case[cid]) for cid in case_ids
    ]
    b_metrics = [
        metric_fn(policy_b_grades[cid], all_grades_by_case[cid]) for cid in case_ids
    ]
    obs_delta = sum(b - a for a, b in zip(a_metrics, b_metrics)) / n

    deltas = []
    for _ in range(n_bootstrap):
        sampled_a, sampled_b = 0.0, 0.0
        for _ in range(n):
            idx = rng.randrange(n)
            sampled_a += a_metrics[idx]
            sampled_b += b_metrics[idx]
        deltas.append((sampled_b - sampled_a) / n)

    deltas.sort()
    lo_idx = int((alpha / 2) * n_bootstrap)
    hi_idx = int((1 - alpha / 2) * n_bootstrap)
    p_pos = sum(1 for d in deltas if d > 0) / n_bootstrap
    return {
        "mean_delta": round(obs_delta, 6),
        "lower": round(deltas[lo_idx], 6),
        "upper": round(deltas[hi_idx], 6),
        "p_positive": round(p_pos, 4),
        "n": n,
    }


# ── Policy runner ────────────────────────────────────────────────────


@dataclass
class PolicyRunResult:
    policy_id: str
    metrics_by_case: dict[str, RankingMetrics]
    elapsed_seconds: float
    # for bootstrap: case_id -> ranked grades in order
    ranked_grades_by_case: dict[str, list[int]]


def _run_policy(
    policy_id: str,
    cases,
    scorer: SnapshotSemanticScorer,
    rank_fn: Callable[[RankingRequest], RankingResult],
    *,
    include_semantic: bool,
) -> PolicyRunResult:
    metrics: dict[str, RankingMetrics] = {}
    ranked_grades: dict[str, list[int]] = {}
    t0 = time.perf_counter()
    for case in cases:
        req = _build_request(case, scorer=scorer, include_semantic=include_semantic, policy_id=policy_id)
        result = rank_fn(req)
        m = evaluate_v2(case, result)
        metrics[case.case_id] = m
        ranked_grades[case.case_id] = [_grade_for(case, rc.candidate_id) for rc in result.ranked]
    elapsed = time.perf_counter() - t0
    return PolicyRunResult(
        policy_id=policy_id, metrics_by_case=metrics, elapsed_seconds=elapsed,
        ranked_grades_by_case=ranked_grades,
    )


def macro_average(metrics: dict[str, RankingMetrics]) -> dict[str, float]:
    if not metrics:
        return {}
    n = len(metrics)
    return {
        "ndcg_at_5": round(sum(m.ndcg_at_5 for m in metrics.values()) / n, 4),
        "ndcg_at_10": round(sum(m.ndcg_at_10 for m in metrics.values()) / n, 4),
        "mrr_at_10": round(sum(m.mrr_at_10 for m in metrics.values()) / n, 4),
        "precision_at_5": round(sum(m.precision_at_5 for m in metrics.values()) / n, 4),
        "recall_at_20": round(sum(m.recall_at_20 for m in metrics.values()) / n, 4),
    }
