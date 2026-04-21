"""Changeset versioning for the KnowledgeGraph.

AtomSpace-inspired frame/changeset model where each mutation generates
a lightweight ChangeRecord rather than full snapshots. Frames are
reconstructed by replaying changesets.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ChangeRecord(BaseModel):
    """A single atomic change to the knowledge graph."""

    version: int
    timestamp: datetime = Field(default_factory=datetime.now)
    operation: str  # add_entity, add_relationship, update_truth, reinforce, weaken, merge
    target_id: str
    target_type: str  # "entity" or "relationship"
    old_content_hash: str | None = None
    new_content_hash: str | None = None
    delta: dict[str, Any] | None = None

    @staticmethod
    def compute_content_hash(data: dict) -> str:
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]


class ChangeBuffer:
    """Accumulates changes within a transaction and flushes atomically."""

    def __init__(self):
        self._records: list[ChangeRecord] = []
        self._version_counter: int = 0

    def _next_version(self) -> int:
        self._version_counter += 1
        return self._version_counter

    def record_entity_add(self, entity_id: str, content_hash: str) -> ChangeRecord:
        record = ChangeRecord(
            version=self._next_version(),
            operation="add_entity",
            target_id=entity_id,
            target_type="entity",
            new_content_hash=content_hash,
        )
        self._records.append(record)
        return record

    def record_truth_update(
        self, entity_id: str, old_hash: str | None, new_hash: str
    ) -> ChangeRecord:
        record = ChangeRecord(
            version=self._next_version(),
            operation="update_truth",
            target_id=entity_id,
            target_type="entity",
            old_content_hash=old_hash,
            new_content_hash=new_hash,
        )
        self._records.append(record)
        return record

    def record_relationship_add(
        self, source_id: str, target_id: str, content_hash: str
    ) -> ChangeRecord:
        record = ChangeRecord(
            version=self._next_version(),
            operation="add_relationship",
            target_id=f"{source_id}->{target_id}",
            target_type="relationship",
            new_content_hash=content_hash,
        )
        self._records.append(record)
        return record

    def record_reinforce(
        self, source_id: str, target_id: str, old_weight: float, new_weight: float
    ) -> ChangeRecord:
        record = ChangeRecord(
            version=self._next_version(),
            operation="reinforce",
            target_id=f"{source_id}->{target_id}",
            target_type="relationship",
            delta={"field": "weight", "old": old_weight, "new": new_weight},
        )
        self._records.append(record)
        return record

    def record_weaken(
        self, source_id: str, target_id: str, old_weight: float, new_weight: float
    ) -> ChangeRecord:
        record = ChangeRecord(
            version=self._next_version(),
            operation="weaken",
            target_id=f"{source_id}->{target_id}",
            target_type="relationship",
            delta={"field": "weight", "old": old_weight, "new": new_weight},
        )
        self._records.append(record)
        return record

    def record_merge(self, survivor_id: str, absorbed_id: str) -> ChangeRecord:
        record = ChangeRecord(
            version=self._next_version(),
            operation="merge",
            target_id=survivor_id,
            target_type="entity",
            delta={"survivor": survivor_id, "absorbed": absorbed_id},
        )
        self._records.append(record)
        return record

    def flush(self) -> list[ChangeRecord]:
        records = list(self._records)
        self._records.clear()
        return records

    def clear(self) -> None:
        self._records.clear()

    @property
    def pending_count(self) -> int:
        return len(self._records)


class VersionLog:
    """Persistent append-only log of changeset records."""

    def __init__(self, persist_path: str):
        self._path = Path(persist_path)
        self._entries: list[ChangeRecord] = []
        self._load()

    def append(self, records: list[ChangeRecord]) -> None:
        if not records:
            return
        self._entries.extend(records)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            for record in records:
                f.write(record.model_dump_json() + "\n")

    def get_version(self, version: int) -> ChangeRecord | None:
        for entry in self._entries:
            if entry.version == version:
                return entry
        return None

    def get_changes_since(self, version: int) -> list[ChangeRecord]:
        return [e for e in self._entries if e.version > version]

    def get_changes_for(self, target_id: str) -> list[ChangeRecord]:
        return [e for e in self._entries if e.target_id == target_id]

    @property
    def latest_version(self) -> int:
        if not self._entries:
            return 0
        return self._entries[-1].version

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._entries.append(ChangeRecord.model_validate_json(line))
            logger.info("Loaded version log: %d entries", len(self._entries))
        except Exception as e:
            logger.warning("Failed to load version log: %s", e)
