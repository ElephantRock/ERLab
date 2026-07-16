"""Tests for P0.3.3: vector retrieval audit schema and constraints.

Proves:
  - Migration 023 preserves existing rows (no fabrications)
  - DB constraints: status vocabulary, coverage equation, composite FK
  - Results cannot reference vectors outside the eligible snapshot
  - Migration round-trip stable
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
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
from backend.db.models import (
    EmbeddingProfile,
    Paper,
    PipelineRun,
    RunSearchReconciliation,
    VectorIndexRecord,
    VectorRetrievalEligibleRecord,
    VectorRetrievalEvent,
    VectorRetrievalResult,
    VectorRetrievalScopePaper,
)
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


_run_counter = [0]


def _setup_full(engine):
    """Create a complete governed setup: run, profile, paper, indexed vector."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        _run_counter[0] += 1
        run = PipelineRun(
            run_id_str=f"r_p033_{_run_counter[0]}", domain="AI",
            status="completed", config_json="{}", stages_completed="[]",
            provenance_version="provenance_v1",
        )
        s.add(run); s.flush()

        s.add(RunSearchReconciliation(
            run_id=run.id, reconciliation_schema_version="run_reconciliation_v1",
            status="pending", reconciliation_attempt_count=0,
        ))

        pid = compute_profile_id("lmstudio", "qwen3", 4, "l2", "v1")
        s.add(EmbeddingProfile(
            profile_id=pid, profile_schema_version="embedding_profile_v1",
            provider="lmstudio", model_identifier="qwen3", dimension=4,
            normalization_policy="l2", chunking_schema_version="v1",
            collection_name=compute_collection_name(pid),
            verification_status="unverified",
        ))

        paper = Paper(source_id="test:1", source="arxiv", title="Test",
                      authors="[]", keywords="[]", ingested=0)
        s.add(paper); s.flush()

        ch = compute_content_hash("content")
        vid = compute_vector_record_id(paper.id, "title_abstract:0", ch, pid)
        now = datetime.now(timezone.utc)
        s.add(VectorIndexRecord(
            vector_record_id=vid, paper_id=paper.id, chunk_key="title_abstract:0",
            content_kind="title_abstract", content_hash=ch, embedding_profile_id=pid,
            collection_name=compute_collection_name(pid),
            index_status="indexed", attempt_count=1,
            indexed_at=now, backend_verified_at=now,
        ))
        s.commit()
        return run.id, pid, paper.id, vid
    finally:
        s.close()


# ── 1. DB constraint tests ───────────────────────────────────────────


def test_invalid_status_rejected():
    engine = _make_engine()
    run_id, pid, _, _ = _setup_full(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO vector_retrieval_events "
                "(run_id, stage_name, retrieval_key, request_schema_version, "
                " scope_mode, scope_schema_version, scope_fingerprint, "
                " embedding_profile_id, profile_verification_status_snapshot, "
                " query_vector_fingerprint, input_fingerprint, "
                " requested_top_k, allowed_paper_count, indexed_paper_count, "
                " unindexed_paper_count, eligible_vector_record_count, coverage_status, status) "
                "VALUES (:rid, 'test', 'rk', 'v1', 'current_run_only', 'vs1', 'fp', "
                " :pid, 'unverified', 'qfp', 'ifp', 5, 1, 1, 0, 1, 'complete', 'bogus')"
            ), {"rid": run_id, "pid": pid})
            s.commit()
    finally:
        s.close()


