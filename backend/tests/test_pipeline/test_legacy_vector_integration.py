"""P0.3.5H integrated lifecycle tests.

Exercises the complete production path:
  scan → map → plan targets → reindex via VectorIndexer → reconcile
using an ephemeral fake backend and deterministic embedding provider.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

from sqlalchemy import create_engine, event, func, select, update
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import (
    EmbeddingProfile,
    GlobalLibraryMembership,
    LegacyVectorInventoryRecord,
    LegacyVectorReindexTarget,
    Paper,
    PaperDiscovery,
    RunPaper,
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
    verify_source_drift,
)
from backend.pipeline.vector_backend import GovernedVectorBackend
from backend.pipeline.vector_contracts import compute_collection_name, compute_profile_id
from backend.pipeline.vector_indexer import index_document


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


def _setup_profile_and_papers(engine, n_papers=3):
    """Create profile + canonical papers that legacy records will map to."""
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
                      title=f"Canonical Paper {i}", authors="[]", keywords="[]", ingested=0)
            s.add(p); s.flush()
            paper_ids.append(p.id)
        s.commit()
        return pid, coll, paper_ids
    finally:
        s.close()


class _EphemeralBackend(GovernedVectorBackend):
    """In-memory governed backend for integration tests."""
    def __init__(self):
        self._store: dict[str, dict] = {}
        self.upsert_count = 0

    def ensure_profile_collection(self, *, collection_name, embedding_profile_id, embedding_dimension):
        return MagicMock(name=collection_name)

    def upsert_vector(self, *, collection_name, vector_record_id, embedding, document, metadata):
        self._store[vector_record_id] = {"embedding": tuple(embedding), "document": document, "metadata": dict(metadata)}
        self.upsert_count += 1

    def read_vector(self, *, collection_name, vector_record_id):
        rec = self._store.get(vector_record_id)
        if rec is None:
            return None
        meta = rec["metadata"]
        from backend.pipeline.vector_backend import BackendVectorRecord
        return BackendVectorRecord(
            vector_record_id=vector_record_id,
            paper_id=meta.get("paper_id", 0),
            chunk_key=meta.get("chunk_key", ""),
            content_kind=meta.get("content_kind", ""),
            content_hash=meta.get("content_hash", ""),
            embedding_profile_id=meta.get("embedding_profile_id", ""),
            index_schema_version=meta.get("index_schema_version", ""),
            document=rec["document"],
            embedding=rec["embedding"],
        )

    def delete_vector(self, *, collection_name, vector_record_id):
        self._store.pop(vector_record_id, None)

    def verify_absent(self, *, collection_name, vector_record_id):
        return vector_record_id not in self._store


class _DeterministicEmbeddingProvider:
    def __init__(self, dim=4):
        self._dim = dim
        self.call_count = 0
    async def embed_single(self, text):
        self.call_count += 1
        return [0.1 * (i + 1) for i in range(self._dim)]


class _FakeLegacyBackend:
    """Fake legacy research_papers collection."""
    def __init__(self, records=None):
        self._records = {r.legacy_record_id: r for r in (records or [])}

    def get_collection_identity(self):
        return LegacyCollectionIdentity("research_papers", len(self._records))

    def count_records(self):
        return len(self._records)

    def read_records_page(self, *, offset, limit):
        ids = sorted(self._records.keys())
        return [self._records[rid] for rid in ids[offset:offset + limit]]

    def read_record(self, legacy_record_id):
        return self._records.get(legacy_record_id)

    def add_record(self, record):
        self._records[record.legacy_record_id] = record

    def remove_record(self, legacy_record_id):
        self._records.pop(legacy_record_id, None)


def _profile_dict():
    return {
        "provider": "test",
        "model_identifier": "model",
        "dimension": 4,
        "normalization_policy": "l2",
        "chunking_schema_version": "v1",
    }


# ── 1. Full integrated lifecycle ─────────────────────────────────────


def test_full_integrated_lifecycle():
    """Scan → map → plan → reindex → reconcile — the complete path."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=2)

    # Legacy records with paper_id pointing to canonical papers
    legacy_records = [
        LegacyVectorRecord(
            legacy_record_id="legacy_1",
            metadata={"paper_id": paper_ids[0], "title": "Canonical Paper 0", "source": "arxiv"},
            document="OLD LEGACY TEXT - should not be used",
            embedding_dimension=4,
        ),
        LegacyVectorRecord(
            legacy_record_id="legacy_2",
            metadata={"paper_id": paper_ids[1], "title": "Canonical Paper 1", "source": "arxiv"},
            document="ANOTHER LEGACY TEXT",
            embedding_dimension=4,
        ),
    ]
    legacy_backend = _FakeLegacyBackend(legacy_records)
    gov_backend = _EphemeralBackend()
    embed_provider = _DeterministicEmbeddingProvider(dim=4)
    Session = sessionmaker(bind=engine)

    # Phase 1: Create inventory run
    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    # Phase 2: Scan
    scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)

    # Phase 3: Map
    run_mapping_phase(Session, inventory_run_id=run_id)

    # Phase 4: Plan targets
    target_count = plan_reindex_targets(Session, inventory_run_id=run_id, embedding_profile_id=pid)
    assert target_count == 2

    # Phase 5: Reindex
    counts = asyncio.run(execute_reindex_targets(
        Session, inventory_run_id=run_id,
        governed_backend=gov_backend,
        embedding_provider=embed_provider,
        profile_dict=_profile_dict(),
        embedding_profile_id=pid,
    ))
    assert counts["indexed"] == 2
    assert counts["failed"] == 0
    assert embed_provider.call_count == 2  # One per target

    # Phase 6: Reconcile
    valid, detail = reconcile_inventory_aggregates(Session, inventory_run_id=run_id)
    assert valid, f"reconciliation failed: {detail}"

    # Verify governed vectors exist
    s = Session()
    try:
        vir_records = s.execute(
            select(VectorIndexRecord).where(
                VectorIndexRecord.embedding_profile_id == pid,
                VectorIndexRecord.index_status == "indexed",
            )
        ).scalars().all()
        assert len(vir_records) == 2

        # Verify inventory records have terminal dispositions
        inv_records = s.execute(
            select(LegacyVectorInventoryRecord).where(
                LegacyVectorInventoryRecord.inventory_run_id == run_id
            )
        ).scalars().all()
        assert all(r.disposition is not None for r in inv_records)
        assert all(r.disposition in ("reindexed", "already_indexed") for r in inv_records)
    finally:
        s.close()


