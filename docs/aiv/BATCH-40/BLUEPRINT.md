# BATCH-40 BLUEPRINT — Gap Detail Page

**Batch ID:** BATCH-40 | **Version:** 1.0 | **Cycle Mode:** STANDARD  
**Lead:** Lead Agent | **Date:** 2026-05-02  
**SLAs:** Review 30min | Execution 60min | Partial 15min | **Sequencing:** Sequential  

## BATCH GOAL
Create a dedicated gap detail page at /gaps/:id showing full gap information, truth values, cluster membership, related ideas, and navigation.

## SCOPE
**MUST:**
1. Create GapDetailPage component in frontend/src/pages/gap-detail.tsx
2. Add /gaps/:id route to App.tsx
3. Display title, description, gap type, confidence, truth values, potential impact
4. Show "Related Ideas" section (ideas linked via source_gap_ids)
5. Show "Cluster Membership" section
6. Make GapCard navigate to /gaps/:id on click
7. Back button to Gaps Explorer

**MUST NOT:** Add gap feedback (BATCH-41), gap-to-paper navigation (BATCH-45), modify backend API

## HARD BOUNDARIES
- HB-01: Page renders within 2 seconds
- HB-02: GapCard click navigates to /gaps/:id
- HB-03: Back button returns to Gaps Explorer
- HB-04: No existing test may break

## DATA MODELS
GET /gaps/{id} response (backend/api/routes/gaps.py — already exists):
```json
{"gap": {"id": 1, "title": "...", "description": "...", "gap_type": "methodological",
  "confidence": 0.85, "potential_impact": "high", "idea_count": 3,
  "pipeline_run_id": 1, "created_at": "2026-05-02T14:30:00"}}
```

Post BATCH-39, the list endpoint also returns truth and related_clusters. The get_gap detail endpoint needs the same enrichment.

Frontend ResearchGap type (post BATCH-39):
```ts
{ id, title, description, gap_type, confidence, potential_impact, idea_count,
  truth?: { frequency, confidence, evidence_count }, related_clusters?: number[] | null }
```

## TASK LIST

### TASK-01: Gap Detail Page Component
- Files: frontend/src/pages/gap-detail.tsx (new), frontend/src/App.tsx, frontend/src/components/gaps/gap-card.tsx, frontend/src/api/gaps.ts
- Tests: frontend/src/pages/__tests__/batch40-gap-detail.test.tsx
- 10 tests: title/description, gap type badge, confidence bar, truth values, related ideas, cluster membership, back button, not-found, loading skeleton, GapCard click navigation
- AC: /gaps/:id route works, all fields displayed, all tests pass

## BATCH ACCEPTANCE
- BAC-01: /gaps/:id route renders gap detail
- BAC-02: GapCard click navigates to detail page
- BAC-03: CHANGELOG.md updated
- BAC-04: Docs archived under /docs/aiv/BATCH-40/

## LEAD RESPONSE TO REVIEW
**Verdict:** APPROVE (Inline Review — 0 flags). Blueprint cleared for execution.
