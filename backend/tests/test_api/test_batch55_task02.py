"""BATCH-55 TASK-02: list_runs serialization tests."""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.pipeline import router

app = FastAPI()
app.include_router(router, prefix="/api/v1/pipeline")


def _mock_session():
    """Create a mock session context manager."""
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    return ms, mc


def _make_run(run_id=1, status="completed", domain="AI/NLP", ideas=None, session_id=None):
    """Create a mock PipelineRun with an ideas list."""
    run = MagicMock()
    run.id = run_id
    run.status = status
    run.domain = domain
    run.current_stage = "done" if status == "completed" else "running"
    run.ideas = ideas or []
    run.session_id = session_id
    run.created_at = datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC)
    run.completed_at = datetime(2026, 5, 2, 12, 5, 0, tzinfo=UTC) if status == "completed" else None
    run.error_message = None
    return run


def test_55_02_01_list_runs_returns_200():
    """GET /runs returns 200 with valid run data."""
    run = _make_run(run_id=1, status="completed")
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = [run]
    # count query
    ms.execute.return_value.scalar_one.return_value = 1

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/api/v1/pipeline/runs")

    assert resp.status_code == 200
    body = resp.json()
    assert "runs" in body
    assert "total" in body
    assert len(body["runs"]) == 1
    assert body["runs"][0]["status"] == "completed"


def test_55_02_02_runs_with_ideas_return_correct_ideas_count():
    """Runs with ideas return the correct ideas_count in the response."""
    idea1 = MagicMock()
    idea1.id = 10
    idea2 = MagicMock()
    idea2.id = 11

    run = _make_run(run_id=2, status="completed", ideas=[idea1, idea2])
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = [run]
    ms.execute.return_value.scalar_one.return_value = 1

    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/api/v1/pipeline/runs")

    assert resp.status_code == 200
    body = resp.json()
    assert body["runs"][0]["ideas_count"] == 2
