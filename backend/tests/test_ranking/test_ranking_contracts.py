"""Tests for P1.2: canonical ranking contracts."""

from __future__ import annotations

import math
import pytest

from backend.ranking.contracts import (
    DISPOSITION_EXCLUDED_INVALID,
    DISPOSITION_SELECTED,
    RankingCandidate,
    RankingRequest,
    RankingResult,
    RankedCandidate,
    compute_tie_break_key,
    validate_ranked_candidate,
    validate_ranking_result,
)


def _make_candidate(cid: str, lexical=None, semantic=None) -> RankingCandidate:
    return RankingCandidate(
        candidate_id=cid, target_kind="paper",
        canonical_text_hash="h" * 64,
        lexical_input_score=lexical, semantic_input_score=semantic,
    )


def _make_ranked(cid: str, rank: int, final: float, hybrid: float,
                 disposition=DISPOSITION_SELECTED, input_pos: int = 0) -> RankedCandidate:
    return RankedCandidate(
        candidate_id=cid, input_position=input_pos,
        component_scores={"lexical": 0.5},
        hybrid_score=hybrid, reranker_score=None, final_score=final,
        final_rank=rank, tie_break_key=compute_tie_break_key(cid, final, hybrid),
        disposition=disposition,
    )


class TestScoreValidation:
    def test_nan_rejected(self):
        rc = _make_ranked("a", 1, float("nan"), 0.5)
        errors = validate_ranked_candidate(rc)
        assert any("NaN" in e for e in errors)

    def test_inf_rejected(self):
        rc = _make_ranked("a", 1, float("inf"), 0.5)
        errors = validate_ranked_candidate(rc)
        assert any("infinite" in e for e in errors)

    def test_valid_scores_pass(self):
        rc = _make_ranked("a", 1, 0.9, 0.8)
        errors = validate_ranked_candidate(rc)
        assert not errors


class TestResultValidation:
    def test_duplicate_candidate_ids_rejected(self):
        request = RankingRequest(
            ranking_surface="discovery_ranking",
            ranking_intent="general_research_relevance",
            query_text="test",
            candidates=(_make_candidate("a"), _make_candidate("b")),
            ranking_policy_id="test",
            final_limit=2,
        )
        result = RankingResult(
            request=request,
            ranked=(_make_ranked("a", 1, 0.9, 0.8), _make_ranked("a", 2, 0.7, 0.6)),
            policy_id="test", policy_version="v1",
        )
        errors = validate_ranking_result(result)
        assert "duplicate_candidate_ids" in errors

    def test_missing_candidates_rejected(self):
        request = RankingRequest(
            ranking_surface="discovery_ranking",
            ranking_intent="general_research_relevance",
            query_text="test",
            candidates=(_make_candidate("a"), _make_candidate("b"), _make_candidate("c")),
            ranking_policy_id="test",
            final_limit=2,
        )
        result = RankingResult(
            request=request,
            ranked=(_make_ranked("a", 1, 0.9, 0.8), _make_ranked("b", 2, 0.7, 0.6)),
            policy_id="test", policy_version="v1",
        )
        errors = validate_ranking_result(result)
        assert any("missing_candidates" in e for e in errors)

    def test_extra_candidates_rejected(self):
        request = RankingRequest(
            ranking_surface="discovery_ranking",
            ranking_intent="general_research_relevance",
            query_text="test",
            candidates=(_make_candidate("a"),),
            ranking_policy_id="test",
            final_limit=1,
        )
        result = RankingResult(
            request=request,
            ranked=(_make_ranked("a", 1, 0.9, 0.8), _make_ranked("x", 2, 0.7, 0.6,
                       disposition=DISPOSITION_EXCLUDED_INVALID)),
            policy_id="test", policy_version="v1",
        )
        errors = validate_ranking_result(result)
        assert any("extra_candidates" in e for e in errors)

    def test_non_contiguous_ranks_rejected(self):
        request = RankingRequest(
            ranking_surface="discovery_ranking",
            ranking_intent="general_research_relevance",
            query_text="test",
            candidates=(_make_candidate("a"), _make_candidate("b")),
            ranking_policy_id="test",
            final_limit=2,
        )
        result = RankingResult(
            request=request,
            ranked=(_make_ranked("a", 1, 0.9, 0.8), _make_ranked("b", 3, 0.7, 0.6)),
            policy_id="test", policy_version="v1",
        )
        errors = validate_ranking_result(result)
        assert any("non_contiguous" in e for e in errors)

    def test_valid_result_passes(self):
        request = RankingRequest(
            ranking_surface="discovery_ranking",
            ranking_intent="general_research_relevance",
            query_text="test",
            candidates=(_make_candidate("a"), _make_candidate("b")),
            ranking_policy_id="test",
            final_limit=2,
        )
        result = RankingResult(
            request=request,
            ranked=(_make_ranked("a", 1, 0.9, 0.8), _make_ranked("b", 2, 0.7, 0.6)),
            policy_id="test", policy_version="v1",
        )
        errors = validate_ranking_result(result)
        assert not errors


class TestTieBreak:
    def test_higher_score_sorts_first(self):
        key1 = compute_tie_break_key("a", 0.9, 0.8)
        key2 = compute_tie_break_key("b", 0.7, 0.6)
        assert key1 < key2  # string comparison = descending score

    def test_same_final_score_breaks_by_hybrid(self):
        key1 = compute_tie_break_key("a", 0.9, 0.8)
        key2 = compute_tie_break_key("b", 0.9, 0.7)
        assert key1 < key2

    def test_same_scores_breaks_by_id(self):
        key1 = compute_tie_break_key("aaa", 0.9, 0.8)
        key2 = compute_tie_break_key("bbb", 0.9, 0.8)
        assert key1 < key2  # "aaa" < "bbb"

    def test_deterministic(self):
        key1 = compute_tie_break_key("a", 0.9, 0.8, 0.7)
        key2 = compute_tie_break_key("a", 0.9, 0.8, 0.7)
        assert key1 == key2


class TestCandidateImmutability:
    def test_candidate_is_frozen(self):
        import dataclasses
        assert dataclasses.is_dataclass(RankingCandidate)
        c = _make_candidate("a")
        # Frozen dataclass should raise on assignment
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.candidate_id = "b"
