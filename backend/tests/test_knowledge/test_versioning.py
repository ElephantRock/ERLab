"""Tests for knowledge graph versioning, adjacency index, and ChangeRecord."""

import tempfile

from backend.pipeline.knowledge.adjacency import AdjacencyIndex
from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.knowledge.versioning import ChangeBuffer, ChangeRecord, VersionLog


class TestChangeRecord:
    def test_compute_content_hash_deterministic(self):
        data = {"id": "e1", "name": "test"}
        h1 = ChangeRecord.compute_content_hash(data)
        h2 = ChangeRecord.compute_content_hash(data)
        assert h1 == h2
        assert len(h1) == 16

    def test_compute_content_hash_differs_on_change(self):
        h1 = ChangeRecord.compute_content_hash({"id": "e1", "val": 1})
        h2 = ChangeRecord.compute_content_hash({"id": "e1", "val": 2})
        assert h1 != h2


class TestChangeBuffer:
    def test_record_entity_add(self):
        buf = ChangeBuffer()
        rec = buf.record_entity_add("e1", "hash123")
        assert rec.operation == "add_entity"
        assert rec.target_id == "e1"
        assert rec.new_content_hash == "hash123"

    def test_record_truth_update(self):
        buf = ChangeBuffer()
        rec = buf.record_truth_update("e1", "old_hash", "new_hash")
        assert rec.operation == "update_truth"
        assert rec.old_content_hash == "old_hash"
        assert rec.new_content_hash == "new_hash"

    def test_record_reinforce(self):
        buf = ChangeBuffer()
        rec = buf.record_reinforce("a", "b", 1.0, 1.1)
        assert rec.operation == "reinforce"
        assert rec.delta == {"field": "weight", "old": 1.0, "new": 1.1}

    def test_record_merge(self):
        buf = ChangeBuffer()
        rec = buf.record_merge("survivor", "absorbed")
        assert rec.operation == "merge"
        assert rec.delta["absorbed"] == "absorbed"

    def test_flush_clears(self):
        buf = ChangeBuffer()
        buf.record_entity_add("e1", "h1")
        buf.record_entity_add("e2", "h2")
        records = buf.flush()
        assert len(records) == 2
        assert buf.pending_count == 0

    def test_version_increments(self):
        buf = ChangeBuffer()
        r1 = buf.record_entity_add("e1", "h1")
        r2 = buf.record_entity_add("e2", "h2")
        assert r2.version > r1.version


