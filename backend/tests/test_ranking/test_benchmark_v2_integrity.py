"""Tests for P1B.1: expanded benchmark v2 integrity.

These tests enforce the benchmark quality floor from Decision 3 and the
blind-adjudication discipline from Decision 3:
- minimum case counts per surface
- all required adversarial slices represented in every domain and both surfaces
- balanced splits across calibration / development / held_out
- every judgment has annotation provenance (rationale + confidence)
- no content_hash collisions within a case
- the frozen fingerprint refuses to compute pre-adjudication
- the blind adjudication package strips grades / confidence / rationales
"""

from __future__ import annotations

from backend.ranking.benchmark_v2_registry import (
    ALL_DISCOVERY_V2,
    ALL_RETRIEVAL_V2,
    ALL_V2_CASES,
    BENCHMARK_V2,
    build_blind_adjudication_package,
    build_blind_adjudication_package_v2,
    compute_benchmark_v2_fingerprint,
    compute_provisional_fingerprint,
    frozen_v2_cases,
    is_gate1_complete,
    slice_coverage_report,
    validate_benchmark_v2,
)
from backend.ranking.benchmark_v2_schema import (
    ALL_SLICE_TYPES,
    DISAGREE_NONE,
    DISAGREE_RESOLVED,
    REQUIRED_ADVERSARIAL_SLICES,
)


class TestBenchmarkV2QualityFloor:
    def test_discovery_count_at_least_30(self):
        assert len(ALL_DISCOVERY_V2) >= 30

    def test_retrieval_count_at_least_30(self):
        assert len(ALL_RETRIEVAL_V2) >= 30

    def test_three_domains_represented(self):
        domains = {c.research_domain for c in ALL_V2_CASES}
        assert {"machine_learning", "biomedical", "nlp"} <= domains

    def test_each_domain_has_at_least_10_cases_per_surface(self):
        from collections import Counter
        for surface_key, cases in (("discovery", ALL_DISCOVERY_V2), ("retrieval", ALL_RETRIEVAL_V2)):
            by_domain = Counter(c.research_domain for c in cases)
            for d in ("machine_learning", "biomedical", "nlp"):
                assert by_domain[d] >= 10, f"{surface_key}/{d}: {by_domain[d]}"

    def test_all_required_slices_in_both_surfaces(self):
        report = slice_coverage_report()
        assert report["missing_required_slices"] == []
        for required in REQUIRED_ADVERSARIAL_SLICES:
            entry = report["by_slice"][required]
            assert entry["discovery"] >= 1, f"{required} missing from discovery"
            assert entry["retrieval"] >= 1, f"{required} missing from retrieval"

    def test_each_required_slice_spans_three_domains(self):
        report = slice_coverage_report()
        for required in REQUIRED_ADVERSARIAL_SLICES:
            entry = report["by_slice"][required]
            assert len(entry["domains"]) == 3, (
                f"{required} only in domains {entry['domains']}"
            )

    def test_splits_balanced(self):
        from collections import Counter
        counts = Counter(c.split for c in ALL_V2_CASES)
        assert set(counts.keys()) == {"calibration", "development", "held_out"}
        # No split should hold more than 40% of cases (rough balance check).
        total = len(ALL_V2_CASES)
        for split, n in counts.items():
            assert n / total <= 0.40, f"split {split} over-represented: {n}/{total}"

    def test_held_out_non_empty_per_surface(self):
        assert any(c.split == "held_out" for c in ALL_DISCOVERY_V2)
        assert any(c.split == "held_out" for c in ALL_RETRIEVAL_V2)


class TestBenchmarkV2SchemaIntegrity:
    def test_no_validation_errors(self):
        errors = validate_benchmark_v2()
        assert errors == [], f"benchmark v2 validation errors: {errors[:5]}"

    def test_case_ids_unique(self):
        ids = [c.case_id for c in ALL_V2_CASES]
        assert len(ids) == len(set(ids)), "duplicate case_ids"

    def test_no_candidate_id_collisions_within_case(self):
        for case in ALL_V2_CASES:
            ids = [c.candidate_id for c in case.candidates]
            assert len(ids) == len(set(ids)), f"{case.case_id}: duplicate candidate_ids"

    def test_no_content_hash_collisions_within_case(self):
        for case in ALL_V2_CASES:
            hashes = [c.content_hash for c in case.candidates]
            assert len(hashes) == len(set(hashes)), f"{case.case_id}: duplicate content_hashes"

    def test_each_candidate_has_judgment_provenance(self):
        for case in ALL_V2_CASES:
            for c in case.candidates:
                assert c.candidate_id in case.judgments, (
                    f"{case.case_id}: missing judgment for {c.candidate_id}"
                )

    def test_provenance_has_rationale_and_confidence(self):
        for case in ALL_V2_CASES:
            for cid, prov in case.judgments.items():
                assert prov.initial.rationale.strip(), (
                    f"{case.case_id}/{cid}: empty initial rationale"
                )
                assert 0.0 <= prov.initial.annotation_confidence <= 1.0
                assert 0 <= prov.initial.grade <= 3

    def test_primary_slice_in_vocabulary(self):
        for case in ALL_V2_CASES:
            assert case.primary_slice in ALL_SLICE_TYPES, (
                f"{case.case_id}: bad primary_slice {case.primary_slice}"
            )

    def test_ranking_surfaces_labeled(self):
        for case in ALL_DISCOVERY_V2:
            assert case.ranking_surface == "discovery_ranking"
        for case in ALL_RETRIEVAL_V2:
            assert case.ranking_surface == "retrieval_ranking"


