# Pipeline

Pipeline execution, run management, sessions, scheduler, and autonomous cycles.

**Base path:** `/api/v1/pipeline`

---

## Trigger Pipeline Run

`POST /api/v1/pipeline/run`

Start a new research pipeline run. Returns `202` immediately with a `run_id`.

### Request Body

| Field | Type | Default | Description |
|:------|:-----|:--------|:------------|
| `domain` | string | required | Research domain (e.g., `"AI/NLP"`) |
| `max_gaps` | int | `5` | Maximum gaps to detect |
| `generation_rounds` | int | `3` | Number of generation rounds |
| `ideas_per_round` | int | `5` | Ideas generated per round |
| `run_novelty` | bool | `true` | Run novelty checking |
| `run_feasibility` | bool | `true` | Run feasibility scoring |
| `run_synthesis` | bool | `true` | Run proposal synthesis |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/run \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"domain": "AI/NLP", "max_gaps": 5, "generation_rounds": 2, "ideas_per_round": 3}'
```

### Example Response (202)

```json
{"run_id": "run_20260502_143000", "status": "running"}
```

---

## List Pipeline Runs

`GET /api/v1/pipeline/runs`

### Query Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `limit` | int | `20` | Max results |
| `offset` | int | `0` | Results to skip |

### Example Response

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

---

## Get Run Details

`GET /api/v1/pipeline/runs/detail/{run_id}`

Get full run details by database ID.

---

## Stream Pipeline Progress

`GET /api/v1/pipeline/runs/{run_id_str}/progress`

Stream pipeline progress via **Server-Sent Events (SSE)**.

### Example Request

```bash
curl -N -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/pipeline/runs/run_20260502_143000/progress"
```

### SSE Events

```
data: {"stage": "generation", "index": 1, "total": 5, "elapsed": 2.3}
data: {"stage": "novelty", "index": 2, "total": 5, "elapsed": 5.1}
data: {"done": true}
```

---

## Cancel a Pipeline Run

`DELETE /api/v1/pipeline/runs/{run_id_str}`

### Example Request

```bash
curl -X DELETE -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/pipeline/runs/run_20260502_143000
```

### Example Response

```json
{"status": "cancelled", "run_id": "run_20260502_143000"}
```

---

## Resume a Pipeline

`POST /api/v1/pipeline/resume/{run_id}`

Resume a failed pipeline from its last checkpoint.

### Example Response

```json
{"run_id": "run_20260502_143000", "status": "running", "resumed_from": "novelty"}
```

---

## Sessions

### Create Session

`POST /api/v1/pipeline/sessions`

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/sessions \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Session", "max_runs": 10, "max_cost_usd": 50.0}'
```

### List Sessions

`GET /api/v1/pipeline/sessions?state=active&limit=20`

### Session Actions

| Endpoint | Method | Description |
|:---------|:-------|:------------|
| `/sessions/{id}/activate` | POST | Activate a session |
| `/sessions/{id}/pause` | POST | Pause a session |
| `/sessions/{id}/resume` | POST | Resume a paused session |
| `/sessions/{id}/end` | POST | End a session |
| `/sessions/{id}/budget` | GET | Check session budget |

---

## Autonomous Cycle

| Endpoint | Method | Description |
|:---------|:-------|:------------|
| `/pipeline/autonomous` | POST | Start autonomous research cycle |
| `/pipeline/autonomous/stop` | POST | Stop autonomous cycle |
| `/pipeline/autonomous/history` | GET | Get autonomous cycle history |

### Example: Start Autonomous Cycle

```bash
curl -X POST http://localhost:8000/api/v1/pipeline/autonomous \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"domain": "AI/NLP", "max_runs": 3}'
```

---

## Scheduler

| Endpoint | Method | Description |
|:---------|:-------|:------------|
| `/pipeline/scheduler/start` | POST | Start the scheduler |
| `/pipeline/scheduler/stop` | POST | Stop the scheduler |
| `/pipeline/scheduler/status` | GET | Get scheduler status |
