# Costs

Track token usage and costs across pipeline runs, providers, and models.

**Base path:** `/api/v1/costs`

---

## Cost Summary

`GET /api/v1/costs/summary`

Total cost summary across all recorded cost events.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/costs/summary
```

### Example Response

```json
{
  "total_cost_usd": 1.23,
  "total_tokens": 150000,
  "event_count": 42
}
```

---

## Cost by Provider

`GET /api/v1/costs/by-provider`

Cost breakdown grouped by LLM provider.

### Example Response

```json
{
  "openai": {
    "cost_usd": 0.5,
    "input_tokens": 1000,
    "output_tokens": 500,
    "calls": 10
  },
  "anthropic": {
    "cost_usd": 0.73,
    "input_tokens": 2000,
    "output_tokens": 800,
    "calls": 15
  }
}
```

---

## Cost by Stage

`GET /api/v1/costs/by-stage`

Cost breakdown grouped by pipeline stage.

### Example Response

```json
{
  "generation": {"cost_usd": 0.45, "tokens": 50000},
  "novelty": {"cost_usd": 0.30, "tokens": 35000},
  "feasibility": {"cost_usd": 0.25, "tokens": 30000},
  "synthesis": {"cost_usd": 0.23, "tokens": 35000}
}
```

---

## Cost by Model

`GET /api/v1/costs/by-model`

Cost breakdown grouped by provider and model.

### Example Response

```json
{
  "openai/gpt-4o": {"cost_usd": 0.80, "tokens": 80000, "calls": 20},
  "anthropic/claude-3-haiku": {"cost_usd": 0.43, "tokens": 70000, "calls": 22}
}
```

---

## Cost for a Specific Run

`GET /api/v1/costs/run/{run_id}`

Load persisted cost events for a specific pipeline run.

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/costs/run/run_20260502_143000
```

### Example Response

```json
{
  "run_id": "run_20260502_143000",
  "events": [
    {"stage": "generation", "provider": "openai", "model": "gpt-4o", "cost_usd": 0.15, "tokens": 12000}
  ],
  "total_cost_usd": 0.45
}
```
