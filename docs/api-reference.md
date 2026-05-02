# Elephant Rock Research API Guide

> Base URL: `http://localhost:8000/api/v1`
> Authentication: `X-API-Key` header (if configured)

---

## Table of Contents

1. [Health Check](#health-check)
2. [Platform Status](#platform-status)
3. [Pipeline](#pipeline)
4. [Ideas](#ideas)
5. [Gaps](#gaps)
6. [Knowledge Base](#knowledge-base)
7. [Memory](#memory)
8. [Governance](#governance)
9. [Cost Tracking](#cost-tracking)
10. [Traces & Observability](#traces--observability)
11. [Error Responses](#error-responses)

---

## Health Check

### `GET /health`

Returns platform health status. **No authentication required.**

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{"status": "ok", "version": "0.1.0"}
```

---

## Platform Status

### `GET /api/v1/status`

Returns platform configuration and enabled features.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/status
```

**Response:**
```json
{
  "app_name": "Elephant Rock",
  "version": "0.1.0",
  "config": {
    "default_provider": "openai",
    "memory_enabled": true,
    "self_improve_enabled": false,
    "autonomy_enabled": false,
    "budget_enabled": false,
    "governance_enabled": false
  },
  "defaults": {
    "generation_rounds": 3,
    "ideas_per_round": 5,
    "novelty_top_k": 20
  }
}
```

---

## Pipeline

### `POST /api/v1/pipeline/run`

Start a new research pipeline run. Returns immediately with a `run_id`.

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/run \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "AI/NLP",
    "max_gaps": 5,
    "generation_rounds": 2,
    "ideas_per_round": 3,
    "run_novelty": true,
    "run_feasibility": true,
    "run_synthesis": true
  }'
```

**Response (202):**
```json
{"run_id": "run_20260502_143000", "status": "running"}
```

### `GET /api/v1/pipeline/runs`

List pipeline runs with pagination.

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/pipeline/runs?limit=20&offset=0"
```

**Response:**
```json
{
  "runs": [
    {
      "id": 1,
      "status": "completed",
      "domain": "AI/NLP",
      "current_stage": "done",
      "ideas_count": 5,
      "created_at": "2026-05-02 14:30:00",
      "completed_at": "2026-05-02 14:45:00",
      "error_message": null
    }
  ],
  "total": 1
}
```

### `GET /api/v1/pipeline/runs/detail/{run_id}`

Get full run details by database ID.

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/runs/detail/1
```

### `GET /api/v1/pipeline/runs/{run_id_str}/progress`

Stream pipeline progress via Server-Sent Events (SSE).

```bash
curl -N -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/pipeline/runs/run_20260502_143000/progress"
```

**SSE Events:**
```
data: {"stage": "generation", "index": 1, "total": 5, "elapsed": 2.3}
data: {"stage": "novelty", "index": 2, "total": 5, "elapsed": 5.1}
data: {"done": true}
```

### `DELETE /api/v1/pipeline/runs/{run_id_str}`

Cancel a running pipeline.

```bash
curl -X DELETE -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/runs/run_20260502_143000
```

### `POST /api/v1/pipeline/resume/{run_id}`

Resume a failed pipeline from its last checkpoint.

```bash
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/resume/run_20260502_143000
```

### `POST /api/v1/pipeline/autonomous`

Start an autonomous research cycle.

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/autonomous \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"domain": "AI/NLP", "max_runs": 3}'
```

### Scheduler Endpoints

```bash
# Start scheduler
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/scheduler/start

# Stop scheduler
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/scheduler/stop

# Scheduler status
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/scheduler/status
```

### Session Endpoints

```bash
# Create session
curl -X POST http://localhost:8000/api/v1/pipeline/sessions \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Session", "max_runs": 10, "max_cost_usd": 50.0}'

# List sessions
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/pipeline/sessions?state=active&limit=20"

# Get session
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/sessions/sess_abc123

# Activate session
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/sessions/sess_abc123/activate

# Pause session
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/sessions/sess_abc123/pause

# Resume session
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/sessions/sess_abc123/resume

# End session
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/sessions/sess_abc123/end

# Check session budget
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/sessions/sess_abc123/budget
```

---

## Ideas

### `GET /api/v1/ideas/`

List research ideas with optional filters.

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/ideas/?domain=AI/NLP&min_score=0.5&limit=20&offset=0"
```

### `GET /api/v1/ideas/{idea_id}`

Get full idea details with reports and proposals.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/ideas/1
```

### `POST /api/v1/ideas/{idea_id}/feedback`

Submit user feedback for an idea.

```bash
curl -X POST http://localhost:8000/api/v1/ideas/1/feedback \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"rating": 4, "notes": "Strong methodology, needs more evaluation detail"}'
```

### `POST /api/v1/ideas/{idea_id}/refine`

Re-run novelty, feasibility, and synthesis for an idea.

```bash
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/ideas/1/refine
```

---

## Gaps

### `GET /api/v1/gaps/`

List research gaps. Uses latest completed run if `run_id` omitted.

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/gaps/?run_id=1&limit=20"
```

### `GET /api/v1/gaps/{gap_id}`

Get gap details.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/gaps/1
```

---

## Knowledge Base

### `GET /api/v1/knowledge/stats`

Get knowledge base configuration.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/knowledge/stats
```

### `POST /api/v1/knowledge/search`

Semantic search across the knowledge base.

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer attention mechanisms", "top_k": 10}'
```

---

## Memory

### `GET /api/v1/memory/recall`

Query the agent memory system.

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/memory/recall?query=novel+transformer&top_k=10"
```

### `GET /api/v1/memory/stats`

Get memory system statistics.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/memory/stats
```

### `DELETE /api/v1/memory/{entry_id}`

Delete a memory entry.

```bash
curl -X DELETE -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/memory/mem_abc123
```

---

## Governance

### `GET /api/v1/governance/pending`

List all pending governance approvals.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/governance/pending
```

### `POST /api/v1/governance/{decision_id}/approve`

Approve a pending decision.

```bash
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/governance/gap_001/approve
```

### `POST /api/v1/governance/{decision_id}/deny`

Deny a pending decision with optional amendment.

```bash
curl -X POST http://localhost:8000/api/v1/governance/gap_001/deny \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"amendment": "Please refine the methodology section"}'
```

---

## Cost Tracking

### `GET /api/v1/costs/summary`

Total cost summary.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/costs/summary
```

### `GET /api/v1/costs/by-provider`

Cost breakdown by provider.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/costs/by-provider
```

### `GET /api/v1/costs/by-stage`

Cost breakdown by pipeline stage.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/costs/by-stage
```

### `GET /api/v1/costs/by-model`

Cost breakdown by provider/model.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/costs/by-model
```

### `GET /api/v1/costs/run/{run_id}`

Load persisted cost events for a specific run.

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/costs/run/run_20260502_143000
```

---

## Traces & Observability

### `GET /api/v1/traces/summary`

Summary of all in-memory traces.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/traces/summary
```

### `GET /api/v1/traces/trace/{trace_id}`

Get all spans for a specific trace.

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/traces/trace/abc-123
```

### `GET /api/v1/traces/metrics`

Current metrics snapshot.

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/traces/metrics
```

---

## Error Responses

All error responses use a standardized format:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "hint": "Check the resource ID and try again"
  }
}
```

| HTTP Status | Code | Description |
|:-----------:|:-----|:------------|
| 400 | `BAD_REQUEST` | Malformed request |
| 401 | `UNAUTHORIZED` | Invalid or missing API key |
| 404 | `NOT_FOUND` | Resource not found |
| 422 | `UNPROCESSABLE_ENTITY` | Validation error |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 500 | `PROVIDER_CONFIG_ERROR` | LLM provider misconfigured |
| 503 | `SERVICE_UNAVAILABLE` | Feature disabled or unavailable |

Every error response includes an `X-Request-Id` header (UUID4) for tracing.

### Example Error: 401 Unauthorized

```
HTTP/1.1 401 Unauthorized
X-Request-Id: a1b2c3d4-e5f6-7890-abcd-ef1234567890

{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or missing API key",
    "hint": "Provide a valid API key via the X-API-Key header"
  }
}
```

### Example Error: 404 Not Found

```
HTTP/1.1 404 Not Found
X-Request-Id: f9e8d7c6-b5a4-3210-fedc-ba0987654321

{
  "error": {
    "code": "NOT_FOUND",
    "message": "Idea not found"
  }
}
```

### Example Error: 422 Validation Error

```
HTTP/1.1 422 Unprocessable Entity
X-Request-Id: 1234abcd-5678-ef90-cdef-1234567890ab

{
  "error": {
    "code": "UNPROCESSABLE_ENTITY",
    "message": "body.rating: Input should be greater than or equal to 1",
    "hint": "Check request body fields against the API schema"
  }
}
```
