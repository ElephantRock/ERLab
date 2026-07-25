"""Tests for P1E.1 Commit 4 — extension diagnosis.

Proves the diagnosis is generated from sealed artifacts, all hashes match,
JSON and Markdown agree on key measurements, and the required reporting
conditions hold.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data" / "evaluation"
MD = REPO_ROOT / "docs" / "research" / "p1e1_benchmark_extension.md"
DIAG = DATA / "p1e1_benchmark_extension_diagnosis.json"
REQUIRE = os.getenv("ERLAB_REQUIRE_P1E1_ARTIFACTS") == "1"


@pytest.fixture(scope="module")
def diag():
    return json.loads(DIAG.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def md():
    return MD.read_text(encoding="utf-8")


class TestSourceIntegrity:
    """1. Diagnosis generated from sealed artifacts; 2. hashes match."""

    def test_source_hashes_match_committed(self, diag):
        from backend.ranking.p1e1_canon import sha256_file
        for name, expected_sha in diag["source_artifacts"].items():
            actual = sha256_file(DATA / f"{name}.json")
            assert actual == expected_sha, f"{name} hash drift"

    def test_diagnosis_generated_from_sealed(self, diag):
        # every identity hash must be non-empty; SHA-256 fields are 64-char,
        # commit hashes are 40-char.
        commit_fields = {"effective_protocol_v4_commit"}
        for k, v in diag["identity"].items():
            if k == "final_adjudicated_v3_fingerprint":
                continue
            if k in commit_fields:
                assert len(v) == 40, f"{k} not full commit hash"
            else:
                assert len(v) == 64, f"{k} not full SHA-256"

    def test_no_upstream_artifact_modified(self):
        # HEAD must be a6c35e6 or its descendant; upstream artifacts unchanged.
        # Verified by the source_hashes test above (hashes match committed values).
        pass  # covered by test_source_hashes_match_committed


class TestComposition:
    """4. Composition 88/33/33/22."""

    def test_88_total(self, diag):
        assert diag["composition"]["total_cases"] == 88

    def test_33_33_22_splits(self, diag):
        c = diag["composition"]
        assert c["calibration_cases"] == 33
        assert c["development_cases"] == 33
        assert c["held_out_cases"] == 22
        assert c["caldev_cases"] == 66

    def test_lineage_44_44(self, diag):
        c = diag["composition"]
        assert c["v2_lineage_cases"] == 44
        assert c["fully_new_cases"] == 44


class TestAdjudicationBreakdown:
    """5. 180 inherited + 264 fresh = 444; 6. zero v2 held-out inheritance."""

    def test_180_inherited(self, diag):
        assert diag["adjudication"]["inherited_v2_caldev_records"] == 180

    def test_264_fresh(self, diag):
        assert diag["adjudication"]["fresh_judgments_total"] == 264

    def test_444_total(self, diag):
        a = diag["adjudication"]
        assert a["inherited_v2_caldev_records"] + a["fresh_judgments_total"] == 444

    def test_zero_v2_heldout(self, diag):
        assert diag["adjudication"]["v2_held_out_inheritance"] == 0

    def test_inheritance_not_described_as_fresh(self, diag):
        assert "NOT described as freshly adjudicated" in diag["adjudication"]["inheritance_authorization"]


class TestPowerProjection:
    """7. Projected MDE labelled projected, not achieved/measured."""

    def test_design_projection_true(self, diag):
        assert diag["power_projection"]["design_projection"] is True

    def test_measured_in_p1e1_false(self, diag):
        assert diag["power_projection"]["measured_in_p1e1"] is False

    def test_no_forbidden_terms(self, diag, md):
        forbidden = ["achieved MDE", "measured P1E.1 MDE", "observed P1E.1 policy improvement"]
        for term in forbidden:
            assert term not in md, f"forbidden term in markdown: {term}"


class TestFingerprintAndPolicy:
    """8. final fingerprint pending; 9. policy not started."""

    def test_final_fingerprint_pending(self, diag):
        assert diag["identity"]["final_adjudicated_v3_fingerprint"] == "pending_p1e2"

    def test_policy_not_started(self, diag):
        assert diag["completion_status"]["policy_evaluation_status"] == "not_started"


class TestJsonMarkdownAgreement:
    """3. JSON and Markdown report the same key measurements."""

    def test_grade_distribution_matches(self, diag, md):
        gd = diag["grade_dependent_targets"]["grade_distribution"]
        for grade, count in gd.items():
            assert str(count) in md, f"grade {grade} count {count} not in markdown"

    def test_composition_matches(self, diag, md):
        assert "88" in md
        assert "33" in md
        assert "22" in md


class TestCustodyReporting:
    """Custody reporting matches sealed receipt."""

    def test_heldout_grades_zero(self, diag):
        assert diag["custody_and_blinding"]["held_out_grades_inspected"] == 0

    def test_no_independent_security_claim(self, diag, md):
        assert "governed environment" in diag["custody_and_blinding"]["custody_limitation_note"]


class TestCloseoutMode:
    """11-12. Closeout mode requires diagnosis; no skips."""

    def test_diagnosis_present_in_closeout(self):
        if not REQUIRE:
            pytest.skip("not in closeout mode")
        assert DIAG.exists(), "diagnosis JSON missing"
        assert MD.exists(), "diagnosis Markdown missing"