def test_coverage_equation_enforced():
    engine = _make_engine()
    run_id, pid, _, _ = _setup_full(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        # unindexed != allowed - indexed → should fail
        with pytest.raises(SAIntegrityError):
            s.execute(text(
                "INSERT INTO vector_retrieval_events "
                "(run_id, stage_name, retrieval_key, request_schema_version, "
                " scope_mode, scope_schema_version, scope_fingerprint, "
                " embedding_profile_id, profile_verification_status_snapshot, "
                " query_vector_fingerprint, input_fingerprint, "
                " requested_top_k, allowed_paper_count, indexed_paper_count, "
                " unindexed_paper_count, eligible_vector_record_count, coverage_status, status) "
                "VALUES (:rid, 'test', 'rk', 'v1', 'current_run_only', 'vs1', 'fp', "
                " :pid, 'unverified', 'qfp', 'ifp', 5, 10, 8, 1, 8, 'partial', 'pending')"
            ), {"rid": run_id, "pid": pid})
            s.commit()
    finally:
        s.close()


def _make_event(s, run_id, pid):
    """Create a valid retrieval event via ORM. Returns event_id."""
    event = VectorRetrievalEvent(
        run_id=run_id, stage_name="test", retrieval_key="rk",
        request_schema_version="v1",
        scope_mode="current_run_only", scope_schema_version="vs1",
        scope_fingerprint="fp",
        embedding_profile_id=pid,
        profile_verification_status_snapshot="unverified",
        query_vector_fingerprint="qfp",
        input_fingerprint="ifp",
        requested_top_k=5,
        allow_partial_index_coverage=False,
        allowed_paper_count=1, indexed_paper_count=1,
        unindexed_paper_count=0, eligible_vector_record_count=1,
        coverage_status="complete", status="success",
        returned_result_count=0,
        completed_at=datetime.now(timezone.utc),
    )
    s.add(event); s.flush()
    return event.id


def test_composite_fk_result_must_be_in_eligible():
    """Result referencing a vector NOT in the eligible snapshot is rejected."""
    engine = _make_engine()
    run_id, pid, paper_id, vid = _setup_full(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        event_id = _make_event(s, run_id, pid)
        s.add(VectorRetrievalEligibleRecord(
            retrieval_event_id=event_id, vector_record_id=vid,
        ))
        s.commit()

        with pytest.raises(SAIntegrityError):
            s.add(VectorRetrievalResult(
                retrieval_event_id=event_id, rank=1,
                vector_record_id="nonexistent_vector_id",
                canonical_distance=0.5,
            ))
            s.commit()
    finally:
        s.close()


def test_result_in_eligible_accepted():
    """Result referencing a vector IN the eligible snapshot is accepted."""
    engine = _make_engine()
    run_id, pid, paper_id, vid = _setup_full(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        event_id = _make_event(s, run_id, pid)
        s.add(VectorRetrievalEligibleRecord(
            retrieval_event_id=event_id, vector_record_id=vid,
        ))
        s.commit()

        s.add(VectorRetrievalResult(
            retrieval_event_id=event_id, rank=1,
            vector_record_id=vid, canonical_distance=0.1,
        ))
        s.commit()
        assert True
    finally:
        s.close()


def test_duplicate_rank_rejected():
    engine = _make_engine()
    run_id, pid, paper_id, vid = _setup_full(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        event_id = _make_event(s, run_id, pid)
        s.add(VectorRetrievalEligibleRecord(
            retrieval_event_id=event_id, vector_record_id=vid,
        ))
        s.commit()

        s.add(VectorRetrievalResult(
            retrieval_event_id=event_id, rank=1,
            vector_record_id=vid, canonical_distance=0.1,
        ))
        s.commit()

        with pytest.raises(SAIntegrityError):
            s.add(VectorRetrievalResult(
                retrieval_event_id=event_id, rank=1,
                vector_record_id=vid, canonical_distance=0.2,
            ))
            s.commit()
    finally:
        s.close()


def test_duplicate_vector_in_results_rejected():
    engine = _make_engine()
    run_id, pid, paper_id, vid = _setup_full(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        event_id = _make_event(s, run_id, pid)
        s.add(VectorRetrievalEligibleRecord(
            retrieval_event_id=event_id, vector_record_id=vid,
        ))
        s.commit()

        s.add(VectorRetrievalResult(
            retrieval_event_id=event_id, rank=1,
            vector_record_id=vid, canonical_distance=0.1,
        ))
        s.commit()

        with pytest.raises(SAIntegrityError):
            s.add(VectorRetrievalResult(
                retrieval_event_id=event_id, rank=2,
                vector_record_id=vid, canonical_distance=0.2,
            ))
            s.commit()
    finally:
        s.close()


# ── 2. Migration tests ───────────────────────────────────────────────


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


def test_migration_023_preserves_legacy():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'p033.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "022")
        command.upgrade(cfg, "023")
        engine = create_engine(db_url)
        with engine.connect() as c:
            count = c.execute(text("SELECT COUNT(*) FROM vector_retrieval_events")).scalar()
            assert count == 0, "no fabrications"


def test_migration_023_round_trip():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'rt.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "022")
        command.upgrade(cfg, "023")
        command.downgrade(cfg, "022")
        assert not inspect(create_engine(db_url)).has_table("vector_retrieval_events")
        command.upgrade(cfg, "023")
        assert inspect(create_engine(db_url)).has_table("vector_retrieval_events")
