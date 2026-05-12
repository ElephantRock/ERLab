"""Tests for jina-reranker-v3 integration and reranker factory."""

import asyncio
import pytest

from backend.pipeline.knowledge.reranker import (
    JinaCrossEncoderReranker,
    LMStudioReranker,
    LLMReranker,
    CrossEncoderReranker,
    ScoredDocument,
    create_reranker,
)


SAMPLE_DOCS = [
    {"id": "d1", "text": "The Transformer architecture uses self-attention mechanisms for sequence processing."},
    {"id": "d2", "text": "Baking bread requires flour, water, yeast, and salt."},
    {"id": "d3", "text": "BERT achieves bidirectional representations by masking tokens during pre-training."},
    {"id": "d4", "text": "The weather today is sunny with mild temperatures."},
]
QUERY = "What is the Transformer architecture?"


# ── ScoredDocument Tests ───────────────────────────────────────────────

def test_scored_document():
    """ScoredDocument stores all fields."""
    doc = ScoredDocument(id="p1", text="hello", score=0.9, metadata={"src": "s2"})
    assert doc.id == "p1"
    assert doc.score == 0.9


# ── JinaCrossEncoderReranker (heuristic fallback) Tests ────────────────

def test_jina_reranker_heuristic_fallback():
    """JinaCrossEncoderReranker falls back to heuristic when model fails to load."""
    reranker = JinaCrossEncoderReranker(model_id="nonexistent-model")
    result = asyncio.run(reranker.rerank(QUERY, SAMPLE_DOCS, top_k=3))
    assert len(result) <= 3
    # Heuristic scores based on keyword overlap
    assert all(isinstance(r.score, float) for r in result)


def test_jina_reranker_empty_docs():
    """JinaCrossEncoderReranker handles empty document list."""
    reranker = JinaCrossEncoderReranker()
    result = asyncio.run(reranker.rerank("query", []))
    assert result == []


def test_jina_reranker_heuristic_scores_ordered():
    """Heuristic fallback orders by score descending."""
    reranker = JinaCrossEncoderReranker(model_id="nonexistent-model")
    result = asyncio.run(reranker.rerank(QUERY, SAMPLE_DOCS))
    scores = [r.score for r in result]
    assert scores == sorted(scores, reverse=True)


def test_jina_reranker_heuristic_query_overlap():
    """Heuristic gives higher score to docs with query keywords."""
    reranker = JinaCrossEncoderReranker(model_id="nonexistent-model")
    result = asyncio.run(reranker.rerank("transformer", SAMPLE_DOCS))
    # d1 mentions "Transformer" → should score highest
    assert result[0].id == "d1"


def test_jina_reranker_set_fallback():
    """set_fallback configures alternative reranker."""
    primary = JinaCrossEncoderReranker(model_id="nonexistent-model")
    fallback = LMStudioReranker(api_base="http://localhost:9999/v1")
    primary.set_fallback(fallback)
    assert primary._fallback is fallback


# ── LLMReranker Tests ──────────────────────────────────────────────────

class MockProvider:
    """Mock LLM provider for testing."""
    async def complete(self, messages, **kwargs):
        return "0.85"


class MockProviderBad:
    """Mock provider that returns non-numeric."""
    async def complete(self, messages, **kwargs):
        return "I think this is relevant"


def test_llm_reranker():
    """LLMReranker scores documents via provider."""
    reranker = LLMReranker(MockProvider())
    result = asyncio.run(reranker.rerank(QUERY, SAMPLE_DOCS, top_k=2))
    assert len(result) == 2
    assert result[0].score == 0.85


def test_llm_reranker_extracts_score():
    """LLMReranker._extract_score handles various formats."""
    assert LLMReranker._extract_score("0.85") == 0.85
    assert LLMReranker._extract_score("Score: 0.7") == 0.7
    assert LLMReranker._extract_score("not a number") == 0.5  # default


def test_llm_reranker_handles_bad_response():
    """LLMReranker handles non-numeric responses."""
    reranker = LLMReranker(MockProviderBad())
    result = asyncio.run(reranker.rerank(QUERY, SAMPLE_DOCS[:1]))
    # Default score when parsing fails
    assert result[0].score == 0.5


# ── Factory Tests ──────────────────────────────────────────────────────

def test_create_reranker_auto():
    """create_reranker('auto') returns RemoteReranker with fallback chain."""
    from backend.pipeline.knowledge.reranker import RemoteReranker

    reranker = create_reranker("auto")
    assert isinstance(reranker, RemoteReranker)
    assert reranker._fallback is not None  # Has JinaCrossEncoderReranker fallback


def test_create_reranker_cross_encoder():
    """create_reranker('cross-encoder') returns JinaCrossEncoderReranker."""
    reranker = create_reranker("cross-encoder")
    assert isinstance(reranker, JinaCrossEncoderReranker)


def test_create_reranker_lm_studio():
    """create_reranker('lm-studio') returns LMStudioReranker."""
    reranker = create_reranker("lm-studio")
    assert isinstance(reranker, LMStudioReranker)


def test_create_reranker_llm():
    """create_reranker('llm') returns LLMReranker."""
    reranker = create_reranker("llm", provider=MockProvider())
    assert isinstance(reranker, LLMReranker)


def test_create_reranker_llm_requires_provider():
    """create_reranker('llm') raises without provider."""
    with pytest.raises(ValueError, match="provider"):
        create_reranker("llm")


def test_create_reranker_unknown():
    """create_reranker raises for unknown method."""
    with pytest.raises(ValueError, match="Unknown"):
        create_reranker("nonexistent-method")


# ── RemoteReranker Tests ──────────────────────────────────────────────

def test_remote_reranker_unreachable_uses_fallback():
    """RemoteReranker falls back when service unreachable."""
    from backend.pipeline.knowledge.reranker import RemoteReranker

    remote = RemoteReranker(base_url="http://localhost:19999")
    remote.set_fallback(JinaCrossEncoderReranker(model_id="nonexistent-model"))
    result = asyncio.run(remote.rerank("transformer", SAMPLE_DOCS, top_k=2))
    assert len(result) <= 2
    # Falls through to heuristic
    assert all(isinstance(r.score, float) for r in result)


def test_remote_reranker_empty_docs():
    """RemoteReranker handles empty document list."""
    from backend.pipeline.knowledge.reranker import RemoteReranker

    remote = RemoteReranker(base_url="http://localhost:19999")
    result = asyncio.run(remote.rerank("query", []))
    assert result == []


def test_create_reranker_auto_uses_remote():
    """create_reranker('auto') returns RemoteReranker as primary."""
    from backend.pipeline.knowledge.reranker import RemoteReranker

    reranker = create_reranker("auto")
    assert isinstance(reranker, RemoteReranker)


def test_create_reranker_remote():
    """create_reranker('remote') returns RemoteReranker."""
    from backend.pipeline.knowledge.reranker import RemoteReranker

    reranker = create_reranker("remote", reranker_url="http://gpu-machine:8100")
    assert isinstance(reranker, RemoteReranker)