class TestBenchmarkV2FreezeDiscipline:
    def test_gate1_is_complete(self):
        """Post-adjudication: every v2 judgment has a frozen record."""
        assert is_gate1_complete() is True

    def test_frozen_fingerprint_computes_post_adjudication(self):
        """The frozen fingerprint must compute and be deterministic."""
        fp1 = compute_benchmark_v2_fingerprint()
        fp2 = compute_benchmark_v2_fingerprint()
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_frozen_view_has_full_provenance(self):
        """Every frozen judgment carries initial + second_pass + adjudicated grade."""
        frozen = frozen_v2_cases()
        assert len(frozen) == len(ALL_V2_CASES)
        for case in frozen:
            for cid, prov in case.judgments.items():
                assert prov.second_pass is not None, (
                    f"{case.case_id}/{cid}: missing blind second-pass"
                )
                assert prov.adjudicated_grade is not None, (
                    f"{case.case_id}/{cid}: missing adjudicated grade"
                )
                assert prov.disagreement_status in (DISAGREE_NONE, DISAGREE_RESOLVED), (
                    f"{case.case_id}/{cid}: bad disagreement_status {prov.disagreement_status}"
                )

    def test_frozen_view_validates(self):
        frozen = frozen_v2_cases()
        errors: list[str] = []
        for case in frozen:
            errors.extend(case.validate())
        assert errors == [], f"frozen view validation errors: {errors[:5]}"

    def test_frozen_view_preserves_candidate_pools_and_splits(self):
        """Frozen cases must not alter candidate pools, splits, or queries."""
        frozen_by_id = {c.case_id: c for c in frozen_v2_cases()}
        for orig in ALL_V2_CASES:
            fz = frozen_by_id[orig.case_id]
            assert fz.split == orig.split
            assert fz.query_text == orig.query_text
            assert fz.primary_slice == orig.primary_slice
            assert tuple(c.candidate_id for c in fz.candidates) == tuple(
                c.candidate_id for c in orig.candidates
            )
            assert [c.content_hash for c in fz.candidates] == [
                c.content_hash for c in orig.candidates
            ]

    def test_provisional_fingerprint_is_deterministic(self):
        fp1 = compute_provisional_fingerprint()
        fp2 = compute_provisional_fingerprint()
        assert fp1 == fp2
        assert len(fp1) == 64


class TestBlindAdjudicationPackage:
    def test_package_has_all_cases(self):
        pkg = build_blind_adjudication_package()
        assert len(pkg["cases"]) == len(ALL_V2_CASES)

    def test_package_strips_judgments(self):
        """The blind package must NOT contain any grade/confidence/rationale."""
        pkg = build_blind_adjudication_package()
        for case_entry in pkg["cases"]:
            assert "judgments" not in case_entry, (
                f"{case_entry['case_id']}: blind package leaked judgments"
            )
            # And no candidate carries a grade/confidence.
            for cand in case_entry["candidates"]:
                assert "grade" not in cand
                assert "confidence" not in cand
                assert "rationale" not in cand

    def test_package_retains_case_metadata_and_text(self):
        pkg = build_blind_adjudication_package()
        case0 = pkg["cases"][0]
        for key in ("case_id", "domain", "surface", "intent", "primary_slice",
                    "query_text", "candidates"):
            assert key in case0
        cand0 = case0["candidates"][0]
        for key in ("candidate_id", "title", "abstract", "content_hash"):
            assert key in cand0

    def test_package_exposes_slice_context(self):
        """Slice labels are retained so the adjudicator knows what the case tests."""
        pkg = build_blind_adjudication_package()
        for case_entry in pkg["cases"]:
            assert "primary_slice" in case_entry
            assert "secondary_slices" in case_entry


