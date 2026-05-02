# Recommendations Implementation Roadmap — AIV Framework v5.1

**Lead Programmer:** Lead Agent  
**Date Issued:** 2026-05-02  
**Framework:** AIV v5.1 (binding)  
**Baseline:** 286 frontend tests, 1,428 backend tests, 142 commits, BATCH-37 closed  
**Next Batch:** BATCH-38  

---

## Roadmap Summary

10 Batches across 4 Phases, executed in 6 Waves. Each Batch follows the full AIV lifecycle: Blueprint → Review → Lead Response → Execution → Report → Partial Sign-Off → Certificate.

| Wave | Batches | Parallelism | Focus |
|:---|:---|:---|:---|
| 1 | BATCH-38 | Sequential | Gap data integrity — persist truth values, cluster reports, related clusters |
| 2 | BATCH-39 | Sequential | Gap API enrichment — search, filter, sort, enriched responses |
| 3 | BATCH-40 | Sequential | Gap Detail Page — `/gaps/:id` route with full detail view |
| 4 | BATCH-41 + BATCH-42 | Parallel | Gap feedback/lifecycle + Cross-run deduplication |
| 5 | BATCH-43 + BATCH-44 | Parallel | Cluster visualization + Gap analytics dashboard |
| 6 | BATCH-45 + BATCH-46 + BATCH-47 | Parallel | Gap→paper navigation + Export + Global search |

**Estimated new tests:** ~98 (62 backend + 36 frontend)  
**Estimated final total:** ~1,812 tests  

---

## BATCH-38: Gap Data Persistence & Truth Values

**Cycle Mode:** STANDARD | **Tasks:** 2 | **Files:** backend/db/models.py, alembic/versions/002_gap_enrichment.py, backend/pipeline/persistence.py

### BATCH GOAL
Eliminate data loss in gap persistence by persisting TruthValue fields, related_clusters, and ClusterReport to the database, enabling faithful roundtrip reconstruction of ResearchGap objects.

### SCOPE
**MUST do:**
- Add truth_frequency, truth_confidence, truth_evidence_count columns to research_gaps
- Add related_clusters JSON Text column to research_gaps
- Add cluster_report_json JSON Text column to pipeline_runs
- Update persist_gaps() to write truth + related_clusters
- Add persist_cluster_report() to write cluster_report_json
- Update load_gaps() to reconstruct ResearchGap with truth and related_clusters
- Create Alembic migration 002_gap_enrichment

**MUST NOT do:** Modify frontend files, change /gaps API response shape, remove/rename existing columns, alter pipeline stage execution

### HARD BOUNDARIES
- **HB-01:** All new columns MUST have DEFAULT values (no data migration needed)
- **HB-02:** Alembic upgrade MUST use batch mode for SQLite compatibility
- **HB-03:** load_gaps() roundtrip fidelity — reconstruct identical ResearchGap objects
- **HB-04:** No existing test may break — baseline 1,714

### DATA MODELS
**ResearchGapDB new columns:**
- truth_frequency: Float, default=0.5
- truth_confidence: Float, default=0.5
- truth_evidence_count: Integer, default=0
- related_clusters: Text, nullable (JSON array string)

**PipelineRun new column:**
- cluster_report_json: Text, nullable (JSON object string)

### TASK LIST

**TASK-01: Database Schema Migration**
- Files: backend/db/models.py, alembic/versions/002_gap_enrichment.py
- Tests: migration upgrade creates columns, downgrade removes them, existing data survives
- AC: `alembic upgrade head` succeeds, all 5 columns have defaults, downgrade succeeds

**TASK-02: Update Persistence Layer**
- Files: backend/pipeline/persistence.py
- Tests: persist_gaps writes truth/related_clusters, persist_cluster_report writes JSON, load_gaps reconstructs with truth, full roundtrip fidelity
- AC: All truth columns populated, load_gaps returns matching objects, all 1,428 backend tests pass

### BATCH ACCEPTANCE
- BAC-01: All 5 new columns exist with correct types and defaults
- BAC-02: Roundtrip fidelity confirmed by integration test
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-38/

---

## BATCH-39: Gap API Search, Filter & Sort

