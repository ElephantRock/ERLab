# Traces & Observability

Distributed tracing and metrics for all pipeline operations.

**Base path:** `/api/v1/traces`

---

## Trace Summary

`GET /api/v1/traces/summary`

Summary of all in-memory traces.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/traces/summary
```

### Example Response

```json
{
  "total_traces": 42,
  "active_traces": 3,
  "error_rate": 0.05
}
```

---

## Get Trace Spans

`GET /api/v1/traces/trace/{trace_id}`

Get all spans for a specific trace by its ID.

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/traces/trace/abc-123
```

### Example Response

```json
{
  "trace_id": "abc-123",
  "spans": [
    {
      "name": "generation",
      "duration_ms": 1500,
      "status": "ok",
      "attributes": {"model": "gpt-4o", "tokens": 1200}
    },
    {
      "name": "novelty",
      "duration_ms": 800,
      "status": "ok",
      "attributes": {"comparison_count": 15}
    }
  ]
}
```

---

## Trace Metrics

`GET /api/v1/traces/metrics`

Current metrics snapshot for all observed operations.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/traces/metrics
```

### Example Response

```json
{
  "operations": {
    "pipeline.run": {"count": 42, "avg_duration_ms": 45000, "p99_duration_ms": 120000},
    "generation": {"count": 210, "avg_duration_ms": 3000, "p99_duration_ms": 8000},
    "novelty_check": {"count": 210, "avg_duration_ms": 1500, "p99_duration_ms": 4000}
  }
}
```
