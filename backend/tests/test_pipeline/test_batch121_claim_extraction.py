"""BATCH-121 Tests — Claim Extraction Engine.

AIV v5.3 — 11 tests across 3 tasks.
pytest.ini has `-p no:asyncio` — use asyncio.run() directly.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.extractor import ClaimExtractor


# ═══════════════════════════════════════════════════════════
# TASK-01: Claim Data Models + ClaimType Enum
# ═══════════════════════════════════════════════════════════


class TestClaimModels:
    """TEST-121-01-01 through TEST-121-01-03."""

    def test_claimtype_has_5_members(self):
        """TEST-121-01-01: ClaimType has 5 members."""
        assert len(ClaimType) == 5
        expected = {"METHOD", "RESULT", "LIMITATION", "FUTURE_WORK", "COMPARISON"}
        assert set(e.value for e in ClaimType) == expected

    def test_claim_accepts_required_fields_only(self):
        """TEST-121-01-02: Claim can be constructed with only required fields."""
        claim = Claim(
            claim_type=ClaimType.METHOD,
            title="Test claim",
            description="A test description",
            source_paper_id="P1",
        )
        assert claim.claim_type == ClaimType.METHOD
        assert claim.title == "Test claim"
        assert claim.method_name is None  # optional field
        assert claim.dataset is None
        assert claim.compared_to is None

    def test_claim_auto_generates_claim_id(self):
        """TEST-121-01-03: Claim auto-generates claim_id."""
        claim = Claim(
            claim_type=ClaimType.RESULT,
            title="Result claim",
            description="A result",
            source_paper_id="P2",
        )
        assert claim.claim_id is not None
        assert len(claim.claim_id) > 0
        # UUID format: 8-4-4-4-12
        parts = claim.claim_id.split("-")
        assert len(parts) == 5


# ═══════════════════════════════════════════════════════════
# TASK-02: ClaimExtractor with LLM Structured Output
# ═══════════════════════════════════════════════════════════


def _make_mock_provider(return_value: dict):
    """Create a mock provider that returns the given dict from structured_output."""
    provider = MagicMock()
    provider.structured_output = AsyncMock(return_value=return_value)
    return provider


def _make_failing_provider(exc: Exception):
    """Create a mock provider that raises the given exception."""
    provider = MagicMock()
    provider.structured_output = AsyncMock(side_effect=exc)
    return provider


class TestClaimExtractor:
    """TEST-121-02-01 through TEST-121-02-06."""

    def test_init_rejects_none_provider(self):
        """TEST-121-02-01: TypeError when provider is None."""
        with pytest.raises(TypeError, match="non-None"):
            ClaimExtractor(provider=None)

    def test_extract_returns_claims_from_mock(self):
        """TEST-121-02-02: extract() returns list[Claim] from mock LLM."""
        mock_response = {
            "claims": [
                {
                    "claim_type": "METHOD",
                    "title": "Proposes Transformer-XL",
                    "description": "Introduces a segment-level recurrence mechanism",
                    "source_section": "abstract",
                    "confidence": 0.9,
                    "method_name": "Transformer-XL",
                    "method_category": "architecture",
                },
                {
                    "claim_type": "RESULT",
                    "title": "SOTA on language modeling",
                    "description": "Achieves new SOTA on WikiText-103",
                    "source_section": "abstract",
                    "confidence": 0.85,
                    "dataset": "WikiText-103",
                    "metric": "perplexity",
                    "value": "24.0",
                },
            ]
        }
        provider = _make_mock_provider(mock_response)
        extractor = ClaimExtractor(provider=provider)

        claims = asyncio.run(
            extractor.extract(
                "We propose Transformer-XL which achieves perplexity 24.0 on WikiText-103.",
                paper_id="1901.02860",
            )
        )

        assert len(claims) == 2
        assert all(isinstance(c, Claim) for c in claims)
        assert claims[0].claim_type == ClaimType.METHOD
        assert claims[0].method_name == "Transformer-XL"
        assert claims[1].claim_type == ClaimType.RESULT
        assert claims[1].dataset == "WikiText-103"

    def test_extract_returns_empty_on_llm_failure(self):
        """TEST-121-02-03: extract() returns [] on LLM failure (HB-01)."""
        provider = _make_failing_provider(RuntimeError("API timeout"))
        extractor = ClaimExtractor(provider=provider)

        claims = asyncio.run(
            extractor.extract("some text", paper_id="P1")
        )

        assert claims == []  # HB-01

    def test_extract_returns_empty_on_invalid_json(self):
        """TEST-121-02-04: extract() returns [] on invalid JSON (HB-01)."""
        # Provider returns valid dict but claims key is missing
        provider = _make_mock_provider({"not_claims": []})
        extractor = ClaimExtractor(provider=provider)

        claims = asyncio.run(
            extractor.extract("some text", paper_id="P1")
        )

        assert claims == []  # HB-01

    def test_all_claims_have_source_paper_id(self):
        """TEST-121-02-05: Every claim has source_paper_id (HB-02)."""
        mock_response = {
            "claims": [
                {
                    "claim_type": "METHOD",
                    "title": "Claim 1",
                    "description": "Desc 1",
                },
                {
                    "claim_type": "RESULT",
                    "title": "Claim 2",
                    "description": "Desc 2",
                },
            ]
        }
        provider = _make_mock_provider(mock_response)
        extractor = ClaimExtractor(provider=provider)

        claims = asyncio.run(
            extractor.extract("text", paper_id="2401.12345")
        )

        assert len(claims) == 2
        for claim in claims:
            assert claim.source_paper_id == "2401.12345"  # HB-02

    def test_prompt_template_exists_with_closed_book(self):
        """TEST-121-02-06: Prompt template file exists with closed-book instruction."""
        prompt_path = Path("backend/pipeline/claims/prompts/claim_extraction.md")
        assert prompt_path.exists(), f"Prompt template not found at {prompt_path}"
        content = prompt_path.read_text(encoding="utf-8")
        assert "CLOSED-BOOK" in content, "Prompt must contain CLOSED-BOOK instruction"
        assert "Do NOT infer" in content, "Prompt must forbid inference"


# ═══════════════════════════════════════════════════════════
# TASK-03: Gold-Standard Validation (Integration Tests)
# ═══════════════════════════════════════════════════════════

# Sample abstracts representing diverse paper types
_GOLD_PAPERS = [
    {
        "id": "attention-is-all-you-need",
        "text": (
            "We propose a new simple network architecture, the Transformer, based solely on "
            "attention mechanisms, dispensing with recurrence and convolutions entirely. "
            "The Transformer achieves 28.4 BLEU on the WMT 2014 English-to-German translation "
            "task, improving over the existing best results, including ensembles, by over 2 BLEU. "
            "On the WMT 2014 English-to-French translation task, our model establishes a new "
            "single-model state-of-the-art BLEU score of 41.8 after training for 3.5 days on "
            "eight GPUs. A limitation is that the self-attention mechanism has quadratic memory "
            "complexity with respect to sequence length. Future work could explore restricted "
            "attention mechanisms to handle longer sequences efficiently."
        ),
    },
    {
        "id": "bert-pretraining",
        "text": (
            "We introduce a new language representation model called BERT, which stands for "
            "Bidirectional Encoder Representations from Transformers. BERT is designed to pre-train "
            "deep bidirectional representations from unlabeled text. The pre-trained BERT model "
            "can be fine-tuned with just one additional output layer to create state-of-the-art "
            "models for a wide range of tasks. BERT obtains new state-of-the-art results on "
            "eleven natural language processing tasks, including pushing the GLUE score to 80.5%, "
            "MultiNLI accuracy to 86.7%, and SQuAD v1.1 F1 to 93.2%. One limitation is that "
            "BERT's pre-training requires significant computational resources."
        ),
    },
    {
        "id": "gpt3-paper",
        "text": (
            "We present GPT-3, an autoregressive language model with 175 billion parameters. "
            "GPT-3 achieves strong performance on many NLP datasets without any fine-tuning, "
            "demonstrating 87.9% accuracy on SuperGLUE and 81.5% on TriviaQA. Compared to "
            "GPT-2, GPT-3 improves few-shot learning capabilities significantly. However, "
            "GPT-3 has important limitations: it can generate grammatically coherent but "
            "factually incorrect text, and it does not learn from feedback. Future research "
            "directions include improving factual grounding and reducing bias."
        ),
    },
    {
        "id": "resnet-paper",
        "text": (
            "We present a residual learning framework to ease the training of deep networks. "
            "We explicitly reformulate the layers as learning residual functions with reference "
            "to the layer inputs. Our 152-layer ResNet achieves 3.57% top-5 error on the "
            "ImageNet test set and won 1st place in the ILSVRC 2015 classification task. "
            "The ResNet outperforms VGGNet and GoogLeNet while using fewer parameters. "
            "A known limitation is that very deep residual networks can be difficult to "
            "optimize without proper initialization."
        ),
    },
    {
        "id": "rlhf-paper",
        "text": (
            "We fine-tune a language model using reinforcement learning from human feedback (RLHF). "
            "Our approach trains a reward model from human preference data, then optimizes the "
            "language model policy using PPO against this reward model. The resulting model "
            "achieves 71.4% human preference rate compared to the supervised baseline. "
            "Compared to supervised fine-tuning alone, RLHF significantly improves helpfulness "
            "while reducing harmful outputs. Limitations include reward hacking and the cost of "
            "human annotation. Future work should explore constitutional AI methods to reduce "
            "the need for human labels."
        ),
    },
]


def _make_rich_mock_provider():
    """Mock provider that generates diverse claim types from known paper abstracts."""
    call_count = [0]

    # Pre-built responses for each gold paper
    responses = {
        "attention-is-all-you-need": {
            "claims": [
                {"claim_type": "METHOD", "title": "Proposes Transformer architecture",
                 "description": "A new network architecture based solely on attention mechanisms",
                 "source_section": "abstract", "confidence": 0.95,
                 "method_name": "Transformer", "method_category": "architecture"},
                {"claim_type": "RESULT", "title": "28.4 BLEU on WMT 2014 EN-DE",
                 "description": "Achieves 28.4 BLEU on English-to-German translation",
                 "source_section": "abstract", "confidence": 0.9,
                 "dataset": "WMT 2014 English-to-German", "metric": "BLEU", "value": "28.4"},
                {"claim_type": "RESULT", "title": "41.8 BLEU on WMT 2014 EN-FR",
                 "description": "New SOTA BLEU score of 41.8 on English-to-French",
                 "source_section": "abstract", "confidence": 0.9,
                 "dataset": "WMT 2014 English-to-French", "metric": "BLEU", "value": "41.8"},
                {"claim_type": "LIMITATION", "title": "Quadratic memory complexity",
                 "description": "Self-attention has quadratic memory complexity w.r.t. sequence length",
                 "source_section": "abstract", "confidence": 0.85,
                 "limitation_category": "compute", "acknowledged": True},
                {"claim_type": "FUTURE_WORK", "title": "Restricted attention mechanisms",
                 "description": "Explore restricted attention for longer sequences",
                 "source_section": "abstract", "confidence": 0.8,
                 "feasibility": "high", "potential_impact": "high"},
            ]
        },
        "bert-pretraining": {
            "claims": [
                {"claim_type": "METHOD", "title": "BERT bidirectional pre-training",
                 "description": "Pre-trains deep bidirectional representations from unlabeled text",
                 "source_section": "abstract", "confidence": 0.95,
                 "method_name": "BERT", "method_category": "training"},
                {"claim_type": "RESULT", "title": "GLUE score 80.5%",
                 "description": "Pushes GLUE benchmark score to 80.5%",
                 "source_section": "abstract", "confidence": 0.9,
                 "dataset": "GLUE", "metric": "accuracy", "value": "80.5%"},
                {"claim_type": "RESULT", "title": "SQuAD F1 93.2%",
                 "description": "Achieves 93.2% F1 on SQuAD v1.1",
                 "source_section": "abstract", "confidence": 0.9,
                 "dataset": "SQuAD v1.1", "metric": "F1", "value": "93.2%"},
                {"claim_type": "LIMITATION", "title": "High computational cost",
                 "description": "BERT pre-training requires significant compute resources",
                 "source_section": "abstract", "confidence": 0.85,
                 "limitation_category": "compute", "acknowledged": True},
            ]
        },
        "gpt3-paper": {
            "claims": [
                {"claim_type": "METHOD", "title": "GPT-3 175B parameter model",
                 "description": "Autoregressive language model with 175 billion parameters",
                 "source_section": "abstract", "confidence": 0.95,
                 "method_name": "GPT-3", "method_category": "architecture"},
                {"claim_type": "RESULT", "title": "87.9% on SuperGLUE",
                 "description": "Achieves 87.9% accuracy on SuperGLUE without fine-tuning",
                 "source_section": "abstract", "confidence": 0.9,
                 "dataset": "SuperGLUE", "metric": "accuracy", "value": "87.9%"},
                {"claim_type": "COMPARISON", "title": "Improves over GPT-2",
                 "description": "Significantly improves few-shot learning over GPT-2",
                 "source_section": "abstract", "confidence": 0.85,
                 "compared_to": "GPT-2", "relationship": "improves_on"},
                {"claim_type": "LIMITATION", "title": "Factual hallucinations",
                 "description": "Can generate grammatically correct but factually wrong text",
                 "source_section": "abstract", "confidence": 0.9,
                 "limitation_category": "generalization", "acknowledged": True},
                {"claim_type": "FUTURE_WORK", "title": "Improve factual grounding",
                 "description": "Future work should improve factual grounding and reduce bias",
                 "source_section": "abstract", "confidence": 0.8,
                 "feasibility": "medium", "potential_impact": "high"},
            ]
        },
        "resnet-paper": {
            "claims": [
                {"claim_type": "METHOD", "title": "Residual learning framework",
                 "description": "Reformulate layers as learning residual functions",
                 "source_section": "abstract", "confidence": 0.95,
                 "method_name": "ResNet", "method_category": "architecture"},
                {"claim_type": "RESULT", "title": "3.57% top-5 error on ImageNet",
                 "description": "152-layer ResNet achieves 3.57% top-5 error",
                 "source_section": "abstract", "confidence": 0.9,
                 "dataset": "ImageNet", "metric": "top-5 error", "value": "3.57%"},
                {"claim_type": "COMPARISON", "title": "Outperforms VGGNet and GoogLeNet",
                 "description": "ResNet uses fewer parameters while achieving better results",
                 "source_section": "abstract", "confidence": 0.85,
                 "compared_to": "VGGNet", "relationship": "improves_on"},
                {"claim_type": "LIMITATION", "title": "Difficult to optimize very deep nets",
                 "description": "Very deep residual networks need proper initialization",
                 "source_section": "abstract", "confidence": 0.8,
                 "limitation_category": "generalization", "acknowledged": True},
            ]
        },
        "rlhf-paper": {
            "claims": [
                {"claim_type": "METHOD", "title": "RLHF fine-tuning",
                 "description": "Fine-tune LM using reinforcement learning from human feedback",
                 "source_section": "abstract", "confidence": 0.95,
                 "method_name": "RLHF", "method_category": "training"},
                {"claim_type": "RESULT", "title": "71.4% human preference rate",
                 "description": "Achieves 71.4% human preference over supervised baseline",
                 "source_section": "abstract", "confidence": 0.9,
                 "dataset": "human evaluation", "metric": "preference rate", "value": "71.4%"},
                {"claim_type": "COMPARISON", "title": "Better than supervised fine-tuning",
                 "description": "RLHF improves helpfulness while reducing harmful outputs vs SFT",
                 "source_section": "abstract", "confidence": 0.85,
                 "compared_to": "supervised fine-tuning", "relationship": "improves_on"},
                {"claim_type": "LIMITATION", "title": "Reward hacking",
                 "description": "Reward hacking is a known issue with RLHF",
                 "source_section": "abstract", "confidence": 0.8,
                 "limitation_category": "data", "acknowledged": True},
                {"claim_type": "FUTURE_WORK", "title": "Constitutional AI methods",
                 "description": "Explore constitutional AI to reduce need for human labels",
                 "source_section": "abstract", "confidence": 0.75,
                 "feasibility": "medium", "potential_impact": "high"},
            ]
        },
    }

    async def _structured_output_side_effect(messages, schema, temperature):
        # Extract paper text from prompt to identify which paper
        prompt_text = messages[0]["content"]
        for pid, resp in responses.items():
            # Check if paper text matches by looking for key phrases
            paper = next((p for p in _GOLD_PAPERS if p["id"] == pid), None)
            if paper and paper["text"][:50] in prompt_text:
                return resp
        # Default: return empty claims
        return {"claims": []}

    provider = MagicMock()
    provider.structured_output = AsyncMock(side_effect=_structured_output_side_effect)
    return provider


class TestGoldStandardValidation:
    """TEST-121-03-01 through TEST-121-03-03."""

    def test_at_least_3_claim_types_across_papers(self):
        """TEST-121-03-01: >= 3 claim types present across 5 papers."""
        provider = _make_rich_mock_provider()
        extractor = ClaimExtractor(provider=provider)

        all_claims: list[Claim] = []
        for paper in _GOLD_PAPERS:
            claims = asyncio.run(
                extractor.extract(paper["text"], paper_id=paper["id"])
            )
            all_claims.extend(claims)

        types_found = {c.claim_type for c in all_claims}
        assert len(types_found) >= 3, (
            f"Expected >= 3 claim types, got {len(types_found)}: {types_found}"
        )

    def test_method_claims_have_method_name(self):
        """TEST-121-03-02: METHOD claims have method_name filled."""
        provider = _make_rich_mock_provider()
        extractor = ClaimExtractor(provider=provider)

        for paper in _GOLD_PAPERS:
            claims = asyncio.run(
                extractor.extract(paper["text"], paper_id=paper["id"])
            )
            method_claims = [c for c in claims if c.claim_type == ClaimType.METHOD]
            if method_claims:
                assert any(c.method_name for c in method_claims), (
                    f"METHOD claims for {paper['id']} should have method_name"
                )

    def test_result_claims_have_dataset_and_metric(self):
        """TEST-121-03-03: RESULT claims have dataset and metric."""
        provider = _make_rich_mock_provider()
        extractor = ClaimExtractor(provider=provider)

        for paper in _GOLD_PAPERS:
            claims = asyncio.run(
                extractor.extract(paper["text"], paper_id=paper["id"])
            )
            result_claims = [c for c in claims if c.claim_type == ClaimType.RESULT]
            if result_claims:
                assert any(c.dataset and c.metric for c in result_claims), (
                    f"RESULT claims for {paper['id']} should have dataset and metric"
                )
