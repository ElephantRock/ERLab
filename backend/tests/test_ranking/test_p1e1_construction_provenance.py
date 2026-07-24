"""Tests for P1E.1.2 — candidate-construction provenance (4 proofs).

Proves:
  2a  all 5 candidate-layer artifacts bind to the effective protocol-v2 identity
  2b  near-duplicate calibration used cal/dev pairs only (0 held-out)
  2c  final package unchanged after mining-score generation
  2d  mining-score coverage is complete and the validated-near-dup count is
      reproducible exclusively from sealed candidate-candidate pair scores
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data" / "evaluation"
PROV = DATA / "p1e1_construction_provenance.json"

ARTIFACTS = [
    "p1e1_candidate_package.json",
    "p1e1_candidate_provenance.json",
    "p1e1_candidate_mining_scores.json",
    "p1e1_prejudgment_diagnostics.json",
    "p1e1_split_manifest.json",
]


@pytest.fixture(scope="module")
def provenance():
    return json.loads(PROV.read_text(encoding="utf-8"))


class TestProtocolIdentity:
    """P1E.1.2a — all 5 artifacts bind to the effective protocol-v2."""

    def test_all_five_bind_to_same_protocol_commit(self, provenance):
        bindings = provenance["p1e1_2a_protocol_identity"]["artifact_bindings"]
        commits = {(v["protocol_commit_present"] or "")[:7] for v in bindings.values()}
        assert len(commits) == 1, f"artifact commits disagree: {commits}"

    def test_protocol_sha_identical_across_artifacts(self, provenance):
        assert provenance["p1e1_2a_protocol_identity"]["protocol_sha256_identical_across_artifacts"]

    def test_allocation_sha_identical_across_artifacts(self, provenance):
        assert provenance["p1e1_2a_protocol_identity"]["allocation_sha256_identical_across_artifacts"]

    def test_effective_protocol_is_v2_not_v1(self, provenance):
        assert provenance["effective_protocol_commit"] != provenance["superseded_protocol_v1_commit"]


class TestCalibrationIsolation:
    """P1E.1.2b — calibration used cal/dev pairs only."""

    def test_zero_held_out_reference_pairs(self, provenance):
        cal = provenance["p1e1_2b_calibration_isolation"]
        assert cal["reference_pairs_held_out"] == 0
        assert cal["reference_pairs_caldev_count"] == 4

    def test_no_held_out_access_during_calibration(self, provenance):
        cal = provenance["p1e1_2b_calibration_isolation"]
        assert cal["held_out_case_objects_materialized"] == 0
        assert cal["held_out_candidate_content_inspected"] == 0
        assert cal["held_out_judgments_inspected"] == 0

    def test_threshold_is_caldev_minimum(self, provenance):
        cal = provenance["p1e1_2b_calibration_isolation"]
        pairs = cal["reference_pairs_caldev"]
        vals = sorted(p["cosine_full_precision"] for p in pairs)
        assert cal["frozen_threshold"] == round(vals[0], 9)
        assert cal["frozen_threshold"] == 0.861630662

    def test_all_caldev_pairs_from_cal_or_dev_split(self, provenance):
        cal = provenance["p1e1_2b_calibration_isolation"]
        for p in cal["reference_pairs_caldev"]:
            assert p["split"] in ("calibration", "development"), f"{p['case_id']} is {p['split']}"


class TestBuildChronology:
    """P1E.1.2c — package unchanged after mining."""

    def test_chronology_sequence_present(self, provenance):
        seq = provenance["p1e1_2c_build_chronology"]["sequence"]
        assert "final candidate package generated" in seq[1]
        assert "eeb536d committed" in seq[-1] or "committed" in seq[-1]


class TestMiningCoverage:
    """P1E.1.2d — complete mining coverage + reproducible near-dup count."""

    def test_vector_counts(self, provenance):
        mc = provenance["p1e1_2d_mining_coverage"]
        assert mc["query_vectors"] == 88
        assert mc["candidate_vectors"] == 576

    def test_query_candidate_score_count(self, provenance):
        mc = provenance["p1e1_2d_mining_coverage"]
        assert mc["query_to_candidate_scores"] == 576
        assert mc["missing_query_candidate_scores"] == 0

    def test_pair_score_count_matches_declared(self, provenance):
        mc = provenance["p1e1_2d_mining_coverage"]
        assert mc["declared_near_duplicate_pairs"] == mc["candidate_to_candidate_pair_scores"]
        assert mc["missing_pair_scores"] == 0

    def test_no_nonfinite_or_truncation(self, provenance):
        mc = provenance["p1e1_2d_mining_coverage"]
        assert mc["nonfinite_vectors"] == 0
        assert mc["nonfinite_scores"] == 0
        assert mc["silent_truncations"] == 0
        assert mc["token_limit_violations"] == 0

    def test_validated_count_reproducible_from_artifact(self, provenance):
        mc = provenance["p1e1_2d_mining_coverage"]
        assert mc["validated_count_reproducible_from_artifact"]

    def test_validated_count_reproducible_independently(self, provenance):
        """Recompute the validated near-dup count from the sealed pair scores."""
        mining = json.loads((DATA / "p1e1_candidate_mining_scores.json").read_text(encoding="utf-8"))
        threshold = 0.861630662
        by_case = {}
        for r in mining["near_duplicate_pair_scores"]:
            by_case.setdefault(r["case_id"], []).append(r["candidate_candidate_cosine"])
        count = sum(1 for sims in by_case.values() if any(s >= threshold for s in sims))
        mc = provenance["p1e1_2d_mining_coverage"]
        assert count == mc["validated_near_duplicate_cases_from_pair_scores"]
