"""Tests for tiered memory, namespace isolation, and cross-agent sharing."""

import asyncio
import tempfile

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryQuery, MemoryType
from backend.pipeline.memory.tiers import MemoryTier, TieredMemoryService


def _entry(content: str, namespace: str = "default", agent_id: str | None = None) -> MemoryEntry:
    return MemoryEntry(
        id=f"entry_{hash(content) % 10000}",
        content=content,
        memory_type=MemoryType.SEMANTIC,
        namespace=namespace,
        agent_id=agent_id,
        truth=TruthValue.from_observation(),
    )


class TestTieredMemory:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.svc = TieredMemoryService(
            working_capacity=5,
            archival_path=f"{self._tmpdir}/archival",
        )

    def test_store_and_recall_working(self):
        asyncio.run(self._store_and_recall_working())

    async def _store_and_recall_working(self):
        await self.svc.store(_entry("alpha observation", "test"), tier=MemoryTier.WORKING)
        await self.svc.store(_entry("beta observation", "test"), tier=MemoryTier.WORKING)

        results = await self.svc.recall(MemoryQuery(query="alpha", namespace="test", top_k=10))
        assert len(results) == 1
        assert "alpha" in results[0].content

    def test_lru_eviction_to_archival(self):
        asyncio.run(self._lru_eviction())

    async def _lru_eviction(self):
        for i in range(6):
            await self.svc.store(_entry(f"observation number {i}", "test"), tier=MemoryTier.WORKING)

        assert self.svc.working_count == 5
        results = await self.svc.recall(MemoryQuery(query="observation number 0", top_k=10))
        assert len(results) >= 1

    def test_promote_archival_to_working(self):
        asyncio.run(self._test_promote())

    async def _test_promote(self):
        await self.svc.store(_entry("archival data", "test"), tier=MemoryTier.ARCHIVAL)
        assert self.svc.working_count == 0

        archival_entries = self.svc._archival._index
        entry_id = list(archival_entries.keys())[0]

        ok = await self.svc.promote(entry_id)
        assert ok
        assert self.svc.working_count == 1

    def test_demote_working_to_archival(self):
        asyncio.run(self._test_demote())

    async def _test_demote(self):
        await self.svc.store(_entry("hot data", "test"), tier=MemoryTier.WORKING)
        assert self.svc.working_count == 1

        entry_id = list(self.svc._working.keys())[0]
        ok = await self.svc.demote(entry_id)
        assert ok
        assert self.svc.working_count == 0

    def test_agent_isolation(self):
        asyncio.run(self._test_isolation())

    async def _test_isolation(self):
        await self.svc.store(
            MemoryEntry(
                id="a",
                content="agent A secret",
                memory_type=MemoryType.SEMANTIC,
                namespace="private_a",
                agent_id="agent_a",
                truth=TruthValue.from_observation(),
            ),
            tier=MemoryTier.WORKING,
        )
        await self.svc.store(
            MemoryEntry(
                id="b",
                content="agent B secret",
                memory_type=MemoryType.SEMANTIC,
                namespace="private_b",
                agent_id="agent_b",
                truth=TruthValue.from_observation(),
            ),
            tier=MemoryTier.WORKING,
        )

        results_a = await self.svc.recall(
            MemoryQuery(query="secret", namespace="private_a", top_k=10)
        )
        assert len(results_a) == 1
        assert "agent A" in results_a[0].content

        results_b = await self.svc.recall(
            MemoryQuery(query="secret", namespace="private_b", top_k=10)
        )
        assert len(results_b) == 1
        assert "agent B" in results_b[0].content


class TestSharedKnowledgeBase:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.memory = TieredMemoryService(
            working_capacity=50,
            archival_path=f"{self._tmpdir}/archival",
        )
        from backend.pipeline.memory.sharing import SharedKnowledgeBase

        self.shared = SharedKnowledgeBase(self.memory)

    def test_publish_and_subscribe(self):
        asyncio.run(self._test_pubsub())

    async def _test_pubsub(self):
        await self.shared.publish("RAG improves retrieval 15%", agent_id="ideator")
        await self.shared.publish("BM25 is keyword-based", agent_id="critic")
        results = await self.shared.subscribe(query="retrieval", top_k=10)
        assert len(results) >= 1

    def test_filter_by_agent(self):
        asyncio.run(self._test_filter())

    async def _test_filter(self):
        await self.shared.publish("Insight from ideator", agent_id="ideator")
        await self.shared.publish("Insight from critic", agent_id="critic")
        results = await self.shared.subscribe(agent_id="ideator", top_k=10)
        assert all("agent:ideator" in r.tags for r in results)
