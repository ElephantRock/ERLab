"""BATCH-159: 5-State Verification + Staged Confidence Deepening.

TASK-01: VerificationState 5-state enum (5 tests)
TASK-02: TrustTier gates in CitationClaimAuditor (5 tests)
TASK-03: Temporal decay for confidence (4 tests)
"""
import math
from datetime import datetime
from unittest.mock import MagicMock

import pytest


# ─── TASK-01: VerificationState ─────────────────────────────

class TestVerificationState:

    def test_01_five_states_exist(self):
        from backend.pipeline.verification.reference_verifier import VerificationState
        states = [s.value for s in VerificationState]
        assert "supported" in states
        assert "partially_supported" in states
        assert "insufficient_evidence" in states
        assert "contradicted" in states
        assert "unverified" in states
        assert len(states) == 5

    def test_02_citation_check_default_unverified(self):
        from backend.pipeline.verification.reference_verifier import (
            CitationCheck, VerificationState,
        )
        check = CitationCheck(
            citation_text="Smith et al., 2020",
            author="Smith",
            year="2020",
        )
        assert check.verification_state == VerificationState.UNVERIFIED
        assert check.decayed_confidence == 0.0

    def test_03_verify_sets_supported_state(self):
        from backend.pipeline.verification.reference_verifier import (
            ReferenceVerifier, VerificationState,
        )
        verifier = ReferenceVerifier()
        report = verifier.verify(
            "Smith et al. (2020) showed improvements.",
            [{"title": "Test Paper", "authors": ["Smith"], "year": "2020"}],
        )
        assert len(report.citations) > 0
        # At least one citation should be SUPPORTED or PARTIALLY_SUPPORTED
        verified = [c for c in report.citations
                    if c.verification_state in (VerificationState.SUPPORTED, VerificationState.PARTIALLY_SUPPORTED)]
        assert len(verified) >= 1, f"States: {[c.verification_state for c in report.citations]}"

    def test_04_verify_sets_unverified_for_missing(self):
        from backend.pipeline.verification.reference_verifier import (
            ReferenceVerifier, VerificationState,
        )
        verifier = ReferenceVerifier()
        report = verifier.verify(
            "Nonexistent et al. (2099) showed nothing.",
            [{"title": "Real Paper", "authors": ["Real"], "year": "2020"}],
        )
        unverifiable = [c for c in report.citations if c.verification_state == VerificationState.UNVERIFIED]
        assert len(unverifiable) >= 1

    def test_05_backward_compat_found_in_corpus(self):
        from backend.pipeline.verification.reference_verifier import (
            CitationCheck, VerificationState,
        )
        check = CitationCheck(
            citation_text="Test",
            author="Test",
            year="2024",
            found_in_corpus=True,
            verification_state=VerificationState.SUPPORTED,
        )
        assert check.found_in_corpus is True
        assert check.verification_state == VerificationState.SUPPORTED


# ─── TASK-02: TrustTier gates ───────────────────────────────

