BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID: BATCH-37 | Version: 1.0 | SIMPLIFIED | Lead | 2026-05-02

SIMPLIFIED: 1 Task, new endpoint + new component only.

BATCH GOAL: World model panel on knowledge graph page.

TASK-01: World Model Viewer
  Files: backend/api/routes/knowledge_graph.py (MODIFY — add /world-model endpoint)
         frontend/src/components/knowledge-graph/world-model-panel.tsx (NEW)
         frontend/src/pages/knowledge-graph.tsx (MODIFY — add panel)
  Tests: TEST-37-01-01: GET /knowledge-graph/world-model returns model data
         TEST-37-01-02: World model panel renders
         TEST-37-01-03: Panel shows entity relationships
  Commit: feat(batch-37/task-01): add world model viewer to knowledge graph

DEPENDENCY: BATCH-34
BASELINE: ~1,862 | Delta: +3 | Target: ~1,865
BAC: ✓ | Lead Sign: Lead + 2026-05-02 12:35
═══════════════════════════════════════════════════════════