**Cycle Mode:** STANDARD | **Tasks:** 2 | **Files:** backend/api/routes/gaps.py, backend/db/crud.py, frontend/src/pages/gaps-explorer.tsx, frontend/src/api/gaps.ts, frontend/src/api/types.ts

### BATCH GOAL
Add search, filter, sort, and enriched response fields to the gaps API and mirror those capabilities in the frontend Gaps Explorer.

### SCOPE
**MUST do:**
- Add search, gap_type, min_confidence, sort_by, sort_order params to GET /gaps/
- Add CRUD functions for filtered/sorted gap queries
- Include truth and related_clusters in gap API responses
- Add search input, type filter, confidence slider, sort dropdown to Gaps Explorer

**MUST NOT do:** Add new DB tables/columns (BATCH-38), create gap detail page (BATCH-40), modify pipeline

### HARD BOUNDARIES
- **HB-01:** All new query params optional with defaults matching current behavior
- **HB-02:** SQL injection prevention — parameterized queries only
- **HB-03:** Frontend shows "N gaps found" matching API total
- **HB-04:** No existing test may break

### DATA MODELS
**New GET /gaps/ params:** search (str), gap_type (str), min_confidence (float), sort_by (confidence|date|type), sort_order (asc|desc)

**New response fields per gap:**
- truth: { frequency, confidence, evidence_count }
- related_clusters: list[int] | null

**Frontend type additions:** truth?, related_clusters?

### TASK LIST

**TASK-01: Backend Gap Filter/Sort/Search API**
- Files: backend/api/routes/gaps.py, backend/db/crud.py
- Tests (8): search filter, gap_type filter, min_confidence filter, sort by confidence, sort by date, truth in response, SQL injection safety, default params reproduce current behavior
- AC: All params optional, invalid sort_by ignored gracefully

**TASK-02: Frontend Gaps Explorer Search/Filter/Sort**
- Files: frontend/src/pages/gaps-explorer.tsx, frontend/src/api/gaps.ts, frontend/src/api/types.ts
- Tests (6): search input renders, gap type filter 4 options, confidence slider, sort dropdown, filters passed as params, "N gaps found" displays
- AC: Mirrors Ideas Browser UX pattern, all 286 frontend tests pass

### BATCH ACCEPTANCE
- BAC-01: GET /gaps/ supports search, gap_type, min_confidence, sort_by, sort_order
- BAC-02: Gaps Explorer has search, filter, and sort controls
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-39/

---

## BATCH-40: Gap Detail Page

**Cycle Mode:** STANDARD | **Tasks:** 1 | **Files:** frontend/src/pages/gap-detail.tsx (new), frontend/src/App.tsx, frontend/src/components/gaps/gap-card.tsx, frontend/src/api/gaps.ts

### BATCH GOAL
Create a dedicated gap detail page at /gaps/:id showing full gap information, truth values, cluster membership, related ideas, and navigation.

### SCOPE
**MUST do:**
- Create GapDetailPage component with full gap information
- Add /gaps/:id route to App.tsx
- Display title, description, gap type, confidence, truth values, potential impact
- Show "Related Ideas" section (ideas linked via source_gap_ids)
- Show "Cluster Membership" section
- Make GapCard navigate to /gaps/:id on click
- Back button to Gaps Explorer

**MUST NOT do:** Add gap feedback (BATCH-41), gap-to-paper navigation (BATCH-45), modify backend API

### HARD BOUNDARIES
- **HB-01:** Page renders within 2 seconds
- **HB-02:** GapCard click navigates to /gaps/:id (no dead clicks)
- **HB-03:** Back button returns to Gaps Explorer
- **HB-04:** No existing test may break

### TASK LIST

**TASK-01: Gap Detail Page Component**
- Files: frontend/src/pages/gap-detail.tsx (new), frontend/src/App.tsx, frontend/src/components/gaps/gap-card.tsx, frontend/src/api/gaps.ts
- Tests (10): title/description render, gap type badge, confidence bar, truth values section, related ideas section, cluster membership section, back button navigation, not-found state, loading skeleton, GapCard click navigation
- AC: /gaps/:id route works, all fields displayed, all frontend tests pass

