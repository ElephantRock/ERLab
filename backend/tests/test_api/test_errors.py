"""Tests for API error handling."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError, NotFoundError, ServiceUnavailableError


def _make_app():
    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        import uuid
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers={"X-Request-Id": str(uuid.uuid4())},
        )

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
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Resource missing"


def test_service_unavailable_returns_503():
    client = TestClient(_make_app())
    resp = client.get("/unavailable")
    assert resp.status_code == 503
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert body["error"]["message"] == "Service down"


def test_generic_exception_returns_500():
    import uuid

    from fastapi.responses import JSONResponse

    app = FastAPI()

    @app.exception_handler(Exception)
    async def generic_handler(request, exc):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error",
                    "hint": "Quote request ID when reporting",
                }
            },
            headers={"X-Request-Id": str(uuid.uuid4())},
        )

    @app.get("/boom")
    async def boom():
        raise RuntimeError("unexpected")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "INTERNAL_ERROR"


def test_api_error_has_request_id_header():
    import uuid as uuid_mod
    client = TestClient(_make_app())
    resp = client.get("/not-found")
    request_id = resp.headers.get("x-request-id")
    assert request_id is not None
    # Should be a valid UUID
    uuid_mod.UUID(request_id)
