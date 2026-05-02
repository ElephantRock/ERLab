# Governance

Human-in-the-loop approval workflow for critical pipeline decisions.

**Base path:** `/api/v1/governance`

---

## List Pending Approvals

`GET /api/v1/governance/pending`

List all pending governance approvals awaiting human decision.

### Example Request

```bash
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/governance/pending
```

### Example Response

```json
{
  "pending": [
    {
      "id": "gap_001",
      "type": "gap_approval",
      "summary": "Methodological gap in cross-domain evaluation"
    }
  ]
}
```

---

## Approve a Decision

`POST /api/v1/governance/{decision_id}/approve`

Approve a pending governance decision.

### Example Request

```bash
curl -X POST -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/governance/gap_001/approve
```

### Example Response

```json
{"status": "approved", "decision_id": "gap_001"}
```

---

## Deny a Decision

`POST /api/v1/governance/{decision_id}/deny`

Deny a pending decision with an optional amendment.

### Request Body

| Field | Type | Description |
|:------|:-----|:------------|
| `amendment` | string | Optional feedback or requested changes |

### Example Request

```bash
curl -X POST http://localhost:8000/api/v1/governance/gap_001/deny \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"amendment": "Please refine the methodology section"}'
```

### Example Response

```json
{"status": "denied", "decision_id": "gap_001", "amendment": "Please refine the methodology section"}
```
