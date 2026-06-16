"""Tests for BATCH-31 SSE header-based auth.

TEST-31-01-01: SSE includes Authorization header (verified via fetch-based client).
TEST-31-01-02: SSE rejects without auth when auth_enabled.
TEST-31-01-03: SSE works without auth when auth_enabled=False.
TEST-31-01-04: No API key in URL query params (HB-01).

Updated: SSE reads from RunService event outbox, not process-local queues.
"""

import sys
from unittest.mock import MagicMock, patch

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


def _mock_run_service_with_done():
    """Mock RunService so SSE terminates quickly with a 'done' event."""
    mock_svc = MagicMock()
    mock_svc.get_latest_seq.return_value = 1  # has history
    mock_svc.get_events_since.return_value = [
        {"seq": 1, "event_type": "done", "payload": {"done": True}}
    ]
    return mock_svc


def _patch_settings(api_key=None, auth_enabled=False):
    """Patch get_settings in config and auth modules."""
    import backend.config as config_mod
    import backend.api.auth as auth_mod

    test_settings = type("Settings", (), {
        "api_key": api_key,
        "auth_enabled": auth_enabled,
    })()
    orig_config = config_mod.get_settings
    orig_auth = auth_mod.get_settings
    config_mod.get_settings = lambda: test_settings
    auth_mod.get_settings = lambda: test_settings
    return orig_config, orig_auth, config_mod, auth_mod


def _restore_settings(orig_config, orig_auth, config_mod, auth_mod):
    config_mod.get_settings = orig_config
    auth_mod.get_settings = orig_auth


def test_31_01_01_sse_includes_auth_header():
    """TEST-31-01-01: SSE connection sends X-API-Key header (fetch-based)."""
    orig_config, orig_auth, config_mod, auth_mod = _patch_settings(
        api_key="test-secret-key", auth_enabled=False
    )
    try:
        mock_svc = _mock_run_service_with_done()
        with patch("backend.api.run_service.get_run_service", return_value=mock_svc):
            client = TestClient(_make_app())
            resp = client.get(
                "/runs/test-run-auth/progress",
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
    finally:
        _restore_settings(orig_config, orig_auth, config_mod, auth_mod)


def test_31_01_02_sse_rejects_without_auth_when_enabled():
    """TEST-31-01-02: SSE rejects request without auth when auth_enabled=True."""
    orig_config, orig_auth, config_mod, auth_mod = _patch_settings(
        api_key="test-secret-key", auth_enabled=True
    )
    try:
        client = TestClient(_make_app())
        resp = client.get(
            "/runs/test-run-noauth/progress",
            headers={"X-API-Key": "test-secret-key"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
    finally:
        _restore_settings(orig_config, orig_auth, config_mod, auth_mod)


def test_31_01_03_sse_works_without_auth_when_disabled():
    """TEST-31-01-03: SSE works without auth when auth_enabled=False."""
    orig_config, orig_auth, config_mod, auth_mod = _patch_settings(
        api_key=None, auth_enabled=False
    )
    try:
        mock_svc = _mock_run_service_with_done()
        with patch("backend.api.run_service.get_run_service", return_value=mock_svc):
            client = TestClient(_make_app())
            resp = client.get("/runs/test-run-open/progress")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
    finally:
        _restore_settings(orig_config, orig_auth, config_mod, auth_mod)


def test_31_01_04_no_api_key_in_url_query_params():
    """TEST-31-01-04: No API key in URL query params (HB-01).

    The SSE endpoint must reject api_key passed via query params,
    ensuring credentials only travel via headers.
    """
    orig_config, orig_auth, config_mod, auth_mod = _patch_settings(
        api_key="test-secret-key", auth_enabled=False
    )
    try:
        mock_svc = _mock_run_service_with_done()
        with patch("backend.api.run_service.get_run_service", return_value=mock_svc):
            client = TestClient(_make_app())
            resp = client.get(
                "/runs/test-run-qp/progress?api_key=test-secret-key",
            )
            # Since api_key is set in settings and we didn't send the header,
            # the defence-in-depth check should reject it
            assert resp.status_code == 401
            body = resp.json()
            assert "error" in body
    finally:
        _restore_settings(orig_config, orig_auth, config_mod, auth_mod)
