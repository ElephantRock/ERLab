# BATCH-37 CHANGELOG

## TASK-01: World Model Viewer
**Commit:** `feat(batch-37/task-01): add world model viewer to knowledge graph`
**Status:** ✅ Complete

### Changes

#### Backend — `backend/api/routes/knowledge_graph.py` (MODIFY)
- Added `GET /knowledge-graph/world-model` endpoint
- Returns high-level summary: total counts, entity/relationship type distributions, top 10 entities by confidence, top 10 strongest relationships by weight

#### Frontend — `frontend/src/api/knowledge-graph.ts` (MODIFY)
- Added `WorldModel` interface
- Added `getWorldModel()` API function

#### Frontend — `frontend/src/components/knowledge-graph/world-model-panel.tsx` (NEW)
- `WorldModelPanel` component: displays world model summary with entity types, relationship types, top entities, and strongest relationships

#### Frontend — `frontend/src/pages/knowledge-graph.tsx` (MODIFY)
- Added `WorldModelPanel` import and `useQuery` hook for world model data
- Renders panel above the filters section

### Tests (3/3 ✅)

| Test ID | Description | Result |
|---------|-------------|--------|
| TEST-37-01-01 | `GET /knowledge-graph/world-model` returns model data with correct counts, distributions, top entities, and strongest relationships | ✅ PASSED |
| TEST-37-01-02 | `WorldModelPanel` renders header, summary stats, entity type tags, and relationship type tags | ✅ PASSED |
| TEST-37-01-03 | `WorldModelPanel` shows top entity names and strongest relationship source/target/relation | ✅ PASSED |

### Files Modified
```
backend/api/routes/knowledge_graph.py              |  +45
backend/tests/test_api/test_knowledge_graph.py     |  +37
frontend/src/api/knowledge-graph.ts                |  +17
frontend/src/components/knowledge-graph/
  world-model-panel.tsx                            | +126 (NEW)
  __tests__/graph-components.test.tsx              |  +64
frontend/src/pages/knowledge-graph.tsx             |  +9
```

**Delta: +309 lines, −3 lines | Target: ~1,865 ✅**
