# Ideas

Manage research ideas — list, retrieve, provide feedback, and refine.

**Base path:** `/api/v1/ideas`

---

## List Research Ideas

`GET /api/v1/ideas/`

List research ideas with optional domain, score, search, and sort filters.

### Query Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `domain` | string | — | Filter by domain (e.g., `"AI/NLP"`) |
| `min_score` | float | `0.0` | Minimum overall score (0.0–1.0) |
| `search` | string | — | Full-text keyword search on title |
| `sort_by` | string | — | Sort field: `score`, `novelty`, `feasibility`, `date` |
| `sort_order` | string | `desc` | Sort direction: `desc` or `asc` |
| `limit` | int | `20` | Max results (1–100) |
| `offset` | int | `0` | Number of results to skip |

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/ideas/?domain=AI/NLP&min_score=0.5&limit=20"
```

### Example Response

```json
{
  "ideas": [
    {
      "id": 1,
      "title": "Adaptive Attention for Low-Resource NMT",
      "domain": "AI/NLP",
      "problem_statement": "...",
      "proposed_method": "...",
      "novelty_score": 0.82,
      "feasibility_score": 0.75,
      "overall_score": 0.79,
      "created_at": "2026-05-02 14:35:00"
    }
  ],
  "total": 42,
  "score_guide": {"excellent": 0.8, "good": 0.6, "fair": 0.4, "poor": 0.2}
}
```

---

## Get Idea Details

`GET /api/v1/ideas/{idea_id}`

Retrieve full idea details including reports and proposals.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/ideas/1
```

### Example Response

```json
{
  "id": 1,
  "title": "Adaptive Attention for Low-Resource NMT",
  "domain": "AI/NLP",
  "problem_statement": "...",
  "proposed_method": "...",
  "expected_contributions": "...",
  "novelty_score": 0.82,
  "feasibility_score": 0.75,
  "overall_score": 0.79,
  "novelty_report": "...",
  "feasibility_report": "...",
  "proposal_md": "# Research Proposal\n...",
  "created_at": "2026-05-02 14:35:00"
}
```

---

## Submit Feedback

`POST /api/v1/ideas/{idea_id}/feedback`

Submit user feedback for an idea.

### Request Body

| Field | Type | Description |
|:------|:-----|:------------|
| `rating` | int | Rating (1–5) |
| `notes` | string | Optional text feedback |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/ideas/1/feedback \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"rating": 4, "notes": "Strong methodology, needs more evaluation detail"}'
```

### Example Response

```json
{"status": "ok", "idea_id": 1, "feedback_id": 7}
```

---

## Refine an Idea

`POST /api/v1/ideas/{idea_id}/refine`

Re-run novelty, feasibility, and synthesis for an existing idea.

### Example Request

```bash
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/ideas/1/refine
```

### Example Response

```json
{"status": "ok", "idea_id": 1, "message": "Idea refined with updated scores"}
```