### BATCH ACCEPTANCE
- BAC-01: /gaps/:id route renders gap detail
- BAC-02: GapCard click navigates to detail page
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-40/

---

## BATCH-41: Gap Feedback & Lifecycle

**Cycle Mode:** STANDARD | **Tasks:** 2 | **Files:** backend/db/models.py, alembic/versions/003_gap_feedback.py, backend/db/crud.py, backend/api/routes/gaps.py, backend/api/schemas.py, frontend/src/components/gaps/gap-feedback-form.tsx (new), frontend/src/pages/gap-detail.tsx

### BATCH GOAL
Add user feedback (star rating + notes) and lifecycle status tracking to research gaps.

### SCOPE
**MUST do:**
- Add status, user_rating, user_notes columns to ResearchGapDB
- Create Alembic migration 003_gap_feedback
- Add POST /gaps/{id}/feedback and PATCH /gaps/{id}/status endpoints
- Add GapFeedbackForm component (star rating + notes)
- Add status dropdown on gap detail page

**MUST NOT do:** Add gap deduplication (BATCH-42), modify gap analysis pipeline

### HARD BOUNDARIES
- **HB-01:** status ∈ {identified, investigating, addressed} — 422 for others
- **HB-02:** user_rating ∈ [1, 5] — 422 for others
- **HB-03:** Forward-only lifecycle: identified → investigating → addressed — 422 for reversions
- **HB-04:** No existing test may break

### DATA MODELS
**ResearchGapDB new columns:**
- status: String(20), default="identified"
- user_rating: Integer, nullable
- user_notes: Text, nullable

### TASK LIST

**TASK-01: Backend Feedback & Status Endpoints**
- Files: backend/db/models.py, alembic/versions/003_gap_feedback.py, backend/db/crud.py, backend/api/routes/gaps.py, backend/api/schemas.py
- Tests (8): feedback success, rating validation (422), status transition success, invalid status (422), forward-only enforcement, response includes new fields, migration adds columns, existing tests pass

**TASK-02: Frontend Feedback Form & Status Dropdown**
- Files: frontend/src/components/gaps/gap-feedback-form.tsx (new), frontend/src/pages/gap-detail.tsx, frontend/src/api/gaps.ts, frontend/src/api/types.ts
- Tests (8): star rating renders with hover, click sets rating, submit disabled until rated, status dropdown 3 options, status change calls PATCH, success toast, notes 2000 char limit, existing tests pass

### BATCH ACCEPTANCE
- BAC-01: Users can rate gaps 1-5 stars and leave notes
- BAC-02: Users can transition gap status forward-only
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-41/

---

## BATCH-42: Cross-Run Gap Deduplication

**Cycle Mode:** STANDARD | **Tasks:** 1 | **Files:** backend/db/models.py, alembic/versions/004_gap_dedup.py, backend/db/crud.py, backend/pipeline/persistence.py, backend/api/routes/gaps.py

### BATCH GOAL
Prevent duplicate gap rows across pipeline runs by content-hash deduplication, with truth revision on existing rows.

### SCOPE
**MUST do:**
- Add canonical_id and content_hash columns to ResearchGapDB
- Create Alembic migration 004_gap_dedup
- Update persist_gaps() to check for existing gaps by content_hash
- When duplicate found: revise truth values using OpenNARS revision, skip insert
- Add GET /gaps/canonical endpoint for deduplicated view

**MUST NOT do:** Delete existing gap rows, modify gap analysis stage, change frontend

### HARD BOUNDARIES
- **HB-01:** content_hash deterministic — same title → same hash
- **HB-02:** Case-insensitive, strip non-word characters before hashing
- **HB-03:** Duplicate found → truth revision via OpenNARS revise(), never overwrite
- **HB-04:** No existing test may break

### DATA MODELS
**ResearchGapDB new columns:**
- canonical_id: String(128), nullable
- content_hash: String(64), nullable (SHA-256 of normalized title)

**Normalization:** lowercase → strip [^\w\s] → strip extra whitespace → SHA-256 hex

### TASK LIST

