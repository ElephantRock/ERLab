"""Knowledge graph entities with Union-Find deduplication.

Entity types: PAPER, AUTHOR, METHOD, DATASET, CONCEPT.
Union-Find provides O(α(n)) deduplication across runs.
Content-hash provides O(1) structural identity and dedup-by-construction.
"""

import hashlib
from enum import Enum

from pydantic import BaseModel, Field

from backend.pipeline.knowledge.truth import TruthValue


class EntityType(str, Enum):
    PAPER = "paper"
    AUTHOR = "author"
    METHOD = "method"
    DATASET = "dataset"
    CONCEPT = "concept"


class KnowledgeEntity(BaseModel):
    id: str  # Deterministic: f"{entity_type}:{normalized_name}"
    entity_type: EntityType
    name: str
    aliases: list[str] = Field(default_factory=list)
    properties: dict = {}
    truth: TruthValue = Field(default_factory=TruthValue.initial)

    @property
    def content_hash(self) -> str:
        """Content-addressable identity hash (SHA-256[:16])."""
        raw = f"{self.entity_type.value}:{self.name}:{self.truth.frequency}:{self.truth.confidence}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class EntityResolution:
    """Union-Find entity resolution for deduplication across runs."""

    def __init__(self):
        self._parent: dict[str, str] = {}
        self._rank: dict[str, int] = {}

    def find(self, entity_id: str) -> str:
        """Find the canonical ID for an entity."""
        if entity_id not in self._parent:
            self._parent[entity_id] = entity_id
            self._rank[entity_id] = 0
            return entity_id

        # Path compression
        if self._parent[entity_id] != entity_id:
            self._parent[entity_id] = self.find(self._parent[entity_id])
        return self._parent[entity_id]

    def union(self, id_a: str, id_b: str) -> None:
        """Merge two entities. The higher-rank entity becomes canonical."""
        root_a = self.find(id_a)
        root_b = self.find(id_b)
        if root_a == root_b:
            return

        # Union by rank
        if self._rank[root_a] < self._rank[root_b]:
            root_a, root_b = root_b, root_a
        self._parent[root_b] = root_a
        if self._rank[root_a] == self._rank[root_b]:
            self._rank[root_a] += 1

    def canonical_id(self, entity_id: str) -> str:
        """Get the canonical (root) ID for an entity."""
        return self.find(entity_id)

    def are_same(self, id_a: str, id_b: str) -> bool:
        """Check if two entity IDs resolve to the same canonical entity."""
        return self.find(id_a) == self.find(id_b)