# ── 2. Duplicate targets ─────────────────────────────────────────────


def test_duplicate_targets_dedup():
    """Three legacy records → one paper → one target, one indexer call."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=1)

    legacy_records = [
        LegacyVectorRecord(
            legacy_record_id=f"legacy_{i}",
            metadata={"paper_id": paper_ids[0], "title": "Canonical Paper 0", "source": "arxiv"},
            document=f"Legacy doc {i}",
            embedding_dimension=4,
        )
        for i in range(3)
    ]
    legacy_backend = _FakeLegacyBackend(legacy_records)
    gov_backend = _EphemeralBackend()
    embed_provider = _DeterministicEmbeddingProvider(dim=4)
    Session = sessionmaker(bind=engine)

    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)
    run_mapping_phase(Session, inventory_run_id=run_id)
    target_count = plan_reindex_targets(Session, inventory_run_id=run_id, embedding_profile_id=pid)
    assert target_count == 1  # One target for one paper

    counts = asyncio.run(execute_reindex_targets(
        Session, inventory_run_id=run_id,
        governed_backend=gov_backend,
        embedding_provider=embed_provider,
        profile_dict=_profile_dict(),
        embedding_profile_id=pid,
    ))

    # One indexing call, one backend write
    assert embed_provider.call_count == 1
    assert gov_backend.upsert_count == 1

    # Verify source record dispositions
    s = Session()
    try:
        records = s.execute(
            select(LegacyVectorInventoryRecord.disposition).where(
                LegacyVectorInventoryRecord.inventory_run_id == run_id
            )
        ).all()
        dispositions = [r[0] for r in records]
        assert "reindexed" in dispositions  # Representative
        assert dispositions.count("duplicate_target") == 2  # Other two
    finally:
        s.close()


# ── 3. Canonical content enforcement ─────────────────────────────────


def test_canonical_content_not_legacy():
    """Embedding provider receives canonical content, not legacy document."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=1)

    legacy_record = LegacyVectorRecord(
        legacy_record_id="legacy_1",
        metadata={"paper_id": paper_ids[0], "title": "Canonical Paper 0", "source": "arxiv"},
        document="COMPLETELY DIFFERENT LEGACY TEXT",
        embedding_dimension=4,
    )
    legacy_backend = _FakeLegacyBackend([legacy_record])
    gov_backend = _EphemeralBackend()

    received_texts: list[str] = []
    class _CapturingProvider:
        async def embed_single(self, text):
            received_texts.append(text)
            return [0.1, 0.2, 0.3, 0.4]

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

    asyncio.run(execute_reindex_targets(
        Session, inventory_run_id=run_id,
        governed_backend=gov_backend,
        embedding_provider=_CapturingProvider(),
        profile_dict=_profile_dict(),
        embedding_profile_id=pid,
    ))

    # The embedding text must be the canonical title+abstract, not legacy doc
    assert len(received_texts) == 1
    assert "COMPLETELY DIFFERENT LEGACY TEXT" not in received_texts[0]
    assert "Canonical Paper 0" in received_texts[0]