**TASK-01: Content Hash Dedup in Persistence**
- Files: backend/db/models.py, alembic/versions/004_gap_dedup.py, backend/db/crud.py, backend/pipeline/persistence.py, backend/api/routes/gaps.py
- Tests (6): deterministic hash, case-insensitive hashing, first persist sets canonical_id, second persist revises truth (no new row), canonical endpoint returns deduped data, existing tests pass
- AC: Duplicates get truth revision, canonical endpoint returns one per unique gap

### BATCH ACCEPTANCE
- BAC-01: No two rows with same content_hash
- BAC-02: GET /gaps/canonical returns deduplicated data
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-42/

---

## BATCH-43: Cluster Visualization

**Cycle Mode:** STANDARD | **Tasks:** 1 | **Files:** backend/api/routes/gaps.py, frontend/src/components/gaps/cluster-scatter.tsx (new), frontend/src/pages/gaps-explorer.tsx

### BATCH GOAL
Expose paper cluster data via API and render an interactive cluster visualization in the frontend Gaps Explorer.

### SCOPE
**MUST do:**
- Add GET /gaps/clusters endpoint returning cluster data for a run
- Create ClusterScatterPlot SVG component
- Add "Clusters" tab to Gaps Explorer page

**MUST NOT do:** Modify clustering algorithm, add analytics charts (BATCH-44), change pipeline execution

### HARD BOUNDARIES
- **HB-01:** Cluster endpoint returns cluster_report_json from PipelineRun; null → empty list
- **HB-02:** Client-side SVG only (no D3 dependency)
- **HB-03:** No existing test may break

### DATA MODELS
**GET /gaps/clusters response:** { clusters: [...], total_papers: N, run_id: ID }

Each cluster: { cluster_id, label, paper_count, top_terms, avg_citations }

### TASK LIST

**TASK-01: Cluster API + Scatter Visualization**
- Files: backend/api/routes/gaps.py, frontend/src/components/gaps/cluster-scatter.tsx (new), frontend/src/pages/gaps-explorer.tsx
- Tests (8): clusters endpoint returns data, null report returns [], no run_id → latest run, scatter renders dots with labels, clusters tab renders, paper count per cluster, empty state message, existing tests pass
- AC: SVG scatter per HB-02, data sourced from cluster_report_json per HB-01

### BATCH ACCEPTANCE
- BAC-01: GET /gaps/clusters endpoint returns cluster data
- BAC-02: Gaps Explorer has Clusters tab with scatter visualization
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-43/

---

## BATCH-44: Gap Analytics Dashboard

**Cycle Mode:** STANDARD | **Tasks:** 1 | **Files:** backend/api/routes/gaps.py, backend/db/crud.py, frontend/src/components/charts/gap-type-distribution.tsx (new), frontend/src/components/charts/gap-confidence-trend.tsx (new), frontend/src/pages/dashboard.tsx

### BATCH GOAL
Add aggregated gap analytics to the dashboard showing type distribution, confidence trends, and most-frequently-identified gaps across runs.

### SCOPE
**MUST do:**
- Add GET /gaps/stats endpoint with type distribution, avg confidence, top recurring gaps, confidence trend
- Create lazy-loaded gap chart components (type distribution + trend)
- Add "Top Gaps" section to Dashboard

**MUST NOT do:** Modify gap detail page, add cluster visualization (BATCH-43), change gap generation

### HARD BOUNDARIES
- **HB-01:** Stats endpoint returns within 500ms with 1000+ gaps
- **HB-02:** Chart components lazy-loaded (React.lazy + Suspense)
- **HB-03:** No existing test may break

### DATA MODELS
**GET /gaps/stats response:**
```json
{
  "type_distribution": { "methodological": 15, "empirical": 8 },
  "avg_confidence": 0.72,
  "total_gaps": 31,
  "top_gaps": [{ "title": "...", "frequency": 5, "avg_confidence": 0.88 }],
  "confidence_trend": [{ "run_id": 1, "avg_confidence": 0.65, "gap_count": 5 }]
}
```

### TASK LIST

