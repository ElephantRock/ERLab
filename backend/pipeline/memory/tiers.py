"""Tiered memory architecture — working + archival tiers.

Working tier: LRU-bounded in-memory cache for hot, current-session data.
Archival tier: Persistent JSONL + vector search for long-term knowledge.

Promotion/demotion moves entries between tiers based on access patterns.

Reference: letta's core/recall/archival three-tier model.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from enum import Enum
from typing import TYPE_CHECKING

from backend.pipeline.memory.models import MemoryEntry, MemoryQuery

if TYPE_CHECKING:
    from backend.pipeline.knowledge.retriever import TwoStageRetriever
    from backend.pipeline.memory.service import MemoryService

logger = logging.getLogger(__name__)


class MemoryTier(str, Enum):
    WORKING = "working"
    ARCHIVAL = "archival"


class TieredMemoryService:
    """Two-tier memory: bounded working cache + persistent archival store.

    Working tier is an LRU OrderedDict (fast O(1) access, bounded capacity).
    Archival tier delegates to a MemoryService with optional vector retrieval.
    """

    def __init__(
        self,
        working_capacity: int = 100,
        archival_path: str = "./data/memory/archival",
        retriever: TwoStageRetriever | None = None,
    ):
        self._working_capacity = working_capacity
        self._working: OrderedDict[str, MemoryEntry] = OrderedDict()
        self._archival_path = archival_path
        self._retriever = retriever

        # Lazy-load archival store to avoid circular import
        self._archival_store: MemoryService | None = None

    @property
    def _archival(self):
        """Lazy-load archival MemoryService."""
        if self._archival_store is None:
            from backend.pipeline.memory.service import MemoryService

            self._archival_store = MemoryService(
                persist_path=self._archival_path,
                retriever=self._retriever,
            )
        return self._archival_store

    async def store(
        self,
        entry: MemoryEntry,
        tier: MemoryTier = MemoryTier.WORKING,
    ) -> str:
        """Store entry to the specified tier. Returns entry ID."""
        if tier == MemoryTier.WORKING:
            return await self._store_working(entry)
        return await self._archival.store(entry)

    async def recall(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Search working tier first, then archival. Merge and dedup."""
        results: dict[str, MemoryEntry] = {}

        # Working tier: fast O(n) scan
        for entry in self._working.values():
            if query.memory_type and entry.memory_type != query.memory_type:
                continue
            if query.namespace and entry.namespace != query.namespace:
                continue
            if entry.truth.confidence < query.min_confidence:
                continue
            if query.query.lower() in entry.content.lower():
                results[entry.id] = entry

        # Archival tier: delegate to MemoryService (uses retriever if configured)
        archival_results = await self._archival.recall(query)
        for entry in archival_results:
            if entry.id not in results:
                results[entry.id] = entry
            # Auto-promote frequently accessed archival entries
            if entry.access_count >= 3:
                try:
                    await self.promote(entry.id)
                    logger.debug("Auto-promoted entry %s (access_count=%d)", entry.id, entry.access_count)
                except Exception:
                    pass

        # Sort by truth expectation then recency
        sorted_results = sorted(
            results.values(),
            key=lambda e: (e.truth.expectation, e.created_at.timestamp()),
            reverse=True,
        )

        return sorted_results[: query.top_k]

    async def promote(self, entry_id: str) -> bool:
        """Move entry from archival to working tier."""
        # Check if already in working
        if entry_id in self._working:
            return True

        # Find in archival by querying with ID
        archival_entries = self._archival._index
        if entry_id not in archival_entries:
            return False

        entry = archival_entries[entry_id]
        await self._store_working(entry)
        return True

    async def demote(self, entry_id: str) -> bool:
        """Move entry from working to archival tier."""
        if entry_id not in self._working:
            return False

        entry = self._working.pop(entry_id)
        await self._archival.store(entry)
        return True

    @property
    def working_count(self) -> int:
        return len(self._working)

    @property
    def archival_count(self) -> int:
        return len(self._archival._index)

    # ── Internal ────────────────────────────────────────────────

    async def _store_working(self, entry: MemoryEntry) -> str:
        """Store to working tier with LRU eviction."""
        if entry.id in self._working:
            self._working.move_to_end(entry.id)
            # Revise truth
            existing = self._working[entry.id]
            existing.truth = existing.truth.revise(entry.truth)
            existing.access_count += 1
        else:
            # Evict oldest if at capacity
            while len(self._working) >= self._working_capacity:
                oldest_id, oldest_entry = self._working.popitem(last=False)
                # Demote to archival
                await self._archival.store(oldest_entry)
                logger.debug("Demoted entry %s to archival (LRU eviction)", oldest_id)
            self._working[entry.id] = entry

        return entry.id
