"""Elephant Rock Research API — FastAPI application."""

import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.auth import get_current_user, verify_api_key
from backend.api.errors import APIError
from backend.api.routes import auth as auth_routes, collaboration, costs, evaluation, experiments, exports, gaps, governance, ideas, knowledge, knowledge_graph, literature, memory, model_config, notifications, pipeline, plugins, recombination, search, status, traces
from backend.api import ws as ws_module

app = FastAPI(
    title="Elephant Rock Research API",
    version="0.1.0",
    description="AI/NLP Research Idea Generation Platform",
)

# ── Middleware ──────────────────────────────────────────────────────


def _get_cors_origins() -> list[str]:
    from backend.config import get_settings

    return get_settings().effective_cors_origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
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

# Auth routes — always available (no API key dependency)
app.include_router(
    auth_routes.router, prefix="/api/v1/auth", tags=["auth"]
)

_auth = [Depends(verify_api_key)]

app.include_router(
    pipeline.router, prefix="/api/v1/pipeline", tags=["pipeline"], dependencies=_auth
)
app.include_router(ideas.router, prefix="/api/v1/ideas", tags=["ideas"], dependencies=_auth)
app.include_router(gaps.router, prefix="/api/v1/gaps", tags=["gaps"], dependencies=_auth)
app.include_router(search.router, prefix="/api/v1/search", tags=["search"], dependencies=_auth)
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
app.include_router(
    collaboration.router,
    prefix="/api/v1/ideas",
    tags=["collaboration"],
    dependencies=_auth,
)
# Public shared-idea endpoint (no auth required)
app.include_router(
    collaboration.router,
    prefix="/api/v1",
    tags=["shared"],
)
app.include_router(
    exports.router, prefix="/api/v1/export", tags=["export"], dependencies=_auth
)
app.include_router(
    plugins.router, prefix="/api/v1/plugins", tags=["plugins"], dependencies=_auth
)
app.include_router(
    model_config.router, prefix="/api/v1/settings", tags=["settings"], dependencies=_auth
)
app.include_router(
    notifications.router, prefix="/api/v1/notifications", tags=["notifications"], dependencies=_auth
)
app.include_router(
    experiments.router, prefix="/api/v1/experiments", tags=["experiments"], dependencies=_auth
)
app.include_router(
    recombination.router,
    prefix="/api/v1/recombination",
    tags=["recombination"],
    dependencies=_auth,
)

# Evaluation benchmarks (BATCH-RAG-01)
app.include_router(
    evaluation.router,
    prefix="/api/v1/evaluation",
    tags=["evaluation"],
    dependencies=_auth,
)

# WebSocket — no auth dependency; auth happens inside the handler
app.include_router(ws_module.router)


# ── JWT Auth Middleware (BATCH-28) ──────────────────────────────────

@app.middleware("http")
async def jwt_auth_middleware(request: Request, call_next):
    """When auth_enabled=True, validate JWT on all routes except auth endpoints."""
    from backend.config import get_settings
    from backend.api.auth import decode_access_token
    from backend.api.errors import UnauthorizedError

    settings = get_settings()
    path = request.url.path

    # Skip auth for public routes
    if not settings.auth_enabled:
        return await call_next(request)
    if path.startswith("/api/v1/auth/") or path == "/health" or path.startswith("/docs") or path.startswith("/openapi"):
        return await call_next(request)

    # Validate Bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError(detail="Authentication required", hint="Provide a Bearer token")

    try:
        decode_access_token(auth_header[7:])
    except UnauthorizedError:
        raise

    return await call_next(request)


@app.on_event("startup")
async def startup():
    from backend.db.database import init_db

    init_db()

    from backend.config import get_settings
    from backend.logging_config import configure_logging
    from backend.monitoring.sentry import init_sentry

    settings = get_settings()
    configure_logging(settings.debug)
    init_sentry(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )

    # Startup security warnings (BATCH-137, BATCH-140)
    import logging
    _log = logging.getLogger(__name__)

    # BATCH-140: Warn when debug is forced off in production
    if settings.is_production and settings.debug:
        _log.warning(
            "CONFIG: debug=True ignored in production mode (EROCK_ENV=production). "
            "Debug is forced off for security."
        )

    # BATCH-140: Production JWT secret enforcement (fires REGARDLESS of auth_enabled)
    if settings.is_production and settings.jwt_secret == "dev-secret-change-in-production":
        _log.error(
            "FATAL: Running in production with default JWT secret. "
            "Set EROCK_JWT_SECRET to a strong random string."
        )
        raise RuntimeError("Insecure JWT secret in production mode")

    # BATCH-137: Warn when JWT secret is default AND auth enabled (development only)
    if (
        not settings.is_production
        and settings.auth_enabled
        and settings.jwt_secret == "dev-secret-change-in-production"
    ):
        _log.warning(
            "SECURITY: JWT secret is the default value while auth_enabled=True. "
            "Change EROCK_JWT_SECRET in .env to a strong random string for production use."
        )

    # BATCH-137: Warn when no LLM API key is configured and LM Studio is disabled
    has_any_api_key = any([
        settings.openai_api_key,
        settings.anthropic_api_key,
        settings.gemini_api_key,
    ])
    if not has_any_api_key and not settings.lmstudio_enabled:
        _log.warning(
            "CONFIG: No LLM API key configured and LM Studio is disabled. "
            "Set at least one of EROCK_OPENAI_API_KEY, EROCK_ANTHROPIC_API_KEY, "
            "EROCK_GEMINI_API_KEY, or enable EROCK_LMSTUDIO_ENABLED=true for local inference."
        )

    # Warn about missing Semantic Scholar API key (BATCH-68)
    if not settings.semantic_scholar_api_key:
        _log.warning(
            "S2_API_KEY not set. Semantic Scholar API will be rate-limited (429 errors). "
            "Get a key at https://www.semanticscholar.org/product/api#api-key"
        )

    _get_limiter()

    # Initialize governance approval manager
    if settings.governance_enabled:
        from backend.api.routes.governance import set_approval_manager
        from backend.pipeline.governance.approval import ApprovalManager
        manager = ApprovalManager(timeout_seconds=settings.governance_approval_timeout)
        set_approval_manager(manager)
        _log.info("Governance approval manager initialized")

    # Initialize Universal Model Manager (dynamic model discovery + routing)
    try:
        from backend.providers.model_manager import get_model_manager
        mm = get_model_manager()
        await mm.initialize(settings)
        _log.info("Universal Model Manager initialized")
    except Exception as e:
        _log.warning(
            "Model Manager initialization failed (non-fatal): %s. "
            "Pipeline will use legacy provider factory.",
            e,
        )


@app.get("/health", summary="Health check", description="Returns platform health status and version.")
async def health():
    """Health check endpoint.

    Returns:
        {"status": "ok", "version": "0.1.0"}
    """
    return {"status": "ok", "version": "0.1.0"}
