"""Citation-integrity regression proof: admission score persistence.

persist_search_results must write the computed relevance score into
``RunPaper.relevance_score`` for BOTH admitted and below-threshold excluded
candidates, and record an explicit exclusion reason for candidates whose
relevance scoring failed — so the admission decision is durably auditable.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base
from backend.db.models import Paper as DbPaper
from backend.db.models import PipelineRun, RunPaper
from backend.pipeline.literature.models import Author
from backend.pipeline.literature.models import Paper as SearchPaper
from backend.pipeline.persistence import (
    CandidateWithDiscoveries,
    DiscoveryMetadata,
    PipelinePersistence,
    SearchQueryData,
    compute_query_key,
)


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def _make_candidate(source_id: str, title: str) -> CandidateWithDiscoveries:
    paper = SearchPaper(
        id=source_id,
        source="openalex",
        title=title,
        abstract="Test abstract",
        authors=[Author(name="Test Author")],
        year=2024,
        venue="ACL",
    )
    disc = DiscoveryMetadata(
        query_key=compute_query_key("q", "template", "base", 0),
        source="openalex",
        source_record_id=f"W-{source_id}",
        source_rank=0,
    )
    return CandidateWithDiscoveries(paper=paper, discoveries=[disc])


def test_persists_scores_for_admitted_and_excluded(monkeypatch):
    engine = _make_engine()
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def patched_get_session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    from backend.db import database as db_module

    monkeypatch.setattr(db_module, "get_session", patched_get_session)

    setup = factory()
    run = PipelineRun(
        run_id_str="run_scores_1",
        domain="test",
        status="running",
        provenance_version="provenance_v1",
    )
    setup.add(run)
    setup.commit()
    run_id = run.id
    setup.close()

    candidates = [
        _make_candidate("admitted:1", "On-domain paper"),
        _make_candidate("excluded:1", "Off-domain paper"),
        _make_candidate("failed:1", "Unscorable paper"),
    ]
    query = SearchQueryData(
        "q", "template", "base", 0, compute_query_key("q", "template", "base", 0)
    )
    persistence = PipelinePersistence()
    persistence.persist_search_results(
        candidates,
        [query],
        run_id,
        admitted_source_ids={"admitted:1"},
        relevance_scores={"admitted:1": 0.87, "excluded:1": 0.12},
        admission_exclusions={"failed:1": "embedding vector malformed"},
    )

    verify = factory()
    rows = {
        rp_id: (sel, score, reason)
        for rp_id, sel, score, reason in verify.execute(
            select(
                DbPaper.source_id,
                RunPaper.selected_for_downstream,
                RunPaper.relevance_score,
                RunPaper.exclusion_reason,
            )
            .join(RunPaper, RunPaper.paper_id == DbPaper.id)
            .where(RunPaper.run_id == run_id)
        ).all()
    }

    assert rows["admitted:1"] == (True, pytest.approx(0.87), None)
    assert rows["excluded:1"] == (False, pytest.approx(0.12), "below_threshold")
    assert rows["failed:1"][0] is False
    assert rows["failed:1"][1] is None  # never a fabricated 0.0
    assert rows["failed:1"][2] == "embedding vector malformed"
    verify.close()


def test_replay_fully_reconciles_existing_rows(monkeypatch):
    """Re-persist over existing RunPaper rows must clear stale admission state.

    Regression for the review blocker: the update path previously only
    promoted rows to admitted and never demoted them, and left prior
    scores/reasons in place when the current decision had none.
    """
    engine = _make_engine()
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def patched_get_session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    from backend.db import database as db_module

    monkeypatch.setattr(db_module, "get_session", patched_get_session)

    setup = factory()
    run = PipelineRun(
        run_id_str="run_scores_3",
        domain="test",
        status="running",
        provenance_version="provenance_v1",
    )
    setup.add(run)
    setup.commit()
    run_id = run.id
    setup.close()

    candidates = [
        _make_candidate("flips:1", "Was admitted now excluded"),
        _make_candidate("fails:1", "Was scored now unscorable"),
    ]
    query = SearchQueryData(
        "q", "template", "base", 0, compute_query_key("q", "template", "base", 0)
    )
    persistence = PipelinePersistence()

    # First pass: both admitted with scores.
    persistence.persist_search_results(
        candidates,
        [query],
        run_id,
        admitted_source_ids={"flips:1", "fails:1"},
        relevance_scores={"flips:1": 0.9, "fails:1": 0.8},
    )

    # Replay with a different decision: flips:1 excluded-but-scored,
    # fails:1 unscorable (no score, explicit failure reason).
    persistence.persist_search_results(
        candidates,
        [query],
        run_id,
        admitted_source_ids=set(),
        relevance_scores={"flips:1": 0.05},
        admission_exclusions={"fails:1": "paper embedding dimension mismatch"},
    )

    verify = factory()
    rows = {
        sid: (sel, stage, score, reason)
        for sid, sel, stage, score, reason in verify.execute(
            select(
                DbPaper.source_id,
                RunPaper.selected_for_downstream,
                RunPaper.selection_stage,
                RunPaper.relevance_score,
                RunPaper.exclusion_reason,
            )
            .join(RunPaper, RunPaper.paper_id == DbPaper.id)
            .where(RunPaper.run_id == run_id)
        ).all()
    }

    assert rows["flips:1"] == (False, None, pytest.approx(0.05), "below_threshold")
    assert rows["fails:1"] == (False, None, None, "paper embedding dimension mismatch")
    verify.close()


def test_scoring_failure_rows_without_scores_are_marked(monkeypatch):
    """Without any valid scores, excluded rows still carry explicit reasons."""
    engine = _make_engine()
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def patched_get_session():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    from backend.db import database as db_module

    monkeypatch.setattr(db_module, "get_session", patched_get_session)

    setup = factory()
    run = PipelineRun(
        run_id_str="run_scores_2",
        domain="test",
        status="running",
        provenance_version="provenance_v1",
    )
    setup.add(run)
    setup.commit()
    run_id = run.id
    setup.close()

    candidates = [_make_candidate("only:1", "Some paper")]
    query = SearchQueryData(
        "q", "template", "base", 0, compute_query_key("q", "template", "base", 0)
    )
    persistence = PipelinePersistence()
    persistence.persist_search_results(
        candidates,
        [query],
        run_id,
        admitted_source_ids=set(),
        relevance_scores={},
        admission_exclusions={"only:1": "domain query embedding failed"},
    )

    verify = factory()
    row = verify.execute(
        select(RunPaper).where(RunPaper.run_id == run_id)
    ).scalar_one()
    assert row.selected_for_downstream is False
    assert row.relevance_score is None
    assert row.exclusion_reason == "domain query embedding failed"
    verify.close()
