"""Elephant Rock Research API — FastAPI application."""

import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.auth import verify_api_key
from backend.api.errors import APIError
from backend.api.routes import costs, gaps, governance, ideas, knowledge, knowledge_graph, literature, memory, pipeline, status, traces

app = FastAPI(
    title="Elephant Rock Research API",
    version="0.1.0",
    description="AI/NLP Research Idea Generation Platform",
)

# ── Middleware ──────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    try:
        import structlog

        structlog.get_logger().info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=round(elapsed * 1000, 2),
        )
    except Exception:
        pass
    return response


# ── Rate Limiting ───────────────────────────────────────────────────

_limiter = None


def _get_limiter():
    global _limiter
    if _limiter is None:
        from slowapi import Limiter
        from slowapi.util import get_remote_address

        from backend.config import get_settings

        settings = get_settings()
        if settings.rate_limit_enabled:
            _limiter = Limiter(
                key_func=get_remote_address,
                default_limits=[f"{settings.rate_limit_per_minute}/minute"],
            )
            app.state.limiter = _limiter
    return _limiter


# ── Unified Error Handler ─────────────────────────────────────────
# AR-01: The unified error handler is the single authority for error
# serialization. All error responses use the format:
#   {"error": {"code": "...", "message": "...", "hint": "..."}}
# with an X-Request-Id header (UUID4).


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    """Handle all APIError exceptions with standardized format."""
    request_id = str(uuid.uuid4())
    body = exc.to_dict()
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers={"X-Request-Id": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic/FastAPI validation errors (422) with standardized format."""
    request_id = str(uuid.uuid4())
    details = []
    for err in exc.errors():
        loc = ".".join(str(l) for l in err.get("loc", []))
        details.append(f"{loc}: {err.get('msg', 'validation error')}")
    message = "; ".join(details) if details else "Validation error"
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "UNPROCESSABLE_ENTITY",
                "message": message,
                "hint": "Check request body fields against the API schema",
            }
        },
        headers={"X-Request-Id": request_id},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions with standardized format."""
    request_id = str(uuid.uuid4())
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "hint": f"Quote request ID {request_id} when reporting this issue",
            }
        },
        headers={"X-Request-Id": request_id},
    )


# ── Routes ─────────────────────────────────────────────────────────

_auth = [Depends(verify_api_key)]

app.include_router(
    pipeline.router, prefix="/api/v1/pipeline", tags=["pipeline"], dependencies=_auth
)
app.include_router(ideas.router, prefix="/api/v1/ideas", tags=["ideas"], dependencies=_auth)
app.include_router(gaps.router, prefix="/api/v1/gaps", tags=["gaps"], dependencies=_auth)
app.include_router(
    knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"], dependencies=_auth
)
app.include_router(status.router, prefix="/api/v1/status", tags=["status"], dependencies=_auth)
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"], dependencies=_auth)
app.include_router(
    governance.router, prefix="/api/v1/governance", tags=["governance"], dependencies=_auth
)
app.include_router(costs.router, prefix="/api/v1/costs", tags=["costs"], dependencies=_auth)
app.include_router(traces.router, prefix="/api/v1/traces", tags=["traces"], dependencies=_auth)
app.include_router(
    literature.router, prefix="/api/v1/literature", tags=["literature"], dependencies=_auth
)
app.include_router(
    knowledge_graph.router,
    prefix="/api/v1/knowledge-graph",
    tags=["knowledge-graph"],
    dependencies=_auth,
)


@app.on_event("startup")
async def startup():
    from backend.db.database import init_db

    init_db()

    from backend.config import get_settings
    from backend.logging_config import configure_logging

    configure_logging(get_settings().debug)

    _get_limiter()


@app.get("/health", summary="Health check", description="Returns platform health status and version.")
async def health():
    """Health check endpoint.

    Returns:
        {"status": "ok", "version": "0.1.0"}
    """
    return {"status": "ok", "version": "0.1.0"}
