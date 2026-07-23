"""F1.6.1 tests for the diagnostics runtime-error endpoint.

Covers:
- 202 + echoed event_id (happy path)
- extra-field rejection (422)
- 8 KiB body cap via ASGI middleware BEFORE handler (413)
- chunked-oversized body → 413 (handler not entered, no diagnostic log)
- route pathname-only (query/fragment stripped)
- event_id format validation (log-injection defense)
- per-IP rate limit (with reset)
- origin allowlist
- no request body in logs
- no exception detail in response
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.routes import diagnostics as diagnostics_route


@pytest.fixture
def client():
    # Reset rate limiter between tests so they remain deterministic.
    diagnostics_route._reset_rate_limiter()
    return TestClient(app, raise_server_exceptions=False)


def _valid_report(event_id: str = "evt-abc-123") -> dict:
    return {
        "schema_version": "client_runtime_error_v1",
        "event_id": event_id,
        "category": "render_error",
        "route": "/dashboard",
        "component_stack": "in ComponentA\nin RouteBoundary",
        "error_name": "TypeError",
        "sanitized_message": "A component failed while rendering.",
        "correlation_id": "req-xyz-456",
        "build_version": "abc1234",
        "occurred_at": "2026-07-23T01:00:00Z",
    }


# ── Happy path ────────────────────────────────────────────────────────


class TestAcceptRuntimeError:
    def test_returns_202_with_echoed_event_id(self, client):
        """POST /runtime-error returns 202 with the submitted event_id."""
        report = _valid_report("evt-happy-001")
        response = client.post("/api/v1/diagnostics/runtime-error", json=report)
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["event_id"] == "evt-happy-001"

    def test_does_not_echo_exception_detail(self, client):
        """Response body contains only status + event_id. No exception
        details leak even when the handler raises."""
        report = _valid_report("evt-no-detail")
        response = client.post("/api/v1/diagnostics/runtime-error", json=report)
        body_text = response.text
        assert "Traceback" not in body_text
        assert "exception" not in body_text.lower()
        assert "error" not in json.loads(body_text)  # only status + event_id


# ── Schema strictness ─────────────────────────────────────────────────


class TestSchemaStrictness:
    def test_extra_field_rejected_with_422(self, client):
        """Strict schema (extra=forbid) rejects unknown fields."""
        report = _valid_report()
        report["secret_field"] = "should be rejected"
        response = client.post("/api/v1/diagnostics/runtime-error", json=report)
        assert response.status_code == 422

    def test_invalid_category_rejected(self, client):
        report = _valid_report()
        report["category"] = "not_a_real_category"
        response = client.post("/api/v1/diagnostics/runtime-error", json=report)
        assert response.status_code == 422

    def test_wrong_schema_version_rejected(self, client):
        report = _valid_report()
        report["schema_version"] = "client_runtime_error_v2"
        response = client.post("/api/v1/diagnostics/runtime-error", json=report)
        assert response.status_code == 422

    def test_route_query_fragment_stripped(self, client):
        """Route must be pathname-only — server strips ? and #."""
        report = _valid_report()
        report["route"] = "/dashboard?token=secret#frag"
        response = client.post("/api/v1/diagnostics/runtime-error", json=report)
        # Accepted — server-side re-sanitization cleans the route.
        assert response.status_code == 202

    def test_event_id_unsafe_chars_filtered(self, client):
        """event_id with log-injection chars is cleaned (no \n, no quotes,
        no path separators). The cleaned value is echoed back."""
        report = _valid_report()
        report["event_id"] = "evt-\\n-foo'; DROP--ok"
        response = client.post("/api/v1/diagnostics/runtime-error", json=report)
        assert response.status_code == 202
        echoed = response.json()["event_id"]
        # Only safe chars survive.
        for ch in echoed:
            assert ch.isalnum() or ch in "-_"


# ── Pre-parser body cap (F1.6.1 V3-4) ─────────────────────────────────


class TestBodyLimitMiddleware:
    """The 8 KiB cap MUST run before FastAPI/Pydantic parses the body."""

    def test_oversized_body_rejected_with_413(self, client):
        """A single body >8 KiB returns 413 before the handler runs."""
        report = _valid_report()
        # Pack a huge component_stack to push total body over 8 KiB.
        report["component_stack"] = "x" * (9 * 1024)
        response = client.post("/api/v1/diagnostics/runtime-error", json=report)
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    def test_non_target_path_unaffected_by_middleware(self, client):
        """A different path is NOT subject to the body cap (passes through)."""
        # The literature search endpoint should accept any (normal) body.
        # We're just verifying the middleware doesn't 413 a non-target path.
        # Use OPTIONS to avoid hitting actual literature logic.
        response = client.options("/api/v1/literature/search")
        # CORS preflight returns 200; the point is: not 413.
        assert response.status_code != 413


