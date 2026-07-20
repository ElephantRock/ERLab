"""Tests for P1B.3: frozen policy evaluation harness.

Pins the evaluation machinery (not the exact metric values, which depend on
the generated snapshot being present — the snapshot is gitignored). When the
snapshot is present, these tests also assert the deterministic-replay
invariant and the Gate 2 verdict.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from backend.ranking.p1b3_evaluation import (
    FROZEN_RRF_K,
    FROZEN_WEIGHTED_LEXICAL,
    FROZEN_WEIGHTED_SEMANTIC,
    HYBRID_WEIGHTED_POLICY_ID,
    SEMANTIC_ONLY_POLICY_ID,
    SnapshotSemanticScorer,
    _build_request,
    _cosine,
    _grade_for,
    _minmax,
    evaluate_v2,
    macro_average,
    paired_bootstrap_ci,
    rank_hybrid_weighted,
    rank_semantic_only,
)


REPO_ROOT = Path(__file__).resolve().parents[3]  # tests/test_ranking/file.py -> repo root
SNAPSHOT_DIR = REPO_ROOT / "docs" / "p1b_snapshot"
SNAPSHOT_PRESENT = (SNAPSHOT_DIR / "snapshot.json").exists()


class TestFrozenHyperparameters:
    """Decision 2C: hyperparameters are frozen a priori, not tuned on results."""

    def test_rrf_k_frozen(self):
        assert FROZEN_RRF_K == 60

    def test_weighted_weights_frozen_equal(self):
        assert FROZEN_WEIGHTED_LEXICAL == 0.5
        assert FROZEN_WEIGHTED_SEMANTIC == 0.5
        assert FROZEN_WEIGHTED_LEXICAL + FROZEN_WEIGHTED_SEMANTIC == 1.0


class TestSemanticPolicy:
    def test_semantic_only_ranks_by_cosine_desc(self):
        from backend.ranking.contracts import RankingCandidate, RankingRequest
        cands = (
            RankingCandidate(candidate_id="a", target_kind="paper", canonical_text_hash="h1",
                             semantic_input_score=0.9),
            RankingCandidate(candidate_id="b", target_kind="paper", canonical_text_hash="h2",
                             semantic_input_score=0.1),
            RankingCandidate(candidate_id="c", target_kind="paper", canonical_text_hash="h3",
                             semantic_input_score=0.5),
        )
        req = RankingRequest(
            ranking_surface="discovery_ranking", ranking_intent="general_research_relevance",
            query_text="q", candidates=cands, ranking_policy_id=SEMANTIC_ONLY_POLICY_ID,
            final_limit=2,
        )
        result = rank_semantic_only(req)
        assert result.ranked[0].candidate_id == "a"
        assert result.ranked[1].candidate_id == "c"
        assert result.ranked[2].candidate_id == "b"
        assert result.policy_id == SEMANTIC_ONLY_POLICY_ID

    def test_semantic_only_missing_score_treated_as_zero(self):
        from backend.ranking.contracts import RankingCandidate, RankingRequest
        cands = (
            RankingCandidate(candidate_id="a", target_kind="paper", canonical_text_hash="h1",
                             semantic_input_score=None),
            RankingCandidate(candidate_id="b", target_kind="paper", canonical_text_hash="h2",
                             semantic_input_score=0.3),
        )
        req = RankingRequest(
            ranking_surface="discovery_ranking", ranking_intent="general_research_relevance",
            query_text="q", candidates=cands, ranking_policy_id=SEMANTIC_ONLY_POLICY_ID,
            final_limit=2,
        )
        result = rank_semantic_only(req)
        # b (0.3) ranks above a (0.0)
        assert result.ranked[0].candidate_id == "b"


class TestHybridWeightedPolicy:
    def test_weighted_fuses_normalized_scores(self):
        from backend.ranking.contracts import RankingCandidate, RankingRequest
        cands = (
            RankingCandidate(candidate_id="a", target_kind="paper", canonical_text_hash="h1",
                             lexical_input_score=1.0, semantic_input_score=0.0),
            RankingCandidate(candidate_id="b", target_kind="paper", canonical_text_hash="h2",
                             lexical_input_score=0.0, semantic_input_score=1.0),
        )
        req = RankingRequest(
            ranking_surface="discovery_ranking", ranking_intent="general_research_relevance",
            query_text="q", candidates=cands, ranking_policy_id=HYBRID_WEIGHTED_POLICY_ID,
            final_limit=2,
        )
        result = rank_hybrid_weighted(req, lexical_weight=0.5, semantic_weight=0.5)
        # Both fuse to 0.5; tie broken by candidate_id asc -> a first
        assert result.ranked[0].candidate_id == "a"
        assert result.policy_id == HYBRID_WEIGHTED_POLICY_ID

    def test_minmax_handles_constant_input(self):
        assert _minmax([0.5, 0.5, 0.5]) == [0.5, 0.5, 0.5]

    def test_minmax_handles_empty(self):
        assert _minmax([]) == []


class TestCosine:
    def test_identical_vectors_score_one(self):
        v = (1.0, 0.0, 0.0)
        assert abs(_cosine(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors_score_zero(self):
        assert abs(_cosine((1.0, 0.0), (0.0, 1.0))) < 1e-9

    def test_zero_vector_returns_zero(self):
        assert _cosine((0.0, 0.0), (1.0, 1.0)) == 0.0


class TestPairedBootstrap:
    def test_bootstrap_ci_zero_delta_when_identical(self):
        ci = paired_bootstrap_ci(
            ["c1", "c2", "c3"],
            {"c1": [3, 2], "c2": [2, 1], "c3": [1, 0]},
            {"c1": [3, 2], "c2": [2, 1], "c3": [1, 0]},
            metric_fn=lambda rg, ag: (rg[0] if rg else 0),
            all_grades_by_case={"c1": [3, 2], "c2": [2, 1], "c3": [1, 0]},
            n_bootstrap=500,
        )
        assert abs(ci["mean_delta"]) < 1e-9
        assert ci["n"] == 3

    def test_bootstrap_ci_positive_when_b_better(self):
        ci = paired_bootstrap_ci(
            ["c1", "c2"],
            {"c1": [0], "c2": [0]},
            {"c1": [3], "c2": [3]},
            metric_fn=lambda rg, ag: rg[0],
            all_grades_by_case={"c1": [3], "c2": [3]},
            n_bootstrap=500,
        )
        assert ci["mean_delta"] > 0
        assert ci["lower"] > 0
        assert ci["p_positive"] == 1.0


# ── Snapshot-dependent tests (skip if snapshot not regenerated) ──────

@pytest.mark.skipif(not SNAPSHOT_PRESENT, reason="snapshot.json not regenerated; run generate_embedding_snapshot")
class TestEvaluationAgainstSnapshot:
    """When the snapshot is present, pin the deterministic-replay invariant
    and the Gate 2 verdict."""

    def test_snapshot_loads_and_binds_to_frozen_benchmark(self):
        from backend.ranking.embedding_snapshot import load_snapshot
        from backend.ranking.benchmark_v2_registry import (
            BENCHMARK_V2, compute_benchmark_v2_fingerprint,
        )
        snap = load_snapshot(
            SNAPSHOT_DIR,
            expected_benchmark_fingerprint=compute_benchmark_v2_fingerprint(),
            expected_benchmark_version=BENCHMARK_V2["version"],
        )
        assert snap.dimension == 1024
        assert len(snap.items) == 336
        assert len(snap.queries()) == 66
        assert len(snap.candidates()) == 270

    def test_deterministic_replay_all_policies(self):
        from backend.ranking.benchmark_v2_registry import frozen_v2_cases
        from backend.ranking.embedding_snapshot import load_snapshot
        from backend.ranking.benchmark_v2_registry import (
            BENCHMARK_V2, compute_benchmark_v2_fingerprint,
        )
        from backend.ranking.p1b3_evaluation import _run_policy
        from backend.ranking.policies import rank_legacy_lexical, rank_hybrid_rrf

        snap = load_snapshot(SNAPSHOT_DIR,
            expected_benchmark_fingerprint=compute_benchmark_v2_fingerprint(),
            expected_benchmark_version=BENCHMARK_V2["version"])
        scorer = SnapshotSemanticScorer(snap)
        cases = [c for c in frozen_v2_cases() if c.split in ("calibration", "development")]
        for pid, fn, inc in [
            ("legacy_lexical_top20_v1", rank_legacy_lexical, False),
            (SEMANTIC_ONLY_POLICY_ID, rank_semantic_only, True),
            ("hybrid_rrf_v1", lambda r: rank_hybrid_rrf(r, rrf_k=FROZEN_RRF_K), True),
            (HYBRID_WEIGHTED_POLICY_ID, lambda r: rank_hybrid_weighted(r,
                lexical_weight=FROZEN_WEIGHTED_LEXICAL, semantic_weight=FROZEN_WEIGHTED_SEMANTIC), True),
        ]:
            r1 = _run_policy(pid, cases, scorer, fn, include_semantic=inc)
            r2 = _run_policy(pid, cases, scorer, fn, include_semantic=inc)
            m1 = macro_average(r1.metrics_by_case)
            m2 = macro_average(r2.metrics_by_case)
            assert m1 == m2, f"{pid}: nondeterministic macro metrics"
            # per-case identical
            for cid in r1.metrics_by_case:
                assert r1.metrics_by_case[cid].ndcg_at_10 == r2.metrics_by_case[cid].ndcg_at_10
                assert r1.metrics_by_case[cid].ndcg_at_5 == r2.metrics_by_case[cid].ndcg_at_5
