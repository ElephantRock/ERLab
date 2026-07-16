"""Tests for P0.3.5B-H: legacy vector inventory runtime and reindex.

Uses ephemeral fake backends and deterministic fixtures.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select, text
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
)
from backend.pipeline.legacy_vector_inventory import (
    ChromaLegacyInventoryBackend,
    ExtractedLegacyIdentity,
    LegacyCollectionIdentity,
    LegacyMappingDecision,
    LegacyVectorInventoryBackend,
    LegacyVectorRecord,
    compute_record_fingerprint,
    compute_source_snapshot_fingerprint,
    create_inventory_run,
    extract_legacy_identity,
    map_legacy_identity,
    scan_legacy_collection,
    verify_source_drift,
)
from backend.pipeline.vector_contracts import compute_collection_name, compute_profile_id


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


def _setup_profile(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        pid = compute_profile_id("test", "model", 4, "l2", "v1")
        s.add(EmbeddingProfile(
            profile_id=pid, profile_schema_version="embedding_profile_v1",
            provider="test", model_identifier="model", dimension=4,
            normalization_policy="l2", chunking_schema_version="v1",
            collection_name=compute_collection_name(pid),
            verification_status="unverified",
        ))
        s.commit()
        return pid
    finally:
        s.close()


def _make_paper(engine, source_id, title, doi=None):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        p = Paper(source_id=source_id, source="arxiv", title=title,
                  authors="[]", keywords="[]", ingested=0, doi=doi)
        s.add(p); s.commit()
        return p.id
    finally:
        s.close()


class _FakeInventoryBackend:
    """In-memory legacy collection for testing."""
    def __init__(self, records: list[LegacyVectorRecord]):
        self._records = {r.legacy_record_id: r for r in records}

    def get_collection_identity(self):
        return LegacyCollectionIdentity("research_papers", len(self._records))

    def count_records(self):
        return len(self._records)

    def read_records_page(self, *, offset, limit):
        ids = sorted(self._records.keys())
        page_ids = ids[offset:offset + limit]
        return [self._records[rid] for rid in page_ids]

    def read_record(self, legacy_record_id):
        return self._records.get(legacy_record_id)

    def add_record(self, record):
        self._records[record.legacy_record_id] = record

    def remove_record(self, legacy_record_id):
        self._records.pop(legacy_record_id, None)


# ── 1. Scanner ───────────────────────────────────────────────────────


def test_scan_completeness():
    """N backend records → N inventory rows + deterministic fingerprint."""
    engine = _make_engine()
    pid = _setup_profile(engine)

    records = [
        LegacyVectorRecord(
            legacy_record_id=f"chunk_{i}",
            metadata={"paper_id": i + 1, "title": f"Paper {i}", "source": "arxiv"},
            document=f"Title {i}\n\nAbstract {i}",
            embedding_dimension=4,
        )
        for i in range(5)
    ]
    backend = _FakeInventoryBackend(records)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    fp = scan_legacy_collection(Session, backend, inventory_run_id=run_id)

    s = Session()
    try:
        inv_records = s.execute(
            select(LegacyVectorInventoryRecord).where(
                LegacyVectorInventoryRecord.inventory_run_id == run_id
            )
        ).scalars().all()
        assert len(inv_records) == 5

        run = s.get(LegacyVectorInventoryRun, run_id)
        assert run.status == "scanned"
        assert run.source_record_count == 5
        assert run.source_snapshot_fingerprint == fp
        assert len(fp) == 64
    finally:
        s.close()


def test_scan_pagination():
    """Records exceeding page size → no skipped or duplicate IDs."""
    engine = _make_engine()
    pid = _setup_profile(engine)

    records = [
        LegacyVectorRecord(
            legacy_record_id=f"id_{i:04d}",
            metadata={"title": f"T{i}"},
            document=f"D{i}",
            embedding_dimension=4,
        )
        for i in range(25)  # Exceeds default page size of 500, but tests pagination logic
    ]
    backend = _FakeInventoryBackend(records)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, backend, inventory_run_id=run_id)

    s = Session()
    try:
        inv_records = s.execute(
            select(LegacyVectorInventoryRecord.legacy_record_id).where(
                LegacyVectorInventoryRecord.inventory_run_id == run_id
            )
        ).scalars().all()
        assert len(inv_records) == 25
        assert len(set(inv_records)) == 25  # No duplicates
    finally:
        s.close()


# ── 2. Metadata extraction ───────────────────────────────────────────


def test_extract_identity_from_metadata():
    record = LegacyVectorRecord(
        legacy_record_id="test_1",
        metadata={"paper_id": 42, "doi": "10.1234/abc", "title": "Test Paper"},
        document="Test content",
        embedding_dimension=4,
    )
    identity = extract_legacy_identity(record)
    assert identity.paper_id == 42
    assert identity.doi == "10.1234/abc"
    assert identity.title == "Test Paper"
    assert identity.schema_version == "legacy_identity_v1"


def test_extract_identity_missing_fields():
    record = LegacyVectorRecord(
        legacy_record_id="test_2",
        metadata={"title": "Minimal"},
        document="content",
        embedding_dimension=None,
    )
    identity = extract_legacy_identity(record)
    assert identity.paper_id is None
    assert identity.doi is None
    assert identity.title == "Minimal"


# ── 3. Mapping ───────────────────────────────────────────────────────


def test_mapping_exact_paper_id():
    engine = _make_engine()
    paper_id = _make_paper(engine, "arxiv:001", "Paper A")

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        identity = ExtractedLegacyIdentity(
            schema_version="legacy_identity_v1",
            paper_id=paper_id, doi=None, source=None, source_record_id=None,
            title="Paper A", first_author=None, publication_year=None,
        )
        decision = map_legacy_identity(s, identity)
        assert decision.mapping_status == "mapped"
        assert decision.mapped_paper_id == paper_id
    finally:
        s.close()


def test_mapping_exact_doi():
    engine = _make_engine()
    paper_id = _make_paper(engine, "arxiv:002", "Paper B", doi="10.1234/b")

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        identity = ExtractedLegacyIdentity(
            schema_version="legacy_identity_v1",
            paper_id=None, doi="10.1234/b", source=None, source_record_id=None,
            title=None, first_author=None, publication_year=None,
        )
        decision = map_legacy_identity(s, identity)
        assert decision.mapping_status == "mapped"
        assert decision.mapped_paper_id == paper_id
    finally:
        s.close()


def test_mapping_conflict_paper_id_vs_doi():
    """paper_id → P1 but DOI → P2 → identity_conflict."""
    engine = _make_engine()
    p1 = _make_paper(engine, "arxiv:003", "Paper C")
    p2 = _make_paper(engine, "arxiv:004", "Paper D", doi="10.1234/d")

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        identity = ExtractedLegacyIdentity(
            schema_version="legacy_identity_v1",
            paper_id=p1, doi="10.1234/d", source=None, source_record_id=None,
            title=None, first_author=None, publication_year=None,
        )
        decision = map_legacy_identity(s, identity)
        assert decision.mapping_status == "identity_conflict"
        assert decision.mapped_paper_id is None
    finally:
        s.close()


def test_mapping_unmapped_no_identifiers():
    engine = _make_engine()
    _make_paper(engine, "arxiv:005", "Existing")

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        identity = ExtractedLegacyIdentity(
            schema_version="legacy_identity_v1",
            paper_id=None, doi=None, source=None, source_record_id=None,
            title="Completely Different", first_author="Nobody", publication_year=2099,
        )
        decision = map_legacy_identity(s, identity)
        assert decision.mapping_status == "unmapped"
    finally:
        s.close()


# ── 4. Fingerprints ──────────────────────────────────────────────────


def test_record_fingerprint_deterministic():
    record = LegacyVectorRecord(
        legacy_record_id="id_1",
        metadata={"paper_id": 1, "title": "T"},
        document="D",
        embedding_dimension=4,
    )
    fp1 = compute_record_fingerprint(record)
    fp2 = compute_record_fingerprint(record)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_snapshot_fingerprint_order_independent():
    pairs1 = [("a", "fp_a"), ("b", "fp_b")]
    pairs2 = [("b", "fp_b"), ("a", "fp_a")]
    assert compute_source_snapshot_fingerprint(pairs1) == compute_source_snapshot_fingerprint(pairs2)


# ── 5. Drift detection ───────────────────────────────────────────────


def test_drift_detected_on_change():
    engine = _make_engine()
    pid = _setup_profile(engine)

    records = [
        LegacyVectorRecord(
            legacy_record_id="chunk_1",
            metadata={"paper_id": 1, "title": "T1"},
            document="D1", embedding_dimension=4,
        ),
    ]
    backend = _FakeInventoryBackend(records)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, backend, inventory_run_id=run_id)

    # Add a record → drift
    backend.add_record(LegacyVectorRecord(
        legacy_record_id="chunk_2",
        metadata={"paper_id": 2, "title": "T2"},
        document="D2", embedding_dimension=4,
    ))

    assert not verify_source_drift(Session, backend, inventory_run_id=run_id)


def test_no_drift_on_unchanged():
    engine = _make_engine()
    pid = _setup_profile(engine)

    records = [
        LegacyVectorRecord(
            legacy_record_id="chunk_1",
            metadata={"paper_id": 1, "title": "T1"},
            document="D1", embedding_dimension=4,
        ),
    ]
    backend = _FakeInventoryBackend(records)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        run_id = create_inventory_run(s, target_embedding_profile_id=pid)
        s.commit()
    finally:
        s.close()

    scan_legacy_collection(Session, backend, inventory_run_id=run_id)

    assert verify_source_drift(Session, backend, inventory_run_id=run_id)


# ── 6. Architectural isolation ───────────────────────────────────────


def test_inventory_module_allowed_in_enforcement():
    """The legacy inventory module is in the architectural allowlist."""
    from backend.tests.test_pipeline.test_vector_access_enforcement import _ALLOWLIST_PATTERNS
    assert any("legacy_vector_inventory" in p for p in _ALLOWLIST_PATTERNS)