class TestTrustTierGates:

    def test_06_audit_item_trust_tier_default(self):
        from backend.pipeline.verification.citation_claim_auditor import CitationAuditItem
        item = CitationAuditItem(
            ref_index=1,
            ref_exists=True,
            claim_text="Test claim",
            context_verified=True,
            context_justification="Matched",
            quantitative_claims=[],
            quantitative_verified=True,
            trust_contribution=0.9,
        )
        assert item.trust_tier == "UNVERIFIED"  # Before compute_trust_tiers()

    def test_07_compute_tiers_very_high(self):
        from backend.pipeline.verification.citation_claim_auditor import (
            CitationAuditItem, CitationAuditReport,
        )
        item = CitationAuditItem(
            ref_index=1, ref_exists=True, claim_text="Test",
            context_verified=True, context_justification="OK",
            quantitative_claims=[], quantitative_verified=True,
            trust_contribution=0.95,
        )
        report = CitationAuditReport(
            proposal_id=0, total_citations=1, verified_citations=1,
            fabricated_citations=0, context_mismatches=0, quantitative_errors=0,
            trust_score=0.95, items=[item], model_used="test", status="complete",
        )
        report.compute_trust_tiers()
        assert item.trust_tier == "VERY_HIGH"
        assert report.trust_gate_warnings is not None

    def test_08_compute_tiers_unverified(self):
        from backend.pipeline.verification.citation_claim_auditor import (
            CitationAuditItem, CitationAuditReport,
        )
        item = CitationAuditItem(
            ref_index=1, ref_exists=False, claim_text="Test",
            context_verified=False, context_justification="Not found",
            quantitative_claims=[], quantitative_verified=False,
            trust_contribution=0.0,
        )
        report = CitationAuditReport(
            proposal_id=0, total_citations=1, verified_citations=0,
            fabricated_citations=1, context_mismatches=0, quantitative_errors=0,
            trust_score=0.0, items=[item], model_used="test", status="complete",
        )
        report.compute_trust_tiers()
        assert item.trust_tier == "UNVERIFIED"
        assert any("FABRICATED" in w for w in report.trust_gate_warnings)

    def test_09_low_trust_warning(self):
        from backend.pipeline.verification.citation_claim_auditor import (
            CitationAuditItem, CitationAuditReport,
        )
        items = [
            CitationAuditItem(
                ref_index=i, ref_exists=True, claim_text="Test",
                context_verified=(i == 0), context_justification="Mixed",
                quantitative_claims=[], quantitative_verified=False,
                trust_contribution=0.2,
            )
            for i in range(4)
        ]
        report = CitationAuditReport(
            proposal_id=0, total_citations=4, verified_citations=1,
            fabricated_citations=0, context_mismatches=3, quantitative_errors=3,
            trust_score=0.2, items=items, model_used="test", status="complete",
        )
        report.compute_trust_tiers()
        assert any("LOW_TRUST" in w for w in report.trust_gate_warnings)

    def test_10_to_dict_includes_tier_and_warnings(self):
        from backend.pipeline.verification.citation_claim_auditor import (
            CitationAuditItem, CitationAuditReport,
        )
        item = CitationAuditItem(
            ref_index=1, ref_exists=True, claim_text="Test",
            context_verified=True, context_justification="OK",
            quantitative_claims=[], quantitative_verified=True,
            trust_contribution=1.0,
        )
        report = CitationAuditReport(
            proposal_id=0, total_citations=1, verified_citations=1,
            fabricated_citations=0, context_mismatches=0, quantitative_errors=0,
            trust_score=1.0, items=[item], model_used="test", status="complete",
        )
        report.compute_trust_tiers()
        d = report.to_dict()
        assert "trust_tier" in d["items"][0]
        assert "trust_gate_warnings" in d


# ─── TASK-03: Temporal Decay ─────────────────────────────────

class TestTemporalDecay:

    def test_11_brand_new_full_confidence(self):
        from backend.pipeline.verification.temporal_decay import decay_factor
        assert decay_factor(0) == 1.0

    def test_12_one_year_half_life(self):
        from backend.pipeline.verification.temporal_decay import decay_factor
        factor = decay_factor(365, half_life=365)
        assert abs(factor - 0.5) < 0.01

    def test_13_apply_decay_with_year(self):
        from backend.pipeline.verification.temporal_decay import apply_decay
        current_year = datetime.utcnow().year
        # Paper from current year — no decay
        result = apply_decay(0.9, current_year)
        assert result == 0.9

        # Paper from 3 years ago — some decay
        result_old = apply_decay(0.9, current_year - 3, reference_year=current_year)
        assert result_old < 0.9
        assert result_old > 0.0

    def test_14_apply_decay_no_year(self):
        from backend.pipeline.verification.temporal_decay import apply_decay
        # No year — no decay applied
        assert apply_decay(0.8, None) == 0.8
        assert apply_decay(0.0, 2020) == 0.0
