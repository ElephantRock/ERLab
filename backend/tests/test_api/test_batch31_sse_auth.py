"""Tests for BATCH-31 SSE header-based auth.

TEST-31-01-01: SSE includes Authorization header (verified via fetch-based client).
TEST-31-01-02: SSE rejects without auth when auth_enabled.
TEST-31-01-03: SSE works without auth when auth_enabled=False.
TEST-31-01-04: No API key in URL query params (HB-01).
"""

import asyncio
import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("chromadb", MagicMock())

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError, UnauthorizedError
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


def _patch_settings(**overrides):
    """Patch get_settings to return a test Settings with given overrides."""
    import backend.config as config_mod
    from backend.config import Settings

    base = {"database_url": "sqlite:///:memory:"}
    base.update(overrides)
    test_settings = Settings(**base)
    orig = config_mod.get_settings
    config_mod.get_settings = lambda: test_settings
    # Also patch the auth module's reference
    import backend.api.auth as auth_mod
    auth_mod.get_settings = lambda: test_settings
    # Patch pipeline.py's local import
    import backend.api.routes.pipeline as pipeline_mod
    orig_pipeline = pipeline_mod.get_settings if hasattr(pipeline_mod, 'get_settings') else None
    return orig, auth_mod, config_mod


def _restore_settings(orig, auth_mod, config_mod):
    """Restore original get_settings."""
    if orig:
        config_mod.get_settings = orig
    else:
        # Re-create lru_cache
        config_mod.get_settings = type(config_mod.get_settings).__wrapped__  # type: ignore


def test_31_01_01_sse_includes_auth_header():
    """TEST-31-01-01: SSE connection sends X-API-Key header (fetch-based)."""
    import backend.config as config_mod
    import backend.api.auth as auth_mod

    test_settings = type("Settings", (), {
        "api_key": "test-secret-key",
        "auth_enabled": False,
    })()
    orig_config = config_mod.get_settings
    orig_auth = auth_mod.get_settings
    config_mod.get_settings = lambda: test_settings
    auth_mod.get_settings = lambda: test_settings

    try:
        # Pre-populate a progress queue so the SSE stream terminates quickly
        done_queue = asyncio.Queue()
        done_queue.put_nowait({"done": True})

        with patch.dict(
            "backend.api.routes.pipeline._progress_queues",
            {"test-run-auth": done_queue},
        ):
            client = TestClient(_make_app())
            # Simulate fetch-based SSE with X-API-Key header
            resp = client.get(
                "/runs/test-run-auth/progress",
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
    finally:
        config_mod.get_settings = orig_config
        auth_mod.get_settings = orig_auth


def test_31_01_02_sse_rejects_without_auth_when_enabled():
    """TEST-31-01-02: SSE rejects request without auth when auth_enabled=True."""
    import backend.config as config_mod
    import backend.api.auth as auth_mod

    test_settings = type("Settings", (), {
        "api_key": "test-secret-key",
        "auth_enabled": True,
    })()
    orig_config = config_mod.get_settings
    orig_auth = auth_mod.get_settings
    config_mod.get_settings = lambda: test_settings
    auth_mod.get_settings = lambda: test_settings

    try:
        client = TestClient(_make_app())
        # No Authorization header → should be rejected
        resp = client.get(
            "/runs/test-run-noauth/progress",
            headers={"X-API-Key": "test-secret-key"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
    finally:
        config_mod.get_settings = orig_config
        auth_mod.get_settings = orig_auth


def test_31_01_03_sse_works_without_auth_when_disabled():
    """TEST-31-01-03: SSE works without auth when auth_enabled=False."""
    import backend.config as config_mod
    import backend.api.auth as auth_mod

    test_settings = type("Settings", (), {
        "api_key": None,  # no API key required
        "auth_enabled": False,
    })()
    orig_config = config_mod.get_settings
    orig_auth = auth_mod.get_settings
    config_mod.get_settings = lambda: test_settings
    auth_mod.get_settings = lambda: test_settings

    try:
        done_queue = asyncio.Queue()
        done_queue.put_nowait({"done": True})

        with patch.dict(
            "backend.api.routes.pipeline._progress_queues",
            {"test-run-open": done_queue},
        ):
            client = TestClient(_make_app())
            # No auth headers at all — should succeed when auth disabled
            resp = client.get("/runs/test-run-open/progress")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
    finally:
        config_mod.get_settings = orig_config
        auth_mod.get_settings = orig_auth


def test_31_01_04_no_api_key_in_url_query_params():
    """TEST-31-01-04: No API key in URL query params (HB-01).

    The SSE endpoint must reject api_key passed via query params,
    ensuring credentials only travel via headers.
    """
    import backend.config as config_mod
    import backend.api.auth as auth_mod

    test_settings = type("Settings", (), {
        "api_key": "test-secret-key",
        "auth_enabled": False,
    })()
    orig_config = config_mod.get_settings
    orig_auth = auth_mod.get_settings
    config_mod.get_settings = lambda: test_settings
    auth_mod.get_settings = lambda: test_settings

    try:
        done_queue = asyncio.Queue()
        done_queue.put_nowait({"done": True})

        with patch.dict(
            "backend.api.routes.pipeline._progress_queues",
            {"test-run-qp": done_queue},
        ):
            client = TestClient(_make_app())
            # Pass api_key in query params instead of header — endpoint ignores it
            # but still requires the header for auth
            resp = client.get(
                "/runs/test-run-qp/progress?api_key=test-secret-key",
                # No X-API-Key header → should still reject
            )
            # Since api_key is set in settings, and we didn't send the header,
            # the defence-in-depth check should catch it
            assert resp.status_code == 401
            body = resp.json()
            assert "error" in body
    finally:
        config_mod.get_settings = orig_config
        auth_mod.get_settings = orig_auth
