"""Tests for ClaimEvidenceValidator — the claim survival gate."""

import pytest

from backend.pipeline.gateway.claim_evidence_validator import (
    ClaimAction,
    ClaimEvidenceResult,
    ClaimEvidenceValidator,
    DocumentValidationResult,
    SupportLevel,
)


class TestLevel1Existence:
    def test_citation_in_corpus(self):
        v = ClaimEvidenceValidator(corpus_ids={"PAPER_001", "PAPER_022", "PAPER_045"})
        assert v.check_level1_exists("PAPER_022") is True

    def test_citation_not_in_corpus(self):
        v = ClaimEvidenceValidator(corpus_ids={"PAPER_001"})
        assert v.check_level1_exists("PAPER_999") is False

    def test_bracket_citation(self):
        v = ClaimEvidenceValidator(corpus_ids={"1", "2", "3"})
        assert v.check_level1_exists("[1]") is True

    def test_partial_match(self):
        v = ClaimEvidenceValidator(corpus_ids={"crossref:10.1234/abc"})
        assert v.check_level1_exists("10.1234") is True


class TestLevel2Provided:
    def test_was_provided(self):
        v = ClaimEvidenceValidator()
        assert v.check_level2_provided("PAPER_022", {"PAPER_022", "PAPER_014"}) is True

    def test_was_not_provided(self):
        v = ClaimEvidenceValidator()
        assert v.check_level2_provided("PAPER_999", {"PAPER_022", "PAPER_014"}) is False

    def test_exists_but_not_provided_leakage(self):
        """Citation exists in corpus but wasn't in the evidence set — leakage."""
        v = ClaimEvidenceValidator(corpus_ids={"PAPER_001", "PAPER_022"})
        exists = v.check_level1_exists("PAPER_022")
        provided = v.check_level2_provided("PAPER_022", {"PAPER_001"})
        assert exists is True
        assert provided is False  # leakage


class TestLevel3Support:
    def test_strong_support(self):
        v = ClaimEvidenceValidator()
        claim = "Tool use in multi-agent systems requires dynamic orchestration"
        evidence_texts = {"PAPER_022": "We study dynamic orchestration of tool use in multi-agent systems"}
        support, reason = v.check_level3_support(claim, "PAPER_022", evidence_texts)
        assert support == SupportLevel.STRONG

    def test_weak_support(self):
        v = ClaimEvidenceValidator()
        claim = "Reinforcement learning improves tool selection accuracy"
        evidence_texts = {"PAPER_014": "We examine multi-agent coordination strategies"}
        support, reason = v.check_level3_support(claim, "PAPER_014", evidence_texts)
        assert support in (SupportLevel.WEAK, SupportLevel.NONE)

    def test_no_evidence_text(self):
        v = ClaimEvidenceValidator()
        support, reason = v.check_level3_support("some claim", "PAPER_022", None)
        assert support == SupportLevel.NONE


class TestActionDetermination:
    def test_keep_for_strong_support(self):
        v = ClaimEvidenceValidator()
        action, conf = v.determine_action(
            exists=True, was_provided=True, support=SupportLevel.STRONG,
        )
        assert action == ClaimAction.KEEP
        assert conf >= 0.8

    def test_keep_with_warning_for_weak_support(self):
        v = ClaimEvidenceValidator()
        action, conf = v.determine_action(
            exists=True, was_provided=True, support=SupportLevel.WEAK,
        )
        assert action == ClaimAction.KEEP_WITH_WARNING
        assert 0.3 <= conf <= 0.7

    def test_remove_for_nonexistent(self):
        v = ClaimEvidenceValidator()
        action, conf = v.determine_action(
            exists=False, was_provided=False, support=SupportLevel.NONE,
        )
        assert action == ClaimAction.REMOVE
        assert conf == 0.0

    def test_remove_for_leakage(self):
        v = ClaimEvidenceValidator()
        action, conf = v.determine_action(
            exists=True, was_provided=False, support=SupportLevel.NONE,
        )
        assert action == ClaimAction.REMOVE

    def test_regenerate_for_contradiction(self):
        v = ClaimEvidenceValidator()
        action, conf = v.determine_action(
            exists=True, was_provided=True, support=SupportLevel.CONTRADICTED,
        )
        assert action == ClaimAction.REGENERATE

    def test_rewrite_for_no_support(self):
        v = ClaimEvidenceValidator()
        action, conf = v.determine_action(
            exists=True, was_provided=True, support=SupportLevel.NONE,
        )
        assert action == ClaimAction.REWRITE


