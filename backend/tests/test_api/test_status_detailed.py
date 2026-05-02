"""BATCH-13 / TASK-02 — Status detailed endpoint tests.

TEST-13-02-07: GET /status/detailed returns version + provider + db_status.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app():
    """Create a minimal FastAPI app with the status router mounted."""
    app = FastAPI()

    from backend.api.routes.status import router as status_router
    app.include_router(status_router, prefix="/api/v1/status")

    return app


def test_status_detailed_returns_version_provider_db():
    """TEST-13-02-07: GET /status/detailed returns version + provider + db_status."""
    app = _make_app()
    client = TestClient(app)

    resp = client.get("/api/v1/status/detailed")
    assert resp.status_code == 200

    data = resp.json()
    assert "version" in data
    assert "provider" in data
    assert "db_status" in data

    # Version should be a non-empty string
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0

    # Provider should be a non-empty string
    assert isinstance(data["provider"], str)
    assert len(data["provider"]) > 0

    # db_status should be either "ok" or "error"
    assert data["db_status"] in ("ok", "error")
