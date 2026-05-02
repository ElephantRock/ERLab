# Knowledge Base

Manage the semantic knowledge base — statistics, search, and document ingestion.

**Base path:** `/api/v1/knowledge`

---

## Knowledge Base Statistics

`GET /api/v1/knowledge/stats`

Get knowledge base configuration and enriched statistics including document and chunk counts.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/knowledge/stats
```

### Example Response

```json
{
  "chroma_persist_dir": "./data/chroma",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "total_documents": 5,
  "total_chunks": 42
}
```

---

## Search Knowledge Base

`POST /api/v1/knowledge/search`

Semantic search across the knowledge base.

### Request Body

| Field | Type | Default | Description |
|:------|:-----|:--------|:------------|
| `query` | string | required | Natural language search query |
| `top_k` | int | `10` | Maximum number of results |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer attention mechanisms", "top_k": 10}'
```

### Example Response

```json
{
  "query": "transformer attention mechanisms",
  "results": [
    {
      "content": "Multi-head attention allows the model to attend to information...",
      "source": "paper_123.pdf",
      "chunk_id": "chunk_456",
      "score": 0.92
    }
  ]
}
```

---

## Upload and Ingest PDF

`POST /api/v1/knowledge/upload`

Upload a PDF file and ingest it into the knowledge base.

### Request

Send a `multipart/form-data` request with the PDF file.

!!! warning "File Validation"
    Only valid PDF files are accepted. The system checks for the `%PDF` magic header
    to prevent executable or malicious file uploads.

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/upload \
  -H "X-API-Key: your-key" \
  -F "file=@research-paper.pdf"
```

### Example Response

```json
{
  "status": "ok",
  "filename": "research-paper.pdf",
  "chunks_indexed": 15
}
```
