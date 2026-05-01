"""Tests for API key authentication."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.api.auth import verify_api_key


def _make_app():
    from backend.api.errors import APIError

    app = FastAPI()

    @app.exception_handler(APIError)
    async def handle_api_error(request, exc):
        from fastapi.responses import JSONResponse
        import uuid
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers={"X-Request-Id": str(uuid.uuid4())},
        )

    @app.get("/test", dependencies=[Depends(verify_api_key)])
    async def test_endpoint():
        return {"ok": True}

    return app


def _patch_settings(api_key_value):
    """Monkey-patch get_settings and return a cleanup function."""
    from backend.api import auth

    original = auth.get_settings

    class _FakeSettings:
        api_key = api_key_value

    auth.get_settings = lambda: _FakeSettings()
    return original


def _restore(original):
    from backend.api import auth

    auth.get_settings = original


def test_no_key_configured_passes():
    original = _patch_settings(None)
    try:
        client = TestClient(_make_app())
        resp = client.get("/test")
        assert resp.status_code == 200
    finally:
        _restore(original)


def test_valid_key_passes():
    original = _patch_settings("test-secret")
    try:
        client = TestClient(_make_app())
        resp = client.get("/test", headers={"X-API-Key": "test-secret"})
        assert resp.status_code == 200
    finally:
        _restore(original)


def test_missing_key_returns_401():
    original = _patch_settings("test-secret")
    try:
        client = TestClient(_make_app())
        resp = client.get("/test")
        assert resp.status_code == 401
    finally:
        _restore(original)


def test_wrong_key_returns_401():
    original = _patch_settings("test-secret")
    try:
        client = TestClient(_make_app())
        resp = client.get("/test", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401
    finally:
        _restore(original)
