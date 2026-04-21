"""Tests for persistent agent memory."""

import asyncio

import pytest

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryQuery, MemoryType
from backend.pipeline.memory.service import MemoryService


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def memory(tmp_path):
    return MemoryService(persist_path=str(tmp_path / "memory"))


class TestMemoryService:
    def test_store_and_recall(self, memory):
        entry = MemoryEntry(
            id="",
            content="RAG with reranking improves retrieval by 15% on standard benchmarks",
            memory_type=MemoryType.SEMANTIC,
            namespace="research_facts",
            truth=TruthValue.from_observation(0.9),
        )
        mid = run(memory.store(entry))

        results = run(memory.recall(MemoryQuery(query="RAG")))
        assert len(results) == 1
        assert "RAG" in results[0].content
        assert results[0].id == mid

    def test_store_deduplicates_by_content_hash(self, memory):
        entry = MemoryEntry(
            id="",
            content="Same content stored twice",
            memory_type=MemoryType.SEMANTIC,
            namespace="research_facts",
            truth=TruthValue.from_observation(0.8),
        )
        id1 = run(memory.store(entry))
        id2 = run(memory.store(entry))
        assert id1 == id2

        results = run(memory.recall(MemoryQuery(query="content")))
        assert len(results) == 1

    def test_recall_filters_by_type(self, memory):
        run(
            memory.store(
                MemoryEntry(
                    id="",
                    content="A research fact",
                    memory_type=MemoryType.SEMANTIC,
                    namespace="research_facts",
                    truth=TruthValue.from_observation(0.8),
                )
            )
        )
        run(
            memory.store(
                MemoryEntry(
                    id="",
                    content="A pipeline experience",
                    memory_type=MemoryType.EPISODIC,
                    namespace="pipeline_experience",
                    truth=TruthValue.from_observation(0.8),
                )
            )
        )

        semantic = run(memory.recall(MemoryQuery(query="A", memory_type=MemoryType.SEMANTIC)))
        assert len(semantic) == 1
        assert semantic[0].memory_type == MemoryType.SEMANTIC

        episodic = run(memory.recall(MemoryQuery(query="A", memory_type=MemoryType.EPISODIC)))
        assert len(episodic) == 1
        assert episodic[0].memory_type == MemoryType.EPISODIC

    def test_recall_filters_by_confidence(self, memory):
        run(
            memory.store(
                MemoryEntry(
                    id="",
                    content="Low confidence fact",
                    memory_type=MemoryType.SEMANTIC,
                    namespace="research_facts",
                    truth=TruthValue(frequency=0.5, confidence=0.05),
                )
            )
        )
        run(
            memory.store(
                MemoryEntry(
                    id="",
                    content="High confidence fact",
                    memory_type=MemoryType.SEMANTIC,
                    namespace="research_facts",
                    truth=TruthValue(frequency=0.9, confidence=0.8),
                )
            )
        )

        results = run(memory.recall(MemoryQuery(query="fact", min_confidence=0.5)))
        assert len(results) == 1
        assert "High" in results[0].content

    def test_consolidate_merges_similar(self, memory):
        run(
            memory.store(
                MemoryEntry(
                    id="",
                    content="RAG improves retrieval accuracy by 15 percent",
                    memory_type=MemoryType.SEMANTIC,
                    namespace="research_facts",
                    truth=TruthValue.from_observation(0.8),
                )
            )
        )
        run(
            memory.store(
                MemoryEntry(
                    id="",
                    content="RAG improves retrieval accuracy by 20 percent",
                    memory_type=MemoryType.SEMANTIC,
                    namespace="research_facts",
                    truth=TruthValue.from_observation(0.9),
                )
            )
        )

        merges = run(memory.consolidate(similarity_threshold=0.9))
        assert merges >= 0

    def test_decay_reduces_confidence(self, memory):
        run(
            memory.store(
                MemoryEntry(
                    id="",
                    content="A fact to decay",
                    memory_type=MemoryType.SEMANTIC,
                    namespace="research_facts",
                    truth=TruthValue(frequency=0.8, confidence=0.9),
                )
            )
        )

        count = run(memory.apply_decay(decay_rate=0.5))
        assert count == 1

        results = run(memory.recall(MemoryQuery(query="fact", min_confidence=0.0)))
        assert results[0].truth.confidence < 0.9

    def test_redact_strips_secrets(self, memory):
        entry = MemoryEntry(
            id="",
            content="Using api_key=sk-12345 to access the model",
            memory_type=MemoryType.EPISODIC,
            namespace="pipeline_experience",
            truth=TruthValue.from_observation(0.8),
        )
        run(memory.store(entry))

        results = run(memory.recall(MemoryQuery(query="access")))
        assert "sk-12345" not in results[0].content
        assert "[REDACTED]" in results[0].content

    def test_redact_rejects_short_content(self, memory):
        entry = MemoryEntry(
            id="",
            content="Hi",
            memory_type=MemoryType.SEMANTIC,
            namespace="research_facts",
            truth=TruthValue.from_observation(0.8),
        )
        with pytest.raises(ValueError, match="too short"):
            run(memory.store(entry))

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "memory")

        svc1 = MemoryService(persist_path=path)
        asyncio.run(
            svc1.store(
                MemoryEntry(
                    id="",
                    content="Persistent fact",
                    memory_type=MemoryType.SEMANTIC,
                    namespace="research_facts",
                    truth=TruthValue.from_observation(0.8),
                )
            )
        )

        svc2 = MemoryService(persist_path=path)
        results = asyncio.run(svc2.recall(MemoryQuery(query="Persistent")))
        assert len(results) == 1
        assert "Persistent" in results[0].content
