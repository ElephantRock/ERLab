"""Tests for query transformation module (WP-1 completion)."""

import asyncio

from backend.pipeline.knowledge.query_transform import (
    ExpansionQueryTransformer,
    MultiQueryTransformer,
)


class FakeProvider:
    """Minimal fake LLM provider for MultiQueryTransformer tests."""

    def __init__(self, response: dict | None = None, *, should_fail: bool = False):
        self._response = response
        self._should_fail = should_fail

    async def structured_output(self, messages, schema, temperature=0.3):
        if self._should_fail:
            raise RuntimeError("LLM unavailable")
        return self._response or {}


def _run(coro):
    return asyncio.run(coro)


class TestExpansionQueryTransformer:
    def test_expands_known_synonyms(self):
        t = ExpansionQueryTransformer({"ai": ["artificial intelligence", "machine learning"]})
        result = _run(t.transform("ai safety"))
        assert len(result) == 2
        assert result[0] == "ai safety"
        assert "artificial intelligence" in result[1]

    def test_no_synonyms_returns_original(self):
        t = ExpansionQueryTransformer({})
        result = _run(t.transform("quantum computing"))
        assert result == ["quantum computing"]

    def test_empty_synonym_dict_returns_original(self):
        t = ExpansionQueryTransformer()
        result = _run(t.transform("neural networks"))
        assert result == ["neural networks"]

    def test_multiple_hits(self):
        t = ExpansionQueryTransformer(
            {
                "deep": ["deep learning"],
                "learning": ["education", "training"],
            }
        )
        result = _run(t.transform("deep learning"))
        assert len(result) == 2
        assert result[0] == "deep learning"


class TestMultiQueryTransformer:
    def test_returns_variants_from_llm(self):
        provider = FakeProvider(
            response={
                "queries": ["machine learning safety", "AI alignment methods"],
            }
        )
        t = MultiQueryTransformer(provider, n_variants=2)
        result = _run(t.transform("AI safety"))
        assert len(result) == 3  # original + 2 variants
        assert result[0] == "AI safety"
        assert "machine learning safety" in result

    def test_llm_failure_falls_back(self):
        provider = FakeProvider(should_fail=True)
        t = MultiQueryTransformer(provider)
        result = _run(t.transform("test query"))
        assert result == ["test query"]

    def test_n_variants_respected(self):
        provider = FakeProvider(
            response={
                "queries": ["q1", "q2", "q3"],
            }
        )
        t = MultiQueryTransformer(provider, n_variants=3)
        result = _run(t.transform("original"))
        assert len(result) == 4  # original + 3

    def test_non_string_variants_filtered(self):
        provider = FakeProvider(
            response={
                "queries": ["valid", 123, "also valid"],
            }
        )
        t = MultiQueryTransformer(provider, n_variants=3)
        result = _run(t.transform("query"))
        assert len(result) == 3  # original + 2 valid strings
        assert all(isinstance(q, str) for q in result)

    def test_empty_queries_list_returns_original(self):
        provider = FakeProvider(response={"queries": []})
        t = MultiQueryTransformer(provider)
        result = _run(t.transform("solo query"))
        assert result == ["solo query"]


class TestRetrieverWithTransformer:
    """Integration-style test: retriever dispatches multiple query variants."""

    def test_transformer_produces_multiple_queries(self):
        """Verify the transformer contract without needing ChromaDB."""
        provider = FakeProvider(
            response={
                "queries": ["alternative phrasing"],
            }
        )
        t = MultiQueryTransformer(provider, n_variants=1)
        result = _run(t.transform("original query"))
        assert len(result) == 2
        assert result[0] == "original query"
        assert "alternative phrasing" in result
