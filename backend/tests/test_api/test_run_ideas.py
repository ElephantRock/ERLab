"""Tests for GET /runs/{run_id}/ideas endpoint (BATCH-12/TASK-01)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.errors import APIError
from backend.api.routes.pipeline import router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import Idea, PipelineRun

# ── Test app setup ──────────────────────────────────────────────


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router)
    return app


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


# ── TEST-12-01-01: get_ideas_for_run returns correct ideas ──────


def test_12_01_01_get_ideas_for_run_returns_correct_ideas(db_session):
    """Unit: get_ideas_for_run returns ideas linked to the given run."""
    run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
    crud.create_idea(
        db_session,
        title="Idea A",
        problem_statement="Problem A",
        proposed_method="Method A",
        pipeline_run_id=run.id,
    )
    crud.create_idea(
        db_session,
        title="Idea B",
        problem_statement="Problem B",
        proposed_method="Method B",
        pipeline_run_id=run.id,
    )

    ideas = crud.get_ideas_for_run(db_session, run.id)
    assert len(ideas) == 2
    assert ideas[0].title == "Idea A"
    assert ideas[1].title == "Idea B"
    assert all(i.pipeline_run_id == run.id for i in ideas)


# ── TEST-12-01-02: get_ideas_for_run returns empty list for no ideas ──


def test_12_01_02_get_ideas_for_run_returns_empty_for_no_ideas(db_session):
    """Unit: get_ideas_for_run returns an empty list when run has no ideas."""
    run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")

    ideas = crud.get_ideas_for_run(db_session, run.id)
    assert ideas == []


# ── TEST-12-01-03: GET /runs/{id}/ideas returns 200 with ideas ──


def test_12_01_03_endpoint_returns_200_with_ideas():
    """Integration: GET /runs/{id}/ideas returns 200 and correct payload."""
    mock_run = PipelineRun(
        id=1,
        status="completed",
        domain="AI/NLP",
        config_json="{}",
        stages_completed="[]",
    )
    mock_idea = Idea(
        id=10,
        title="Idea A",
        problem_statement="Problem A",
        proposed_method="Method A",
        expected_contributions="Contrib A",
        domain="AI/NLP",
        novelty_score=0.8,
        feasibility_score=7.0,
        overall_score=0.75,
        pipeline_run_id=1,
    )

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.get_pipeline_run", return_value=mock_run), \
         patch("backend.db.crud.get_ideas_for_run", return_value=[mock_idea]), \
         patch("backend.db.crud.count_ideas_for_run", return_value=1):
        client = TestClient(_make_app())
        resp = client.get("/runs/1/ideas")

    assert resp.status_code == 200
    body = resp.json()
    assert "ideas" in body
    assert "total" in body
    assert body["total"] == 1
    assert body["ideas"][0]["title"] == "Idea A"
    assert body["ideas"][0]["problem_statement"] == "Problem A"
    assert body["ideas"][0]["proposed_method"] == "Method A"
    assert body["ideas"][0]["expected_contributions"] == "Contrib A"
    assert body["ideas"][0]["domain"] == "AI/NLP"
    assert body["ideas"][0]["novelty_score"] == 0.8
    assert body["ideas"][0]["feasibility_score"] == 7.0
    assert body["ideas"][0]["overall_score"] == 0.75


# ── TEST-12-01-04: GET /runs/{invalid}/ideas returns 404 ────────


def test_12_01_04_endpoint_returns_404_for_nonexistent_run():
    """Integration: GET /runs/{invalid}/ideas returns 404 for non-existent run."""
    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.get_pipeline_run", return_value=None):
        client = TestClient(_make_app())
        resp = client.get("/runs/99999/ideas")

    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body


# ── TEST-12-01-05: Response includes total count field ──────────


def test_12_01_05_response_includes_total_count():
    """Unit: Response includes the total count field matching ideas length."""
    mock_run = PipelineRun(
        id=1,
        status="completed",
        domain="AI/NLP",
        config_json="{}",
        stages_completed="[]",
    )
    mock_ideas = [
        Idea(
            id=i,
            title=f"Idea {i}",
            problem_statement=f"Problem {i}",
            proposed_method=f"Method {i}",
            pipeline_run_id=1,
        )
        for i in range(1, 4)
    ]

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.get_pipeline_run", return_value=mock_run), \
         patch("backend.db.crud.get_ideas_for_run", return_value=mock_ideas), \
         patch("backend.db.crud.count_ideas_for_run", return_value=3):
        client = TestClient(_make_app())
        resp = client.get("/runs/1/ideas")

    body = resp.json()
    assert body["total"] == 3
    assert len(body["ideas"]) == 3


# ── TEST-12-01-06: Endpoint is read-only (GET only, no mutation) ─


def test_12_01_06_endpoint_is_read_only():
    """Unit: POST to /runs/{id}/ideas is rejected (405 Method Not Allowed)."""
    client = TestClient(_make_app())
    resp = client.post("/runs/1/ideas", json={})
    assert resp.status_code == 405

    resp = client.put("/runs/1/ideas", json={})
    assert resp.status_code == 405

    resp = client.patch("/runs/1/ideas", json={})
    assert resp.status_code == 405