class TestVersionLog:
    def test_append_and_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = VersionLog(f"{tmp}/test.jsonl")
            records = [
                ChangeRecord(
                    version=1, operation="add_entity", target_id="e1", target_type="entity"
                ),
                ChangeRecord(
                    version=2, operation="add_entity", target_id="e2", target_type="entity"
                ),
            ]
            log.append(records)
            assert log.entry_count == 2
            assert log.latest_version == 2
            assert log.get_version(1).target_id == "e1"

    def test_changes_since(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = VersionLog(f"{tmp}/test.jsonl")
            log.append(
                [
                    ChangeRecord(
                        version=1, operation="add_entity", target_id="e1", target_type="entity"
                    ),
                    ChangeRecord(
                        version=2, operation="add_entity", target_id="e2", target_type="entity"
                    ),
                    ChangeRecord(
                        version=3, operation="add_entity", target_id="e3", target_type="entity"
                    ),
                ]
            )
            since = log.get_changes_since(1)
            assert len(since) == 2

    def test_changes_for_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = VersionLog(f"{tmp}/test.jsonl")
            log.append(
                [
                    ChangeRecord(
                        version=1, operation="add_entity", target_id="e1", target_type="entity"
                    ),
                    ChangeRecord(
                        version=2, operation="update_truth", target_id="e1", target_type="entity"
                    ),
                    ChangeRecord(
                        version=3, operation="add_entity", target_id="e2", target_type="entity"
                    ),
                ]
            )
            changes = log.get_changes_for("e1")
            assert len(changes) == 2

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/test.jsonl"
            log = VersionLog(path)
            log.append(
                [
                    ChangeRecord(
                        version=1, operation="add_entity", target_id="e1", target_type="entity"
                    )
                ]
            )
            log2 = VersionLog(path)
            assert log2.entry_count == 1

    def test_latest_version_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = VersionLog(f"{tmp}/empty.jsonl")
            assert log.latest_version == 0


class TestAdjacencyIndex:
    def test_add_and_query(self):
        idx = AdjacencyIndex()
        idx.add_relationship("a", "b")
        idx.add_relationship("a", "c")
        neighbors = idx.get_neighbor_ids("a")
        assert neighbors == {"b", "c"}

    def test_bidirectional(self):
        idx = AdjacencyIndex()
        idx.add_relationship("a", "b")
        assert "a" in idx.get_neighbor_ids("b")
        assert "b" in idx.get_neighbor_ids("a")

    def test_outgoing_incoming(self):
        idx = AdjacencyIndex()
        idx.add_relationship("a", "b")
        assert "b" in idx.get_outgoing("a")
        assert "a" in idx.get_incoming("b")

    def test_remove_entity(self):
        idx = AdjacencyIndex()
        idx.add_relationship("a", "b")
        idx.add_relationship("b", "c")
        idx.remove_entity("b")
        assert "b" not in idx.get_neighbor_ids("a")
        assert "b" not in idx.get_neighbor_ids("c")

    def test_rebuild(self):
        idx = AdjacencyIndex()
        idx.rebuild([("a", "b"), ("b", "c")])
        assert idx.get_neighbor_ids("b") == {"a", "c"}

    def test_edge_count(self):
        idx = AdjacencyIndex()
        idx.add_relationship("a", "b")
        idx.add_relationship("b", "c")
        assert idx.edge_count == 2


class TestKnowledgeGraphVersioning:
    def _make_entity(self, eid: str, name: str = "test") -> KnowledgeEntity:
        return KnowledgeEntity(
            id=eid,
            entity_type=EntityType.CONCEPT,
            name=name,
            truth=TruthValue.from_observation(),
        )

    def test_versioning_disabled_no_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json", versioning_enabled=False)
            kg.add_entity(self._make_entity("e1"))
            kg.save()
            assert kg.get_version_log() is None

    def test_versioning_enabled_tracks_additions(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json", versioning_enabled=True)
            kg.add_entity(self._make_entity("e1"))
            kg.save()
            log = kg.get_version_log()
            assert log is not None
            assert log.entry_count >= 1

    def test_versioning_tracks_truth_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json", versioning_enabled=True)
            kg.add_entity(self._make_entity("e1"))
            kg.add_entity(self._make_entity("e1"))  # Revises truth
            kg.save()
            log = kg.get_version_log()
            ops = [e.operation for e in log._entries]
            assert "update_truth" in ops

    def test_versioning_tracks_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json", versioning_enabled=True)
            kg.add_entity(self._make_entity("e1", "alpha"))
            kg.add_entity(self._make_entity("e2", "beta"))
            kg.merge_entities("e1", "e2")
            kg.save()
            log = kg.get_version_log()
            ops = [e.operation for e in log._entries]
            assert "merge" in ops

    def test_adjacency_speeds_up_neighbors(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json", versioning_enabled=True)
            kg.add_entity(self._make_entity("a"))
            kg.add_entity(self._make_entity("b"))
            kg.add_relationship(
                KnowledgeRelationship(
                    source_id="a",
                    target_id="b",
                    relation_type=RelationType.BUILDS_ON,
                    truth=TruthValue.from_observation(),
                )
            )
            neighbors = kg.get_neighbors("a")
            assert len(neighbors) == 1
            assert neighbors[0].id == "b"

    def test_get_changes_since(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json", versioning_enabled=True)
            kg.add_entity(self._make_entity("e1"))
            kg.save()
            changes = kg.get_changes_since(0)
            assert len(changes) >= 1
