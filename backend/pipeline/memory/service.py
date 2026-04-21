"""Memory service — persistent agent memory backed by JSONL + optional hybrid retrieval.

Implements the Ajnan Universal Kernel-Write Invariant: every write passes
through redact_and_validate() with no exceptions.

When a TwoStageRetriever is provided, recall() uses BM25+semantic hybrid
search instead of substring matching.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from backend.pipeline.memory.models import MemoryEntry, MemoryQuery, MemoryRevision, MemoryType

if TYPE_CHECKING:
    from backend.pipeline.knowledge.retriever import TwoStageRetriever

logger = logging.getLogger(__name__)

# Patterns to strip during redaction
_REDACTION_PATTERNS = [
    re.compile(r"(api[_-]?key|token|password|secret)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),  # email addresses
]


class MemoryService:
    """Persistent agent memory with typed storage and quality gates."""

    def __init__(
        self,
        persist_path: str = "./data/memory",
        retriever: TwoStageRetriever | None = None,
    ):
        self._path = Path(persist_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._store_path = self._path / "memory.jsonl"
        self._index: dict[str, MemoryEntry] = {}
        self._retriever = retriever
        self._last_decay: datetime = datetime.now()
        self._load()

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Enforces redact_and_validate invariant."""
        validated = self.redact_and_validate(entry.content)
        entry = MemoryEntry(
            id=self._content_hash(validated, entry.memory_type, entry.namespace),
            content=validated,
            memory_type=entry.memory_type,
            namespace=entry.namespace,
            agent_id=entry.agent_id,
            truth=entry.truth,
            source_run_id=entry.source_run_id,
            tags=entry.tags,
            created_at=entry.created_at,
        )

        if entry.id in self._index:
            existing = self._index[entry.id]
            # Record provenance before updating
            revision = MemoryRevision(
                revision_number=len(existing.revision_history) + 1,
                content=existing.content,
                truth=existing.truth,
                agent_id=entry.agent_id,
                reason="update",
            )
            existing.revision_history.append(revision)
            existing.truth = existing.truth.revise(entry.truth)
            existing.access_count += 1
            existing.accessed_at = datetime.now()
        else:
            self._index[entry.id] = entry

        self._append(entry)

        # Keep BM25 index in sync (if retriever is configured)
        if self._retriever is not None:
            self._retriever.bm25_index.add_documents(  # type: ignore[attr-defined]
                ids=[entry.id],
                texts=[entry.content],
                metadatas=[
                    {
                        "memory_type": entry.memory_type.value,
                        "namespace": entry.namespace,
                    }
                ],
            )

        return entry.id

    async def recall(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Retrieve memories matching query criteria.

        Uses hybrid retrieval when a TwoStageRetriever is configured,
        otherwise falls back to substring matching.
        """
        await self.maybe_decay()
        if self._retriever:
            return await self._semantic_recall(query)
        return await self._text_recall(query)

    async def _text_recall(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Original substring-based recall (backward compatible)."""
        results: list[MemoryEntry] = []

        for entry in self._index.values():
            if query.memory_type and entry.memory_type != query.memory_type:
                continue
            if query.namespace and entry.namespace != query.namespace:
                continue
            if query.agent_id and entry.agent_id != query.agent_id:
                continue
            if entry.truth.confidence < query.min_confidence:
                continue
            if query.query.lower() in entry.content.lower():
                results.append(entry)

        results.sort(
            key=lambda e: (e.truth.expectation, e.created_at.timestamp()),
            reverse=True,
        )

        for entry in results[: query.top_k]:
            entry.access_count += 1
            entry.accessed_at = datetime.now()

        return results[: query.top_k]

    async def _semantic_recall(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Hybrid BM25+semantic recall via TwoStageRetriever."""
        filter_meta: dict = {}
        if query.memory_type:
            filter_meta["memory_type"] = query.memory_type.value
        if query.namespace:
            filter_meta["namespace"] = query.namespace

        retrieval_results = await self._retriever.retrieve(  # type: ignore[union-attr]
            query=query.query,
            n_results=query.top_k,
            filter_metadata=filter_meta or None,
        )

        results: list[MemoryEntry] = []
        for r in retrieval_results:
            entry = self._index.get(r.id)
            if entry and entry.truth.confidence >= query.min_confidence:
                entry.access_count += 1
                entry.accessed_at = datetime.now()
                results.append(entry)

        return results

    async def consolidate(self, similarity_threshold: float = 0.9) -> int:
        """Consolidate similar memories. Returns number of merges performed."""
        merges = 0
        entries = list(self._index.values())
        to_remove: set[str] = set()

        for i, entry_a in enumerate(entries):
            if entry_a.id in to_remove:
                continue
            for j in range(i + 1, len(entries)):
                entry_b = entries[j]
                if entry_b.id in to_remove:
                    continue
                if entry_a.memory_type != entry_b.memory_type:
                    continue

                # Simple text overlap similarity
                words_a = set(entry_a.content.lower().split())
                words_b = set(entry_b.content.lower().split())
                if not words_a or not words_b:
                    continue
                similarity = len(words_a & words_b) / len(words_a | words_b)

                if similarity >= similarity_threshold:
                    # Merge: keep the one with higher truth confidence
                    if entry_b.truth.confidence > entry_a.truth.confidence:
                        entry_a.truth = entry_a.truth.revise(entry_b.truth)
                    else:
                        entry_a.truth = entry_a.truth.revise(entry_b.truth)
                    to_remove.add(entry_b.id)
                    merges += 1

        for mid in to_remove:
            del self._index[mid]

        if to_remove:
            self._save_all()

        return merges

    async def apply_decay(self, decay_rate: float = 0.99) -> int:
        """Apply temporal truth decay to all memories. Returns count decayed."""
        count = 0
        for entry in self._index.values():
            old_conf = entry.truth.confidence
            entry.truth = entry.truth.decay(decay_rate)
            if entry.truth.confidence < old_conf:
                count += 1

        if count > 0:
            self._save_all()
        return count

    async def maybe_decay(self, decay_rate: float = 0.99, min_interval_hours: int = 24) -> int:
        """Apply decay only if min_interval_hours have elapsed since last decay."""
        elapsed = (datetime.now() - self._last_decay).total_seconds() / 3600
        if elapsed < min_interval_hours:
            return 0
        count = await self.apply_decay(decay_rate)
        self._last_decay = datetime.now()
        if count:
            logger.info("Applied decay to %d memories (interval=%.1fh)", count, elapsed)
        return count

    async def delete(self, entry_id: str) -> bool:
        """Delete a memory entry by ID. Returns True if found and removed."""
        if entry_id not in self._index:
            return False
        del self._index[entry_id]
        self._save_all()
        return True

    def redact_and_validate(self, content: str) -> str:
        """Ajnan Universal Kernel-Write Invariant.

        Strip PII, secrets, and validate content before any write.
        No memory is stored without passing through this method.
        """
        result = content
        for pattern in _REDACTION_PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        # Strip null bytes and normalize whitespace
        result = result.replace("\x00", "").strip()
        if len(result) < 5:
            raise ValueError(f"Content too short after validation: {len(result)} chars")
        return result

    @staticmethod
    def _content_hash(content: str, memory_type: MemoryType, namespace: str) -> str:
        """SHA-256 content-addressable ID (Ajnan pattern)."""
        raw = f"{memory_type.value}:{namespace}:{content}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _append(self, entry: MemoryEntry) -> None:
        """Append entry to JSONL log."""
        with open(self._store_path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    def _save_all(self) -> None:
        """Rewrite the full JSONL log (after consolidation/decay)."""
        with open(self._store_path, "w", encoding="utf-8") as f:
            for entry in self._index.values():
                f.write(entry.model_dump_json() + "\n")

    def _load(self) -> None:
        """Load existing memories from JSONL log."""
        if not self._store_path.exists():
            return
        with open(self._store_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = MemoryEntry.model_validate_json(line)
                    self._index[entry.id] = entry
                except Exception as e:
                    logger.warning("Skipping corrupted memory entry: %s", e)
        logger.info("Loaded %d memories from %s", len(self._index), self._store_path)
