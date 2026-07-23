"""Diagnostics routes — client-side runtime error ingest.

F1.6.1: governed anonymous endpoint for the frontend's runtime-error
reporter. Returns a 202 validated acknowledgment echoing the submitted
event_id.

The endpoint is intentionally narrow:

- One POST route: ``POST /runtime-error`` (mounted under
  ``/api/v1/diagnostics``). ONLY this exact path is JWT-bypassed in
  ``app.py`` (method+path match, not prefix).
- Strict schema with ``extra = "forbid"`` — extra fields rejected.
- Server-side re-sanitization (truncate strings, normalize category).
- 8 KiB body cap enforced by ASGI middleware BEFORE this route's parser
  runs (see ``backend/api/middleware/diagnostics_body_limit.py``).
- Per-IP rate limit (10/minute default) via a bounded in-memory counter.
- Allowed-origin policy (same-origin + localhost); 403 otherwise.
- Structured ``structlog`` warning only — NO raw model dump, NO request
  object logging.

The endpoint NEVER returns exception details in the response. The only
response body is ``{"status": "accepted", "event_id": "<echoed>"}``.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Deque, Dict, Literal, Tuple

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

router = APIRouter()

# ── Schema ────────────────────────────────────────────────────────────

Category = Literal[
    "render_error",
    "lazy_route_error",
    "global_error",
    "unhandled_rejection",
]

# Bounded string lengths — server-side re-sanitization mirrors the
# frontend sanitizer so a misbehaving or hostile client cannot poison
# the diagnostic log.
MAX_EVENT_ID = 64
MAX_CATEGORY = 32
MAX_ROUTE = 512
MAX_COMPONENT_STACK = 4096
MAX_ERROR_NAME = 128
MAX_SANITIZED_MESSAGE = 256
MAX_BUILD_VERSION = 64
MAX_CORRELATION_ID = 128


class ClientRuntimeErrorReportV1(BaseModel):
    """Strict request schema for runtime-error reports."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["client_runtime_error_v1"] = "client_runtime_error_v1"
    event_id: str = Field(min_length=1, max_length=MAX_EVENT_ID)
    category: Category
    route: str = Field(default="", max_length=MAX_ROUTE)
    component_stack: str | None = Field(default=None, max_length=MAX_COMPONENT_STACK)
    error_name: str = Field(default="Error", max_length=MAX_ERROR_NAME)
    sanitized_message: str = Field(default="", max_length=MAX_SANITIZED_MESSAGE)
    correlation_id: str | None = Field(default=None, max_length=MAX_CORRELATION_ID)
    build_version: str | None = Field(default=None, max_length=MAX_BUILD_VERSION)
    occurred_at: str = Field(default="", max_length=64)

    @field_validator("route")
    @classmethod
    def _route_pathname_only(cls, v: str) -> str:
        """Strip query and fragment — only pathname is permitted."""
        if not v:
            return ""
        # Drop everything after ? or #. The frontend sanitizer should
        # already send pathname only; this is defense-in-depth.
        for sep in ("?", "#"):
            idx = v.find(sep)
            if idx >= 0:
                v = v[:idx]
        return v

    @field_validator("event_id")
    @classmethod
    def _safe_event_id(cls, v: str) -> str:
        """Allow UUIDs and short ASCII safe-strings only."""
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        return "".join(c for c in v if c in allowed)[:MAX_EVENT_ID]

    @field_validator("correlation_id")
    @classmethod
    def _safe_correlation_id(cls, v: str | None) -> str | None:
        """Allow UUIDs and short ASCII safe-strings only."""
        if v is None:
            return None
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        return "".join(c for c in v if c in allowed)[:MAX_CORRELATION_ID]


# ── Rate limiter (simple in-memory per-IP) ────────────────────────────

RATE_LIMIT_PER_MINUTE = 10
RATE_WINDOW_SECONDS = 60
MAX_TRACKED_IPS = 10_000  # bounded — prevents unbounded growth under load

_ip_hits: Dict[str, Deque[float]] = {}


