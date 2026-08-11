"""Tests for the canonical GovernedEmbeddingAdapter (P0.4B0.3).

The adapter replaces three byte-identical private ``_EmbeddingAdapter``
classes that did no structural validation. These tests prove the new
adapter:
  * propagates provider failures (no silent zero-vector fallback)
  * rejects result-count mismatches
  * rejects non-numeric / bool / non-finite elements
  * rejects all-zero vectors
  * exposes effective configuration identity
"""

from __future__ import annotations

import asyncio

import pytest

from backend.pipeline.governed_embedding_adapter import (
    GOVERNED_EMBEDDING_ADAPTER_CONTRACT_VERSION,
    GovernedEmbeddingAdapter,
    GovernedEmbeddingAdapterError,
)


class _FakeService:
    """Minimal EmbeddingService stand-in (embed_texts only)."""

    def __init__(self, vectors: list[list[float]] | None = None,
                 exc: Exception | None = None) -> None:
        self._vectors = vectors
        self._exc = exc
        self.calls: list[list[str]] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self._exc is not None:
            raise self._exc
        assert self._vectors is not None
        return self._vectors


def _adapter(service: _FakeService, *, dimension: int = 3) -> GovernedEmbeddingAdapter:
    return GovernedEmbeddingAdapter(
        embedding_service=service,
        provider_kind="test",
        requested_model="test-model",
        configured_dimension=dimension,
    )


class TestAdapterIdentity:
    def test_exposes_effective_configuration(self):
        adapter = _adapter(_FakeService(), dimension=768)
        assert adapter.provider_kind == "test"
        assert adapter.requested_model == "test-model"
        assert adapter.configured_dimension == 768
        assert adapter.normalization_policy == "l2"
        assert adapter.adapter_contract_version == GOVERNED_EMBEDDING_ADAPTER_CONTRACT_VERSION


class TestEmbedDocuments:
    def test_happy_path_returns_tuples(self):
        svc = _FakeService(vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        adapter = _adapter(svc)
        result = asyncio.run(adapter.embed_documents(["a", "b"]))
        assert result == ((0.1, 0.2, 0.3), (0.4, 0.5, 0.6))
        assert svc.calls == [["a", "b"]]

    def test_empty_input_returns_empty_tuple(self):
        adapter = _adapter(_FakeService())
        assert asyncio.run(adapter.embed_documents([])) == ()

    def test_provider_failure_propagates(self):
        # The pre-B0 LMStudio adapter silently returned zero vectors here.
        # The canonical adapter must propagate the failure honestly.
        svc = _FakeService(exc=RuntimeError("provider down"))
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a"]))
        assert "provider down" in str(excinfo.value)
        assert "RuntimeError" in str(excinfo.value)

    def test_result_count_mismatch_rejected(self):
        svc = _FakeService(vectors=[[0.1, 0.2, 0.3]])  # only 1, expected 2
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a", "b"]))
        assert "1 vectors" in str(excinfo.value)
        assert "2" in str(excinfo.value)

    def test_dimension_mismatch_rejected(self):
        svc = _FakeService(vectors=[[0.1, 0.2]])  # dim 2, expected 3
        adapter = _adapter(svc, dimension=3)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a"]))
        assert "dimension 2" in str(excinfo.value)
        assert "expected 3" in str(excinfo.value)

    def test_bool_element_rejected(self):
        # bool is a subclass of int; the adapter must exclude it explicitly.
        svc = _FakeService(vectors=[[0.1, True, 0.3]])
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a"]))
        assert "element 1 is bool" in str(excinfo.value)

    def test_non_numeric_rejected(self):
        svc = _FakeService(vectors=[[0.1, "oops", 0.3]])
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a"]))
        assert "element 1 is str" in str(excinfo.value)
        assert "not numeric" in str(excinfo.value)

    def test_nan_rejected(self):
        svc = _FakeService(vectors=[[0.1, float("nan"), 0.3]])
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a"]))
        assert "non-finite" in str(excinfo.value)

    def test_inf_rejected(self):
        svc = _FakeService(vectors=[[0.1, float("inf"), 0.3]])
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a"]))
        assert "non-finite" in str(excinfo.value)

    def test_all_zero_vector_rejected(self):
        # The pre-B0 LMStudio adapter returned zero vectors on failure and
        # let downstream code reject them. The canonical adapter rejects
        # at its own boundary.
        svc = _FakeService(vectors=[[0.0, 0.0, 0.0]])
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a"]))
        assert "all-zero" in str(excinfo.value)

    def test_empty_vector_rejected(self):
        svc = _FakeService(vectors=[[]])
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_documents(["a"]))
        assert "empty" in str(excinfo.value)


class TestEmbedQuery:
    def test_happy_path_returns_tuple(self):
        svc = _FakeService(vectors=[[0.4, 0.5, 0.6]])
        adapter = _adapter(svc)
        result = asyncio.run(adapter.embed_query("query text"))
        assert result == (0.4, 0.5, 0.6)

    def test_provider_failure_propagates(self):
        svc = _FakeService(exc=ValueError("auth failed"))
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_query("q"))
        assert "auth failed" in str(excinfo.value)

    def test_empty_provider_result_rejected(self):
        svc = _FakeService(vectors=[])
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError) as excinfo:
            asyncio.run(adapter.embed_query("q"))
        assert "None" in str(excinfo.value) or "empty" in str(excinfo.value)


class TestEmbedSingleBackwardCompat:
    """The indexer's existing call site uses embed_single -> list[float].
    Keep it working so B0.3 lands without forcing a vector_indexer rewrite;
    B0.9 will require the role-named methods.
    """

    def test_embed_single_returns_list(self):
        svc = _FakeService(vectors=[[0.1, 0.2, 0.3]])
        adapter = _adapter(svc)
        result = asyncio.run(adapter.embed_single("text"))
        assert isinstance(result, list)
        assert result == [0.1, 0.2, 0.3]

    def test_embed_single_propagates_failure(self):
        svc = _FakeService(exc=RuntimeError("provider down"))
        adapter = _adapter(svc)
        with pytest.raises(GovernedEmbeddingAdapterError):
            asyncio.run(adapter.embed_single("text"))
