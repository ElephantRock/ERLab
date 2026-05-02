# Memory

Query and manage the agent memory system — persistent knowledge across pipeline runs.

**Base path:** `/api/v1/memory`

---

## Recall Memories

`GET /api/v1/memory/recall`

Query the agent memory system for relevant stored knowledge.

### Query Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `query` | string | required | Natural language search query |
| `memory_type` | string | — | Filter by memory type |
| `top_k` | int | `10` | Maximum results (1–100) |

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/memory/recall?query=novel+transformer&top_k=10"
```

### Example Response

```json
{
  "query": "novel transformer",
  "results": [
    {
      "content": "Multi-head attention with adaptive span shows promise...",
      "type": "insight",
      "confidence": 0.85,
      "created_at": "2026-05-02 14:40:00"
    }
  ]
}
```

---

## Memory Statistics

`GET /api/v1/memory/stats`

Get memory system statistics.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/memory/stats
```

### Example Response

```json
{
  "total_entries": 128,
  "by_type": {
    "insight": 45,
    "gap": 30,
    "idea": 53
  },
  "persist_dir": "./data/memory"
}
```

---

## Delete a Memory Entry

`DELETE /api/v1/memory/{entry_id}`

Delete a specific memory entry.

### Example Request

```bash
curl -X DELETE -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/memory/mem_abc123
```

### Example Response

```json
{"status": "ok", "deleted_id": "mem_abc123"}
```
