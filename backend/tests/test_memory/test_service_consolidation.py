"""Tests for MemoryService integration with consolidation."""

import pytest

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryType


@pytest.fixture
def memory(tmp_path):
    from backend.pipeline.memory.service import MemoryService
    return MemoryService(persist_path=str(tmp_path / "mem"))


def _make_entry(content: str, confidence: float = 0.8) -> MemoryEntry:
    return MemoryEntry(
        id="",
        content=content,
        memory_type=MemoryType.SEMANTIC,
        namespace="research_facts",
        truth=TruthValue.from_observation(confidence),
    )


class TestMemoryServiceConsolidate:
    @pytest.mark.anyio
    async def test_consolidate_merges_similar(self, memory):
        await memory.store(_make_entry("RAG with reranking improves retrieval by 15 percent"))
        await memory.store(_make_entry("RAG with reranking improves retrieval by 15 percent on benchmarks"))

        merges = await memory.consolidate(similarity_threshold=0.5)
        assert merges == 1

    @pytest.mark.anyio
    async def test_consolidate_no_similar(self, memory):
        await memory.store(_make_entry("RAG improves retrieval performance"))
        await memory.store(_make_entry("quantum entanglement is a physical phenomenon"))

        merges = await memory.consolidate(similarity_threshold=0.9)
        assert merges == 0

    @pytest.mark.anyio
    async def test_consolidate_empty_memory(self, memory):
        merges = await memory.consolidate()
        assert merges == 0

    @pytest.mark.anyio
    async def test_consolidate_keeps_higher_confidence(self, memory):
        await memory.store(_make_entry("the same text repeated here with some words", confidence=0.7))
        await memory.store(_make_entry("the same text repeated here with other words", confidence=0.95))

        merges = await memory.consolidate(similarity_threshold=0.5)
        assert merges == 1

    @pytest.mark.anyio
    async def test_consolidate_preserves_different_types(self, memory):
        e1 = MemoryEntry(
            id="", content="test content repeated identically",
            memory_type=MemoryType.SEMANTIC, namespace="research_facts",
            truth=TruthValue.from_observation(0.8),
        )
        e2 = MemoryEntry(
            id="", content="test content repeated identically",
            memory_type=MemoryType.EPISODIC, namespace="research_facts",
            truth=TruthValue.from_observation(0.8),
        )
        await memory.store(e1)
        await memory.store(e2)

        merges = await memory.consolidate(similarity_threshold=0.5)
        assert merges == 0

    @pytest.mark.anyio
    async def test_delete_removes_entry(self, memory):
        mid = await memory.store(_make_entry("something to delete"))
        result = await memory.delete(mid)
        assert result is True
        result2 = await memory.delete(mid)
        assert result2 is False
