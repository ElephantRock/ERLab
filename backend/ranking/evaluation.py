"""P1.7: Ranking evaluation metrics.

Computes nDCG@k, MRR@k, Precision@k for ranking benchmark evaluation.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from backend.ranking.benchmark_cases import BenchmarkCase
from backend.ranking.contracts import RankingResult


@dataclass(frozen=True)
class RankingMetrics:
    """Metrics for one benchmark case."""

    case_id: str
    ndcg_at_5: float
    ndcg_at_10: float
    mrr_at_10: float
    precision_at_5: float
    recall_at_20: float


def _dcg_at_k(grades: Sequence[int], k: int) -> float:
    """Discounted Cumulative Gain at k."""
    dcg = 0.0
    for i, g in enumerate(grades[:k]):
        dcg += (2 ** g - 1) / math.log2(i + 2)
    return dcg


def _ndcg_at_k(ranked_grades: Sequence[int], k: int) -> float:
    """Normalized DCG at k."""
    dcg = _dcg_at_k(ranked_grades, k)
    ideal = sorted(ranked_grades, reverse=True)
    idcg = _dcg_at_k(ideal, k)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def _mrr_at_k(ranked_grades: Sequence[int], k: int) -> float:
    """Mean Reciprocal Rank at k."""
    for i, g in enumerate(ranked_grades[:k]):
        if g > 0:
            return 1.0 / (i + 1)
    return 0.0


def _precision_at_k(ranked_grades: Sequence[int], k: int, threshold: int = 1) -> float:
    """Precision at k (fraction of top-k that are relevant)."""
    if k == 0:
        return 0.0
    relevant = sum(1 for g in ranked_grades[:k] if g >= threshold)
    return relevant / k


def _recall_at_k(ranked_grades: Sequence[int], k: int, all_grades: Sequence[int],
                 threshold: int = 1) -> float:
    """Recall at k."""
    total_relevant = sum(1 for g in all_grades if g >= threshold)
    if total_relevant == 0:
        return 1.0
    retrieved_relevant = sum(1 for g in ranked_grades[:k] if g >= threshold)
    return retrieved_relevant / total_relevant


def evaluate_ranking(
    case: BenchmarkCase,
    result: RankingResult,
) -> RankingMetrics:
    """Evaluate one ranking result against benchmark judgments."""
    # Get grades in ranked order
    ranked_grades: list[int] = []
    all_grades: list[int] = []

    for rc in result.ranked:
        j = case.judgments.get(rc.candidate_id)
        grade = j.grade if j else 0
        ranked_grades.append(grade)

    for c in case.candidates:
        j = case.judgments.get(c.candidate_id)
        all_grades.append(j.grade if j else 0)

    return RankingMetrics(
        case_id=case.case_id,
        ndcg_at_5=_ndcg_at_k(ranked_grades, 5),
        ndcg_at_10=_ndcg_at_k(ranked_grades, 10),
        mrr_at_10=_mrr_at_k(ranked_grades, 10),
        precision_at_5=_precision_at_k(ranked_grades, 5),
        recall_at_20=_recall_at_k(ranked_grades, 20, all_grades),
    )


def macro_average(metrics: list[RankingMetrics]) -> dict[str, float]:
    """Compute macro averages across cases."""
    if not metrics:
        return {"ndcg_at_5": 0, "ndcg_at_10": 0, "mrr_at_10": 0, "precision_at_5": 0, "recall_at_20": 0}

    n = len(metrics)
    return {
        "ndcg_at_5": sum(m.ndcg_at_5 for m in metrics) / n,
        "ndcg_at_10": sum(m.ndcg_at_10 for m in metrics) / n,
        "mrr_at_10": sum(m.mrr_at_10 for m in metrics) / n,
        "precision_at_5": sum(m.precision_at_5 for m in metrics) / n,
        "recall_at_20": sum(m.recall_at_20 for m in metrics) / n,
    }
