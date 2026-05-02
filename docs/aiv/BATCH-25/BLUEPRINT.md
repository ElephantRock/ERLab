BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-25
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02

BATCH GOAL: Interactive knowledge graph visualization with entity detail,
filtering, and search.

HB-01: Graph visualization MUST use client-side rendering only (D3 or simple canvas).
HB-02: Initial render MUST be limited to 100 entities. Lazy-load on filter.

DATA MODELS:
  KnowledgeEntity: {id, entity_type, name, aliases, properties, truth: {confidence, source_count}}
  KnowledgeRelationship: {source_id, target_id, relation_type, weight, evidence, truth}
  KnowledgeGraph methods: get_entity, get_neighbors, entity_count, get_graph_stats

  NEW endpoints (backend/api/routes/knowledge_graph.py):
    GET /api/v1/knowledge-graph/stats → {entity_count, relationship_count, entity_types: {...}}
    GET /api/v1/knowledge-graph/entities?type=...&search=...&limit=100 → Entity[]
    GET /api/v1/knowledge-graph/entity/{id} → Entity + relationships
    GET /api/v1/knowledge-graph/subgraph/{id}?depth=2 → {entities, relationships}

DEPENDENCY: BATCH-24
BASELINE: ~1,741 | Delta: +16 (6 backend + 10 frontend) | Target: ~1,757

TASK LIST (SEQUENTIAL):
───────────────────────────────────────────────────────────

TASK-01: Backend — Knowledge Graph API Routes
  Files: backend/api/routes/knowledge_graph.py (NEW)
         backend/api/app.py (MODIFY — register)
  Tests: TEST-25-01-01: GET /stats returns entity/relationship counts
         TEST-25-01-02: GET /entities returns entity list (limit 100)
         TEST-25-01-03: GET /entities?type=X filters by type
         TEST-25-01-04: GET /entity/{id} returns entity with relationships
         TEST-25-01-05: GET /subgraph/{id} returns connected subgraph
         TEST-25-01-06: Entity not found returns 404
  Commit: feat(batch-25/task-01): add knowledge graph API endpoints

TASK-02: Frontend — Graph API Client
  Files: frontend/src/api/knowledge-graph.ts (NEW)
  Tests: TEST-25-02-01: getGraphStats() correct endpoint
         TEST-25-02-02: getEntities() accepts type/search params
         TEST-25-02-03: getEntity(id) correct endpoint
         TEST-25-02-04: getSubgraph(id, depth) correct endpoint
  Commit: feat(batch-25/task-02): add knowledge graph API client

TASK-03: Frontend — Graph Canvas Component
  Files: frontend/src/components/knowledge-graph/graph-canvas.tsx (NEW)
         frontend/src/components/knowledge-graph/entity-detail.tsx (NEW)
  Tests: TEST-25-03-01: GraphCanvas renders with entities
         TEST-25-03-02: Entity click shows detail panel
         TEST-25-03-03: Type filter updates visible entities
  Commit: feat(batch-25/task-03): add knowledge graph canvas and entity detail

TASK-04: Frontend — Knowledge Graph Page
  Files: frontend/src/pages/knowledge-graph.tsx (NEW)
         frontend/src/App.tsx (MODIFY — add /knowledge-graph route + sidebar item)
         frontend/src/components/layout/sidebar.tsx (MODIFY — add nav item)
  Tests: TEST-25-04-01: Page renders with stats
         TEST-25-04-02: Search filters entities
         TEST-25-04-03: Click entity shows detail panel
  Commit: feat(batch-25/task-04): add knowledge graph explorer page

BAC: BAC-01 Graph visualization works | BAC-02 CHANGELOG | BAC-03 docs
LEAD RESPONSE: Inline review. KnowledgeGraph service verified. ACCEPT.
Lead Sign: Lead + 2026-05-02 09:30

═══════════════════════════════════════════════════════════
