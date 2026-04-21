"""Bidirectional adjacency index for O(1) neighbor lookup.

Replaces the O(n) linear scan in KnowledgeGraph.get_neighbors()
with indexed lookup when versioning is enabled.
"""

from __future__ import annotations


class AdjacencyIndex:
    """Bidirectional adjacency index over knowledge graph relationships."""

    def __init__(self):
        self._outgoing: dict[str, set[str]] = {}  # entity_id -> set of neighbor entity_ids
        self._incoming: dict[str, set[str]] = {}  # entity_id -> set of neighbor entity_ids

    def add_relationship(self, source_id: str, target_id: str) -> None:
        self._outgoing.setdefault(source_id, set()).add(target_id)
        self._incoming.setdefault(target_id, set()).add(source_id)

    def remove_entity(self, entity_id: str) -> None:
        # Remove all edges involving this entity
        neighbors = self.get_neighbor_ids(entity_id)
        for neighbor_id in neighbors:
            if neighbor_id in self._outgoing:
                self._outgoing[neighbor_id].discard(entity_id)
            if neighbor_id in self._incoming:
                self._incoming[neighbor_id].discard(entity_id)
        self._outgoing.pop(entity_id, None)
        self._incoming.pop(entity_id, None)

    def get_neighbor_ids(self, entity_id: str) -> set[str]:
        outgoing = self._outgoing.get(entity_id, set())
        incoming = self._incoming.get(entity_id, set())
        return outgoing | incoming

    def get_outgoing(self, entity_id: str) -> set[str]:
        return set(self._outgoing.get(entity_id, set()))

    def get_incoming(self, entity_id: str) -> set[str]:
        return set(self._incoming.get(entity_id, set()))

    def rebuild(self, relationships: list[tuple[str, str]]) -> None:
        self._outgoing.clear()
        self._incoming.clear()
        for source_id, target_id in relationships:
            self.add_relationship(source_id, target_id)

    @property
    def edge_count(self) -> int:
        return sum(len(neighbors) for neighbors in self._outgoing.values())
