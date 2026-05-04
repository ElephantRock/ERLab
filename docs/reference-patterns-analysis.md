# Reference Patterns Analysis
## From: dify-main, langfuse-main, openlit-main, deepeval-main, posthog-master, mlflow-master

---

## 1. FastAPI Dependency Injection with Graceful Error Handling (503 vs 500)

### Pattern A: PostHog LLM Gateway — Chained `Depends()` with `Annotated` Type Aliases

**File:** `C:\Next AI\ref\posthog-master\posthog-master\services\llm-gateway\src\llm_gateway\dependencies.py`

**Key Pattern:** FastAPI dependencies chained via `Annotated` types, each adding a layer of validation. Services are pulled from `app.state` (set at startup). If the service isn't configured, the dependency itself raises an appropriate HTTP error.

```python
from typing import Annotated
from fastapi import Depends, HTTPException, Request, status

# 1. Pull service from app.state (set at startup)
async def get_db_pool(request: Request) -> "asyncpg.Pool[asyncpg.Record]":
    pool: asyncpg.Pool[asyncpg.Record] = request.app.state.db_pool
    return pool

# 2. Chain dependencies — each one validates and raises appropriate errors
async def get_authenticated_user(
    request: Request,
    db_pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthenticatedUser:
    user = await auth_service.authenticate_request(request, db_pool)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user

# 3. Export reusable type aliases for clean route signatures
DBPool = Annotated[asyncpg.Pool, Depends(get_db_pool)]
CurrentUser = Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
ProductAccessUser = Annotated[AuthenticatedUser, Depends(enforce_product_access)]
RateLimitedUser = Annotated[AuthenticatedUser, Depends(enforce_throttles)]
```

**Usage in routes:**
```python
# File: services/llm-gateway/src/llm_gateway/api/usage.py
@usage_router.get("/{product}")
async def get_usage(
    product: str,
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> UsageResponse:
    runner: ThrottleRunner = request.app.state.throttle_runner  # direct from app.state
    ...
```

**Why this works:** The dependency chain ensures that if any upstream service (DB, auth, rate limiter) is unavailable, the error is caught and translated to the appropriate HTTP status code (401, 403, 429) — never a raw 500.

---

### Pattern B: MLflow Gateway — `AIGatewayException` → `translate_http_exception` Decorator

**File:** `C:\Next AI\ref\mlflow-master\mlflow-master\libs\skinny\mlflow\gateway\exceptions.py`

```python
class AIGatewayException(Exception):
    """Custom exception with explicit status_code, transformed to HTTPException before reaching client."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
```

**File:** `C:\Next AI\ref\mlflow-master\mlflow-master\libs\skinny\mlflow\gateway\utils.py`

```python
def translate_http_exception(func):
    """Decorator for translating MLflow exceptions to HTTP exceptions"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except AIGatewayException as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail)
        except MlflowException as e:
            raise HTTPException(
                status_code=e.get_http_status_code(),
                detail={"error_code": e.error_code, "message": e.message},
            )
    return wrapper
```

**Usage in provider base (returns 501 for unimplemented):**
```python
# File: libs/skinny/mlflow/gateway/providers/base.py
async def _chat(self, payload):
    raise AIGatewayException(
        status_code=501,
        detail=f"The chat route is not implemented for {self.DISPLAY_NAME} models.",
    )
```

**Usage in route handlers (via decorator):**
```python
# File: libs/skinny/mlflow/gateway/app.py
def _create_chat_endpoint(prov: Provider):
    @translate_http_exception  # <-- catches AIGatewayException → HTTPException
    async def _chat(request, payload):
        if payload.stream:
            return await make_streaming_response(prov.chat_stream(payload))
        else:
            return await prov.chat(payload)
    return _chat
```

**Key insight:** The `AIGatewayException` pattern separates *business logic errors* (with specific status codes like 501, 503, 422) from *framework errors*. The `translate_http_exception` decorator is the bridge. This prevents 500s from leaking through.

---

### Pattern C: MLflow Agent Server — 503 for Proxy/Service Unavailability

**File:** `C:\Next AI\ref\mlflow-master\mlflow-master\libs\skinny\mlflow\genai\agent_server\server.py`

```python
try:
    # ... proxy request to chat app ...
except httpx.ConnectError:
    return Response("Service unavailable", status_code=503, media_type="text/plain")
except Exception as e:
    return Response(f"Proxy error: {e!s}", status_code=502, media_type="text/plain")
```

**Key insight:** `ConnectError` (service not running) → 503. Generic proxy error → 502. This is exactly the "graceful degradation" pattern for optional services.

---

### Pattern D: MLflow Exception → HTTP Status Code Mapping

