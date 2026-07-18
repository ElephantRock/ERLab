"""Tests for embedding-based deduplication."""

import pytest

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.embedding_dedup import EmbeddingSimilarity, _cosine_similarity
from backend.pipeline.memory.models import MemoryEntry, MemoryType


class FakeEmbeddingProvider:
    """Fake dedicated EmbeddingProvider — returns identical vectors for all inputs."""

    async def embed(self, texts):
        return [[0.1] * 10 for _ in texts]


def _make_entry(content: str, entry_id: str = "") -> MemoryEntry:
    return MemoryEntry(
        id=entry_id or f"id_{hash(content) % 9999:04d}",
        content=content,
        memory_type=MemoryType.SEMANTIC,
        namespace="research_facts",
        truth=TruthValue.from_observation(0.8),
    )


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert _cosine_similarity([1, 0, 0], [-1, 0, 0]) == pytest.approx(-1.0)

    def test_empty_vectors(self):
        assert _cosine_similarity([], []) == 0.0
        assert _cosine_similarity([1, 2], []) == 0.0

    def test_different_lengths(self):
        assert _cosine_similarity([1, 2], [1, 2, 3]) == 0.0

    def test_zero_norm(self):
        assert _cosine_similarity([0, 0], [1, 1]) == 0.0


class TestEmbeddingSimilarity:
    @pytest.fixture
    def sim(self):
        return EmbeddingSimilarity(provider=FakeEmbeddingProvider())

    @pytest.mark.anyio
    async def test_compute_similarity(self, sim):
        score = await sim.compute_similarity("hello world", "hello world")
        # Same text gets identical embeddings from FakeEmbeddingProvider
        assert score == pytest.approx(1.0)

    @pytest.mark.anyio
    async def test_find_duplicates_empty_list(self, sim):
        result = await sim.find_duplicates([])
        assert result == []

    @pytest.mark.anyio
    async def test_find_duplicates_single_entry(self, sim):
        entries = [_make_entry("only one entry")]
        result = await sim.find_duplicates(entries)
        assert result == []

    @pytest.mark.anyio
    async def test_find_duplicates_with_matches(self, sim):
        # FakeEmbeddingProvider returns identical embeddings for all inputs
        entries = [
            _make_entry("RAG improves retrieval", entry_id="e1"),
            _make_entry("RAG improves reranking", entry_id="e2"),
        ]
        pairs = await sim.find_duplicates(entries, threshold=0.9)
        assert len(pairs) == 1
        id_a, id_b, score = pairs[0]
        assert {id_a, id_b} == {"e1", "e2"}
        assert score >= 0.9

    @pytest.mark.anyio
    async def test_find_duplicates_below_threshold(self, sim):
        class VariedProvider(FakeEmbeddingProvider):
            async def embed(self, texts):
                results = []
                for i, _ in enumerate(texts):
                    vec = [0.0] * 10
                    vec[i % 10] = 1.0
                    results.append(vec)
                return results

        varied_sim = EmbeddingSimilarity(provider=VariedProvider())
        entries = [
            _make_entry("text A", entry_id="a"),
            _make_entry("text B", entry_id="b"),
        ]
        pairs = await varied_sim.find_duplicates(entries, threshold=0.99)
        assert len(pairs) == 0

    @pytest.mark.anyio
    async def test_batch_embed_caches(self, sim):
        e1 = _make_entry("first", entry_id="cached_1")
        await sim._batch_embed([e1])
        assert "cached_1" in sim._cache
        # Second call skips already cached
        await sim._batch_embed([e1])
        assert sim._cache["cached_1"] is not None