# ── 4. Already-indexed target ────────────────────────────────────────


def test_already_indexed_no_embedding_call():
    """Pre-index the target → already_indexed, zero embedding calls."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=1)

    # Pre-index the paper through VectorIndexer
    gov_backend = _EphemeralBackend()
    embed_provider = _DeterministicEmbeddingProvider(dim=4)
    Session = sessionmaker(bind=engine)

    from backend.pipeline.vector_contracts import build_title_abstract_document
    s = Session()
    try:
        paper = s.get(Paper, paper_ids[0])
        title = paper.title
    finally:
        s.close()

    doc = build_title_abstract_document(
        paper_id=paper_ids[0], title=title, abstract=None,
        embedding_profile_id=pid,
    )
    asyncio.run(index_document(
        session_factory=Session, backend=gov_backend,
        embedding_provider=embed_provider, profile=_profile_dict(),
        document=doc,
    ))
    first_call_count = embed_provider.call_count

    # Now run migration
    legacy_record = LegacyVectorRecord(
        legacy_record_id="legacy_1",
        metadata={"paper_id": paper_ids[0], "title": title, "source": "arxiv"},
        document="Legacy text",
        embedding_dimension=4,
    )
    legacy_backend = _FakeLegacyBackend([legacy_record])

    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)
    run_mapping_phase(Session, inventory_run_id=run_id)
    plan_reindex_targets(Session, inventory_run_id=run_id, embedding_profile_id=pid)

    counts = asyncio.run(execute_reindex_targets(
        Session, inventory_run_id=run_id,
        governed_backend=gov_backend,
        embedding_provider=embed_provider,
        profile_dict=_profile_dict(),
        embedding_profile_id=pid,
    ))

    assert counts["already_indexed"] == 1
    assert embed_provider.call_count == first_call_count  # No new embedding calls


# ── 5. Indexer failure ───────────────────────────────────────────────


def test_indexer_failure_prevents_completion():
    """Target failure → inventory cannot complete."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=1)

    legacy_record = LegacyVectorRecord(
        legacy_record_id="legacy_1",
        metadata={"paper_id": paper_ids[0], "title": "Canonical Paper 0", "source": "arxiv"},
        document="Legacy",
        embedding_dimension=4,
    )
    legacy_backend = _FakeLegacyBackend([legacy_record])
    gov_backend = _EphemeralBackend()

    class _FailingProvider:
        async def embed_single(self, text):
            raise RuntimeError("embedding provider down")

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

    counts = asyncio.run(execute_reindex_targets(
        Session, inventory_run_id=run_id,
        governed_backend=gov_backend,
        embedding_provider=_FailingProvider(),
        profile_dict=_profile_dict(),
        embedding_profile_id=pid,
    ))
    assert counts["failed"] == 1

    # Reconciliation must reject completion
    valid, detail = reconcile_inventory_aggregates(Session, inventory_run_id=run_id)
    assert not valid
    assert "failed" in (detail or "").lower()


# ── 6. Source drift ──────────────────────────────────────────────────


def test_source_drift_prevents_completion():
    """Legacy collection changes after scan → verification fails."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=1)

    legacy_records = [
        LegacyVectorRecord(
            legacy_record_id="legacy_1",
            metadata={"paper_id": paper_ids[0], "title": "Canonical Paper 0", "source": "arxiv"},
            document="D1", embedding_dimension=4,
        ),
    ]
    legacy_backend = _FakeLegacyBackend(legacy_records)
    Session = sessionmaker(bind=engine)

    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)

    # Add a record after scan → drift
    legacy_backend.add_record(LegacyVectorRecord(
        legacy_record_id="legacy_new",
        metadata={"paper_id": paper_ids[0], "title": "New", "source": "arxiv"},
        document="D2", embedding_dimension=4,
    ))

    assert not verify_source_drift(Session, legacy_backend, inventory_run_id=run_id)


# ── 7. Ownership isolation ───────────────────────────────────────────


def test_no_ownership_created():
    """Migration does not create Paper, RunPaper, PaperDiscovery, or GlobalLibraryMembership."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=1)

    legacy_record = LegacyVectorRecord(
        legacy_record_id="legacy_1",
        metadata={"paper_id": paper_ids[0], "title": "Canonical Paper 0", "source": "arxiv"},
        document="Legacy", embedding_dimension=4,
    )
    legacy_backend = _FakeLegacyBackend([legacy_record])
    gov_backend = _EphemeralBackend()
    embed_provider = _DeterministicEmbeddingProvider(dim=4)
    Session = sessionmaker(bind=engine)

    # Count before
    s = Session()
    try:
        papers_before = s.execute(select(func.count(Paper.id))).scalar()
        runpapers_before = s.execute(select(func.count(RunPaper.id))).scalar()
        discoveries_before = s.execute(select(func.count(PaperDiscovery.id))).scalar()
        memberships_before = s.execute(select(func.count(GlobalLibraryMembership.paper_id))).scalar()
    finally:
        s.close()

    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)
    run_mapping_phase(Session, inventory_run_id=run_id)
    plan_reindex_targets(Session, inventory_run_id=run_id, embedding_profile_id=pid)
    asyncio.run(execute_reindex_targets(
        Session, inventory_run_id=run_id,
        governed_backend=gov_backend,
        embedding_provider=embed_provider,
        profile_dict=_profile_dict(),
        embedding_profile_id=pid,
    ))

    # Count after
    s = Session()
    try:
        papers_after = s.execute(select(func.count(Paper.id))).scalar()
        runpapers_after = s.execute(select(func.count(RunPaper.id))).scalar()
        discoveries_after = s.execute(select(func.count(PaperDiscovery.id))).scalar()
        memberships_after = s.execute(select(func.count(GlobalLibraryMembership.paper_id))).scalar()
    finally:
        s.close()

    assert papers_after == papers_before
    assert runpapers_after == runpapers_before
    assert discoveries_after == discoveries_before
    assert memberships_after == memberships_before