**File:** `C:\Next AI\ref\mlflow-master\mlflow-master\libs\skinny\mlflow\exceptions.py`

```python
ERROR_CODE_TO_HTTP_STATUS = {
    ErrorCode.Name(INTERNAL_ERROR): 500,
    ErrorCode.Name(NOT_IMPLEMENTED): 501,
    ErrorCode.Name(TEMPORARILY_UNAVAILABLE): 503,  # <-- KEY: maps to 503
    ErrorCode.Name(DEADLINE_EXCEEDED): 504,
    ErrorCode.Name(REQUEST_LIMIT_EXCEEDED): 429,
    # ...
}

class MlflowException(Exception):
    def get_http_status_code(self):
        return ERROR_CODE_TO_HTTP_STATUS.get(self.error_code, 500)
```

---

### Pattern E: PostHog — `ClickHouseAtCapacity` (503)

**File:** `C:\Next AI\ref\posthog-master\posthog-master\posthog\exceptions.py`

```python
class ClickHouseAtCapacity(APIException):
    status_code = 503
    default_detail = "Queries are a little too busy right now. We're working to free up resources. Please try again later."
```

---

## 2. Integration Testing Patterns for LLM/AI Pipelines

### Pattern A: Dify — TestContainers for Real Service Integration

**File:** `C:\Next AI\ref\dify-main\api\tests\test_containers_integration_tests\conftest.py`

**Key approach:** Spin up real Docker containers (PostgreSQL, Redis, Sandbox, Plugin Daemon) using `testcontainers`. Tests run against actual services, not mocks.

```python
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network

class DifyTestContainers:
    def start_containers_with_env(self):
        # Create Docker network for inter-container communication
        self.network = Network()
        self.network.create()

        # Real PostgreSQL
        self.postgres = PostgresContainer(image="postgres:14-alpine").with_network(self.network)
        self.postgres.start()
        os.environ["DB_HOST"] = self.postgres.get_container_host_ip()
        os.environ["DB_PORT"] = str(self.postgres.get_exposed_port(5432))

        # Real Redis
        self.redis = RedisContainer(image="redis:6-alpine", port=6379).with_network(self.network)
        self.redis.start()

        # Graceful degradation: optional container failure doesn't crash the suite
        try:
            self.dify_plugin_daemon.start()
            # ...
        except Exception as e:
            logger.warning("Failed to start Dify Plugin Daemon container: %s", e)
            logger.info("Continuing without plugin daemon - some tests may be limited")
            self.dify_plugin_daemon = None

# Session-scoped: containers start once, shared across all tests
@pytest.fixture(scope="session")
def set_up_containers_and_env():
    _container_manager.start_containers_with_env()
    yield _container_manager
    _container_manager.stop_containers()

# Per-test DB session with transactional isolation
@pytest.fixture
def db_session_with_containers(flask_app_with_containers):
    with flask_app_with_containers.app_context():
        session = db.session()
        try:
            yield session
        finally:
            session.close()
```

**Why this is better than mocking:** Tests exercise real SQL queries, real Redis cache behavior, real Flask middleware stack. The only thing mocked is outbound HTTP (SSRF proxy).

---

### Pattern B: DeepEval — `skipif` for Real API Keys + Stub Models

**File:** `C:\Next AI\ref\deepeval-main\tests\test_core\test_evaluation\test_end_to_end\test_configs.py`

```python
import os
import pytest

# Tests only run when real API key is available
pytestmark = pytest.mark.skipif(
    os.getenv("OPENAI_API_KEY") is None or not os.getenv("OPENAI_API_KEY").strip(),
    reason="needs OPENAI_API_KEY",
)

class TestEvaluate:
    def test_skip_on_missing_params(self):
        test_case = LLMTestCase(input="What is the capital of France?", actual_output="Paris")
        evaluation_result = evaluate(
            test_cases=[test_case],
            metrics=[FaithfulnessMetric()],
            error_config=ErrorConfig(skip_on_missing_params=True),
        )
        assert evaluation_result.test_results[0].success
```

**File:** `C:\Next AI\ref\deepeval-main\tests\test_core\stubs.py` — Comprehensive test stubs that simulate real behavior:

