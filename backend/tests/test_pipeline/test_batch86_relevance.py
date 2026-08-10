"""Tests for BATCH-86 — Relevance Filter.

AIV v5.3 — T1, T2, T5. Use asyncio.run() not @pytest.mark.asyncio.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.pipeline.literature.models import Paper, SearchResult
from backend.pipeline.literature.relevance_filter import (
    RelevanceFilter,
    _cosine_similarity,
)


def _make_result(title, abstract="", score=1.0):
    return SearchResult(
        paper=Paper(id=f"test:{title[:10]}", title=title, abstract=abstract, source="test"),
        relevance_score=score,
        source="test",
    )


class MockEmbeddingProvider:
    """Returns deterministic embeddings based on text content."""
    async def embed(self, text: str) -> list[float]:
        if "machine learning" in text.lower():
            return [0.9, 0.1, 0.0]
        elif "deep learning" in text.lower():
            return [0.85, 0.15, 0.0]
        elif "cooking" in text.lower():
            return [0.1, 0.1, 0.8]
        else:
            return [0.5, 0.5, 0.0]


def test_86_01_cosine_similarity_identical():
    """Identical vectors have similarity 1.0."""
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_86_01_cosine_similarity_orthogonal():
    """Orthogonal vectors have similarity 0.0."""
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_86_01_cosine_similarity_empty():
    """Empty vectors return 0.0."""
    assert _cosine_similarity([], []) == 0.0


def test_86_02_filter_keeps_relevant():
    """Papers relevant to domain are kept."""
    f = RelevanceFilter(embedding_provider=MockEmbeddingProvider(), threshold=0.5)
    papers = [
        _make_result("Machine Learning Advances"),
        _make_result("Deep Learning for NLP"),
    ]
    result = asyncio.run(f.filter(papers, "machine learning"))
    assert len(result) == 2


def test_86_02_filter_removes_irrelevant():
    """Papers irrelevant to domain are removed."""
    f = RelevanceFilter(embedding_provider=MockEmbeddingProvider(), threshold=0.7)
    papers = [
        _make_result("Machine Learning Advances"),
        _make_result("Cooking Italian Pasta"),
    ]
    result = asyncio.run(f.filter(papers, "machine learning"))
    assert len(result) == 1
    assert "Machine Learning" in result[0].paper.title


def test_86_02_minimum_papers_guarantee():
    """At least MIN_PAPERS kept if available (HB-01)."""
    f = RelevanceFilter(
        embedding_provider=MockEmbeddingProvider(),
        threshold=0.99,  # Very high — nothing will pass
        min_papers=2,
    )
    papers = [
        _make_result("Paper A"), _make_result("Paper B"), _make_result("Paper C"),
    ]
    result = asyncio.run(f.filter(papers, "machine learning"))
    assert len(result) >= 2


def test_86_02_no_provider_returns_all():
    """No embedding provider means no filtering."""
    f = RelevanceFilter(embedding_provider=None)
    papers = [_make_result("Paper A"), _make_result("Paper B")]
    result = asyncio.run(f.filter(papers, "test"))
    assert len(result) == 2


def test_86_02_filter_failure_returns_original():
    """Provider failure returns original list (HB-02)."""
    failing_provider = AsyncMock()
    failing_provider.embed = AsyncMock(side_effect=Exception("Embedding failed"))
    f = RelevanceFilter(embedding_provider=failing_provider)
    papers = [_make_result("Paper A")]
    result = asyncio.run(f.filter(papers, "test"))
    assert len(result) == 1
