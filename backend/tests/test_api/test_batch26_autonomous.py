"""Tests for BATCH-26/TASK-01: Autonomous Stop & History endpoints."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("chromadb", MagicMock())

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError
from backend.api.routes import pipeline as pipeline_module
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


def _reset_state():
    """Clear module-level state to avoid test interference."""
    pipeline_module._autonomous_history.clear()
    pipeline_module._cancel_events.clear()
    pipeline_module._progress_queues.clear()


# ── TEST-26-01-01: POST /autonomous/stop stops running cycle ──────

def test_stop_autonomous_cycle_stops_running():
    """POST /autonomous/stop with valid cycle_id returns stopped status."""
    _reset_state()
    mock_orch = MagicMock()
    mock_orch.autonomous_cycle = AsyncMock(return_value=[])

    with patch("backend.pipeline.orchestrator.PipelineOrchestrator", return_value=mock_orch):
        client = TestClient(_make_app())

        # Start a cycle first
        start_resp = client.post("/autonomous", json={"domain": "AI/NLP", "max_runs": 3})
        assert start_resp.status_code == 200
        cycle_id = start_resp.json()["cycle_id"]

        # Stop it
        stop_resp = client.post(f"/autonomous/stop?cycle_id={cycle_id}")
        assert stop_resp.status_code == 200
        body = stop_resp.json()
        assert body["status"] == "stopped"
        assert body["cycle_id"] == cycle_id


# ── TEST-26-01-02: GET /autonomous/history returns cycle list ────

def test_autonomous_history_returns_cycles():
    """GET /autonomous/history returns list of cycles."""
    _reset_state()
    mock_orch = MagicMock()
    mock_orch.autonomous_cycle = AsyncMock(return_value=[])

    with patch("backend.pipeline.orchestrator.PipelineOrchestrator", return_value=mock_orch):
        client = TestClient(_make_app())

        # Start a cycle
        start_resp = client.post("/autonomous", json={"domain": "AI/NLP", "max_runs": 2})
        assert start_resp.status_code == 200
        cycle_id = start_resp.json()["cycle_id"]

        # Get history
        hist_resp = client.get("/autonomous/history")
        assert hist_resp.status_code == 200
        body = hist_resp.json()
        assert "cycles" in body
        assert len(body["cycles"]) == 1
        assert body["cycles"][0]["cycle_id"] == cycle_id
        assert body["cycles"][0]["domain"] == "AI/NLP"


# ── TEST-26-01-03: History shows cycle status ────────────────────

def test_history_shows_cycle_status():
    """History entries include status (running/completed/stopped)."""
    _reset_state()
    mock_orch = MagicMock()
    mock_orch.autonomous_cycle = AsyncMock(return_value=[])

    with patch("backend.pipeline.orchestrator.PipelineOrchestrator", return_value=mock_orch):
        client = TestClient(_make_app())

        # Start cycle
        start_resp = client.post("/autonomous", json={"domain": "Physics", "max_runs": 1})
        cycle_id = start_resp.json()["cycle_id"]

        # Stop it
        client.post(f"/autonomous/stop?cycle_id={cycle_id}")

        # Check history shows stopped
        hist_resp = client.get("/autonomous/history")
        cycles = hist_resp.json()["cycles"]
        stopped_cycle = [c for c in cycles if c["cycle_id"] == cycle_id]
        assert len(stopped_cycle) == 1
        assert stopped_cycle[0]["status"] == "stopped"


# ── TEST-26-01-04: Stop non-existent cycle returns 404 ────────────

def test_stop_nonexistent_cycle_returns_404():
    """POST /autonomous/stop with unknown cycle_id returns 404."""
    _reset_state()
    client = TestClient(_make_app())

    resp = client.post("/autonomous/stop?cycle_id=auto_nonexistent_999")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"


# ── TEST-26-01-05: Scheduler status returns state info ────────────

def test_scheduler_status_returns_state():
    """GET /scheduler/status returns status information."""
    mock_orch = MagicMock()
    mock_orch.scheduler_status.return_value = {"status": "not_configured"}

    with patch(
        "backend.api.routes.pipeline._get_orchestrator", return_value=mock_orch
    ):
        client = TestClient(_make_app())
        resp = client.get("/scheduler/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
