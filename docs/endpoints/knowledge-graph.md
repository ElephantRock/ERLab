# Knowledge Graph

Interactive entity-relationship graph for explored research domains.

**Base path:** `/api/v1/knowledge-graph`

---

## World Model Summary

`GET /api/v1/knowledge-graph/world-model`

Returns a high-level world model summary with top entities, strongest relationships,
and type distribution.

### Example Request

```bash
curl -H "X-API-Key: your-key" \
  http://localhost:8000/api/v1/knowledge-graph/world-model
```

### Example Response

```json
{
  "top_entities": [
    {"id": "ent_1", "name": "Transformer", "entity_type": "method", "confidence": 0.95},
    {"id": "ent_2", "name": "Attention Mechanism", "entity_type": "concept", "confidence": 0.92}
  ],
  "strongest_relationships": [
    {"source": "Transformer", "target": "Attention Mechanism", "type": "uses", "weight": 0.98}
  ],
  "type_distribution": {
    "method": 15,
    "concept": 22,
    "dataset": 8,
    "metric": 5
  }
}
```

---

## Knowledge Graph Statistics

`GET /api/v1/knowledge-graph/stats`

Get overall statistics for the knowledge graph.

### Example Response

```json
{
  "total_entities": 50,
  "total_relationships": 120,
  "entity_types": {"method": 15, "concept": 22, "dataset": 8, "metric": 5},
  "relation_types": {"uses": 30, "evaluates_on": 20, "improves": 25, "cites": 45}
}
```

---

## List Entities

`GET /api/v1/knowledge-graph/entities`

List all entities in the knowledge graph with optional type filter.

### Query Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `entity_type` | string | — | Filter by entity type |
| `limit` | int | `20` | Max results |
| `offset` | int | `0` | Results to skip |

### Example Response

```json
{
  "entities": [
    {
      "id": "ent_1",
      "entity_type": "method",
      "name": "Transformer",
      "aliases": ["Transformers", "Transformer architecture"],
      "properties": {"year": 2017, "paper": "Attention Is All You Need"},
      "truth": {"confidence": 0.95, "frequency": 42, "source_count": 12}
    }
  ]
}
```

---

## Get Entity with Relationships

`GET /api/v1/knowledge-graph/entities/{entity_id}`

Get a single entity with all its relationships (both incoming and outgoing).

### Example Response

```json
{
  "entity": {
    "id": "ent_1",
    "entity_type": "method",
    "name": "Transformer",
    "aliases": ["Transformers"],
    "properties": {"year": 2017}
  },
  "relationships": [
    {"target_id": "ent_2", "target_name": "Attention Mechanism", "relation_type": "uses", "weight": 0.98},
    {"target_id": "ent_5", "target_name": "BERT", "relation_type": "basis_for", "weight": 0.90}
  ]
}
```

---

## Get Connected Subgraph

`GET /api/v1/knowledge-graph/entities/{entity_id}/subgraph`

Get a connected subgraph centered on a specific entity, expanding to N hops.

### Query Parameters

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `depth` | int | `2` | Number of hops to expand |
| `max_nodes` | int | `50` | Maximum nodes in subgraph |

### Example Response

```json
{
  "center": "ent_1",
  "nodes": [
    {"id": "ent_1", "name": "Transformer", "type": "method"},
    {"id": "ent_2", "name": "Attention Mechanism", "type": "concept"}
  ],
  "edges": [
    {"source": "ent_1", "target": "ent_2", "type": "uses", "weight": 0.98}
  ]
}
```