```python
class AlwaysJsonModel:
    """Test stub that always returns JSON text — simulates LLM response
    without making network calls, but exercises real parsing logic."""

    def __init__(self, extractor: Callable[[str], str]):
        self._extractor = extractor

    def generate(self, prompt: str) -> str:
        return self._extractor(prompt)

    @staticmethod
    def balanced_json_after_anchor(anchor_text: str) -> Callable[[str], str]:
        """Returns an extractor that finds the first balanced JSON object after the given anchor."""
        def extractor(prompt: str) -> str:
            anchor_index = prompt.find(anchor_text)
            json_start_index = prompt.find("{", anchor_index)
            brace_depth = 0
            for char_index, character in enumerate(prompt[json_start_index:], start=json_start_index):
                if character == "{": brace_depth += 1
                elif character == "}":
                    brace_depth -= 1
                    if brace_depth == 0:
                        return prompt[json_start_index:char_index + 1]
            raise ValueError(f"Unbalanced braces after anchor '{anchor_text}'.")
        return extractor

class _SleepyMetric(BaseMetric):
    """Metric stub that sleeps to test timeout/retry behavior."""
    def __init__(self, name="sleepy", *, sleep_s=None, should_skip=False, succeed=False):
        self.sleep_s = sleep_s
        self.should_skip = should_skip
        self.succeed = succeed

    def measure(self, test_case, *_args, **_kwargs):
        if self.should_skip:
            self.skipped = True; return
        if self.sleep_s:
            time.sleep(self.sleep_s)
        self.success = bool(self.succeed)
```

**Key insight:** DeepEval distinguishes between:
1. **E2E tests** (need real `OPENAI_API_KEY`) — tagged with `skipif`
2. **Unit tests with realistic stubs** (`AlwaysJsonModel`, `_SleepyMetric`) — test parsing, retry, timeout logic without network
3. **Behavioral stubs** that exercise real code paths (balanced JSON parsing, retry decorators, async cancellation)

---

### Pattern C: DeepEval — Cancellation/Timeout Testing for LLM Calls

**File:** `C:\Next AI\ref\deepeval-main\tests\test_core\test_evaluation\test_execute\test_execute_llm_test_case.py`

```python
pytestmark = pytest.mark.skipif(
    os.getenv("OPENAI_API_KEY") is None or not os.getenv("OPENAI_API_KEY").strip(),
    reason="OPENAI_API_KEY is not set",
)

@pytest.mark.asyncio
async def test_llm_async_persists_metric_on_cancel(monkeypatch, ignore_errors):
    """Even if the test-case coroutine is cancelled, results must still be persisted."""
    metric = AnswerRelevancyMetric(model=GPTModel(model="gpt-5"))

    async def sleepy_a_measure(*args, **kwargs):
        await asyncio.sleep(3600)  # simulate a provider call that takes too long

    monkeypatch.setattr(metric, "a_measure", sleepy_a_measure, raising=True)

    coroutine = asyncio.wait_for(
        _a_execute_llm_test_cases(..., ignore_errors=ignore_errors, ...),
        timeout=0.05,  # small timeout forces cancellation
    )

    # Assert test results are still recorded even on cancellation
    recorded = trm.get_test_run()
    assert len(recorded.test_cases) == 1
```

---

### Pattern D: MLflow Integration Tests

**File:** `C:\Next AI\ref\mlflow-master\mlflow-master\tests\integration\`

MLflow keeps integration tests minimal and focused:

```
tests/integration/
├── async_logging/test_async_logging_integration.py
└── utils.py
```

**File:** `C:\Next AI\ref\mlflow-master\mlflow-master\dev\benchmarks\gateway\fake_server.py` — Fake LLM server for benchmarking:

MLflow uses a fake server that responds like a real LLM provider for load testing. This is the "realistic fake" pattern — exercises the full HTTP stack without hitting real APIs.

---

## 3. API Health Check Patterns for Optional Services

### Pattern A: PostHog — Role-Based Health Checks with Conditional Dependencies

**File:** `C:\Next AI\ref\posthog-master\posthog-master\posthog\health.py`

**This is the gold standard for health checks with optional services.**

```python
ServiceRole = Literal["events", "web", "worker", "decide", "query", "report"]

# Each role declares its REQUIRED dependencies
service_dependencies: dict[ServiceRole, list[str]] = {
    "events": ["http", "kafka_connected"],
    "web": ["http", "postgres", "cache"],
    "worker": ["http", "postgres", "clickhouse", "celery_broker"],
    "decide": ["http"],
    "query": ["http", "postgres", "cache"],
}

# Optional: at least ONE must be healthy (OR logic)
service_conditional_dependencies: dict[ServiceRole, list[str]] = {
    "decide": ["cache", "postgres_flags"],
}

def readyz(request: HttpRequest):
    """Returns 503 if any required dependency is unhealthy, 200 otherwise."""
    if is_shutting_down():
        return JsonResponse({"shutting_down": True}, status=503)

    # Run each check — each returns bool, never raises
    evaluated_checks = {name: check() for name, check in available_checks.items()}

    # 200 only if ALL required checks pass (excluding excluded ones)
    prelim_status = (
        200 if all(v for k, v in evaluated_checks.items() if k not in exclude) else 503
    )

    # Conditional: at least ONE must pass (OR logic)
    if prelim_status == 200 and evaluated_conditional_checks:
        status = 200 if any(v for _, v in evaluated_conditional_checks.items()) else 503
    else:
        status = prelim_status

    return JsonResponse({...}, status=status)

