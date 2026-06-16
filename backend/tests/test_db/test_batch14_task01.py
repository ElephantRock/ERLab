"""Tests for BATCH-14/TASK-01: Sort, Search, Traceability.

TEST-14-01-01 through TEST-14-01-10
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from backend.api.errors import APIError
from backend.api.routes.ideas import router as ideas_router
from backend.api.routes.gaps import router as gaps_router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import Idea, PipelineRun, ResearchGapDB


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(ideas_router, prefix="/ideas")
    app.include_router(gaps_router, prefix="/gaps")
    return app


def _seed_ideas(session):
    """Create a mix of ideas with different scores and titles."""
    ideas = []
    data = [
        ("Test-Driven Idea", "AI/NLP", 0.9, 8.0, 0.85),
        ("Novel Attention Mechanism", "AI/NLP", 0.7, 6.0, 0.65),
        ("Low Score Concept", "AI/NLP", 0.2, 2.0, 0.2),
        ("Computer Vision Breakthrough", "CV", 0.95, 9.0, 0.925),
        ("Another Test Idea", "AI/NLP", 0.5, 5.0, 0.5),
    ]
    for title, domain, nov, feas, overall in data:
        idea = crud.create_idea(
            session,
            title=title,
            problem_statement=f"Problem for {title}",
            proposed_method=f"Method for {title}",
            domain=domain,
        )
        crud.update_idea_scores(
            session,
            idea.id,
            novelty_score=nov,
            feasibility_score=feas,
        )
        ideas.append(idea)
    return ideas


# ── TEST-14-01-01: search param filters ideas by title keyword ──


def test_14_01_01_search_filters_by_title_keyword(db_session):
    """search='Test' should return only ideas with 'Test' in the title."""
    _seed_ideas(db_session)
    results = crud.list_ideas(db_session, limit=10, search="Test")
    titles = [r.title for r in results]
    assert any("Test-Driven" in t for t in titles)
    assert any("Another Test" in t for t in titles)
    # "Novel Attention Mechanism" should NOT match
    assert not any("Novel Attention" in t for t in titles)


# ── TEST-14-01-02: sort_by=score returns ideas ordered by score desc ──


def test_14_01_02_sort_by_score_desc(db_session):
    """sort_by='score' with default desc order should return highest score first."""
    _seed_ideas(db_session)
    results = crud.list_ideas(db_session, limit=10, sort_by="score", sort_order="desc")
    scores = [r.overall_score for r in results if r.overall_score is not None]
    assert scores == sorted(scores, reverse=True)


# ── TEST-14-01-03: min_score=0.7 returns only ideas ≥ 0.7 ──


def test_14_01_03_min_score_filters_correctly(db_session):
    """min_score=0.7 should only return ideas with overall_score >= 0.7."""
    _seed_ideas(db_session)
    results = crud.list_ideas(db_session, limit=10, min_score=0.7)
    for r in results:
        assert r.overall_score >= 0.7


# ── TEST-14-01-04: count_ideas_for_gap returns correct count ──


def test_14_01_04_count_ideas_for_gap(db_session):
    """count_ideas_for_gap should count ideas with matching source_gap_ids."""
    gap_title = "Cross-Domain Transfer"
    crud.create_idea(
        db_session,
        title="Idea A",
        problem_statement="P",
        proposed_method="M",
        source_gap_ids=json.dumps([gap_title, "Other Gap"]),
    )
    crud.create_idea(
        db_session,
        title="Idea B",
        problem_statement="P",
        proposed_method="M",
        source_gap_ids=json.dumps([gap_title]),
    )
    crud.create_idea(
        db_session,
        title="Idea C",
        problem_statement="P",
        proposed_method="M",
        source_gap_ids=None,
    )
    count = crud.count_ideas_for_gap(db_session, gap_title)
    assert count == 2


# ── TEST-14-01-05: GET /ideas?search=test returns matching ideas ──


def test_14_01_05_endpoint_search_returns_matching_ideas():
    """Integration: GET /ideas?search=test returns ideas matching the keyword."""
    mock_ideas = [
        Idea(
            id=1,
            title="Test Idea One",
            problem_statement="P",
            proposed_method="M",
            domain="AI/NLP",
            overall_score=0.8,
        ),
        Idea(
            id=2,
            title="Test Idea Two",
            problem_statement="P",
            proposed_method="M",
            domain="AI/NLP",
            overall_score=0.6,
        ),
    ]

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.list_ideas", return_value=mock_ideas), \
         patch("backend.db.crud.count_ideas", return_value=2):
        client = TestClient(_make_app())
        resp = client.get("/ideas/?search=test")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["ideas"]) == 2
    assert all("Test" in i["title"] for i in body["ideas"])


# ── TEST-14-01-06: GET /gaps includes idea_count field ──


def test_14_01_06_gaps_include_idea_count():
    """Integration: GET /gaps response includes idea_count per gap."""
    mock_run = PipelineRun(
        id=1,
        status="completed",
        domain="AI/NLP",
        config_json="{}",
        stages_completed="[]",
    )
    mock_gaps = [
        ResearchGapDB(
            id=1,
            title="Gap A",
            description="Desc A",
            gap_type="methodological",
            confidence=0.8,
            potential_impact="high",
            pipeline_run_id=1,
        ),
    ]

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.list_gaps_by_run", return_value=mock_gaps), \
         patch("backend.db.crud.count_gaps_by_run", return_value=1), \
         patch("backend.db.crud.search_gaps", return_value=mock_gaps), \
         patch("backend.db.crud.count_search_gaps", return_value=1), \
         patch("backend.db.crud.batch_count_ideas_for_gaps", return_value={"Gap A": 3}), \
         patch("backend.db.crud.count_ideas_for_gap", return_value=3):
        client = TestClient(_make_app())
        resp = client.get("/gaps/")

    assert resp.status_code == 200
    body = resp.json()
    assert "idea_count" in body["gaps"][0]
    assert body["gaps"][0]["idea_count"] == 3


# ── TEST-14-01-07: SQL injection treated as literal string (parameterized) ──


def test_14_01_07_sql_injection_treated_as_literal(db_session):
    """SQL injection attempt in search param is treated as literal text (HB-01)."""
    _seed_ideas(db_session)

    # This should NOT drop any tables or return unexpected results
    results = crud.list_ideas(
        db_session,
        limit=10,
        search="'; DROP TABLE ideas; --",
    )
    # Should return 0 results since no title contains that literal string
    assert len(results) == 0

    # Verify table still exists and is intact
    all_ideas = crud.list_ideas(db_session, limit=100)
    assert len(all_ideas) == 5


# ── TEST-14-01-08: sort_by accepts score/novelty/feasibility/date ──


@pytest.mark.parametrize("sort_field", ["score", "novelty", "feasibility", "date"])
def test_14_01_08_sort_by_accepts_all_fields(db_session, sort_field):
    """sort_by should accept score, novelty, feasibility, and date without error."""
    _seed_ideas(db_session)
    results = crud.list_ideas(db_session, limit=10, sort_by=sort_field)
    assert len(results) > 0


# ── TEST-14-01-09: source_gap_ids persisted on Idea model ──


def test_14_01_09_source_gap_ids_persisted(db_session):
    """source_gap_ids should be stored and retrievable as JSON Text."""
    gap_ids = ["Gap Alpha", "Gap Beta"]
    idea = crud.create_idea(
        db_session,
        title="Idea with Gaps",
        problem_statement="P",
        proposed_method="M",
        source_gap_ids=json.dumps(gap_ids),
    )
    retrieved = crud.get_idea(db_session, idea.id)
    assert retrieved.source_gap_ids is not None
    parsed = json.loads(retrieved.source_gap_ids)
    assert parsed == gap_ids


# ── TEST-14-01-10: null/empty score handled in sort (nulls last) ──


def test_14_01_10_null_score_handled_as_nulls_last(db_session):
    """When sort_by=score, ideas with null scores should appear last."""
    # Create an idea with a score
    scored = crud.create_idea(
        db_session,
        title="Scored Idea",
        problem_statement="P",
        proposed_method="M",
    )
    crud.update_idea_scores(db_session, scored.id, novelty_score=0.9, feasibility_score=9.0)

    # Create an idea without a score
    crud.create_idea(
        db_session,
        title="Unscored Idea",
        problem_statement="P",
        proposed_method="M",
    )

    results = crud.list_ideas(db_session, limit=10, sort_by="score", sort_order="desc")
    assert len(results) == 2
    # The scored idea should come first
    assert results[0].title == "Scored Idea"
    assert results[0].overall_score is not None
    # The unscored idea should be last
    assert results[-1].title == "Unscored Idea"
    assert results[-1].overall_score is None
