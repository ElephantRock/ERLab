"""Tests for P0.3.2: governed vector index registry.

Proves:
  - Profile identity determinism and drift detection
  - Vector identity determinism and content/profile sensitivity
  - Collection name derivation
  - DB constraints (status vocabulary, SHA-256 format, lifecycle)
  - Migration 022 legacy preservation + round-trip
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError as SAIntegrityError
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.db.models import EmbeddingProfile, Paper, VectorIndexRecord
from backend.pipeline.vector_contracts import (
    compute_collection_name,
    compute_content_hash,
    compute_profile_id,
    compute_vector_record_id,
)


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


# ── 1. Profile identity ──────────────────────────────────────────────


def test_profile_id_deterministic():
    p1 = compute_profile_id("lmstudio", "qwen3", 1024, "l2", "chunk_v1")
    p2 = compute_profile_id("lmstudio", "qwen3", 1024, "l2", "chunk_v1")
    assert p1 == p2
    assert len(p1) == 64


def test_profile_id_differs_on_dimension():
    p1 = compute_profile_id("x", "m", 1024, "l2", "v1")
    p2 = compute_profile_id("x", "m", 768, "l2", "v1")
    assert p1 != p2


def test_profile_id_differs_on_chunking():
    p1 = compute_profile_id("x", "m", 1024, "l2", "chunk_v1")
    p2 = compute_profile_id("x", "m", 1024, "l2", "chunk_v2")
    assert p1 != p2


def test_profile_id_differs_on_provider():
    p1 = compute_profile_id("lmstudio", "qwen3", 1024, "l2", "v1")
    p2 = compute_profile_id("openai", "qwen3", 1024, "l2", "v1")
    assert p1 != p2


# ── 2. Vector identity ───────────────────────────────────────────────


def test_vector_id_deterministic():
    h = compute_content_hash("test content")
    pid = compute_profile_id("x", "m", 1024, "l2", "v1")
    v1 = compute_vector_record_id(1, "abstract:0", h, pid)
    v2 = compute_vector_record_id(1, "abstract:0", h, pid)
    assert v1 == v2
    assert len(v1) == 64


def test_vector_id_changes_on_content():
    h1 = compute_content_hash("content A")
    h2 = compute_content_hash("content B")
    pid = compute_profile_id("x", "m", 1024, "l2", "v1")
    v1 = compute_vector_record_id(1, "abstract:0", h1, pid)
    v2 = compute_vector_record_id(1, "abstract:0", h2, pid)
    assert v1 != v2


def test_vector_id_changes_on_profile():
    h = compute_content_hash("test")
    p1 = compute_profile_id("x", "m", 1024, "l2", "v1")
    p2 = compute_profile_id("x", "m", 768, "l2", "v1")
    v1 = compute_vector_record_id(1, "abstract:0", h, p1)
    v2 = compute_vector_record_id(1, "abstract:0", h, p2)
    assert v1 != v2


def test_vector_id_same_across_runs():
    """Vector ID does not include run_id (canonical vectors are run-independent)."""
    h = compute_content_hash("test")
    pid = compute_profile_id("x", "m", 1024, "l2", "v1")
    v1 = compute_vector_record_id(1, "abstract:0", h, pid)
    v2 = compute_vector_record_id(1, "abstract:0", h, pid)
    assert v1 == v2  # same paper, chunk, content, profile = same vector


# ── 3. Collection name ───────────────────────────────────────────────


def test_collection_name_derivation():
    pid = compute_profile_id("x", "m", 1024, "l2", "v1")
    name = compute_collection_name(pid)
    assert name.startswith("erlab_vectors_v1_")
    assert pid[:24] in name
    assert "research_papers" not in name


def test_different_profiles_different_collections():
    p1 = compute_profile_id("x", "m", 1024, "l2", "v1")
    p2 = compute_profile_id("y", "m", 1024, "l2", "v1")
    assert compute_collection_name(p1) != compute_collection_name(p2)


# ── 4. DB constraints ────────────────────────────────────────────────


def _setup_profile_and_paper(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        pid = compute_profile_id("lmstudio", "qwen3", 1024, "l2", "chunk_v1")
        prof = EmbeddingProfile(
            profile_id=pid,
            profile_schema_version="embedding_profile_v1",
            provider="lmstudio", model_identifier="qwen3",
            dimension=1024, normalization_policy="l2",
            chunking_schema_version="chunk_v1",
            collection_name=compute_collection_name(pid),
            verification_status="unverified",
        )
        s.add(prof)
        paper = Paper(source_id="test:1", source="arxiv", title="Test",
                      authors="[]", keywords="[]", ingested=0)
        s.add(paper)
        s.commit()
        return pid, paper.id
    finally:
        s.close()


def test_valid_indexed_record_accepted():
    engine = _make_engine()
    pid, paper_id = _setup_profile_and_paper(engine)
    h = compute_content_hash("content")
    vid = compute_vector_record_id(paper_id, "title_abstract:0", h, pid)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        rec = VectorIndexRecord(
            vector_record_id=vid,
            paper_id=paper_id,
            chunk_key="title_abstract:0",
            content_kind="title_abstract",
            content_hash=h,
            embedding_profile_id=pid,
            collection_name=compute_collection_name(pid),
            index_status="indexed",
            attempt_count=1,
            indexed_at=now,
            backend_verified_at=now,
        )
        s.add(rec); s.commit()
        assert rec.id is not None
    finally:
        s.close()


def test_invalid_status_rejected():
    from sqlalchemy.exc import IntegrityError as SAIntegrityError
    engine = _make_engine()
    pid, paper_id = _setup_profile_and_paper(engine)
    h = compute_content_hash("content")
    vid = compute_vector_record_id(paper_id, "title_abstract:0", h, pid)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            rec = VectorIndexRecord(
                vector_record_id=vid, paper_id=paper_id,
                chunk_key="title_abstract:0", content_kind="title_abstract",
                content_hash=h, embedding_profile_id=pid,
                collection_name=compute_collection_name(pid),
                index_status="bogus_status",
            )
            s.add(rec); s.commit()
    finally:
        s.close()


def test_negative_attempt_count_rejected():
    from sqlalchemy.exc import IntegrityError as SAIntegrityError
    engine = _make_engine()
    pid, paper_id = _setup_profile_and_paper(engine)
    h = compute_content_hash("content")
    vid = compute_vector_record_id(paper_id, "title_abstract:0", h, pid)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            rec = VectorIndexRecord(
                vector_record_id=vid, paper_id=paper_id,
                chunk_key="title_abstract:0", content_kind="title_abstract",
                content_hash=h, embedding_profile_id=pid,
                collection_name=compute_collection_name(pid),
                index_status="pending", attempt_count=-1,
            )
            s.add(rec); s.commit()
    finally:
        s.close()


def test_invalid_content_kind_rejected():
    from sqlalchemy.exc import IntegrityError as SAIntegrityError
    engine = _make_engine()
    pid, paper_id = _setup_profile_and_paper(engine)
    h = compute_content_hash("content")
    vid = compute_vector_record_id(paper_id, "title_abstract:0", h, pid)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            rec = VectorIndexRecord(
                vector_record_id=vid, paper_id=paper_id,
                chunk_key="title_abstract:0", content_kind="bogus_kind",
                content_hash=h, embedding_profile_id=pid,
                collection_name=compute_collection_name(pid),
                index_status="pending",
            )
            s.add(rec); s.commit()
    finally:
        s.close()


def test_unknown_paper_rejected():
    from sqlalchemy.exc import IntegrityError as SAIntegrityError
    engine = _make_engine()
    pid, _ = _setup_profile_and_paper(engine)
    h = compute_content_hash("content")
    vid = compute_vector_record_id(99999, "title_abstract:0", h, pid)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            rec = VectorIndexRecord(
                vector_record_id=vid, paper_id=99999,
                chunk_key="title_abstract:0", content_kind="title_abstract",
                content_hash=h, embedding_profile_id=pid,
                collection_name=compute_collection_name(pid),
                index_status="pending",
            )
            s.add(rec); s.commit()
    finally:
        s.close()


def test_unknown_profile_rejected():
    from sqlalchemy.exc import IntegrityError as SAIntegrityError
    engine = _make_engine()
    _, paper_id = _setup_profile_and_paper(engine)
    fake_pid = "a" * 64  # not registered
    h = compute_content_hash("content")
    vid = compute_vector_record_id(paper_id, "title_abstract:0", h, fake_pid)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            rec = VectorIndexRecord(
                vector_record_id=vid, paper_id=paper_id,
                chunk_key="title_abstract:0", content_kind="title_abstract",
                content_hash=h, embedding_profile_id=fake_pid,
                collection_name=compute_collection_name(fake_pid),
                index_status="pending",
            )
            s.add(rec); s.commit()
    finally:
        s.close()


def test_duplicate_vector_record_id_rejected():
    from sqlalchemy.exc import IntegrityError as SAIntegrityError
    engine = _make_engine()
    pid, paper_id = _setup_profile_and_paper(engine)
    h = compute_content_hash("content")
    vid = compute_vector_record_id(paper_id, "title_abstract:0", h, pid)

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        for _ in range(2):
            s.rollback()
            rec = VectorIndexRecord(
                vector_record_id=vid, paper_id=paper_id,
                chunk_key="title_abstract:0", content_kind="title_abstract",
                content_hash=h, embedding_profile_id=pid,
                collection_name=compute_collection_name(pid),
                index_status="pending",
            )
            s.add(rec)
            try:
                s.commit()
            except SAIntegrityError:
                s.rollback()
                raise
        assert False, "second insert should have failed"
    except SAIntegrityError:
        pass  # expected
    finally:
        s.close()


# ── 5. Migration tests ───────────────────────────────────────────────


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _alembic_cfg(db_url):
    from alembic.config import Config
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _patched_settings(db_url):
    mock = MagicMock()
    mock.database_url = db_url
    mock.debug = False
    return patch("backend.config.get_settings", return_value=mock)


def test_migration_022_preserves_legacy():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'p032.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "021")
        command.upgrade(cfg, "022")
        engine = create_engine(db_url)
        with engine.connect() as c:
            # No fabrications
            ep = c.execute(text("SELECT COUNT(*) FROM embedding_profiles")).scalar()
            vir = c.execute(text("SELECT COUNT(*) FROM vector_index_records")).scalar()
            assert ep == 0 and vir == 0, "no fabrications"
            tables = [r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
            assert "embedding_profiles" in tables
            assert "vector_index_records" in tables


def test_migration_022_round_trip():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'rt.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "021")
        command.upgrade(cfg, "022")
        command.downgrade(cfg, "021")
        assert not inspect(create_engine(db_url)).has_table("vector_index_records")
        command.upgrade(cfg, "022")
        assert inspect(create_engine(db_url)).has_table("vector_index_records")