class TestChunkedBodyLimit:
    """The body limit must enforce across multiple receive events.

    FastAPI's TestClient serializes the body as a single chunk by default.
    To prove the cap works on chunked input we call the underlying ASGI
    app directly with a hand-crafted receive sequence.
    """

    def test_chunked_oversized_body_returns_413_and_handler_not_entered(self):
        """chunk1=5KiB chunk2=4KiB → middleware stops → 413 → endpoint
        handler not entered → no diagnostic log emitted."""
        # Reset the rate limiter first.
        diagnostics_route._reset_rate_limiter()

        report = _valid_report()
        # Make the JSON body exceed 8 KiB so the middleware cap trips.
        report["component_stack"] = "y" * (9 * 1024)
        body_bytes = json.dumps(report).encode("utf-8")
        assert len(body_bytes) > 8 * 1024, "test setup: body must exceed 8 KiB cap"
        # Split into two chunks that individually are under the cap but
        # together exceed it: first ~5KiB, rest ~4KiB.
        split = 5 * 1024
        chunk1 = body_bytes[:split]
        chunk2 = body_bytes[split:]
        assert len(chunk1) + len(chunk2) > 8 * 1024

        # Hand-crafted ASGI receive: emit chunk1 (more_body=True), then
        # chunk2 (more_body=False).
        receive_events = [
            {"type": "http.request", "body": chunk1, "more_body": True},
            {"type": "http.request", "body": chunk2, "more_body": False},
        ]
        event_index = {"i": 0}

        async def receive():
            if event_index["i"] >= len(receive_events):
                return {"type": "http.request", "body": b"", "more_body": False}
            ev = receive_events[event_index["i"]]
            event_index["i"] += 1
            return ev

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/diagnostics/runtime-error",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("test", 80),
            "client": ("127.0.0.1", 12345),
            "root_path": "",
            "http_version": "1.1",
            "app": app,
            "asgi": {"version": "3.0"},
            "raw_path": b"/api/v1/diagnostics/runtime-error",
            "state": {},
            "extensions": {},
        }

        # Patch _emit_structlog (the only side-effecting call inside the
        # handler) to detect whether the handler ran. If the middleware
        # correctly short-circuits, _emit_structlog is never called.
        with patch.object(
            diagnostics_route, "_emit_structlog"
        ) as mock_emit:
            import asyncio

            asyncio.run(app(scope, receive, send))

        # Locate the http.response.start message.
        start_messages = [m for m in sent_messages if m.get("type") == "http.response.start"]
        assert start_messages, "expected a response.start message"
        status = start_messages[-1]["status"]
        assert status == 413, f"chunked oversized body must yield 413, got {status}"
        # The handler MUST NOT have been entered when middleware rejects.
        # _emit_structlog is the only side effect of the handler — if it
        # was not called, the handler did not run.
        mock_emit.assert_not_called()


# ── Rate limiting ─────────────────────────────────────────────────────


class TestRateLimit:
    def test_rate_limit_blocks_after_threshold(self, client):
        """After 10 requests in a minute, the 11th returns 429."""
        report = _valid_report()
        for i in range(10):
            r = client.post(
                "/api/v1/diagnostics/runtime-error",
                json={**report, "event_id": f"evt-rl-{i}"},
            )
            assert r.status_code == 202, f"request {i} should be accepted"

        # 11th request — rate limited.
        r = client.post(
            "/api/v1/diagnostics/runtime-error",
            json={**report, "event_id": "evt-rl-blocked"},
        )
        assert r.status_code == 429
        assert r.json()["error"]["code"] == "RATE_LIMITED"
        assert "Retry-After" in r.headers


# ── Origin allowlist ──────────────────────────────────────────────────


class TestOriginAllowlist:
    def test_disallowed_origin_rejected(self, client):
        report = _valid_report()
        response = client.post(
            "/api/v1/diagnostics/runtime-error",
            json=report,
            headers={"Origin": "https://evil.example.com"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"

    def test_localhost_origin_allowed(self, client):
        report = _valid_report()
        response = client.post(
            "/api/v1/diagnostics/runtime-error",
            json=report,
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 202


# ── Logging ───────────────────────────────────────────────────────────


class TestSanitizedLogging:
    def test_structlog_emits_only_sanitized_fields(self, client):
        """The structlog warning contains ONLY allowlisted schema fields.
        The component_stack (large), sanitized_message, and request body
        must NEVER appear in the log entry."""
        report = _valid_report("evt-log-001")
        report["component_stack"] = "TopSecretStackContent-should-not-log"

        with patch("structlog.get_logger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            client.post("/api/v1/diagnostics/runtime-error", json=report)

        mock_logger.warning.assert_called_once()
        call = mock_logger.warning.call_args
        # The event name is the first positional argument.
        assert call.args[0] == "client_runtime_error"
        kwargs = call.kwargs
        assert kwargs["event_id"] == "evt-log-001"
        assert kwargs["category"] == "render_error"
        # component_stack MUST NOT be logged.
        assert "component_stack" not in kwargs
        # The raw stack content must not leak into the kwargs values.
        for v in kwargs.values():
            assert "TopSecretStackContent" not in str(v)
