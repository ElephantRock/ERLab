"""Tests for EmbeddingService batch_size and fallback wiring."""

import asyncio

import pytest

from backend.pipeline.knowledge.embedding_service import EmbeddingService


class MockProvider:
    """Mock embedding provider for testing."""

    def __init__(self, dim=10):
        self._dim = dim
        self.call_count = 0
        self.batch_sizes: list[int] = []

    async def embed(self, texts):
        self.call_count += 1
        self.batch_sizes.append(len(texts))
        return [[float(i)] * self._dim for i in range(len(texts))]

    @property
    def dimension(self):
        return self._dim

    @property
    def provider_name(self):
        return "mock"


class TestEmbeddingServiceBatchSize:
    def test_default_batch_size(self):
        provider = MockProvider()
        service = EmbeddingService(provider)
        assert service._batch_size == 100

    def test_custom_batch_size(self):
        provider = MockProvider()
        service = EmbeddingService(provider, batch_size=2)
        assert service._batch_size == 2

    def test_batch_size_splits_calls(self):
        provider = MockProvider()
        service = EmbeddingService(provider, batch_size=3)
        texts = ["a", "b", "c", "d", "e"]
        results = asyncio.run(service.embed_texts(texts))
        assert len(results) == 5
        assert provider.call_count == 2  # 3 + 2
        assert provider.batch_sizes == [3, 2]

    def test_empty_texts(self):
        provider = MockProvider()
        service = EmbeddingService(provider, batch_size=2)
        results = asyncio.run(service.embed_texts([]))
        assert results == []
        assert provider.call_count == 0

    def test_single_text(self):
        provider = MockProvider()
        service = EmbeddingService(provider, batch_size=2)
        results = asyncio.run(service.embed_texts(["hello"]))
        assert len(results) == 1
        assert provider.call_count == 1

    def test_exact_batch_boundary(self):
        provider = MockProvider()
        service = EmbeddingService(provider, batch_size=3)
        results = asyncio.run(service.embed_texts(["a", "b", "c"]))
        assert len(results) == 3
        assert provider.call_count == 1
        assert provider.batch_sizes == [3]

    def test_embed_single(self):
        provider = MockProvider()
        service = EmbeddingService(provider, batch_size=2)
        result = asyncio.run(service.embed_single("hello"))
        assert len(result) == provider.dimension

    def test_fallback_on_failure(self):
        class FailProvider:
            async def embed(self, texts):
                raise RuntimeError("API down")

            @property
            def dimension(self):
                return 5

        service = EmbeddingService(FailProvider(), batch_size=2)
        results = asyncio.run(service.embed_texts(["a", "b"]))
        assert len(results) == 2
        assert all(r == [0.0] * 5 for r in results)
