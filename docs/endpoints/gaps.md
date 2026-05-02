# Gaps

View and explore research gaps detected during pipeline runs.

**Base path:** `/api/v1/gaps`

---

## List Research Gaps

`GET /api/v1/gaps/`

List research gaps from a pipeline run. Uses the latest completed run if `run_id` is omitted.

### Query Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `run_id` | int | — | Pipeline run ID (latest if omitted) |
| `limit` | int | `20` | Max results (1–100) |
| `offset` | int | `0` | Number of results to skip |

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/gaps/?run_id=1&limit=20"
```

### Example Response

```json
{
  "gaps": [
    {
      "id": 1,
      "title": "Limited cross-domain evaluation",
      "description": "Most approaches only evaluate on a single domain...",
      "gap_type": "methodological",
      "confidence": 0.85,
      "potential_impact": "high"
    }
  ],
  "total": 5,
  "run_id": 1
}
```

---

## Get Gap Details

`GET /api/v1/gaps/{gap_id}`

Retrieve full details for a specific research gap.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/gaps/1
```

### Example Response

```json
{
  "id": 1,
  "title": "Limited cross-domain evaluation",
  "description": "Most approaches only evaluate on a single domain...",
  "gap_type": "methodological",
  "confidence": 0.85,
  "potential_impact": "high",
  "related_ideas_count": 3,
  "run_id": 1,
  "created_at": "2026-05-02 14:33:00"
}
```
