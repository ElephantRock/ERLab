"""Memory service — persistent agent memory backed by JSONL + ChromaDB.

Implements the Ajnan Universal Kernel-Write Invariant: every write passes
through redact_and_validate() with no exceptions.
"""

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryQuery, MemoryType

logger = logging.getLogger(__name__)

# Patterns to strip during redaction
_REDACTION_PATTERNS = [
    re.compile(r"(api[_-]?key|token|password|secret)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),  # email addresses
]


class MemoryService:
    """Persistent agent memory with typed storage and quality gates."""

    def __init__(self, persist_path: str = "./data/memory"):
        self._path = Path(persist_path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._store_path = self._path / "memory.jsonl"
        self._index: dict[str, MemoryEntry] = {}
        self._load()

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Enforces redact_and_validate invariant."""
        validated = self.redact_and_validate(entry.content)
        entry = MemoryEntry(
            id=self._content_hash(validated, entry.memory_type, entry.namespace),
            content=validated,
            memory_type=entry.memory_type,
            namespace=entry.namespace,
            truth=entry.truth,
            source_run_id=entry.source_run_id,
            tags=entry.tags,
            created_at=entry.created_at,
        )

        if entry.id in self._index:
            # Revise truth value for duplicate content
            existing = self._index[entry.id]
            existing.truth = existing.truth.revise(entry.truth)
            existing.access_count += 1
            existing.accessed_at = datetime.now()
        else:
            self._index[entry.id] = entry

        self._append(entry)
        return entry.id

    async def recall(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Retrieve memories matching query criteria."""
        results: list[MemoryEntry] = []

        for entry in self._index.values():
            if query.memory_type and entry.memory_type != query.memory_type:
                continue
            if query.namespace and entry.namespace != query.namespace:
                continue
            if entry.truth.confidence < query.min_confidence:
                continue
            # Simple text matching for recall
            if query.query.lower() in entry.content.lower():
                results.append(entry)

        # Sort by truth expectation (frequency * confidence), then recency
        results.sort(
            key=lambda e: (e.truth.expectation, e.created_at.timestamp()),
            reverse=True,
        )

        # Update access stats
        for entry in results[: query.top_k]:
            entry.access_count += 1
            entry.accessed_at = datetime.now()

        return results[: query.top_k]

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
        with open(self._store_path, "r", encoding="utf-8") as f:
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
