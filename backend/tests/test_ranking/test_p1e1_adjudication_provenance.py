"""Tests for P1E.1.3 — adjudication provenance (4 governance proofs)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data" / "evaluation"


@pytest.fixture(scope="module")
def ap():
    return json.loads((DATA / "p1e1_adjudication_provenance.json").read_text(encoding="utf-8"))


class TestEffectiveSealLedger:
    """P1E.1.3a — all effective hashes published and bound."""

    def test_ledger_complete(self, ap):
        led = ap["p1e1_3a_effective_seal_ledger"]
        for k in ["protocol_v3_commit", "protocol_v3_sha256",
                  "candidate_corpus_fingerprint", "candidate_package_sha256",
                  "candidate_provenance_sha256", "candidate_mining_scores_sha256",
                  "prejudgment_diagnostics_sha256", "split_manifest_sha256",
                  "caldev_adjudication_sha256", "blind_heldout_package_sha256"]:
            assert led[k], f"missing {k}"

    def test_commit3_artifacts_bind_effective(self, ap):
        assert ap["p1e1_3a_commit3_artifacts_bind_effective"]

    def test_protocol_commit_is_40_chars(self, ap):
        assert len(ap["protocol_v3_commit"]) == 40


class TestInheritedJudgmentPosture:
    """P1E.1.3b — inherited-v2 posture disclosed (deviation, not fresh adjudication)."""

    def test_inheritance_authorized_by_v4(self, ap):
        p = ap["p1e1_3b_inherited_judgment_posture"]
        assert p["inheritance_authorized_by_protocol_v4"] is True
        assert p["deviation_closed"] is True
        assert len(p["protocol_v4_commit"]) == 40

    def test_inherited_count_180(self, ap):
        p = ap["p1e1_3b_inherited_judgment_posture"]
        assert p["inherited_preserved_v2_records"] == 180

    def test_breakdown_sums_to_444(self, ap):
        p = ap["p1e1_3b_inherited_judgment_posture"]
        assert p["inherited_preserved_v2_records"] + p["new_injected_candidate_judgments"] + \
               p["fully_new_case_judgments"] == 444

    def test_no_v2_heldout_parents(self, ap):
        p = ap["p1e1_3b_inherited_judgment_posture"]
        assert p["parent_cases_from_v2_held_out"] == 0

    def test_no_grade_mismatches(self, ap):
        p = ap["p1e1_3b_inherited_judgment_posture"]
        assert p["grade_mismatches_vs_frozen_v2"] == 0

    def test_new_judgments_complete(self, ap):
        p = ap["p1e1_3b_inherited_judgment_posture"]
        assert p["new_judgments_empty_rationale"] == 0
        assert p["new_judgments_empty_adjudicator"] == 0
        assert p["new_injected_candidate_judgments"] + p["fully_new_case_judgments"] == 264


class TestNoPostTargetRegrading:
    """P1E.1.3c — adjudication hash stable across target evaluation."""

    def test_adjudication_hash_stable(self, ap):
        n = ap["p1e1_3c_no_post_target_regrading"]
        assert n["all_three_identical"]

    def test_zero_post_target_changes(self, ap):
        n = ap["p1e1_3c_no_post_target_regrading"]
        assert n["grade_additions_after_target_visibility"] == 0
        assert n["grade_changes_after_target_visibility"] == 0
        assert n["rationale_changes_after_target_visibility"] == 0
        assert n["target_driven_candidate_changes"] == 0

    def test_target_uses_sealed_scores(self, ap):
        n = ap["p1e1_3c_no_post_target_regrading"]
        assert n["target_evaluator_uses_sealed_mining_scores"]


class TestCustodyTransfer:
    """P1E.1.3d — custody separation honestly reported."""

    def test_map_not_in_git(self, ap):
        c = ap["p1e1_3d_custody_transfer"]
        assert c["reconciliation_map_in_git_index_history"] is False

    def test_map_transfer_completed(self, ap):
        c = ap["p1e1_3d_custody_transfer"]
        assert c["map_transferred_to_designated_custodian"] is True
        assert c["transfer_status"] == "accepted"
        assert c["construction_copy_deleted"] is True
        assert c["map_in_adjudicator_workspace"] is False
        assert "operationally blinded" in c["operational_blinding_status"]
        assert "NOT" not in c["operational_blinding_status"]

    def test_receipt_binds_package_and_map(self, ap):
        c = ap["p1e1_3d_custody_transfer"]
        assert c["receipt_blind_package_sha_matches_committed"]
        assert c["mapping_entry_count_matches_package"]
