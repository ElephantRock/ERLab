"""BATCH-27 / TASK-01 — Evolution status endpoint tests.

TEST-27-01-01: GET /status/evolution returns evolution info
TEST-27-01-02: Evolution disabled returns appropriate status
TEST-27-01-03: Evolution enabled shows overlay count
"""

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app():
    """Create a minimal FastAPI app with the status router mounted."""
    app = FastAPI()

    from backend.api.routes.status import router as status_router
    app.include_router(status_router, prefix="/api/v1/status")

    return app


def test_evolution_returns_evolution_info():
    """TEST-27-01-01: GET /status/evolution returns evolution info."""
    app = _make_app()
    client = TestClient(app)

    with patch("backend.api.routes.status.get_settings") as mock_settings:
        settings = MagicMock()
        settings.self_improve_enabled = False
        mock_settings.return_value = settings

        resp = client.get("/api/v1/status/evolution")

    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "overlays_generated" in data
    assert "recent_outcomes" in data
    assert isinstance(data["enabled"], bool)
    assert isinstance(data["overlays_generated"], int)
    assert isinstance(data["recent_outcomes"], list)


def test_evolution_disabled_returns_disabled_status():
    """TEST-27-01-02: Evolution disabled returns appropriate status."""
    app = _make_app()
    client = TestClient(app)

    with patch("backend.api.routes.status.get_settings") as mock_settings:
        settings = MagicMock()
        settings.self_improve_enabled = False
        mock_settings.return_value = settings

        resp = client.get("/api/v1/status/evolution")

    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is False
    assert data["overlays_generated"] == 0
    assert data["recent_outcomes"] == []


def test_evolution_enabled_shows_overlay_count():
    """TEST-27-01-03: Evolution enabled shows overlay count."""
    app = _make_app()
    client = TestClient(app)

    with patch("backend.api.routes.status.get_settings") as mock_settings:
        settings = MagicMock()
        settings.self_improve_enabled = True
        mock_settings.return_value = settings

        resp = client.get("/api/v1/status/evolution")

    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert isinstance(data["overlays_generated"], int)
    assert isinstance(data["recent_outcomes"], list)
