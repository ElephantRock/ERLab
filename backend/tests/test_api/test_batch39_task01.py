"""Tests for BATCH-39 TASK-01: Gap API Search, Filter & Sort.

TEST-39-01-01 through TEST-39-01-08
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError
from backend.api.routes.gaps import router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import Idea, PipelineRun, ResearchGapDB


# ── Test app setup ──────────────────────────────────────────────


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router, prefix="/gaps")
    return app


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def seeded_session(db_session):
    """Seed the test database with a pipeline run and several gaps."""
    run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
    crud.create_gap(
        db_session,
        title="Transfer learning in cross-domain NLP",
        description="Limited methods for cross-domain transfer",
        gap_type="methodological",
        confidence=0.9,
        potential_impact="high",
        pipeline_run_id=run.id,
        truth_frequency=0.8,
        truth_confidence=0.7,
        truth_evidence_count=3,
        related_clusters='[1, 2]',
    )
    crud.create_gap(
        db_session,
        title="Empirical evaluation of transformer scaling",
        description="No empirical studies on scaling laws for small models",
        gap_type="empirical",
        confidence=0.6,
        potential_impact="medium",
        pipeline_run_id=run.id,
        truth_frequency=0.5,
        truth_confidence=0.5,
        truth_evidence_count=0,
        related_clusters=None,
    )
    crud.create_gap(
        db_session,
        title="Theoretical foundations of attention",
        description="Mathematical analysis missing for multi-head attention",
        gap_type="theoretical",
        confidence=0.75,
        potential_impact="high",
        pipeline_run_id=run.id,
        truth_frequency=0.6,
        truth_confidence=0.65,
        truth_evidence_count=1,
        related_clusters='[5]',
    )
    crud.create_gap(
        db_session,
        title="Cross-domain few-shot learning",
        description="Bridging domain gap with few examples",
        gap_type="cross-domain",
        confidence=0.5,
        potential_impact="low",
        pipeline_run_id=run.id,
    )
    return db_session, run


# ── TEST-39-01-01: search='transfer' returns only matching gaps ──


def test_39_01_01_search_filter(seeded_session):
    """search='transfer' returns only gaps whose title/description contain 'transfer'."""
    session, run = seeded_session
    results = crud.search_gaps(session, run_id=run.id, search="transfer")
    assert len(results) == 1
    assert "transfer" in results[0].title.lower()
    assert results[0].gap_type == "methodological"


# ── TEST-39-01-02: gap_type='methodological' filters correctly ──


def test_39_01_02_gap_type_filter(seeded_session):
    """gap_type='methodological' returns only methodological gaps."""
    session, run = seeded_session
    results = crud.search_gaps(session, run_id=run.id, gap_type="methodological")
    assert len(results) == 1
    assert results[0].gap_type == "methodological"


# ── TEST-39-01-03: min_confidence=0.7 excludes low-confidence gaps ──


def test_39_01_03_min_confidence_filter(seeded_session):
    """min_confidence=0.7 returns only gaps with confidence >= 0.7."""
    session, run = seeded_session
    results = crud.search_gaps(session, run_id=run.id, min_confidence=0.7)
    assert all(g.confidence >= 0.7 for g in results)
    # Should include the 0.9 and 0.75 confidence gaps
    assert len(results) == 2


# ── TEST-39-01-04: sort_by='confidence' returns descending order ──


def test_39_01_04_sort_by_confidence(seeded_session):
    """sort_by='confidence' with default desc order returns highest first."""
    session, run = seeded_session
    results = crud.search_gaps(session, run_id=run.id, sort_by="confidence", sort_order="desc")
    assert len(results) == 4
    confidences = [g.confidence for g in results]
    assert confidences == sorted(confidences, reverse=True)


# ── TEST-39-01-05: sort_by='date' returns newest first ──────────


def test_39_01_05_sort_by_date(seeded_session):
    """sort_by='date' with default desc returns newest first."""
    session, run = seeded_session
    results = crud.search_gaps(session, run_id=run.id, sort_by="date", sort_order="desc")
    assert len(results) == 4
    # Items were created sequentially, so the last-created should be first
    dates = [g.created_at for g in results]
    assert dates == sorted(dates, reverse=True)


# ── TEST-39-01-06: Response includes truth and related_clusters ──


def test_39_01_06_truth_and_related_clusters():
    """Integration: GET /gaps/ response includes truth and related_clusters fields."""
    mock_gap = ResearchGapDB(
        id=1,
        title="Test gap",
        description="A test gap",
        gap_type="methodological",
        confidence=0.9,
        potential_impact="high",
        pipeline_run_id=1,
        truth_frequency=0.8,
        truth_confidence=0.7,
        truth_evidence_count=3,
        related_clusters='[1, 2]',
    )

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.count_search_gaps", return_value=1), \
         patch("backend.db.crud.search_gaps", return_value=[mock_gap]), \
         patch("backend.db.crud.count_ideas_for_gap", return_value=0):
        client = TestClient(_make_app())
        resp = client.get("/gaps/", params={"run_id": 1})

    assert resp.status_code == 200, f"Unexpected: {resp.status_code} body={resp.text}"
    body = resp.json()
    assert len(body["gaps"]) == 1

    # Check truth and related_clusters fields
    gap = body["gaps"][0]
    assert "truth" in gap
    assert gap["truth"]["frequency"] == 0.8
    assert gap["truth"]["confidence"] == 0.7
    assert gap["truth"]["evidence_count"] == 3
    assert gap["related_clusters"] == [1, 2]


# ── TEST-39-01-07: SQL injection treated as literal string (HB-02) ──


def test_39_01_07_sql_injection_literal(seeded_session):
    """SQL injection attempt is treated as a literal search string (HB-02)."""
    session, run = seeded_session
    results = crud.search_gaps(session, run_id=run.id, search="'; DROP TABLE research_gaps; --")
    # No results — the injection string is treated as a literal search
    assert len(results) == 0
    # Verify the table still exists and has data
    total = crud.count_gaps_by_run(session, run.id)
    assert total == 4


# ── TEST-39-01-08: Default params reproduce current behavior (HB-01) ──


def test_39_01_08_default_params_backward_compat(seeded_session):
    """Default params produce same results as the original list_gaps_by_run (HB-01)."""
    session, run = seeded_session

    # Original behavior: all gaps for run, sorted by confidence desc
    original = crud.list_gaps_by_run(session, run.id)
    # New behavior with defaults
    new = crud.search_gaps(session, run_id=run.id)

    assert len(new) == len(original)
    # Both sorted by confidence desc
    for o, n in zip(original, new):
        assert o.id == n.id
        assert o.confidence == n.confidence
