# Collaboration

Comments, replies, and sharing for research ideas — team collaboration workflows.

**Base path:** `/api/v1/collaboration`

---

## Add a Comment

`POST /api/v1/collaboration/{idea_id}/comments`

Add a comment (or reply) to a research idea.

### Request Body

| Field | Type | Default | Description |
|:------|:-----|:--------|:------------|
| `author` | string | `"anonymous"` | Comment author name (max 128 chars) |
| `content` | string | required | Comment text (1–5000 chars) |
| `parent_id` | int | `null` | Parent comment ID for threaded replies |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/collaboration/1/comments \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"author": "alice", "content": "Great idea! Consider adding evaluation on low-resource languages."}'
```

### Example Response

```json
{
  "id": 1,
  "idea_id": 1,
  "author": "alice",
  "content": "Great idea! Consider adding evaluation on low-resource languages.",
  "parent_id": null,
  "created_at": "2026-05-02 15:00:00"
}
```

---

## List Comments

`GET /api/v1/collaboration/{idea_id}/comments`

List all comments for a research idea.

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/collaboration/1/comments
```

### Example Response

```json
{
  "idea_id": 1,
  "comments": [
    {
      "id": 1,
      "author": "alice",
      "content": "Great idea! Consider adding evaluation...",
      "parent_id": null,
      "created_at": "2026-05-02 15:00:00"
    }
  ]
}
```

---

## Create Share Link

`POST /api/v1/collaboration/{idea_id}/share`

Generate a shareable link for a research idea.

### Example Request

```bash
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/collaboration/1/share
```

### Example Response

```json
{
  "share_token": "shr_abc123def456",
  "idea_id": 1,
  "share_url": "/shared/shr_abc123def456",
  "created_at": "2026-05-02 15:05:00"
}
```

---

## Get Shared Idea

`GET /api/v1/collaboration/shared/{token}`

Retrieve a shared idea by its share token. No authentication required.

### Example Request

```bash
curl http://localhost:8000/api/v1/collaboration/shared/shr_abc123def456
```

### Example Response

```json
{
  "idea": {
    "id": 1,
    "title": "Adaptive Attention for Low-Resource NMT",
    "domain": "AI/NLP",
    "overall_score": 0.79
  }
}
```
