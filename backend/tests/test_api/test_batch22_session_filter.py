"""Tests for BATCH-22/TASK-01: Session filter and grouping for pipeline runs."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError
from backend.api.routes.pipeline import router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import PipelineRun


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


# ── TEST-22-01-01: GET /runs?session_id=X returns filtered results ──


def test_22_01_01_session_id_filter_returns_matching_runs(db_session):
    """GET /runs?session_id=X returns only runs with that session_id."""
    crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed", session_id="sess-alpha")
    crud.create_pipeline_run(db_session, domain="AI/ML", status="completed", session_id="sess-alpha")
    crud.create_pipeline_run(db_session, domain="AI/CV", status="completed", session_id="sess-beta")

    runs = crud.list_pipeline_runs(db_session, session_id="sess-alpha")
    assert len(runs) == 2
    assert all(r.session_id == "sess-alpha" for r in runs)

    total = crud.count_pipeline_runs(db_session, session_id="sess-alpha")
    assert total == 2


# ── TEST-22-01-02: GET /runs?session_id=nonexistent returns empty ──


def test_22_01_02_session_id_filter_nonexistent_returns_empty(db_session):
    """GET /runs?session_id=nonexistent returns empty results."""
    crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed", session_id="sess-alpha")

    runs = crud.list_pipeline_runs(db_session, session_id="nonexistent")
    assert runs == []

    total = crud.count_pipeline_runs(db_session, session_id="nonexistent")
    assert total == 0


# ── TEST-22-01-03: GET /runs without session_id returns all (existing behavior) ──


def test_22_01_03_no_session_id_returns_all_runs(db_session):
    """GET /runs without session_id returns all runs (existing behavior preserved)."""
    crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed", session_id="sess-alpha")
    crud.create_pipeline_run(db_session, domain="AI/ML", status="completed", session_id="sess-beta")
    crud.create_pipeline_run(db_session, domain="AI/CV", status="completed", session_id=None)

    runs = crud.list_pipeline_runs(db_session)
    assert len(runs) == 3

    total = crud.count_pipeline_runs(db_session)
    assert total == 3


# ── TEST-22-01-04: GET /runs/sessions returns unique session_ids ──


def test_22_01_04_list_session_ids_returns_unique_sessions(db_session):
    """list_session_ids returns unique session_id values grouped correctly."""
    crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed", session_id="sess-alpha")
    crud.create_pipeline_run(db_session, domain="AI/ML", status="completed", session_id="sess-alpha")
    crud.create_pipeline_run(db_session, domain="AI/CV", status="completed", session_id="sess-beta")
    crud.create_pipeline_run(db_session, domain="AI/RL", status="completed", session_id=None)

    sessions = crud.list_session_ids(db_session)
    assert len(sessions) == 2  # Only non-NULL session_ids

    session_map = {s["session_id"]: s for s in sessions}
    assert "sess-alpha" in session_map
    assert "sess-beta" in session_map
    assert session_map["sess-alpha"]["run_count"] == 2
    assert session_map["sess-beta"]["run_count"] == 1


# ── TEST-22-01-05: Session list returns [{session_id, run_count, latest_run_at}] ──


def test_22_01_05_session_list_endpoint_returns_expected_shape():
    """GET /runs/sessions returns [{session_id, run_count, latest_run_at}]."""
    mock_sessions = [
        {"session_id": "sess-alpha", "run_count": 3, "latest_run_at": "2026-05-02 14:30:00+00:00"},
        {"session_id": "sess-beta", "run_count": 1, "latest_run_at": "2026-05-02 10:00:00+00:00"},
    ]

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.list_session_ids", return_value=mock_sessions):
        client = TestClient(_make_app())
        resp = client.get("/runs/sessions")

    assert resp.status_code == 200
    body = resp.json()
    assert "sessions" in body
    assert len(body["sessions"]) == 2
    assert body["sessions"][0]["session_id"] == "sess-alpha"
    assert body["sessions"][0]["run_count"] == 3
    assert body["sessions"][0]["latest_run_at"] == "2026-05-02 14:30:00+00:00"
    assert body["sessions"][1]["session_id"] == "sess-beta"
    assert body["sessions"][1]["run_count"] == 1
