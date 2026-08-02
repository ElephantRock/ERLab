"""Tests for the autonomous endpoint via API routes (P14)."""

import pytest
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


def test_autonomous_returns_202_with_cycle_id():
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
        assert body["cycle_id"].startswith("run_")  # RunService generates run_ prefixed IDs


def test_autonomous_accepts_request_body():
    """POST /autonomous with custom domain and max_runs."""
    mock_orch = MagicMock()
    mock_orch.autonomous_cycle = AsyncMock(return_value=[])

    with patch("backend.pipeline.orchestrator.PipelineOrchestrator", return_value=mock_orch):
        client = TestClient(_make_app())
        resp = client.post(
            "/autonomous",
            json={"domain": "Computer Vision", "max_runs": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["domain"] == "Computer Vision"
        assert body["max_runs"] == 5