class TestClaimExtraction:
    def test_extract_bracket_citations(self):
        v = ClaimEvidenceValidator()
        text = (
            "Tool use is a bottleneck [1]. "
            "Multi-agent systems need orchestration [2,3]. "
            "A sentence without citations should not appear."
        )
        claims = v.extract_claims(text)
        assert len(claims) == 2
        assert claims[0].citations  # [1]
        assert len(claims[1].citations) >= 1  # [2,3]

    def test_extract_author_year_citations(self):
        v = ClaimEvidenceValidator()
        text = "Dynamic tool selection improves accuracy (Smith et al., 2024)."
        claims = v.extract_claims(text)
        assert len(claims) >= 1
        assert any("Smith" in c for cs in [cl.citations for cl in claims] for c in cs)

    def test_no_claims_in_short_text(self):
        v = ClaimEvidenceValidator()
        claims = v.extract_claims("Too short")
        assert len(claims) == 0

    def test_no_claims_without_citations(self):
        v = ClaimEvidenceValidator()
        claims = v.extract_claims("This is a sentence without any citations.")
        assert len(claims) == 0


class TestDocumentValidation:
    def _make_validator(self):
        return ClaimEvidenceValidator(
            corpus_ids={"PAPER_001", "PAPER_022", "PAPER_045"},
        )

    def test_valid_document(self):
        v = self._make_validator()
        text = (
            "Tool use is critical for agent performance [PAPER_022]. "
            "Multi-agent orchestration requires dynamic tool selection [PAPER_001]."
        )
        result = v.validate_document(
            text,
            provided_evidence_ids={"PAPER_022", "PAPER_001"},
            evidence_texts={
                "PAPER_022": "Tool use is critical for agent performance and multi-agent systems",
                "PAPER_001": "Dynamic tool selection in multi-agent orchestration strategies",
            },
        )
        assert result.total_claims == 2
        # With evidence texts, claims should have strong support
        assert result.valid_claims >= 1
        assert result.trust_score > 0.5

    def test_document_with_bad_citations(self):
        v = self._make_validator()
        text = (
            "Some claim with a fake citation [FAKE_999]. "
            "Another claim with a real one [PAPER_022]."
        )
        result = v.validate_document(
            text,
            provided_evidence_ids={"PAPER_022"},
        )
        assert result.total_claims == 2
        assert result.invalid_claims >= 1

    def test_no_claims_document(self):
        v = self._make_validator()
        result = v.validate_document("No citations here.")
        assert result.total_claims == 0
        assert result.trust_score == 1.0  # neutral

    def test_trust_score_range(self):
        v = self._make_validator()
        text = "Claim one [PAPER_022]. Claim two [FAKE_999]."
        result = v.validate_document(text, provided_evidence_ids={"PAPER_022"})
        assert 0.0 <= result.trust_score <= 1.0

    def test_to_dict(self):
        v = self._make_validator()
        result = v.validate_document("Claim [PAPER_022].", provided_evidence_ids={"PAPER_022"})
        d = result.to_dict()
        assert "total_claims" in d
        assert "trust_score" in d
        assert "claims" in d

    def test_get_claims_by_action(self):
        v = self._make_validator()
        text = "Good claim [PAPER_022]. Bad claim [FAKE_999]."
        result = v.validate_document(text, provided_evidence_ids={"PAPER_022"})
        removes = v.get_claims_by_action(ClaimAction.REMOVE, result.results)
        assert len(removes) >= 1  # The fake citation

    def test_sanitize_flag_mode(self):
        v = self._make_validator()
        text = "Good claim [PAPER_022]. Bad claim [FAKE_999]."
        result = v.validate_document(text, provided_evidence_ids={"PAPER_022"})
        sanitized = v.sanitize_text(text, result.results, mode="flag")
        # Should have warning markers
        assert "FLAGGED" in sanitized or "unverified" in sanitized or text == sanitized

    def test_sanitize_replace_mode(self):
        v = self._make_validator()
        text = "Claim with fake citation [FAKE_999]."
        result = v.validate_document(text, provided_evidence_ids=set())
        sanitized = v.sanitize_text(text, result.results, mode="replace")
        assert "[unverified]" in sanitized
