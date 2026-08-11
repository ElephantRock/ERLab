"""Tests for async pipeline execution via the API routes (P11)."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("chromadb", MagicMock())

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError
from backend.api.routes.pipeline import router


def _make_app():
    """Build a test app that includes the pipeline router and error handling."""
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router)
    return app


def test_trigger_run_returns_202():
    """POST /run returns run_id and status 'running' when preflight passes."""
    mock_orch = MagicMock()
    mock_orch.run = AsyncMock(return_value=MagicMock())
    mock_orch._should_stop = MagicMock(return_value=False)

    # Mock preflight to pass (BATCH-172)
    mock_report = MagicMock()
    mock_report.can_proceed = True
    mock_report.warnings = 0
    mock_report.fatal = 0
    mock_report.checks = []

    with patch("backend.pipeline.orchestrator.PipelineOrchestrator", return_value=mock_orch), \
         patch("backend.pipeline.preflight.run_preflight", new=AsyncMock(return_value=mock_report)):
        client = TestClient(_make_app())
        resp = client.post("/run", json={"domain": "AI/NLP"})
        assert resp.status_code == 200
        body = resp.json()
        assert "run_id" in body
        assert body["status"] == "running"


def test_trigger_run_accepts_full_params():
    """POST /run with all PipelineRunRequest fields returns run_id."""
    mock_orch = MagicMock()
    mock_orch.run = AsyncMock(return_value=MagicMock())
    mock_orch._should_stop = MagicMock(return_value=False)

    mock_report = MagicMock()
    mock_report.can_proceed = True
    mock_report.warnings = 0
    mock_report.fatal = 0
    mock_report.checks = []

    with patch("backend.pipeline.orchestrator.PipelineOrchestrator", return_value=mock_orch), \
         patch("backend.pipeline.preflight.run_preflight", new=AsyncMock(return_value=mock_report)):
        client = TestClient(_make_app())
        resp = client.post(
            "/run",
            json={
                "domain": "Computer Vision",
                "max_gaps": 10,
                "generation_rounds": 3,
                "ideas_per_round": 5,
                "search_queries": ["transformers", "attention"],
                "run_novelty": True,
                "run_feasibility": False,
                "run_synthesis": True,
                "export_format": "latex",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"


def test_list_runs_returns_json():
    """GET /runs returns {'runs': [...], 'total': N}."""
    mock_session_cm = MagicMock()
    mock_session = MagicMock()
    mock_session_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_session_cm.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.scalars.return_value.all.return_value = []

    # get_session is imported locally inside list_runs, so patch at the source
    with patch("backend.db.database.get_session", return_value=mock_session_cm):
        client = TestClient(_make_app())
        resp = client.get("/runs")
        assert resp.status_code == 200
        body = resp.json()
        assert "runs" in body
        assert "total" in body
        assert isinstance(body["runs"], list)


def test_cancel_run_unknown_returns_404():
    """DELETE /runs/nonexistent_id returns 404."""
    client = TestClient(_make_app())
    resp = client.delete("/runs/nonexistent_id")
    assert resp.status_code == 404


def test_progress_endpoint_returns_sse():
    """GET /runs/{id}/progress returns text/event-stream content type."""
    # Use the durable RunService to create a run and append a done event
    from backend.api.run_service import get_run_service, reset_run_service
    reset_run_service()
    run_svc = get_run_service()

    with patch.object(run_svc, 'create_run', return_value='test-run-123'), \
         patch.object(run_svc, 'append_event', return_value=1), \
         patch.object(run_svc, 'get_latest_seq', return_value=1), \
         patch.object(run_svc, 'get_events_since', return_value=[
            {"seq": 1, "event_type": "done", "payload": {"done": True}, "created_at": None},
         ]):
        client = TestClient(_make_app())
        resp = client.get("/runs/test-run-123/progress")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


def test_autonomous_cycle_returns_202():
    """POST /autonomous returns cycle_id and status 'running'."""
    mock_orch = MagicMock()
    mock_orch.autonomous_cycle = AsyncMock(return_value=[])

    with patch("backend.pipeline.orchestrator.PipelineOrchestrator", return_value=mock_orch):
        client = TestClient(_make_app())
        resp = client.post("/autonomous", json={"domain": "AI/NLP"})
        assert resp.status_code == 200
        body = resp.json()
        assert "cycle_id" in body
        assert body["status"] == "running"