class TestBlindAdjudicationPackageV2Protocol:
    """Enforces the frozen Gate 1 protocol on the v2 package.

    The protocol (frozen in Decision 3 / Gate 1):
      INCLUDES per case:  case_id, ranking_surface, research question /
      ranking intent, candidate_id, title, abstract/canonical text, rubric,
      domain/context needed for judgment.
      EXCLUDES: provisional grades, confidence, rationales, policy scores,
      semantic scores, baseline ranks, candidate policy ranks, split labels,
      author identity/provenance.
      Candidate order: deterministically shuffled, NOT provisional/baseline
      rank order.
    """

    REQUIRED_CASE_KEYS = {
        "case_id", "ranking_surface", "research_question", "ranking_intent",
        "adjudication_context", "domain", "candidates",
    }
    FORBIDDEN_CASE_KEYS = {"split", "judgments"}
    FORBIDDEN_CAND_KEYS = {
        "grade", "confidence", "rationale",
        "policy_score", "semantic_score", "rank", "baseline_rank",
    }
    REQUIRED_CAND_KEYS = {
        "candidate_id", "title", "abstract", "content_hash",
    }

    def test_package_version_is_v2(self):
        pkg = build_blind_adjudication_package_v2()
        assert pkg["package_version"] == "blind_adjudication_v2"

    def test_package_has_all_cases(self):
        pkg = build_blind_adjudication_package_v2()
        assert len(pkg["cases"]) == len(ALL_V2_CASES)

    def test_package_embeds_full_rubric(self):
        pkg = build_blind_adjudication_package_v2()
        assert "rubric" in pkg
        assert pkg["rubric"]["rubric_version"] == "research_utility_0_to_3_v1"
        # The rubric must define criteria + grade anchors so judgments are
        # criterion-anchored, not subjective.
        assert "criteria" in pkg["rubric"]
        assert "grade_anchors" in pkg["rubric"]
        for grade in ("0", "1", "2", "3"):
            assert grade in pkg["rubric"]["grade_anchors"]

    def test_case_keys_compliant(self):
        pkg = build_blind_adjudication_package_v2()
        for entry in pkg["cases"]:
            keys = set(entry.keys())
            missing = self.REQUIRED_CASE_KEYS - keys
            assert not missing, f"{entry['case_id']} missing: {missing}"
            leaked = self.FORBIDDEN_CASE_KEYS & keys
            assert not leaked, f"{entry['case_id']} leaked forbidden: {leaked}"

    def test_candidate_keys_compliant(self):
        pkg = build_blind_adjudication_package_v2()
        for entry in pkg["cases"]:
            for cand in entry["candidates"]:
                keys = set(cand.keys())
                missing = self.REQUIRED_CAND_KEYS - keys
                assert not missing, (
                    f"{entry['case_id']}/{cand['candidate_id']} missing: {missing}"
                )
                leaked = self.FORBIDDEN_CAND_KEYS & keys
                assert not leaked, (
                    f"{entry['case_id']}/{cand['candidate_id']} leaked: {leaked}"
                )

    def test_candidate_order_is_shuffled_not_author_order(self):
        """At least the majority of cases must have a non-author candidate order."""
        pkg = build_blind_adjudication_package_v2()
        shuffled_count = 0
        for entry, orig in zip(pkg["cases"], ALL_V2_CASES):
            author_order = [c.candidate_id for c in orig.candidates]
            pkg_order = [c["candidate_id"] for c in entry["candidates"]]
            if author_order != pkg_order:
                shuffled_count += 1
        # Some cases may collide by chance (esp. 4-candidate cases); require
        # a clear majority to be reordered.
        assert shuffled_count >= len(ALL_V2_CASES) * 0.8, (
            f"only {shuffled_count}/{len(ALL_V2_CASES)} cases shuffled"
        )

    def test_shuffle_is_reproducible(self):
        p1 = build_blind_adjudication_package_v2()
        p2 = build_blind_adjudication_package_v2()
        for e1, e2 in zip(p1["cases"], p2["cases"]):
            o1 = [c["candidate_id"] for c in e1["candidates"]]
            o2 = [c["candidate_id"] for c in e2["candidates"]]
            assert o1 == o2, f"{e1['case_id']}: shuffle not reproducible"

    def test_no_author_identity_or_provenance_leaked(self):
        pkg = build_blind_adjudication_package_v2()
        for entry in pkg["cases"]:
            for cand in entry["candidates"]:
                # No annotator names or provenance strings on candidates.
                assert "annotator" not in cand
                assert "provenance" not in cand
                assert "initial" not in cand
            assert "annotator" not in entry
            assert "provenance" not in entry


class TestBenchmarkV2Version:
    def test_version_declared(self):
        assert BENCHMARK_V2["version"] == "discovery_ranking_v2+retrieval_ranking_v2"

    def test_version_counts_match_registry(self):
        assert BENCHMARK_V2["discovery_cases"] == len(ALL_DISCOVERY_V2)
        assert BENCHMARK_V2["retrieval_cases"] == len(ALL_RETRIEVAL_V2)
        assert BENCHMARK_V2["total_cases"] == len(ALL_V2_CASES)