**TASK-01: Stats API + Dashboard Charts**
- Files: backend/api/routes/gaps.py, backend/db/crud.py, frontend/src/components/charts/gap-type-distribution.tsx (new), frontend/src/components/charts/gap-confidence-trend.tsx (new), frontend/src/pages/dashboard.tsx
- Tests (10): type_distribution returned, top_gaps sorted by frequency, confidence_trend returned, empty DB returns zeros, type chart renders, trend chart renders, Top Gaps on dashboard, charts lazy-loaded, empty state message, existing tests pass
- AC: All 5 fields returned, charts lazy with Suspense, Top Gaps visible on Dashboard

### BATCH ACCEPTANCE
- BAC-01: GET /gaps/stats returns aggregated analytics
- BAC-02: Dashboard shows gap type distribution and top recurring gaps
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-44/

---

## BATCH-45: Gap-to-Paper Navigation & Related Gaps

**Cycle Mode:** STANDARD | **Tasks:** 1 | **Files:** backend/api/routes/gaps.py, backend/db/crud.py, frontend/src/pages/gap-detail.tsx, frontend/src/api/gaps.ts

### BATCH GOAL
Add navigation from gaps to their source papers and to related gaps that share cluster membership.

### SCOPE
**MUST do:**
- Add GET /gaps/{id}/papers endpoint returning papers from linked clusters
- Add GET /gaps/{id}/related endpoint returning gaps with shared clusters
- Add "Source Papers" section on gap detail page
- Add "Related Gaps" section on gap detail page

**MUST NOT do:** Modify gap analysis pipeline, add export (BATCH-46), change clustering

### HARD BOUNDARIES
- **HB-01:** Paper and related-gap endpoints return within 500ms
- **HB-02:** Source papers from same pipeline run as gap
- **HB-03:** Related gaps share at least one cluster with target
- **HB-04:** No existing test may break

### DATA MODELS
**GET /gaps/{id}/papers:** { papers: [{ id, title, abstract, year, venue, citation_count }], total: N }

**GET /gaps/{id}/related:** { gaps: [{ id, title, confidence, gap_type, shared_clusters }], total: N }

### TASK LIST

**TASK-01: Paper & Related Gap Navigation**
- Files: backend/api/routes/gaps.py, backend/db/crud.py, frontend/src/pages/gap-detail.tsx, frontend/src/api/gaps.ts
- Tests (8): papers endpoint returns data, related gaps endpoint returns data, papers from same run per HB-02, related gaps share clusters per HB-03, Source Papers section renders, Related Gaps section renders, empty states handled, existing tests pass
- AC: Both endpoints return correct data, both sections render on detail page

### BATCH ACCEPTANCE
- BAC-01: Gap detail page shows Source Papers and Related Gaps
- BAC-02: Navigation is bidirectional (gap↔paper, gap↔gap)
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-45/

---

## BATCH-46: Gap & Idea Export (CSV/JSON)

**Cycle Mode:** STANDARD | **Tasks:** 1 | **Files:** backend/api/routes/gaps.py, backend/api/routes/ideas.py, frontend/src/pages/gaps-explorer.tsx, frontend/src/pages/ideas-browser.tsx

### BATCH GOAL
Add CSV and JSON export for gaps and ideas, enabling researchers to download data for external analysis.

### SCOPE
**MUST do:**
- Add GET /gaps/export?format=csv|json endpoint
- Add GET /ideas/export?format=csv|json endpoint
- Add export buttons to Gaps Explorer and Ideas Browser
- CSV includes all visible columns; JSON matches API response shape

**MUST NOT do:** Add PDF export, modify data models, change any POST/PUT/PATCH endpoints

### HARD BOUNDARIES
- **HB-01:** Export endpoints respect same filters as list endpoints
- **HB-02:** CSV must be valid RFC 4180 (proper quoting, UTF-8 BOM)
- **HB-03:** Export button triggers browser download (not navigation)
- **HB-04:** No existing test may break

### DATA MODELS
**GET /gaps/export?format=csv&search=x&gap_type=y:** Returns file download
**GET /ideas/export?format=csv&search=x&domain=y:** Returns file download

### TASK LIST

