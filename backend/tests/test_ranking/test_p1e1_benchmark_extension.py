"""Tests for P1E.1 Commit 3 — cal/dev adjudication, blind held-out, extension.

Covers:
  - seal verification before grade loading
  - adjudication view purity (no mining metadata)
  - grade-dependent targets (66 cal/dev cases)
  - blind held-out package leakage (recursive key/value scan)
  - custody receipt validity
  - extension identity completeness
  - closeout mode (ERLAB_REQUIRE_P1E1_ARTIFACTS=1)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data" / "evaluation"
REQUIRE = os.getenv("ERLAB_REQUIRE_P1E1_ARTIFACTS") == "1"

REQUIRED_ARTIFACTS = [
    "p1e1_caldev_adjudication.json",
    "p1e1_blind_heldout_package.json",
    "p1e1_reconciliation_map_custody_receipt.json",
    "p1e1_benchmark_extension.json",
    "p1e1_candidate_package.json",
    "p1e1_split_manifest.json",
]


@pytest.fixture(scope="module")
def caldev():
    return json.loads((DATA / "p1e1_caldev_adjudication.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def blind():
    return json.loads((DATA / "p1e1_blind_heldout_package.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def receipt():
    return json.loads((DATA / "p1e1_reconciliation_map_custody_receipt.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def extension():
    return json.loads((DATA / "p1e1_benchmark_extension.json").read_text(encoding="utf-8"))


class TestSealVerification:
    """The adjudication artifact must embed all 5 candidate-layer seals."""

    def test_adjudication_embeds_all_seals(self, caldev):
        for seal in ["protocol_commit", "protocol_sha256",
                     "candidate_corpus_fingerprint", "candidate_package_sha256",
                     "candidate_provenance_sha256", "candidate_mining_scores_sha256",
                     "split_manifest_sha256"]:
            assert seal in caldev, f"missing seal {seal}"

    def test_protocol_commit_is_v3_full_hash(self, caldev):
        assert caldev["protocol_commit"] == "679bc0052d0851bef48ab87663166b7a08f85bd6"


class TestAdjudicationPurity:
    """The adjudication view must not expose mining metadata."""

    FORBIDDEN = {"mining_role", "near_duplicate_of", "mining_method", "mining_rationale",
                 "lexical_overlap", "semantic_mining", "query_generation_anchor",
                 "parent_v2_case_id", "parent_v2_candidate_id"}

    def test_grades_contain_no_mining_metadata(self, caldev):
        for r in caldev["grades"]:
            for forbidden in self.FORBIDDEN:
                assert forbidden not in r, f"grade record has {forbidden}"

    def test_every_grade_references_valid_candidate(self, caldev):
        pkg = json.loads((DATA / "p1e1_candidate_package.json").read_text(encoding="utf-8"))
        valid = {(c["case_id"], cc["candidate_id"])
                 for c in pkg["cases"] if c["split"] in ("calibration", "development")
                 for cc in c["candidates"]}
        for r in caldev["grades"]:
            assert (r["v3_case_id"], r["v3_candidate_id"]) in valid

    def test_no_duplicate_or_unknown_grades(self, caldev):
        keys = [(r["v3_case_id"], r["v3_candidate_id"]) for r in caldev["grades"]]
        assert len(keys) == len(set(keys)), "duplicate grade records"
        assert caldev["unknown_or_duplicate_grade_records"] == 0

    def test_no_held_out_grades(self, caldev):
        pkg = json.loads((DATA / "p1e1_candidate_package.json").read_text(encoding="utf-8"))
        held_out_ids = {c["case_id"] for c in pkg["cases"] if c["split"] == "held_out"}
        for r in caldev["grades"]:
            assert r["v3_case_id"] not in held_out_ids, "held-out grade present"


class TestGradeDependentTargets:
    """Grade-dependent targets evaluated over 66 cal/dev cases."""

    def test_all_targets_pass(self, extension):
        assert extension["all_grade_targets_pass"], "not all grade targets pass"

    def test_grade0_ge2_pct(self, extension):
        t = extension["grade_dependent_targets"]["pct_cases_grade0_ge2"]
        assert t["pass"]
        assert t["actual_pct"] >= 80

    def test_hardneg_ge2_pct(self, extension):
        t = extension["grade_dependent_targets"]["pct_cases_hardneg_ge2"]
        assert t["pass"]
        assert t["actual_pct"] >= 60

    def test_unique_best_pct(self, extension):
        t = extension["grade_dependent_targets"]["unique_best"]
        assert t["pass"]
        assert t["actual_pct"] >= 50

    def test_misleading_near_duplicate(self, extension):
        t = extension["grade_dependent_targets"]["adjudicated_misleading_near_duplicate"]
        assert t["pass"]
        assert t["actual"] >= 8

    def test_lexical_confuser(self, extension):
        t = extension["grade_dependent_targets"]["adjudicated_lexical_confuser"]
        assert t["pass"]
        assert t["actual"] >= 8

    def test_grade_distribution_has_negatives(self, extension):
        gd = extension["grade_distribution_caldev"]
        assert gd.get("0", 0) > 0, "no grade-0 candidates"


class TestBlindHeldOutPackage:
    """Blind package: opaque IDs, no leakage, 22 cases."""

    FORBIDDEN_KEYS = {"split", "grade", "relevance", "judgment", "judgment_rationale",
                      "mining_score", "mining_method", "mining_rationale", "mining_role",
                      "constructed_lexical_trap", "near_duplicate_of", "parent_v2_case_id",
                      "parent_v2_candidate_id", "candidate_provenance", "v3_case_id",
                      "v3_candidate_id", "lineage_type", "primary_slice"}

    def test_22_held_out_cases(self, blind):
        assert blind["held_out_cases"] == 22

    def test_opaque_ids_unique(self, blind):
        assert blind["opaque_case_ids_unique"]
        assert blind["opaque_candidate_ids_unique"]

    def test_recursive_leakage_scan(self, blind):
        leaks = []
        def scan(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in self.FORBIDDEN_KEYS:
                        leaks.append(f"{path}.{k}")
                    if isinstance(v, str) and v.startswith("v3_"):
                        leaks.append(f"{path}.{k}=v3-value")
                    scan(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, x in enumerate(obj):
                    scan(x, f"{path}[{i}]")
            elif isinstance(obj, str) and obj.startswith("v3_"):
                leaks.append(f"{path}=v3-value")
        scan(blind)
        assert not leaks, f"blind package leaks: {leaks[:10]}"

    def test_no_held_out_grades_in_package(self, blind):
        for case in blind["cases"]:
            for cc in case["candidates"]:
                assert "grade" not in cc
                assert "judgment" not in cc


class TestCustodyReceipt:
    """Custody receipt binds package to map; map not in repo."""

    def test_receipt_binds_package_and_map(self, receipt, blind):
        assert receipt["blind_package_sha256"] == blind["blind_package_sha256"]
        assert "reconciliation_map_sha256" in receipt

    def test_map_not_committed(self, receipt):
        assert receipt["map_committed_to_repository"] is False

    def test_custodian_role(self, receipt):
        assert receipt["custodian_role"] == "P1E.2 Reconciliation Custodian"

    def test_entry_count_matches(self, receipt, blind):
        # 22 cases + their candidates = total mappings
        n_cands = sum(len(c["candidates"]) for c in blind["cases"])
        assert receipt["mapping_entry_count"] == 22 + n_cands


class TestExtensionIdentity:
    """Extension identity completeness."""

    def test_all_identities_sealed(self, extension):
        ident = extension["identity"]
        assert ident["candidate_benchmark_identity"] == "sealed"
        assert ident["caldev_adjudication_identity"] == "sealed"
        assert ident["blind_heldout_package_identity"] == "sealed"

    def test_final_fingerprint_pending(self, extension):
        assert extension["identity"]["final_adjudicated_v3_fingerprint"] == "pending_p1e2"

    def test_p1e3_not_performed(self, extension):
        assert extension["identity"]["p1e3_policy_evaluation"] == "not_performed"


class TestCloseoutMode:
    """ERLAB_REQUIRE_P1E1_ARTIFACTS=1 hard-fails on missing artifacts."""

    def test_all_required_artifacts_present(self):
        if not REQUIRE:
            pytest.skip("not in closeout mode")
        missing = [a for a in REQUIRED_ARTIFACTS if not (DATA / a).exists()]
        assert not missing, f"missing required artifacts: {missing}"
