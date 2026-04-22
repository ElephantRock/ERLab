"""Entity-centric knowledge graph with Hebbian-like edge consolidation.

Stores entities (papers, authors, methods, datasets, concepts) and their
relationships (cites, uses_method, extends, contradicts, etc.) in an
in-memory graph with JSON persistence. Optional changeset versioning
and adjacency indexing for O(1) neighbor lookup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from backend.pipeline.knowledge.entities import EntityResolution, EntityType, KnowledgeEntity
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType

if TYPE_CHECKING:
    from backend.pipeline.knowledge.activation import ActivationPipeline
    from backend.pipeline.knowledge.adjacency import AdjacencyIndex
    from backend.pipeline.knowledge.streams import StreamRegistry
    from backend.pipeline.knowledge.versioning import ChangeBuffer, VersionLog

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Entity-centric knowledge graph with Hebbian-like edge consolidation."""

    def __init__(
        self, persist_path: str = "./data/knowledge_graph.json", versioning_enabled: bool = False
    ):
        self._path = Path(persist_path)
        self._entities: dict[str, KnowledgeEntity] = {}
        self._relationships: list[KnowledgeRelationship] = []
        self._resolution = EntityResolution()
        self._hash_index: dict[str, str] = {}
        self._incoming_set: dict[str, set[str]] = {}
        self._versioning_enabled = versioning_enabled
        self._change_buffer: ChangeBuffer | None = None
        self._version_log: VersionLog | None = None
        self._adjacency: AdjacencyIndex | None = None
        self._stream_registry: StreamRegistry | None = None
        if versioning_enabled:
            from backend.pipeline.knowledge.adjacency import AdjacencyIndex
            from backend.pipeline.knowledge.versioning import ChangeBuffer, VersionLog

            changes_path = str(persist_path).replace(".json", ".changes.jsonl")
            self._change_buffer = ChangeBuffer()
            self._version_log = VersionLog(changes_path)
            self._adjacency = AdjacencyIndex()
        self._load()

    def add_entity(self, entity: KnowledgeEntity) -> str:
        """Add an entity. Returns canonical ID. Deduplicates by content hash when IDs match."""
        canonical = self._resolution.canonical_id(entity.id)
        content_hash = entity.content_hash

        if canonical in self._entities:
            existing = self._entities[canonical]
            if self._change_buffer:
                from backend.pipeline.knowledge.versioning import ChangeRecord

                old_hash = ChangeRecord.compute_content_hash(existing.model_dump(mode="json"))
            existing.truth = existing.truth.revise(entity.truth)
            if self._change_buffer:
                new_hash = ChangeRecord.compute_content_hash(existing.model_dump(mode="json"))
                self._change_buffer.record_truth_update(canonical, old_hash, new_hash)
            self._hash_index[content_hash] = canonical
            return canonical

        # Content-hash dedup: same content, same ID path — revise truth
        if content_hash in self._hash_index:
            existing_id = self._hash_index[content_hash]
            if existing_id == canonical:
                existing = self._entities.get(existing_id)  # type: ignore[assignment]
                if existing:
                    if self._change_buffer:
                        from backend.pipeline.knowledge.versioning import ChangeRecord

                        old_hash = ChangeRecord.compute_content_hash(
                            existing.model_dump(mode="json")
                        )
                    existing.truth = existing.truth.revise(entity.truth)
                    if self._change_buffer:
                        new_hash = ChangeRecord.compute_content_hash(
                            existing.model_dump(mode="json")
                        )
                        self._change_buffer.record_truth_update(existing_id, old_hash, new_hash)
                    return existing_id

        self._entities[canonical] = entity
        self._hash_index[content_hash] = canonical
        if self._change_buffer:
            from backend.pipeline.knowledge.versioning import ChangeRecord

            ch = ChangeRecord.compute_content_hash(entity.model_dump(mode="json"))
            self._change_buffer.record_entity_add(canonical, ch)
        return canonical

    def add_relationship(self, rel: KnowledgeRelationship) -> None:
        """Add a relationship. If similar one exists, reinforce weight."""
        source = self._resolution.canonical_id(rel.source_id)
        target = self._resolution.canonical_id(rel.target_id)

        for existing in self._relationships:
            if (
                self._resolution.canonical_id(existing.source_id) == source
                and self._resolution.canonical_id(existing.target_id) == target
                and existing.relation_type == rel.relation_type
            ):
                self.reinforce(source, target, rel.relation_type, delta=0.1)
                existing.truth = existing.truth.revise(rel.truth)
                return

        self._relationships.append(
            KnowledgeRelationship(
                source_id=source,
                target_id=target,
                relation_type=rel.relation_type,
                weight=rel.weight,
                evidence=rel.evidence,
                truth=rel.truth,
            )
        )
        self._incoming_set.setdefault(target, set()).add(source)
        if self._adjacency:
            self._adjacency.add_relationship(source, target)
        if self._change_buffer:
            from backend.pipeline.knowledge.versioning import ChangeRecord

            content_hash = ChangeRecord.compute_content_hash(rel.model_dump(mode="json"))
            self._change_buffer.record_relationship_add(source, target, content_hash)

    def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        """Get an entity by ID (resolves to canonical)."""
        canonical = self._resolution.canonical_id(entity_id)
        return self._entities.get(canonical)

    def get_by_content_hash(self, content_hash: str) -> KnowledgeEntity | None:
        """Get an entity by its content hash (O(1) reverse lookup)."""
        entity_id = self._hash_index.get(content_hash)
        if entity_id:
            return self._entities.get(entity_id)
        return None

    def get_referencing_relationships(self, entity_id: str) -> list[KnowledgeRelationship]:
        """Get all relationships that reference this entity (incoming + outgoing)."""
        canonical = self._resolution.canonical_id(entity_id)
        return [
            r
            for r in self._relationships
            if self._resolution.canonical_id(r.source_id) == canonical
            or self._resolution.canonical_id(r.target_id) == canonical
        ]

    def get_outgoing_relationships(self, entity_id: str) -> list[KnowledgeRelationship]:
        canonical = self._resolution.canonical_id(entity_id)
        return [
            r for r in self._relationships
            if self._resolution.canonical_id(r.source_id) == canonical
        ]

    def get_incoming_relationships(self, entity_id: str) -> list[KnowledgeRelationship]:
        canonical = self._resolution.canonical_id(entity_id)
        return [
            r for r in self._relationships
            if self._resolution.canonical_id(r.target_id) == canonical
        ]

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    def get_neighbors(
        self,
        entity_id: str,
        relation_type: RelationType | None = None,
    ) -> list[KnowledgeEntity]:
        """Get neighboring entities connected by relationships."""
        canonical = self._resolution.canonical_id(entity_id)

        if self._adjacency and relation_type is None:
            neighbor_ids = self._adjacency.get_neighbor_ids(canonical)
            return [self._entities[nid] for nid in neighbor_ids if nid in self._entities]

        # Linear scan fallback (used when filtering by relation_type or no adjacency index)
        found_neighbors: set[str] = set()
        for rel in self._relationships:
            src = self._resolution.canonical_id(rel.source_id)
            tgt = self._resolution.canonical_id(rel.target_id)
            if relation_type and rel.relation_type != relation_type:
                continue
            if src == canonical:
                found_neighbors.add(tgt)
            elif tgt == canonical:
                found_neighbors.add(src)

        return [self._entities[nid] for nid in found_neighbors if nid in self._entities]

    def reinforce(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        delta: float = 0.1,
    ) -> None:
        """Increase edge weight (Hebbian-like reinforcement)."""
        source = self._resolution.canonical_id(source_id)
        target = self._resolution.canonical_id(target_id)

        for rel in self._relationships:
            if (
                self._resolution.canonical_id(rel.source_id) == source
                and self._resolution.canonical_id(rel.target_id) == target
                and rel.relation_type == relation_type
            ):
                old_weight = rel.weight
                rel.weight = min(2.0, rel.weight + delta)
                if self._change_buffer:
                    self._change_buffer.record_reinforce(source, target, old_weight, rel.weight)
                return

    def weaken(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        delta: float = 0.05,
    ) -> None:
        """Decrease edge weight (Hebbian-like weakening)."""
        source = self._resolution.canonical_id(source_id)
        target = self._resolution.canonical_id(target_id)

        for rel in self._relationships:
            if (
                self._resolution.canonical_id(rel.source_id) == source
                and self._resolution.canonical_id(rel.target_id) == target
                and rel.relation_type == relation_type
            ):
                old_weight = rel.weight
                rel.weight = max(0.0, rel.weight - delta)
                if self._change_buffer:
                    self._change_buffer.record_weaken(source, target, old_weight, rel.weight)
                return

    def merge_entities(self, id_a: str, id_b: str) -> None:
        """Merge two entities (e.g., duplicate author names)."""
        self._resolution.union(id_a, id_b)
        canonical = self._resolution.canonical_id(id_a)
        other = id_b if canonical == id_a else id_a

        if other in self._entities and canonical not in self._entities:
            entity = self._entities.pop(other)
            entity.id = canonical
            self._entities[canonical] = entity

        if self._change_buffer:
            self._change_buffer.record_merge(canonical, other)
        if self._adjacency:
            self._adjacency.remove_entity(other)

    def get_graph_stats(self) -> dict:
        """Return graph statistics."""
        return {
            "entity_count": len(self._entities),
            "relationship_count": len(self._relationships),
            "entity_types": {
                et.value: sum(1 for e in self._entities.values() if e.entity_type == et)
                for et in EntityType
            },
            "relation_types": {
                rt.value: sum(1 for r in self._relationships if r.relation_type == rt)
                for rt in RelationType
            },
        }

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for ed in data.get("entities", []):
                entity = KnowledgeEntity(**ed)
                self._entities[entity.id] = entity
                self._hash_index[entity.content_hash] = entity.id
                self._resolution.find(entity.id)
            for rd in data.get("relationships", []):
                self._relationships.append(KnowledgeRelationship(**rd))
            if self._adjacency:
                edges = [(r.source_id, r.target_id) for r in self._relationships]
                self._adjacency.rebuild(edges)
            logger.info(
                "Loaded knowledge graph: %d entities, %d relationships",
                len(self._entities),
                len(self._relationships),
            )
        except Exception as e:
            logger.warning("Failed to load knowledge graph: %s", e)

    def save(self) -> None:
        """Persist the knowledge graph to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._change_buffer and self._version_log:
            records = self._change_buffer.flush()
            self._version_log.append(records)
            if self._stream_registry:
                self._stream_registry.process_changes(records)
        data = {
            "entities": [e.model_dump(mode="json") for e in self._entities.values()],
            "relationships": [r.model_dump(mode="json") for r in self._relationships],
        }
        self._path.write_text(json.dumps(data, indent=2, default=str))

    def get_version_log(self) -> VersionLog | None:
        return self._version_log

    def get_changes_since(self, version: int):
        if self._version_log:
            return self._version_log.get_changes_since(version)
        return []

    def attach_stream_registry(self, registry: StreamRegistry) -> None:
        self._stream_registry = registry

    def compute_activation(self, entity_id: str, pipeline: ActivationPipeline) -> float:
        entity = self.get_entity(entity_id)
        if not entity:
            return 0.0
        from backend.pipeline.knowledge.activation import ActivationContext

        context = ActivationContext(
            entity_id=entity_id,
            current_truth=entity.truth,
        )
        return pipeline.compute(context)

    def rank_entities_by_activation(
        self, entity_type: EntityType | None, pipeline: ActivationPipeline
    ) -> list[tuple[str, float]]:
        results = []
        for eid, entity in self._entities.items():
            if entity_type and entity.entity_type != entity_type:
                continue
            score = self.compute_activation(eid, pipeline)
            results.append((eid, score))
        return sorted(results, key=lambda x: x[1], reverse=True)