**TASK-01: Export Endpoints & Frontend Buttons**
- Files: backend/api/routes/gaps.py, backend/api/routes/ideas.py, frontend/src/pages/gaps-explorer.tsx, frontend/src/pages/ideas-browser.tsx
- Tests (8): gaps CSV export returns valid CSV, gaps JSON export returns JSON array, ideas CSV export works, export respects filters per HB-01, CSV has BOM per HB-02, export button renders, button triggers download per HB-03, existing tests pass
- AC: Both formats work for both resources, filters applied

### BATCH ACCEPTANCE
- BAC-01: Gaps and Ideas can be exported as CSV and JSON
- BAC-02: Export respects current filter state
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-46/

---

## BATCH-47: Global Search Across All Resources

**Cycle Mode:** STANDARD | **Tasks:** 2 | **Files:** backend/api/routes/search.py (new), backend/api/app.py, frontend/src/components/layout/app-shell.tsx, frontend/src/components/layout/sidebar.tsx, frontend/src/pages/global-search.tsx (new), frontend/src/App.tsx

### BATCH GOAL
Add unified global search that searches across ideas, gaps, papers, and pipeline runs from a single interface.

### SCOPE
**MUST do:**
- Add GET /search?q=x&types=ideas,gaps,papers,runs endpoint
- Create GlobalSearchPage component with categorized results
- Add search icon/button in app shell header
- Add /search route to App.tsx
- Keyboard shortcut Ctrl+K to open search

**MUST NOT do:** Replace individual resource search (ideas search, gaps search remain), modify any pipeline behavior

### HARD BOUNDARIES
- **HB-01:** Global search returns results within 1 second
- **HB-02:** Results grouped by resource type with counts
- **HB-03:** Ctrl+K opens search from any page
- **HB-04:** No existing test may break

### DATA MODELS
**GET /search?q=x&types=ideas,gaps:**
```json
{
  "query": "transfer learning",
  "results": {
    "ideas": { "total": 5, "items": [...] },
    "gaps": { "total": 3, "items": [...] },
    "papers": { "total": 12, "items": [...] },
    "runs": { "total": 1, "items": [...] }
  },
  "total": 21
}
```

### TASK LIST

**TASK-01: Backend Global Search Endpoint**
- Files: backend/api/routes/search.py (new), backend/api/app.py
- Tests (6): search returns results from all types, type filter works, empty query returns empty, results grouped by type per HB-02, special characters handled safely, existing tests pass
- AC: Endpoint returns grouped results within HB-01 time limit

**TASK-02: Frontend Global Search UI**
- Files: frontend/src/components/layout/app-shell.tsx, frontend/src/components/layout/sidebar.tsx, frontend/src/pages/global-search.tsx (new), frontend/src/App.tsx
- Tests (8): search icon in header, Ctrl+K opens search per HB-03, search page renders with input, results grouped by type, clicking result navigates to resource, empty state shows "No results", loading state shows skeleton, existing tests pass
- AC: Ctrl+K works from any page, results are clickable

### BATCH ACCEPTANCE
- BAC-01: GET /search returns unified results across all resource types
- BAC-02: Ctrl+K opens global search from any page
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-47/

---

## Execution Summary

| Batch | Wave | Backend Tests | Frontend Tests | Total Delta |
|:------|:-----|:-------------|:---------------|:------------|
| BATCH-38 | 1 | +8 | +0 | +8 |
| BATCH-39 | 2 | +8 | +6 | +14 |
| BATCH-40 | 3 | +0 | +10 | +10 |
| BATCH-41 | 4 | +8 | +8 | +16 |
| BATCH-42 | 4 | +6 | +0 | +6 |
| BATCH-43 | 5 | +4 | +4 | +8 |
| BATCH-44 | 5 | +4 | +6 | +10 |
| BATCH-45 | 6 | +4 | +4 | +8 |
| BATCH-46 | 6 | +4 | +4 | +8 |
| BATCH-47 | 6 | +6 | +8 | +14 |
| **Total** | | **+52** | **+50** | **+102** |

**Estimated final test count:** 1,714 + 102 = **~1,816 tests**
**Estimated new documents:** 10 × 4-6 = ~50 AIV documents
**Estimated new git commits:** ~40-50
