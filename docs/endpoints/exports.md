# Exports

Export research ideas as PDF or bulk ZIP archives.

**Base path:** `/api/v1/exports`

---

## Export Idea as PDF

`POST /api/v1/exports/pdf`

Generate and download a PDF for one or more research ideas.

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/exports/pdf \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"idea_ids": [1, 2, 3]}'
```

### Response

Returns a PDF file as `application/pdf` binary stream.

```
Content-Type: application/pdf
Content-Disposition: attachment; filename="elephant-rock-export.pdf"
```

---

## Bulk Export as ZIP

`POST /api/v1/exports/bulk`

Export multiple ideas with all their reports and proposals as a ZIP archive.

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/exports/bulk \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"idea_ids": [1, 2, 3], "include_proposals": true}'
```

### Response

Returns a ZIP file as `application/zip` binary stream.

```
Content-Type: application/zip
Content-Disposition: attachment; filename="elephant-rock-bulk-export.zip"
```

The ZIP contains:

```
elephant-rock-bulk-export/
├── idea-1.json        # Full idea data
├── idea-1-proposal.md # Proposal markdown (if include_proposals=true)
├── idea-2.json
├── idea-2-proposal.md
└── ...
```
