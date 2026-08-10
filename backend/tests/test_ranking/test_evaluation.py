"""Tests for P1.7: ranking evaluation metrics."""

from __future__ import annotations

import pytest

from backend.ranking.benchmark_cases import ALL_DISCOVERY_CASES
from backend.ranking.contracts import (
    RankingCandidate,
    RankingRequest,
)
from backend.ranking.evaluation import (
    _dcg_at_k,
    _mrr_at_k,
    _ndcg_at_k,
    _precision_at_k,
    _recall_at_k,
    evaluate_ranking,
    macro_average,
)
from backend.ranking.policies import rank_legacy_lexical


class TestMetrics:
    def test_dcg_perfect_ranking(self):
        """Perfect ranking: grades in descending order."""
        assert _dcg_at_k([3, 2, 1, 0], 4) > 0

    def test_ndcg_perfect_is_1(self):
        """nDCG of ideal ordering is 1.0."""
        assert _ndcg_at_k([3, 2, 1, 0], 4) == pytest.approx(1.0)

    def test_ndcg_worst_is_0(self):
        """nDCG when all relevant are at the bottom is much lower."""
        grades = [0, 0, 3, 2]
        # With grades at positions 3,4 instead of 1,2, nDCG should be low
        assert _ndcg_at_k(grades, 4) < 0.6

    def test_mrr_first_relevant(self):
        assert _mrr_at_k([0, 3, 0], 3) == pytest.approx(0.5)

    def test_mrr_no_relevant(self):
        assert _mrr_at_k([0, 0, 0], 3) == 0.0

    def test_precision_at_5(self):
        assert _precision_at_k([3, 2, 0, 0, 0], 5) == pytest.approx(0.4)

    def test_recall_at_20(self):
        all_grades = [3, 2, 1, 0, 0]
        # All 3 relevant are in top 5
        assert _recall_at_k([3, 2, 1, 0, 0], 5, all_grades) == pytest.approx(1.0)


class TestEvaluateRanking:
    def test_evaluate_legacy_on_benchmark(self):
        """Evaluate the legacy policy on benchmark cases."""
        results = []
        for case in ALL_DISCOVERY_CASES:
            candidates = tuple(
                RankingCandidate(
                    candidate_id=c.candidate_id, target_kind="paper",
                    canonical_text_hash=c.content_hash,
                    metadata={"title": c.title, "abstract": c.abstract},
                )
                for c in case.candidates
            )
            request = RankingRequest(
                ranking_surface=case.ranking_surface,
                ranking_intent=case.ranking_intent,
                query_text=case.query_text,
                candidates=candidates,
                ranking_policy_id="legacy_lexical_top20_v1",
                final_limit=len(candidates),
            )
            result = rank_legacy_lexical(request)
            metrics = evaluate_ranking(case, result)
            results.append(metrics)

        assert len(results) == len(ALL_DISCOVERY_CASES)

        avg = macro_average(results)
        assert 0 <= avg["ndcg_at_10"] <= 1.0
        assert 0 <= avg["precision_at_5"] <= 1.0
        # Legacy lexical should not be perfect (lexical traps exist)
        assert avg["ndcg_at_10"] < 1.0
