"""BATCH-123 Tests — Wiki Generation Service.

AIV v5.3 — 8 tests across 2 tasks.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.wiki.generator import WikiGenerator
from backend.pipeline.wiki.models import WikiEntry
from backend.pipeline.wiki.verifier import WikiVerifier

# ═══════════════════════════════════════════════════════════
# TASK-01: WikiEntry Model + WikiGenerator
# ═══════════════════════════════════════════════════════════


def _mock_wiki_response():
    return {
        "one_line_summary": "Proposes Transformer architecture for sequence modeling",
        "problem_statement": "Existing sequence models struggle with long-range dependencies",
        "proposed_method": "Self-attention based Transformer architecture",
        "key_insights": [
            "Self-attention can replace recurrence entirely",
            "Achieves SOTA on translation tasks",
        ],
        "method_details": {
            "architecture": "Encoder-decoder with multi-head attention",
            "training_procedure": "Adam optimizer with warmup",
        },
        "experiments": [
            {"dataset": "WMT 2014 EN-DE", "metric": "BLEU", "value": "28.4"}
        ],
        "limitations": ["Quadratic memory complexity"],
        "future_work": ["Restricted attention for longer sequences"],
        "connections": ["BERT", "GPT"],
        "tags": ["transformers", "attention", "NLP"],
        "novelty_assessment": "breakthrough",
        "contribution_type": "methodological",
        "domain": "NLP",
        "subdomain": "Sequence Modeling",
    }


class TestWikiGenerator:
    """TEST-123-01-01 through TEST-123-01-04."""

    def test_wiki_entry_has_all_fields(self):
        """TEST-123-01-01: WikiEntry has all required fields."""
        wiki = WikiEntry(paper_id="test")
        required_attrs = [
            "paper_id", "one_line_summary", "problem_statement",
            "proposed_method", "key_insights", "method_details",
            "experiments", "limitations", "future_work",
            "connections", "code_and_resources", "tags",
            "novelty_assessment", "contribution_type",
            "domain", "subdomain", "quality_score",
            "unsupported_claims", "related_methods",
            "potential_applications", "reproducibility_notes",
        ]
        for attr in required_attrs:
            assert hasattr(wiki, attr), f"Missing: {attr}"

    def test_generator_returns_wiki_from_mock(self):
        """TEST-123-01-02: WikiGenerator returns WikiEntry from mock LLM."""
        provider = MagicMock()
        provider.structured_output = AsyncMock(return_value=_mock_wiki_response())
        gen = WikiGenerator(provider=provider)

        wiki = asyncio.run(gen.generate("paper text about transformers", paper_id="P1"))

        assert isinstance(wiki, WikiEntry)
        assert wiki.paper_id == "P1"
        assert wiki.one_line_summary != ""
        assert len(wiki.key_insights) > 0
        assert wiki.novelty_assessment == "breakthrough"

    def test_generator_returns_empty_on_failure(self):
        """TEST-123-01-03: WikiGenerator returns empty WikiEntry on failure (HB-01)."""
        provider = MagicMock()
        provider.structured_output = AsyncMock(side_effect=RuntimeError("fail"))
        gen = WikiGenerator(provider=provider)

        wiki = asyncio.run(gen.generate("text", paper_id="P2"))
        assert isinstance(wiki, WikiEntry)
        assert wiki.paper_id == "P2"
        assert wiki.one_line_summary == ""  # Empty defaults (HB-01)

    def test_prompt_exists_with_closed_book(self):
        """TEST-123-01-04: Prompt template exists with closed-book instruction."""
        prompt_path = Path("backend/pipeline/wiki/prompts/wiki_generation.md")
        assert prompt_path.exists(), f"Missing prompt at {prompt_path}"
        content = prompt_path.read_text(encoding="utf-8")
        assert "CLOSED-BOOK" in content


# ═══════════════════════════════════════════════════════════
# TASK-02: WikiVerifier
# ═══════════════════════════════════════════════════════════


class TestWikiVerifier:
    """TEST-123-02-01 through TEST-123-02-04."""

    def test_verifier_sets_quality_score(self):
        """TEST-123-02-01: WikiVerifier sets quality_score."""
        verifier = WikiVerifier()
        wiki = WikiEntry(
            paper_id="P1",
            proposed_method="Transformer architecture with self-attention",
            key_insights=["Self-attention replaces recurrence entirely"],
        )
        source = (
            "We propose a Transformer architecture that uses self-attention "
            "to replace recurrence entirely for sequence modeling tasks."
        )
        result = asyncio.run(verifier.verify(wiki, source))
        assert result.quality_score > 0

    def test_verifier_flags_unsupported_claims(self):
        """TEST-123-02-02: WikiVerifier flags unsupported claims."""
        verifier = WikiVerifier()
        wiki = WikiEntry(
            paper_id="P1",
            proposed_method="Quantum computing approach to protein folding",
            key_insights=["Uses quantum entanglement for molecular simulation"],
        )
        source = "We propose a simple neural network for image classification."
        result = asyncio.run(verifier.verify(wiki, source))
        assert len(result.unsupported_claims) > 0

    def test_verifier_does_not_modify_original(self):
        """TEST-123-02-03: WikiVerifier does NOT modify original wiki (HB-02)."""
        verifier = WikiVerifier()
        wiki = WikiEntry(
            paper_id="P1",
            proposed_method="Test method",
            quality_score=0.0,
        )
        original_score = wiki.quality_score
        original_unsupported = len(wiki.unsupported_claims)

        asyncio.run(verifier.verify(wiki, "some source text"))

        assert wiki.quality_score == original_score  # HB-02
        assert len(wiki.unsupported_claims) == original_unsupported

    def test_verifier_handles_empty_source(self):
        """TEST-123-02-04: WikiVerifier handles empty source text."""
        verifier = WikiVerifier()
        wiki = WikiEntry(paper_id="P1", proposed_method="Test")
        result = asyncio.run(verifier.verify(wiki, ""))
        assert result.quality_score < 0.5  # Low quality
        assert len(result.unsupported_claims) > 0
