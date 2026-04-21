"""Tests for API error handling."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError, NotFoundError, ServiceUnavailableError


def _make_app():
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.get("/not-found")
    async def not_found():
        raise NotFoundError("Resource missing")

    @app.get("/unavailable")
    async def unavailable():
        raise ServiceUnavailableError("Service down")

    return app


def test_not_found_returns_404():
    client = TestClient(_make_app())
    resp = client.get("/not-found")
    assert resp.status_code == 404
    assert resp.json() == {"error": "Resource missing"}


def test_service_unavailable_returns_503():
    client = TestClient(_make_app())
    resp = client.get("/unavailable")
    assert resp.status_code == 503
    assert resp.json() == {"error": "Service down"}


def test_generic_exception_returns_500():
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.exception_handler(Exception)
    async def generic_handler(request, exc):
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    @app.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert resp.json() == {"error": "Internal server error"}
