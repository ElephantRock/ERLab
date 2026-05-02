# Literature

Search academic literature and ingest papers into the knowledge base.

**Base path:** `/api/v1/literature`

---

## Search Literature

`GET /api/v1/literature/search`

Search across multiple academic sources (Semantic Scholar, arXiv, OpenAlex) with deduplication.

### Query Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `q` | string | required | Search query string |
| `max_results` | int | `10` | Maximum results (1–100) |

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  "http://localhost:8000/api/v1/literature/search?q=transformer+attention&max_results=5"
```

### Example Response

```json
{
  "papers": [
    {
      "title": "Attention Is All You Need",
      "authors": ["Ashish Vaswani", "..."],
      "year": 2017,
      "abstract": "...",
      "source": "semantic_scholar",
      "doi": "10.48550/arXiv.1706.03762",
      "citation_count": 95000
    }
  ]
}
```

---

## Ingest Paper

`POST /api/v1/literature/ingest`

Ingest a paper into the knowledge base for semantic search.

### Request Body

Paper fields (inherits from `Paper` model). The `title` field is required for confirmation.

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/literature/ingest \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"title": "Attention Is All You Need", "authors": ["Vaswani et al."], "year": 2017}'
```

### Example Response

```json
{"status": "ok", "title": "Attention Is All You Need", "chunks_indexed": 12}
```