def _check_rate_limit(client_ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.monotonic()
    window_start = now - RATE_WINDOW_SECONDS

    if client_ip not in _ip_hits:
        # Bound the registry size — drop oldest entries if at cap.
        if len(_ip_hits) >= MAX_TRACKED_IPS:
            oldest = next(iter(_ip_hits))
            del _ip_hits[oldest]
        _ip_hits[client_ip] = deque()
    hits = _ip_hits[client_ip]
    # Drop expired entries.
    while hits and hits[0] < window_start:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_PER_MINUTE:
        return False
    hits.append(now)
    return True


def _reset_rate_limiter() -> None:
    """Test-only: clear all rate-limit state for deterministic tests."""
    _ip_hits.clear()


# ── Origin allowlist ──────────────────────────────────────────────────


def _origin_allowed(request: Request) -> bool:
    """Allow same-origin requests and localhost.

    Same-origin: no Origin header (typical for same-origin browser
    requests is actually to OMIT it for same-origin GETs, but POSTs from
    fetch typically include it) OR Origin matches the Host header.
    Localhost: any port on localhost or 127.0.0.1 (dev).
    """
    origin = request.headers.get("origin")
    if not origin:
        # No Origin header — permit (curl, server-to-server health checks).
        return True
    host = request.headers.get("host", "")
    # Strip scheme for comparison.
    origin_host = origin
    for scheme in ("https://", "http://"):
        if origin_host.startswith(scheme):
            origin_host = origin_host[len(scheme):]
            break
    # Strip path if present.
    origin_host = origin_host.split("/", 1)[0]
    if origin_host == host:
        return True
    for local in ("localhost", "127.0.0.1"):
        if origin_host == local or origin_host.startswith(local + ":"):
            return True
    return False


# ── Structured logging (sanitized) ────────────────────────────────────


def _emit_structlog(report: ClientRuntimeErrorReportV1, client_ip: str) -> None:
    """Emit a single structured warning. Never logs raw request body,
    never logs headers, never logs the request object. Only the sanitized
    schema fields are recorded."""
    try:
        import structlog

        structlog.get_logger("diagnostics").warning(
            "client_runtime_error",
            event_id=report.event_id,
            category=report.category,
            route=report.route,
            error_name=report.error_name,
            build_version=report.build_version,
            # Intentionally NOT logged: component_stack (large),
            # sanitized_message (could be refined later), correlation_id
            # (only added when we are confident it carries no secrets).
            client_ip=client_ip,
        )
    except Exception:
        # Logging must never break the response path.
        pass


# ── Route ─────────────────────────────────────────────────────────────


@router.post(
    "/runtime-error",
    status_code=202,
    summary="Accept a client-side runtime-error report",
    description=(
        "Governed anonymous endpoint accepting a sanitized client-side "
        "runtime error report. Returns 202 with the echoed event_id. "
        "Rate-limited per IP; body capped at 8 KiB by ASGI middleware."
    ),
)
async def accept_runtime_error(
    report: ClientRuntimeErrorReportV1,
    request: Request,
) -> Response:
    # Origin allowlist — defense against cross-site submission.
    if not _origin_allowed(request):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "ORIGIN_NOT_ALLOWED",
                    "message": "Origin is not permitted to submit runtime-error reports.",
                }
            },
        )

    client_ip = request.client.host if request.client else "unknown"

    # Per-IP rate limit.
    if not _check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": (
                        f"Runtime-error report rate limit "
                        f"({RATE_LIMIT_PER_MINUTE}/minute) exceeded."
                    ),
                }
            },
            headers={
                "Retry-After": str(RATE_WINDOW_SECONDS),
            },
        )

    # Server-side re-sanitization: Pydantic validators already truncated
    # the bounded fields; the only remaining check is that the event_id
    # we echo back matches what was submitted (it always does because we
    # pass the model through unchanged — but this is the documented
    # contract: the response event_id IS the submitted event_id).
    echoed_event_id = report.event_id

    _emit_structlog(report, client_ip)

    return Response(
        status_code=202,
        content=(
            '{"status": "accepted", "event_id": "'
            + echoed_event_id
            + '"}'
        ),
        media_type="application/json",
    )
