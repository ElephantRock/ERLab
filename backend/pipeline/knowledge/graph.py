"""Entity-centric knowledge graph with Hebbian-like edge consolidation.

Stores entities (papers, authors, methods, datasets, concepts) and their
relationships (cites, uses_method, extends, contradicts, etc.) in an
in-memory graph with JSON persistence.
"""

import json
import logging
from pathlib import Path

from backend.pipeline.knowledge.entities import EntityResolution, EntityType, KnowledgeEntity
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
from backend.pipeline.knowledge.truth import TruthValue

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Entity-centric knowledge graph with Hebbian-like edge consolidation."""

    def __init__(self, persist_path: str = "./data/knowledge_graph.json"):
        self._path = Path(persist_path)
        self._entities: dict[str, KnowledgeEntity] = {}
        self._relationships: list[KnowledgeRelationship] = []
        self._resolution = EntityResolution()
        self._load()

    def add_entity(self, entity: KnowledgeEntity) -> str:
        """Add an entity. Returns canonical ID."""
        canonical = self._resolution.canonical_id(entity.id)
        if canonical in self._entities:
            # Revise truth for existing entity
            existing = self._entities[canonical]
            existing.truth = existing.truth.revise(entity.truth)
            return canonical

        self._entities[canonical] = entity
        return canonical

    def add_relationship(self, rel: KnowledgeRelationship) -> None:
        """Add a relationship. If similar one exists, reinforce weight."""
        source = self._resolution.canonical_id(rel.source_id)
        target = self._resolution.canonical_id(rel.target_id)

        # Check for existing relationship between same entities and type
        for existing in self._relationships:
            if (self._resolution.canonical_id(existing.source_id) == source
                    and self._resolution.canonical_id(existing.target_id) == target
                    and existing.relation_type == rel.relation_type):
                # Reinforce existing edge
                self.reinforce(source, target, rel.relation_type, delta=0.1)
                existing.truth = existing.truth.revise(rel.truth)
                return

        self._relationships.append(KnowledgeRelationship(
            source_id=source,
            target_id=target,
            relation_type=rel.relation_type,
            weight=rel.weight,
            evidence=rel.evidence,
            truth=rel.truth,
        ))

    def get_entity(self, entity_id: str) -> KnowledgeEntity | None:
        """Get an entity by ID (resolves to canonical)."""
        canonical = self._resolution.canonical_id(entity_id)
        return self._entities.get(canonical)

    def get_neighbors(
        self,
        entity_id: str,
        relation_type: RelationType | None = None,
    ) -> list[KnowledgeEntity]:
        """Get neighboring entities connected by relationships."""
        canonical = self._resolution.canonical_id(entity_id)
        neighbor_ids: set[str] = set()

        for rel in self._relationships:
            src = self._resolution.canonical_id(rel.source_id)
            tgt = self._resolution.canonical_id(rel.target_id)
            if relation_type and rel.relation_type != relation_type:
                continue
            if src == canonical:
                neighbor_ids.add(tgt)
            elif tgt == canonical:
                neighbor_ids.add(src)

        return [self._entities[nid] for nid in neighbor_ids if nid in self._entities]

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
            if (self._resolution.canonical_id(rel.source_id) == source
                    and self._resolution.canonical_id(rel.target_id) == target
                    and rel.relation_type == relation_type):
                rel.weight = min(2.0, rel.weight + delta)
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
            if (self._resolution.canonical_id(rel.source_id) == source
                    and self._resolution.canonical_id(rel.target_id) == target
                    and rel.relation_type == relation_type):
                rel.weight = max(0.0, rel.weight - delta)
                return

    def merge_entities(self, id_a: str, id_b: str) -> None:
        """Merge two entities (e.g., duplicate author names)."""
        self._resolution.union(id_a, id_b)
        canonical = self._resolution.canonical_id(id_a)
        other = id_b if canonical == id_a else id_a

        # Move entity data to canonical
        if other in self._entities and canonical not in self._entities:
            entity = self._entities.pop(other)
            entity.id = canonical
            self._entities[canonical] = entity

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
                self._resolution.find(entity.id)  # Register in Union-Find
            for rd in data.get("relationships", []):
                self._relationships.append(KnowledgeRelationship(**rd))
            logger.info("Loaded knowledge graph: %d entities, %d relationships",
                        len(self._entities), len(self._relationships))
        except Exception as e:
            logger.warning("Failed to load knowledge graph: %s", e)

    def save(self) -> None:
        """Persist the knowledge graph to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entities": [e.model_dump(mode="json") for e in self._entities.values()],
            "relationships": [r.model_dump(mode="json") for r in self._relationships],
        }
        self._path.write_text(json.dumps(data, indent=2, default=str))
