"""Tests for session API endpoints."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.errors import APIError
from backend.api.routes.pipeline import router
from backend.pipeline.session.manager import SessionManager


def _make_app(tmp_path) -> TestClient:
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.message})

    app.include_router(router, prefix="/pipeline")

    # Patch the _get_orchestrator to return an object with _session_manager
    mgr = SessionManager(data_dir=str(tmp_path / "sessions"))

    class FakeOrchestrator:
        _session_manager = mgr
        scheduler_status = lambda self: None
        start_scheduler = lambda self: None
        stop_scheduler = lambda self: None

    import backend.api.routes.pipeline as routes_mod
    routes_mod._scheduler_orchestrator = FakeOrchestrator()

    return TestClient(app)


class TestSessionAPI:
    def test_create_session(self, tmp_path):
        client = _make_app(tmp_path)
        resp = client.post("/pipeline/sessions", json={"name": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test"
        assert data["state"] == "created"

    def test_list_sessions(self, tmp_path):
        client = _make_app(tmp_path)
        client.post("/pipeline/sessions", json={"name": "a"})
        client.post("/pipeline/sessions", json={"name": "b"})
        resp = client.get("/pipeline/sessions")
        assert resp.status_code == 200
        assert len(resp.json()["sessions"]) == 2

    def test_get_session(self, tmp_path):
        client = _make_app(tmp_path)
        create_resp = client.post("/pipeline/sessions", json={"name": "test"})
        sid = create_resp.json()["id"]
        resp = client.get(f"/pipeline/sessions/{sid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test"

    def test_lifecycle_activate_pause_end(self, tmp_path):
        client = _make_app(tmp_path)
        create_resp = client.post("/pipeline/sessions", json={"name": "test"})
        sid = create_resp.json()["id"]

        # Activate
        resp = client.post(f"/pipeline/sessions/{sid}/activate")
        assert resp.json()["state"] == "active"

        # Pause
        resp = client.post(f"/pipeline/sessions/{sid}/pause")
        assert resp.json()["state"] == "paused"

        # Resume
        resp = client.post(f"/pipeline/sessions/{sid}/resume")
        assert resp.json()["state"] == "active"

        # End
        resp = client.post(f"/pipeline/sessions/{sid}/end")
        assert resp.json()["state"] == "ended"

    def test_budget_endpoint(self, tmp_path):
        client = _make_app(tmp_path)
        create_resp = client.post("/pipeline/sessions", json={"name": "test", "max_runs": 5})
        sid = create_resp.json()["id"]
        resp = client.get(f"/pipeline/sessions/{sid}/budget")
        assert resp.status_code == 200
        assert resp.json()["remaining_runs"] == 5
        assert resp.json()["over_budget"] is False

    def test_get_missing_session(self, tmp_path):
        client = _make_app(tmp_path)
        resp = client.get("/pipeline/sessions/nonexistent")
        assert resp.status_code == 404