# ── 8. Quarantine isolation ──────────────────────────────────────────


def test_quarantined_records_have_no_target():
    """Unmapped records have no mapped_paper_id, no target, no vector."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=1)

    # One mapped, one unmapped
    legacy_records = [
        LegacyVectorRecord(
            legacy_record_id="mapped_1",
            metadata={"paper_id": paper_ids[0], "title": "Canonical Paper 0", "source": "arxiv"},
            document="D1", embedding_dimension=4,
        ),
        LegacyVectorRecord(
            legacy_record_id="unmapped_1",
            metadata={"paper_id": 99999, "title": "Nonexistent", "source": "arxiv"},
            document="D2", embedding_dimension=4,
        ),
    ]
    legacy_backend = _FakeLegacyBackend(legacy_records)
    Session = sessionmaker(bind=engine)

    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, legacy_backend, inventory_run_id=run_id)
    run_mapping_phase(Session, inventory_run_id=run_id)

    s = Session()
    try:
        # Unmapped record
        unmapped = s.execute(
            select(LegacyVectorInventoryRecord).where(
                LegacyVectorInventoryRecord.inventory_run_id == run_id,
                LegacyVectorInventoryRecord.legacy_record_id == "unmapped_1",
            )
        ).scalar_one()
        assert unmapped.mapping_status == "unmapped"
        assert unmapped.mapped_paper_id is None
        assert unmapped.disposition == "quarantined_unmapped"

        # Mapped record
        mapped = s.execute(
            select(LegacyVectorInventoryRecord).where(
                LegacyVectorInventoryRecord.inventory_run_id == run_id,
                LegacyVectorInventoryRecord.legacy_record_id == "mapped_1",
            )
        ).scalar_one()
        assert mapped.mapping_status == "mapped"
        assert mapped.mapped_paper_id == paper_ids[0]
    finally:
        s.close()


# ── 9. Target concurrency ────────────────────────────────────────────


def test_target_concurrency_single_claim():
    """Two workers claim the same planned target → one succeeds."""
    engine = _make_engine()
    pid, coll, paper_ids = _setup_profile_and_papers(engine, n_papers=1)

    legacy_record = LegacyVectorRecord(
        legacy_record_id="legacy_1",
        metadata={"paper_id": paper_ids[0], "title": "Canonical Paper 0", "source": "arxiv"},
        document="D1", embedding_dimension=4,
    )
    legacy_backend = _FakeLegacyBackend([legacy_record])
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

    # Manually claim the target
    s = Session()
    try:
        target = s.execute(
            select(LegacyVectorReindexTarget).where(
                LegacyVectorReindexTarget.inventory_run_id == run_id
            )
        ).scalar_one()
        # First claim succeeds
        claim1 = s.execute(
            update(LegacyVectorReindexTarget)
            .where(
                LegacyVectorReindexTarget.id == target.id,
                LegacyVectorReindexTarget.status == "planned",
            )
            .values(status="indexing", attempt_count=1)
        )
        assert claim1.rowcount == 1
        s.commit()

        # Second claim fails (already indexing)
        claim2 = s.execute(
            update(LegacyVectorReindexTarget)
            .where(
                LegacyVectorReindexTarget.id == target.id,
                LegacyVectorReindexTarget.status == "planned",
            )
            .values(status="indexing", attempt_count=1)
        )
        assert claim2.rowcount == 0
    finally:
        s.close()
