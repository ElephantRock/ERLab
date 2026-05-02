# Sessions

Manage pipeline sessions — group multiple runs under a session with budget and state controls.

**Base path:** `/api/v1/pipeline/sessions`

!!! note "Part of Pipeline Router"
    Session endpoints are served by the pipeline router under `/api/v1/pipeline/sessions`.

---

## Create Session

`POST /api/v1/pipeline/sessions`

### Request Body

| Field | Type | Description |
|:------|:-----|:------------|
| `name` | string | Session name |
| `max_runs` | int | Maximum pipeline runs allowed |
| `max_cost_usd` | float | Maximum cost budget in USD |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/sessions \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Session", "max_runs": 10, "max_cost_usd": 50.0}'
```

### Example Response

```json
{
  "id": "sess_abc123",
  "name": "My Session",
  "state": "active",
  "run_count": 0,
  "max_runs": 10,
  "max_cost_usd": 50.0,
  "created_at": "2026-05-02 14:30:00"
}
```

---

## List Sessions

`GET /api/v1/pipeline/sessions`

### Query Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `state` | string | — | Filter by state: `active`, `paused`, `ended` |
| `limit` | int | `20` | Max results |

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/pipeline/sessions?state=active&limit=20"
```

### Example Response

```json
{
  "sessions": [
    {"id": "sess_abc", "name": "My Session", "state": "active", "run_count": 3}
  ]
}
```

---

## Session Actions

| Endpoint | Method | Description |
|:---------|:-------|:------------|
| `/sessions/{id}/activate` | POST | Activate a session |
| `/sessions/{id}/pause` | POST | Pause a session |
| `/sessions/{id}/resume` | POST | Resume a paused session |
| `/sessions/{id}/end` | POST | End a session permanently |
| `/sessions/{id}/budget` | GET | Check session budget usage |

### Example: Check Budget

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/sessions/sess_abc123/budget
```

### Example Response

```json
{
  "session_id": "sess_abc123",
  "max_cost_usd": 50.0,
  "used_cost_usd": 12.50,
  "remaining_cost_usd": 37.50,
  "max_runs": 10,
  "used_runs": 3,
  "remaining_runs": 7
}
```
