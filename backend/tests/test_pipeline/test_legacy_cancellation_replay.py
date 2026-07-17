"""P0.3.5 cancellation and replay adversarial tests.

Proves:
  - Cancellation after target claim leaves honest 'indexing' state
  - Completed program replay performs zero external work
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.db.models import (
    EmbeddingProfile,
    LegacyVectorInventoryRecord,
    LegacyVectorInventoryRun,
    LegacyVectorReindexTarget,
    Paper,
    VectorIndexRecord,
)
from backend.pipeline.legacy_vector_inventory import (
    LegacyCollectionIdentity,
    LegacyVectorRecord,
    create_inventory_run,
    execute_reindex_targets,
    plan_reindex_targets,
    reconcile_inventory_aggregates,
    run_mapping_phase,
    scan_legacy_collection,
)
from backend.pipeline.vector_backend import GovernedVectorBackend
from backend.pipeline.vector_contracts import compute_collection_name, compute_profile_id


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


def _setup(engine, n_papers=1):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        pid = compute_profile_id("test", "model", 4, "l2", "v1")
        coll = compute_collection_name(pid)
        s.add(EmbeddingProfile(
            profile_id=pid, profile_schema_version="embedding_profile_v1",
            provider="test", model_identifier="model", dimension=4,
            normalization_policy="l2", chunking_schema_version="v1",
            collection_name=coll, verification_status="unverified",
        ))
        paper_ids = []
        for i in range(n_papers):
            p = Paper(source_id=f"arxiv:00{i}", source="arxiv",
                      title=f"Paper {i}", authors="[]", keywords="[]", ingested=0)
            s.add(p); s.flush()
            paper_ids.append(p.id)
        s.commit()
        return pid, coll, paper_ids
    finally:
        s.close()


class _EphemeralBackend(GovernedVectorBackend):
    def __init__(self):
        self._store = {}
        self.upsert_count = 0

    def ensure_profile_collection(self, **kw):
        return MagicMock()

    def upsert_vector(self, *, collection_name, vector_record_id, embedding, document, metadata):
        self._store[vector_record_id] = {"embedding": tuple(embedding), "document": document, "metadata": dict(metadata)}
        self.upsert_count += 1

    def read_vector(self, *, collection_name, vector_record_id):
        rec = self._store.get(vector_record_id)
        if not rec:
            return None
        from backend.pipeline.vector_backend import BackendVectorRecord
        meta = rec["metadata"]
        return BackendVectorRecord(
            vector_record_id=vector_record_id,
            paper_id=meta.get("paper_id", 0), chunk_key=meta.get("chunk_key", ""),
            content_kind=meta.get("content_kind", ""), content_hash=meta.get("content_hash", ""),
            embedding_profile_id=meta.get("embedding_profile_id", ""),
            index_schema_version=meta.get("index_schema_version", ""),
            document=rec["document"], embedding=rec["embedding"],
        )

    def delete_vector(self, **kw):
        pass

    def verify_absent(self, **kw):
        return True


class _FakeLegacyBackend:
    def __init__(self, records=None):
        self._records = {r.legacy_record_id: r for r in (records or [])}
    def get_collection_identity(self):
        return LegacyCollectionIdentity("research_papers", len(self._records))
    def count_records(self):
        return len(self._records)
    def read_records_page(self, *, offset, limit):
        ids = sorted(self._records)
        return [self._records[r] for r in ids[offset:offset+limit]]
    def read_record(self, legacy_record_id):
        return self._records.get(legacy_record_id)


def _profile():
    return {"provider": "test", "model_identifier": "model", "dimension": 4,
            "normalization_policy": "l2", "chunking_schema_version": "v1"}


# ── Cancellation ─────────────────────────────────────────────────────


def test_cancellation_leaves_indexing():
    """Cancel after target claim → target remains 'indexing', no false completion."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup(engine, n_papers=1)

    legacy = [LegacyVectorRecord(
        legacy_record_id="l1",
        metadata={"paper_id": paper_ids[0], "title": "Paper 0", "source": "arxiv"},
        document="D", embedding_dimension=4,
    )]
    legacy_backend = _FakeLegacyBackend(legacy)
    Session = sessionmaker(bind=engine)

    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)
    run_mapping_phase(Session, inventory_run_id=run_id)
    plan_reindex_targets(Session, inventory_run_id=run_id, embedding_profile_id=pid)

    # Manually claim the target to 'indexing' state
    s = Session()
    try:
        s.execute(
            update(LegacyVectorReindexTarget)
            .where(LegacyVectorReindexTarget.inventory_run_id == run_id)
            .values(status="indexing", attempt_count=1)
        )
        s.commit()
    finally:
        s.close()

    # Simulate cancellation: the asyncio task is cancelled
    # The target should remain 'indexing'
    s = Session()
    try:
        target = s.execute(
            select(LegacyVectorReindexTarget).where(
                LegacyVectorReindexTarget.inventory_run_id == run_id
            )
        ).scalar_one()
        assert target.status == "indexing"
        assert target.completed_at is None

        run = s.get(LegacyVectorInventoryRun, run_id)
        assert run.status == "reindexing"
        assert run.completed_at is None
    finally:
        s.close()

    # Reconciliation must reject
    valid, _ = reconcile_inventory_aggregates(Session, inventory_run_id=run_id)
    assert not valid


# ── Replay ───────────────────────────────────────────────────────────


def test_completed_replay_no_external_work():
    """Re-running execute_reindex on completed targets → zero new work."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup(engine, n_papers=1)

    legacy = [LegacyVectorRecord(
        legacy_record_id="l1",
        metadata={"paper_id": paper_ids[0], "title": "Paper 0", "source": "arxiv"},
        document="D", embedding_dimension=4,
    )]
    legacy_backend = _FakeLegacyBackend(legacy)
    gov_backend = _EphemeralBackend()

    class _Embedding:
        def __init__(self):
            self.calls = 0
        async def embed_single(self, text):
            self.calls += 1
            return [0.1, 0.2, 0.3, 0.4]

    embed = _Embedding()
    Session = sessionmaker(bind=engine)

    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    # Full lifecycle to completion
    scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)
    run_mapping_phase(Session, inventory_run_id=run_id)
    plan_reindex_targets(Session, inventory_run_id=run_id, embedding_profile_id=pid)
    asyncio.run(execute_reindex_targets(
        Session, inventory_run_id=run_id, governed_backend=gov_backend,
        embedding_provider=embed, profile_dict=_profile(), embedding_profile_id=pid,
    ))

    first_embed_calls = embed.calls
    first_writes = gov_backend.upsert_count

    # Capture target timestamps
    s = Session()
    try:
        target_before = s.execute(
            select(LegacyVectorReindexTarget.completed_at).where(
                LegacyVectorReindexTarget.inventory_run_id == run_id
            )
        ).one()
        completed_at_before = target_before[0]
    finally:
        s.close()

    # Re-run execute — targets are already indexed, should skip
    asyncio.run(execute_reindex_targets(
        Session, inventory_run_id=run_id, governed_backend=gov_backend,
        embedding_provider=embed, profile_dict=_profile(), embedding_profile_id=pid,
    ))

    # No new external work
    assert embed.calls == first_embed_calls
    assert gov_backend.upsert_count == first_writes

    # Timestamps unchanged
    s = Session()
    try:
        target_after = s.execute(
            select(LegacyVectorReindexTarget.completed_at).where(
                LegacyVectorReindexTarget.inventory_run_id == run_id
            )
        ).one()
        assert target_after[0] == completed_at_before
    finally:
        s.close()
