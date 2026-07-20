"""Tests for P1.1: frozen ranking benchmark integrity."""

from __future__ import annotations

import pytest

from backend.ranking.benchmark_cases import (
    ALL_DISCOVERY_CASES,
    ALL_RETRIEVAL_CASES,
    BENCHMARK_V1,
    BenchmarkCase,
    compute_benchmark_fingerprint,
)


class TestBenchmarkIntegrity:
    def test_discovery_case_count(self):
        assert len(ALL_DISCOVERY_CASES) >= 9  # 3 domains × 3 cases minimum

    def test_retrieval_case_count(self):
        assert len(ALL_RETRIEVAL_CASES) >= 3  # at least 1 per domain

    def test_three_domains_represented(self):
        domains = {c.research_domain for c in ALL_DISCOVERY_CASES + ALL_RETRIEVAL_CASES}
        assert len(domains) >= 3
        assert "machine_learning" in domains
        assert "biomedical" in domains
        assert "nlp" in domains

    def test_each_case_has_candidates(self):
        for case in ALL_DISCOVERY_CASES + ALL_RETRIEVAL_CASES:
            assert len(case.candidates) >= 3, f"{case.case_id} has too few candidates"

    def test_each_candidate_has_judgment(self):
        for case in ALL_DISCOVERY_CASES + ALL_RETRIEVAL_CASES:
            for c in case.candidates:
                assert c.candidate_id in case.judgments, (
                    f"{case.case_id}: missing judgment for {c.candidate_id}"
                )

    def test_grades_are_0_to_3(self):
        for case in ALL_DISCOVERY_CASES + ALL_RETRIEVAL_CASES:
            for j in case.judgments.values():
                assert 0 <= j.grade <= 3, f"{case.case_id}: grade {j.grade} out of range"

    def test_splits_exist(self):
        splits = {c.split for c in ALL_DISCOVERY_CASES + ALL_RETRIEVAL_CASES}
        assert "calibration" in splits
        assert "development" in splits
        assert "held_out" in splits

    def test_held_out_not_empty(self):
        held_out = [c for c in ALL_DISCOVERY_CASES if c.split == "held_out"]
        assert len(held_out) >= 1

    def test_content_hashes_deterministic(self):
        """Recomputing content_hash from text must match."""
        import hashlib
        for case in ALL_DISCOVERY_CASES[:1]:
            c = case.candidates[0]
            expected = hashlib.sha256(f"{c.title}\n\n{c.abstract}".encode()).hexdigest()
            assert c.content_hash == expected

    def test_benchmark_fingerprint_deterministic(self):
        fp1 = compute_benchmark_fingerprint()
        fp2 = compute_benchmark_fingerprint()
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_lexical_trap_cases_exist(self):
        """At least one case must have a lexical trap (high overlap, grade 0)."""
        has_trap = False
        for case in ALL_DISCOVERY_CASES + ALL_RETRIEVAL_CASES:
            for c in case.candidates:
                j = case.judgments.get(c.candidate_id)
                if j and j.grade == 0:
                    has_trap = True
                    break
        assert has_trap, "No lexical trap cases (grade=0) found in benchmark"

    def test_ranking_surfaces_labeled(self):
        for case in ALL_DISCOVERY_CASES:
            assert case.ranking_surface == "discovery_ranking"
        for case in ALL_RETRIEVAL_CASES:
            assert case.ranking_surface == "retrieval_ranking"

    def test_ranking_intents_in_vocabulary(self):
        valid_intents = {
            "general_research_relevance", "evidence_support",
            "method_relevance", "literature_mapping", "gap_analysis",
        }
        for case in ALL_DISCOVERY_CASES + ALL_RETRIEVAL_CASES:
            assert case.ranking_intent in valid_intents, (
                f"{case.case_id}: invalid intent {case.ranking_intent}"
            )
