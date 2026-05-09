"""Tests for source-anchored quote verification and staged confidence.

QA-01: Source-anchored quotes — LLM must produce verbatim quote, system verifies.
QA-02: Staged confidence — claims accumulate trust through verification stages.
QA-03: Simple corroboration — outlier detection against known claims.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.claims.corroboration import check_corroboration
from backend.pipeline.wiki.models import WikiEntry
from backend.pipeline.wiki.verifier import (
    ClaimVerificationResult,
    TrustTier,
    WikiVerifier,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wiki(**overrides) -> WikiEntry:
    defaults = dict(
        paper_id="TEST-001",
        proposed_method="Transformer architecture for sequence-to-sequence learning",
        key_insights=[
            "Self-attention mechanism avoids recurrence",
            "Achieves 28.4 BLEU on WMT English-to-German",
        ],
        experiments=[
            {"dataset": "WMT14 En-De", "metric": "BLEU", "value": "28.4"},
        ],
    )
    defaults.update(overrides)
    return WikiEntry(**defaults)


SOURCE_TEXT = """
The Transformer model architecture eschews recurrence and instead relies entirely
on a self-attention mechanism to draw global dependencies between input and output
sequences. The Transformer achieves 28.4 BLEU on the WMT 2014 English-to-German
translation task, improving over the existing best results, including ensembles.
Self-attention allows the model to look at all positions in the sequence simultaneously.
"""


def _mock_provider(response_json: dict) -> MagicMock:
    """Create a mock provider that returns the given JSON."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=json.dumps(response_json))
    return provider


# ---------------------------------------------------------------------------
# QA-01: Source-Anchored Quote Verification
# ---------------------------------------------------------------------------

class TestSourceAnchoredQuotes:
    """Test that LLM-provided quotes are verified against source text."""

    @pytest.fixture
    def source(self) -> str:
        return SOURCE_TEXT

    def test_quote_exact_match_verified(self, source):
        """When LLM provides exact quote from source → quote_verified=True."""
        verifier = WikiVerifier(provider=None)
        result = verifier._verify_quote_in_source(
            "The Transformer achieves 28.4 BLEU on the WMT 2014 English-to-German translation task",
            source,
        )
        assert result is True

    def test_fabricated_quote_detected(self, source):
        """When LLM fabricates a quote not in source → quote_verified=False."""
        quote = "The Transformer achieves 99.9% accuracy on ImageNet which is revolutionary"
        verifier = WikiVerifier(provider=None)
        result = verifier._verify_quote_in_source(quote, source)
        assert result is False

    def test_quote_with_minor_whitespace_fuzzy_match(self, source):
        """Fuzzy matching handles minor whitespace differences."""
        quote = "The Transformer achieves 28.4 BLEU on the WMT 2014 English-to-German  translation task"  # double space
        verifier = WikiVerifier(provider=None)
        result = verifier._verify_quote_in_source(quote, source)
        assert result is True

    def test_full_verification_pipeline_with_real_quote(self, source):
        """Full verify() flow: LLM returns real quote → HIGH trust tier."""
        provider = _mock_provider({
            "supported": True,
            "reasoning": "Source confirms the BLEU score",
            "supporting_quote": "The Transformer achieves 28.4 BLEU on the WMT 2014 English-to-German translation task",
        })
        verifier = WikiVerifier(provider=provider)
        wiki = _make_wiki()
        result = asyncio.run(verifier.verify(wiki, source))

        # Should have verification results
        assert hasattr(result, "verification_results")
        assert len(result.verification_results) > 0

        # At least one claim should have quote verified
        quote_verified = [cr for cr in result.verification_results if cr.quote_verified]
        assert len(quote_verified) >= 1

    def test_full_verification_pipeline_with_fabricated_quote(self, source):
        """Full verify() flow: LLM returns fabricated quote → marked UNSUPPORTED."""
        provider = _mock_provider({
            "supported": True,
            "reasoning": "Transformer is great",
            "supporting_quote": "The Transformer achieves 99.9% accuracy on ImageNet which is revolutionary and groundbreaking",
        })
        verifier = WikiVerifier(provider=provider)
        wiki = _make_wiki(
            key_insights=["Transformer achieves 99.9% on ImageNet"],
        )
        result = asyncio.run(verifier.verify(wiki, source))

        # Should detect fabricated quote
        fabricated = [cr for cr in result.verification_results if cr.quote_fabricated]
        assert len(fabricated) >= 1

    def test_no_provider_no_crash(self):
        """Verification works without provider (keyword fallback)."""
        verifier = WikiVerifier(provider=None)
        wiki = _make_wiki()
        result = asyncio.run(verifier.verify(wiki, SOURCE_TEXT))
        assert result.quality_score >= 0.0
        assert hasattr(result, "verification_results")


