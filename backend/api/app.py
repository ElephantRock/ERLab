"""Elephant Rock Research API — FastAPI application."""

import time

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.auth import verify_api_key
from backend.api.errors import APIError
from backend.api.routes import costs, gaps, governance, ideas, knowledge, memory, pipeline, status, traces

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


# ── Exception Handlers ─────────────────────────────────────────────


@app.exception_handler(APIError)
async def api_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def generic_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


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


@app.on_event("startup")
async def startup():
    from backend.db.database import init_db

    init_db()

    from backend.config import get_settings
    from backend.logging_config import configure_logging

    configure_logging(get_settings().debug)

    _get_limiter()


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
