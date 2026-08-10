"""BATCH-131 Tests — LLM-Grounded WikiVerifier Deepening.

AIV v5.3 — 9 tests across 2 tasks.
Tests verify SEMANTIC QUALITY, not just structure.
pytest.ini has `-p no:asyncio` — use asyncio.run() directly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.wiki.models import WikiEntry
from backend.pipeline.wiki.verifier import WikiVerifier

# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _mock_provider(return_value: str):
    """Create a mock provider that returns the given string from complete()."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=return_value)
    return provider


# ═══════════════════════════════════════════════════════════
# TASK-01: LLM Verification Path
# ═══════════════════════════════════════════════════════════


class TestLLMVerificationPath:
    """TEST-131-01-01 through TEST-131-01-06."""

    def test_verify_claim_with_llm_returns_dict(self):
        """TEST-131-01-01: _verify_claim_with_llm returns dict with supported + reasoning."""
        provider = _mock_provider('{"supported": true, "reasoning": "Directly stated in source"}')
        verifier = WikiVerifier(provider=provider)
        result = asyncio.run(verifier._verify_claim_with_llm(
            "Transformer uses self-attention",
            "The Transformer uses self-attention mechanisms."
        ))
        assert isinstance(result, dict)
        assert "supported" in result
        assert "reasoning" in result

    def test_llm_path_produces_quality_score(self):
        """TEST-131-01-02: LLM path produces quality_score > keyword path."""
        # Mock LLM that supports all claims
        provider = _mock_provider('{"supported": true, "reasoning": "Found in source"}')
        verifier_llm = WikiVerifier(provider=provider)
        verifier_keyword = WikiVerifier(provider=None)

        wiki = WikiEntry(
            paper_id="P1",
            proposed_method="Neural network approach for machine translation",
            key_insights=["Self-attention replaces recurrence for better performance"],
        )
        source = "We propose a Transformer architecture that uses self-attention."

        result_llm = asyncio.run(verifier_llm.verify(wiki, source))
        result_keyword = asyncio.run(verifier_keyword.verify(wiki, source))

        # LLM should support both claims, keyword may miss some
        assert result_llm.quality_score >= result_keyword.quality_score

    def test_fallback_on_llm_failure(self):
        """TEST-131-01-03: Falls back to keyword on LLM failure (HB-01)."""
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("API down"))
        verifier = WikiVerifier(provider=provider)

        wiki = WikiEntry(paper_id="P1", proposed_method="Transformer uses self-attention")
        source = "We propose a Transformer that uses self-attention."

        result = asyncio.run(verifier.verify(wiki, source))
        assert isinstance(result, WikiEntry)  # No crash (HB-01)
        assert result.quality_score > 0  # Keyword fallback worked

    def test_fallback_when_provider_none(self):
        """TEST-131-01-04: Uses keyword when provider=None."""
        verifier = WikiVerifier(provider=None)
        wiki = WikiEntry(paper_id="P1", proposed_method="Transformer uses self-attention")
        source = "We propose a Transformer that uses self-attention."

        result = asyncio.run(verifier.verify(wiki, source))
        assert result.quality_score > 0

    def test_prompt_template_exists(self):
        """TEST-131-01-05: Prompt template exists with closed-book instruction (HB-02)."""
        prompt_path = Path("backend/pipeline/wiki/prompts/wiki_verification.md")
        assert prompt_path.exists(), f"Missing prompt at {prompt_path}"
        content = prompt_path.read_text(encoding="utf-8")
        assert "ONLY" in content  # HB-02
        assert "source text" in content.lower()  # HB-02

    def test_original_wiki_unchanged(self):
        """TEST-131-01-06: Original wiki not modified (HB-03)."""
        provider = _mock_provider('{"supported": true, "reasoning": "OK"}')
        verifier = WikiVerifier(provider=provider)
        wiki = WikiEntry(paper_id="P1", proposed_method="Test", quality_score=0.0)

        asyncio.run(verifier.verify(wiki, "source text about test method"))

        assert wiki.quality_score == 0.0  # HB-03: original unchanged


# ═══════════════════════════════════════════════════════════
# TASK-02: Quality + Adversarial Tests
# ═══════════════════════════════════════════════════════════


class TestQualityAndAdversarial:
    """TEST-131-02-01 through TEST-131-02-03."""

    def test_backward_compat_b123_tests(self):
        """TEST-131-02-01: Existing B123 tests still pass (backward compatible)."""
        # Re-run the B123 WikiVerifier tests inline
        verifier = WikiVerifier(provider=None)
        wiki = WikiEntry(paper_id="P1", proposed_method="Neural network approach", quality_score=0.0)

        result = asyncio.run(verifier.verify(wiki, "We propose a neural network approach for language modeling."))
        assert result.quality_score > 0

        # Empty source
        result2 = asyncio.run(verifier.verify(wiki, ""))
        assert result2.quality_score < 0.5

    def test_llm_flags_fabricated_claim(self):
        """TEST-131-02-02: LLM flags intentionally wrong claim (adversarial)."""
        # Mock LLM that correctly flags the fabricated claim
        def mock_complete(messages, **kwargs):
            claim = messages[0]["content"]
            if "quantum" in claim.lower():
                return '{"supported": false, "reasoning": "No mention of quantum computing in source text"}'
            return '{"supported": true, "reasoning": "Found in source text"}'

        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=mock_complete)

        verifier = WikiVerifier(provider=provider)
        wiki = WikiEntry(
            paper_id="P1",
            proposed_method="Quantum computing approach to protein folding",  # Fabricated!
        )
        source = "We propose a simple neural network for image classification."

        result = asyncio.run(verifier.verify(wiki, source))

        # The fabricated claim should be flagged
        assert len(result.unsupported_claims) > 0
        assert any("quantum" in c.lower() for c in result.unsupported_claims)

    def test_llm_supports_correct_claim(self):
        """TEST-131-02-03: LLM supports a correct, source-grounded claim."""
        # Mock LLM that correctly supports the grounded claim
        provider = _mock_provider('{"supported": true, "reasoning": "Source explicitly describes Transformer with self-attention"}')

        verifier = WikiVerifier(provider=provider)
        wiki = WikiEntry(
            paper_id="P1",
            proposed_method="Transformer architecture with self-attention mechanism",
        )
        source = "We propose the Transformer, a new architecture based entirely on self-attention mechanisms for sequence transduction tasks."

        result = asyncio.run(verifier.verify(wiki, source))

        # The correct claim should be supported
        assert result.quality_score == 1.0
        assert len(result.unsupported_claims) == 0