# ---------------------------------------------------------------------------
# QA-02: Staged Confidence
# ---------------------------------------------------------------------------

class TestStagedConfidence:
    """Test trust tier assignment and downstream action gates."""

    def test_trust_tier_ordering(self):
        """Trust tiers have correct ordering."""
        assert TrustTier.UNVERIFIED.value == "unverified"
        assert TrustTier.LOW.value == "low"
        assert TrustTier.MEDIUM.value == "medium"
        assert TrustTier.HIGH.value == "high"
        assert TrustTier.VERY_HIGH.value == "very_high"

    def test_is_actionable_display(self):
        """UNVERIFIED claims can be displayed."""
        assert WikiVerifier.is_actionable(TrustTier.UNVERIFIED, "display") is True
        assert WikiVerifier.is_actionable(TrustTier.LOW, "display") is True

    def test_is_actionable_gap_analysis(self):
        """LOW claims can't reach gap analysis."""
        assert WikiVerifier.is_actionable(TrustTier.LOW, "gap_analysis") is False
        assert WikiVerifier.is_actionable(TrustTier.MEDIUM, "gap_analysis") is True
        assert WikiVerifier.is_actionable(TrustTier.HIGH, "gap_analysis") is True

    def test_is_actionable_study_design(self):
        """MEDIUM claims can't reach study design."""
        assert WikiVerifier.is_actionable(TrustTier.MEDIUM, "study_design") is False
        assert WikiVerifier.is_actionable(TrustTier.HIGH, "study_design") is True

    def test_is_actionable_paper_draft(self):
        """Only VERY_HIGH claims reach paper draft."""
        assert WikiVerifier.is_actionable(TrustTier.HIGH, "paper_draft") is False
        assert WikiVerifier.is_actionable(TrustTier.VERY_HIGH, "paper_draft") is True

    def test_keyword_fallback_gets_low_tier(self):
        """Keyword-only verification gets LOW trust tier."""
        verifier = WikiVerifier(provider=None)
        wiki = _make_wiki()
        result = asyncio.run(verifier.verify(wiki, SOURCE_TEXT))

        for cr in result.verification_results:
            assert cr.trust_tier in (TrustTier.LOW, TrustTier.UNVERIFIED)

    def test_llm_without_quote_gets_medium_tier(self):
        """LLM verification without quote gets MEDIUM tier."""
        provider = _mock_provider({
            "supported": True,
            "reasoning": "Seems correct",
            "supporting_quote": None,
        })
        verifier = WikiVerifier(provider=provider)
        wiki = _make_wiki()
        result = asyncio.run(verifier.verify(wiki, SOURCE_TEXT))

        medium_claims = [cr for cr in result.verification_results if cr.trust_tier == TrustTier.MEDIUM]
        assert len(medium_claims) >= 1

    def test_llm_with_real_quote_gets_high_tier(self):
        """LLM verification with verified quote gets HIGH tier."""
        provider = _mock_provider({
            "supported": True,
            "reasoning": "Source confirms",
            "supporting_quote": "The Transformer achieves 28.4 BLEU on the WMT 2014 English-to-German translation task",
        })
        verifier = WikiVerifier(provider=provider)
        wiki = _make_wiki()
        result = asyncio.run(verifier.verify(wiki, SOURCE_TEXT))

        high_claims = [cr for cr in result.verification_results if cr.trust_tier == TrustTier.HIGH]
        assert len(high_claims) >= 1


# ---------------------------------------------------------------------------
# QA-03: Simple Corroboration
# ---------------------------------------------------------------------------

class TestCorroboration:
    """Test simple claim corroboration against known values."""

    def test_corroborated_claim_passes(self):
        """Claim within tolerance of known values → passes."""
        known = [
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.945},
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.940},
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.950},
        ]
        result = check_corroboration("accuracy", "SQuAD", 0.942, known)
        assert result is None  # Within range, no warning

    def test_outlier_claim_flagged(self):
        """Claim far from known values → flagged."""
        known = [
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.945},
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.940},
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.950},
        ]
        result = check_corroboration("accuracy", "SQuAD", 0.999, known)
        assert result is not None
        assert "differs" in result.lower()
        assert "3 corroborated" in result

    def test_insufficient_data_passes(self):
        """Fewer than min_corroborations → no check."""
        known = [
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.945},
        ]
        result = check_corroboration("accuracy", "SQuAD", 0.999, known, min_corroborations=2)
        assert result is None

    def test_different_dataset_no_interference(self):
        """Claims from different datasets don't interfere."""
        known = [
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.945},
            {"metric": "accuracy", "dataset": "SQuAD", "value": 0.940},
            {"metric": "accuracy", "dataset": "ImageNet", "value": 0.761},
        ]
        # ImageNet claim shouldn't affect SQuAD check
        result = check_corroboration("accuracy", "SQuAD", 0.942, known)
        assert result is None