# Each checker NEVER raises — always returns bool
def is_postgres_connected() -> bool:
    try:
        with connections[db_alias].cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("postgres_connection_failure")
        return False
    return True

def is_kafka_connected() -> bool:
    return can_connect_to_kafka()  # returns bool, never raises

# Middleware intercepts health paths before any other middleware
def healthcheck_middleware(get_response):
    def middleware(request):
        if request.path == "/_readyz": return readyz(request)
        elif request.path == "/_livez": return livez(request)
        return get_response(request)
    return middleware
```

**Key design decisions:**
1. **Two endpoints:** `/_livez` (minimal, just "is the process alive?") vs `/_readyz` (full dependency checks)
2. **Role-based:** Each service role has different critical dependencies
3. **Never raise:** Every checker catches all exceptions and returns `False`
4. **Conditional deps:** "At least one of cache/postgres_flags must work" (OR logic)
5. **Exclude parameter:** `?exclude=clickhouse` lets you say "degraded but functional"

---

### Pattern B: MLflow Gateway — Simple Health Endpoint

**File:** `C:\Next AI\ref\mlflow-master\mlflow-master\libs\skinny\mlflow\gateway\app.py`

```python
@app.get(MLFLOW_DEPLOYMENTS_HEALTH_ENDPOINT)
@app.get(MLFLOW_GATEWAY_HEALTH_ENDPOINT, include_in_schema=False)
async def health() -> HealthResponse:
    return {"status": "OK"}
```

### Pattern C: MLflow Agent Server — Health with Registered Function Check

```python
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
```

---

## 4. Data Directory / Self-Improvement Initialization Patterns

### Pattern A: DeepEval — `DotenvHandler` with Auto-Create

**File:** `C:\Next AI\ref\deepeval-main\deepeval\config\dotenv_handler.py`

```python
from pathlib import Path

class DotenvHandler:
    def __init__(self, path: Path):
        self.path = Path(path)

    def upsert(self, mapping: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)  # auto-create dir
        self.path.touch(exist_ok=True)                        # auto-create file
        for key, value in mapping.items():
            set_key(str(self.path), key, value, quote_mode="always")
```

### Pattern B: DeepEval — Dataset Save with Lazy Dir Creation

**File:** `C:\Next AI\ref\deepeval-main\deepeval\dataset\dataset.py` (line 1023)

```python
if not os.path.exists(directory):
    os.makedirs(directory)
```

### Pattern C: DeepEval — Test Run with Parent Dir Creation

**File:** `C:\Next AI\ref\deepeval-main\deepeval\test_run\test_run.py` (line 527)

```python
os.makedirs(parent, exist_ok=True)
```

### Pattern D: DeepEval Config System — `.deepeval` Directory Convention

**File:** `C:\Next AI\ref\deepeval-main\deepeval\config\settings.py`

DeepEval uses a `.deepeval` config directory in the project root, similar to how many tools use dot-directories. Settings are auto-loaded from both `.env` files and JSON config.

---

## Summary: Recommended Patterns for Elephant Rock

### For Graceful 503 on Missing Services:

1. **Adopt the MLflow `AIGatewayException` pattern** — explicit `status_code` on every exception, with a `translate_http_exception` decorator on route handlers
2. **Adopt PostHog's dependency chain** — `Annotated[Type, Depends(getter)]` type aliases that pull from `app.state`
3. **Key rule:** Dependencies should NEVER raise unhandled exceptions. Return `None`/`False` and let the route handler or a wrapper dependency raise the appropriate HTTP status

### For Integration Tests:

1. **Use `pytest.mark.skipif` for tests needing real API keys** — tests run in CI without keys, run locally with keys
2. **Build realistic stubs (not mocks)** — DeepEval's `AlwaysJsonModel` pattern: stubs that exercise real parsing/formatting logic without network calls
3. **Use testcontainers for database/service integration** — Dify's pattern of session-scoped Docker containers
4. **Test cancellation/timeout paths** — verify that LLM calls that hang or get cancelled still persist results

### For Health Checks:

1. **Two endpoints:** liveness (`/_livez`) and readiness (`/_readyz`)
2. **Each checker returns `bool`, never raises**
3. **Support role-based dependency lists** — different services need different backends
4. **Support `exclude` parameter** for degraded-mode health checks
