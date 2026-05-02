# Recommendations Implementation Plan

**Date:** 2026-05-02  
**Baseline:** 286 frontend tests, 1,428 backend tests, 142 git commits  
**Source Studies:** Gap Analysis Deep Study, UX Journey Report, Comprehensive Study Report

---

## Overview

This plan consolidates **45 recommendations** from three studies into **10 implementation batches**, ordered by dependency chain and user impact. Each batch is a self-contained unit of work with clear deliverables, file lists, and test requirements.

**Total scope:** 10 batches covering 4 phases.

---

## Phase 1 — Data Integrity & API (Batches 1–2)

*Fix data loss, add missing API capabilities. Foundation for all downstream batches.*

---

### Batch 1: Gap Data Persistence & Truth Values

**Problem:** `ResearchGap.truth` (TruthValue), `related_clusters`, and `ClusterReport` are lost when gaps are persisted to the database. The `load_gaps()` reconstruction strips these fields.

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 1.1 | Add `truth_frequency`, `truth_confidence`, `truth_evidence_count` columns to `ResearchGapDB` | `backend/db/models.py` |
| 1.2 | Add `related_clusters` JSON Text column to `ResearchGapDB` | `backend/db/models.py` |
| 1.3 | Add `cluster_report_json` JSON Text column to `PipelineRun` | `backend/db/models.py` |
| 1.4 | Create Alembic migration `002_gap_enrichment.py` | `alembic/versions/002_gap_enrichment.py` |
| 1.5 | Update `persist_gaps()` to write truth + cluster data | `backend/pipeline/persistence.py` |
| 1.6 | Update `load_gaps()` to reconstruct truth + related_clusters | `backend/pipeline/persistence.py` |
| 1.7 | Persist `ClusterReport` to `PipelineRun.cluster_report_json` | `backend/pipeline/persistence.py` |
| 1.8 | Backend tests for truth persistence roundtrip | `backend/tests/test_db/test_gap_persistence.py` (new) |

**DB Schema Changes:**

```sql
ALTER TABLE research_gaps ADD COLUMN truth_frequency FLOAT DEFAULT 0.5;
ALTER TABLE research_gaps ADD COLUMN truth_confidence FLOAT DEFAULT 0.5;
ALTER TABLE research_gaps ADD COLUMN truth_evidence_count INTEGER DEFAULT 0;
ALTER TABLE research_gaps ADD COLUMN related_clusters TEXT;  -- JSON array

ALTER TABLE pipeline_runs ADD COLUMN cluster_report_json TEXT;  -- JSON object
```

**Test requirements:** 5+ new backend tests. All existing 286 frontend + 1,428 backend tests must still pass.

---

### Batch 2: Gap API Search, Filter & Sort

**Problem:** The `/gaps/` endpoint has no search, type filter, or confidence range. The frontend Gaps Explorer has no search input or filters (unlike the Ideas Browser which has all three).

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 2.1 | Add `search`, `gap_type`, `min_confidence`, `sort_by`, `sort_order` query params to `GET /gaps/` | `backend/api/routes/gaps.py` |
| 2.2 | Add `count_gaps()` and `list_gaps()` CRUD functions with filter/sort support | `backend/db/crud.py` |
| 2.3 | Add `VALID_GAP_SORT_COLUMNS` map | `backend/db/crud.py` |
| 2.4 | Update gap response to include `truth` and `related_clusters` fields | `backend/api/routes/gaps.py` |
| 2.5 | Backend tests for filter/sort/search | `backend/tests/test_db/test_batch14_task01.py` (extend) |
| 2.6 | Frontend: Add search input, type filter dropdown, confidence slider to Gaps Explorer | `frontend/src/pages/gaps-explorer.tsx` |
| 2.7 | Frontend: Add sort dropdown (confidence, date, type) | `frontend/src/pages/gaps-explorer.tsx` |
| 2.8 | Frontend: Update `listGaps()` API client to pass new params | `frontend/src/api/gaps.ts` |
| 2.9 | Frontend: Update `ResearchGap` type with truth fields | `frontend/src/api/types.ts` |
| 2.10 | Frontend tests for search/filter/sort | `frontend/src/pages/__tests__/gaps-explorer.test.tsx` |

**API Changes:**

```
GET /gaps/?search=evaluation&gap_type=methodological&min_confidence=0.7&sort_by=confidence&sort_order=desc&limit=20&offset=0
```

**Test requirements:** 8+ new backend tests, 6+ new frontend tests. All existing tests pass.

---

## Phase 2 — Gap Detail & Feedback (Batches 3–4)

*Add the missing gap detail page and user feedback loop.*

---

### Batch 3: Gap Detail Page

**Problem:** No `/gaps/:id` route exists. Clicking a gap card does nothing. Users can't see full gap descriptions, related papers, cluster membership, or linked ideas in a dedicated view.

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 3.1 | Frontend: Create `GapDetailPage` component | `frontend/src/pages/gap-detail.tsx` (new) |
| 3.2 | Frontend: Add `/gaps/:id` route to `App.tsx` | `frontend/src/App.tsx` |
| 3.3 | Frontend: Gap detail shows title, description, gap type badge, confidence bar, potential impact, truth values | `frontend/src/pages/gap-detail.tsx` |
| 3.4 | Frontend: "Related Ideas" section — list ideas linked via `source_gap_ids` | `frontend/src/pages/gap-detail.tsx` |
| 3.5 | Frontend: "Cluster Membership" section — show related clusters from API | `frontend/src/pages/gap-detail.tsx` |
| 3.6 | Frontend: Update GapCard click to navigate to `/gaps/{gap.id}` | `frontend/src/components/gaps/gap-card.tsx` |
| 3.7 | Frontend: Back button → Gaps Explorer | `frontend/src/pages/gap-detail.tsx` |
| 3.8 | Frontend tests for gap detail page | `frontend/src/pages/__tests__/gap-detail.test.tsx` (new) |

**Page Layout:**

```
← Back to Gaps
───────────────────────────────────────
Title: "Limited cross-domain evaluation of NLP methods"
Type: [methodological]    Confidence: ████████░░ 82%

Description:
Most NLP methods are evaluated only on English benchmarks...

Potential Impact:
High — would enable multilingual AI systems across 100+ languages

Truth Values:
  Frequency: 0.82  |  Confidence: 0.71  |  Evidence: 3 observations

Related Clusters:
  • Cluster 2 (cross-lingual / transfer / multilingual): 8 papers

Related Ideas (3):
  ┌─ Idea: "Zero-shot cross-lingual transfer via contrastive learning"
  │  Score: 0.78  │  [→ View Idea]
  ├─ Idea: "Multilingual prompt engineering for low-resource languages"
  │  Score: 0.71  │  [→ View Idea]
  └─ Idea: "Adapter-based language transfer without parallel data"
     Score: 0.65  │  [→ View Idea]
```

**Test requirements:** 10+ new frontend tests. All existing tests pass.

---

### Batch 4: Gap Feedback & Lifecycle

**Problem:** Users can rate ideas (1-5 stars) but can't rate gaps. Gaps have no lifecycle state — they're either in the DB or not. There's no way to mark a gap as "being investigated" or "addressed."

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 4.1 | Add `status` column to `ResearchGapDB`: `identified`, `investigating`, `addressed` | `backend/db/models.py` |
| 4.2 | Add `user_rating`, `user_notes` columns to `ResearchGapDB` | `backend/db/models.py` |
| 4.3 | Create Alembic migration `003_gap_feedback.py` | `alembic/versions/003_gap_feedback.py` |
| 4.4 | Add `POST /gaps/{id}/feedback` endpoint (rating + notes) | `backend/api/routes/gaps.py` |
| 4.5 | Add `PATCH /gaps/{id}/status` endpoint (lifecycle transition) | `backend/api/routes/gaps.py` |
| 4.6 | Add `GapFeedbackRequest` and `GapStatusUpdate` schemas | `backend/api/schemas.py` |
| 4.7 | Add `update_gap_feedback()` and `update_gap_status()` CRUD functions | `backend/db/crud.py` |
| 4.8 | Frontend: Add `GapFeedbackForm` component (star rating + notes) | `frontend/src/components/gaps/gap-feedback-form.tsx` (new) |
| 4.9 | Frontend: Add status dropdown on gap detail page | `frontend/src/pages/gap-detail.tsx` |
| 4.10 | Frontend: Add feedback form on gap detail page | `frontend/src/pages/gap-detail.tsx` |
| 4.11 | Frontend: Update `api/gaps.ts` with feedback + status functions | `frontend/src/api/gaps.ts` |
| 4.12 | Backend tests for feedback and status transitions | `backend/tests/test_db/test_gap_feedback.py` (new) |
| 4.13 | Frontend tests for feedback form and status dropdown | `frontend/src/pages/__tests__/gap-detail.test.tsx` (extend) |

**DB Schema Changes:**

```sql
ALTER TABLE research_gaps ADD COLUMN status VARCHAR(20) DEFAULT 'identified';
ALTER TABLE research_gaps ADD COLUMN user_rating INTEGER;
ALTER TABLE research_gaps ADD COLUMN user_notes TEXT;
```

**API Endpoints:**

```
POST /gaps/{id}/feedback   { "rating": 4, "notes": "Confirmed via literature review" }
PATCH /gaps/{id}/status     { "status": "investigating" }
```

**Test requirements:** 8+ new backend tests, 8+ new frontend tests.

---

## Phase 3 — Deduplication & Visualization (Batches 5–7)

*Cross-run gap intelligence and visual exploration.*

---

### Batch 5: Cross-Run Gap Deduplication

**Problem:** Each pipeline run creates fresh gap rows. If the same gap appears in run 1 and run 2, two separate `ResearchGapDB` rows exist with no link between them. The pipeline's in-memory truth revision works, but the results aren't persisted coherently.

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 5.1 | Add `canonical_id` column to `ResearchGapDB` (nullable, for grouping duplicates) | `backend/db/models.py` |
| 5.2 | Add `content_hash` column (SHA-256 of normalized title) for fast dedup | `backend/db/models.py` |
| 5.3 | Create Alembic migration `004_gap_dedup.py` | `alembic/versions/004_gap_dedup.py` |
| 5.4 | Add `find_gap_by_hash()` CRUD function | `backend/db/crud.py` |
| 5.5 | Update `persist_gaps()` to check for existing gaps by content hash before creating new rows | `backend/pipeline/persistence.py` |
| 5.6 | When duplicate found: revise truth values on existing row, skip insert | `backend/pipeline/persistence.py` |
| 5.7 | Add `GET /gaps/canonical` endpoint returning deduplicated gaps with run frequency | `backend/api/routes/gaps.py` |
| 5.8 | Backend tests for dedup logic | `backend/tests/test_db/test_gap_dedup.py` (new) |

**Dedup Logic:**

```python
def _normalize_title(title: str) -> str:
    return re.sub(r'[^\w\s]', '', title.lower().strip())

def _content_hash(title: str) -> str:
    return hashlib.sha256(_normalize_title(title).encode()).hexdigest()
```

When `persist_gaps()` encounters a gap whose content_hash matches an existing row:
1. Revise truth values on existing row using the OpenNARS revision rule
2. Increment `truth_evidence_count`
3. Don't create a new row
4. Link the gap to the current `pipeline_run_id` via existing FK

**Test requirements:** 6+ new backend tests.

---

### Batch 6: Cluster Visualization

**Problem:** The `ClusterReport` (from UMAP + HDBSCAN clustering) is never exposed to the frontend. Users can't see how papers cluster or which clusters produced which gaps.

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 6.1 | Add `GET /gaps/clusters` endpoint returning cluster data for a run | `backend/api/routes/gaps.py` |
| 6.2 | Add `get_clusters_for_run()` CRUD function | `backend/db/crud.py` |
| 6.3 | Frontend: Create `ClusterScatterPlot` component (SVG scatter plot) | `frontend/src/components/gaps/cluster-scatter.tsx` (new) |
| 6.4 | Frontend: Add "Clusters" tab to Gaps Explorer page | `frontend/src/pages/gaps-explorer.tsx` |
| 6.5 | Frontend: Each cluster dot shows paper count, label, and linked gap count | `frontend/src/components/gaps/cluster-scatter.tsx` |
| 6.6 | Frontend tests for cluster visualization | `frontend/src/pages/__tests__/gaps-explorer.test.tsx` (extend) |

**Cluster API Response:**

```json
{
  "clusters": [
    {
      "cluster_id": 0,
      "label": "transformer / attention / BERT",
      "paper_count": 12,
      "top_terms": ["transformer", "attention", "BERT", "encoder", "decoder"],
      "avg_citations": 45.3,
      "linked_gaps": 2
    }
  ],
  "total_papers": 35
}
```

**Test requirements:** 4+ new backend tests, 4+ new frontend tests.

---

### Batch 7: Gap Dashboard & Analytics

**Problem:** No aggregated view of gap data across runs. Users can't see gap type distribution, confidence trends, or which gaps keep reappearing.

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 7.1 | Add `GET /gaps/stats` endpoint: type distribution, confidence histogram, run frequency | `backend/api/routes/gaps.py` |
| 7.2 | Frontend: Add gap analytics section to Dashboard (lazy-loaded chart) | `frontend/src/components/charts/gap-type-distribution.tsx` (new) |
| 7.3 | Frontend: Add gap confidence trend chart | `frontend/src/components/charts/gap-confidence-trend.tsx` (new) |
| 7.4 | Frontend: Add "Top Gaps" section showing most-frequently-identified gaps across runs | `frontend/src/pages/dashboard.tsx` |
| 7.5 | Frontend tests for gap analytics components | `frontend/src/components/charts/__tests__/gap-*.test.tsx` (new) |

**Stats API Response:**

```json
{
  "type_distribution": {
    "methodological": 15,
    "empirical": 8,
    "theoretical": 5,
    "cross-domain": 3
  },
  "avg_confidence": 0.72,
  "total_gaps": 31,
  "top_gaps": [
    {"title": "...", "frequency": 5, "avg_confidence": 0.88},
    {"title": "...", "frequency": 4, "avg_confidence": 0.79}
  ],
  "confidence_trend": [
    {"run_id": 1, "avg_confidence": 0.65, "gap_count": 5},
    {"run_id": 2, "avg_confidence": 0.72, "gap_count": 6}
  ]
}
```

**Test requirements:** 4+ new backend tests, 6+ new frontend tests.

---

## Phase 4 — UX Polish & Integration (Batches 8–10)

*Complete the user experience with navigation, export, and closing features.*

---

### Batch 8: Gap-to-Paper Navigation & Related Gaps

**Problem:** Users can't see which papers contributed to a gap's identification. There's no way to navigate from a gap to its source literature or to discover related gaps.

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 8.1 | Add `GET /gaps/{id}/papers` endpoint returning papers from the same clusters | `backend/api/routes/gaps.py` |
| 8.2 | Add `GET /gaps/{id}/related` endpoint returning gaps with shared clusters | `backend/api/routes/gaps.py` |
| 8.3 | Frontend: "Source Papers" section on gap detail page | `frontend/src/pages/gap-detail.tsx` |
| 8.4 | Frontend: "Related Gaps" section on gap detail page | `frontend/src/pages/gap-detail.tsx` |
| 8.5 | Frontend tests for paper and related gap sections | `frontend/src/pages/__tests__/gap-detail.test.tsx` (extend) |

**Test requirements:** 4+ new backend tests, 4+ new frontend tests.

---

### Batch 9: Gap Export & Notifications

**Problem:** Gaps can't be exported. There are no alerts when high-confidence gaps are detected.

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 9.1 | Add `POST /gaps/export` endpoint (JSON/CSV export) | `backend/api/routes/gaps.py` |
| 9.2 | Add `GapExportRequest` schema | `backend/api/schemas.py` |
| 9.3 | Frontend: Add export button to Gaps Explorer toolbar | `frontend/src/pages/gaps-explorer.tsx` |
| 9.4 | Frontend: Reuse `ExportDialog` component with gap-specific fields | `frontend/src/pages/gaps-explorer.tsx` |
| 9.5 | Frontend tests for export button | `frontend/src/pages/__tests__/gaps-explorer.test.tsx` (extend) |

**Export Formats:**

- **JSON**: Array of `{title, description, gap_type, confidence, potential_impact, status, truth, related_clusters}`
- **CSV**: Flat table with same columns

**Test requirements:** 4+ new backend tests, 3+ new frontend tests.

---

### Batch 10: Global Search & Breadcrumb Navigation

**Problem:** No global search across the platform. Users must navigate to specific pages to find things. No breadcrumb navigation causes users to lose context on deep pages (gap detail → run detail → idea detail).

**Deliverables:**

| ID | Task | Files |
|:---|:---|:---|
| 10.1 | Add `GET /search` endpoint: unified search across ideas, gaps, runs, papers | `backend/api/routes/search.py` (new) |
| 10.2 | Register search router in app.py | `backend/api/app.py` |
| 10.3 | Frontend: Create `GlobalSearch` component (Cmd+K command palette) | `frontend/src/components/search/global-search.tsx` (new) |
| 10.4 | Frontend: Add search to app shell header | `frontend/src/components/layout/app-shell.tsx` |
| 10.5 | Frontend: Create `Breadcrumb` component | `frontend/src/components/layout/breadcrumb.tsx` (new) |
| 10.6 | Frontend: Add breadcrumbs to all detail pages (run detail, idea detail, gap detail) | `frontend/src/pages/*.tsx` |
| 10.7 | Frontend tests for global search and breadcrumbs | `frontend/src/components/__tests__/search.test.tsx` (new) |

**Search API Response:**

```json
{
  "results": [
    {"type": "gap", "id": 5, "title": "Cross-domain transfer", "score": 0.92},
    {"type": "idea", "id": 12, "title": "Zero-shot transfer via contrastive learning", "score": 0.87},
    {"type": "run", "id": 3, "title": "Run #3 — AI/NLP", "score": 0.65}
  ],
  "total": 15
}
```

**Breadcrumb Examples:**

```
Dashboard > Runs > #42 > Gaps > "Cross-domain transfer"
Dashboard > Ideas > "Zero-shot transfer via contrastive learning"
Dashboard > Pipeline > Run in progress
```

**Test requirements:** 6+ new backend tests, 8+ new frontend tests.

---

## Summary

### Batch Overview

| Batch | Phase | Focus | Backend Tasks | Frontend Tasks | Est. New Tests |
|:---|:---|:---|:---|:---|:---|
| **1** | Data Integrity | Truth persistence, cluster report storage | 7 | 0 | 5 |
| **2** | API | Search, filter, sort, truth in responses | 5 | 5 | 14 |
| **3** | Detail Page | `/gaps/:id` route, related ideas, clusters | 0 | 8 | 10 |
| **4** | Feedback | Gap rating, lifecycle status | 7 | 6 | 16 |
| **5** | Deduplication | Content hash, canonical gaps, truth revision | 8 | 0 | 6 |
| **6** | Visualization | Cluster scatter plot, clusters tab | 2 | 4 | 8 |
| **7** | Analytics | Gap dashboard, type distribution, trends | 1 | 5 | 10 |
| **8** | Navigation | Gap→papers, related gaps | 2 | 3 | 8 |
| **9** | Export | JSON/CSV export, export button | 2 | 3 | 7 |
| **10** | UX | Global search, breadcrumbs | 2 | 6 | 14 |
| **Total** | | | **36** | **40** | **~98** |

### Dependency Chain

```
Batch 1 (Truth persistence)
  └── Batch 2 (API filters) ── needs truth columns from B1
       └── Batch 3 (Gap detail) ── needs enriched API from B2
            ├── Batch 4 (Feedback) ── needs gap detail page from B3
            ├── Batch 5 (Dedup) ── independent, can parallel with B4
            └── Batch 6 (Clusters) ── needs cluster_report_json from B1
                 └── Batch 7 (Analytics) ── needs dedup from B5
                      └── Batch 8 (Navigation) ── needs detail page from B3
                           └── Batch 9 (Export) ── independent
                                └── Batch 10 (Global search) ── independent
```

**Parallelization opportunities:**
- B4 + B5 can run in parallel (feedback vs dedup are independent)
- B6 + B7 can run in parallel (both read from B1/B2 data)
- B8 + B9 + B10 can run in parallel (all independent features)

### Execution Order (Optimized)

```
Wave 1:  Batch 1
Wave 2:  Batch 2
Wave 3:  Batch 3
Wave 4:  Batch 4 + Batch 5 (parallel)
Wave 5:  Batch 6 + Batch 7 (parallel)
Wave 6:  Batch 8 + Batch 9 + Batch 10 (parallel)
```

### Expected Test Counts After Completion

| Stage | Frontend Tests | Backend Tests |
|:---|:---|:---|
| Baseline (current) | 286 | 1,428 |
| After Batch 1-2 | 292 | 1,447 |
| After Batch 3 | 302 | 1,447 |
| After Batch 4-5 | 316 | 1,467 |
| After Batch 6-7 | 326 | 1,479 |
| After Batch 8-10 | 343 | 1,495 |
| **Final** | **~343** | **~1,495** |

### Files Created (New)

```
alembic/versions/002_gap_enrichment.py
alembic/versions/003_gap_feedback.py
alembic/versions/004_gap_dedup.py
backend/api/routes/search.py
backend/tests/test_db/test_gap_persistence.py
backend/tests/test_db/test_gap_feedback.py
backend/tests/test_db/test_gap_dedup.py
frontend/src/pages/gap-detail.tsx
frontend/src/components/gaps/gap-feedback-form.tsx
frontend/src/components/gaps/cluster-scatter.tsx
frontend/src/components/charts/gap-type-distribution.tsx
frontend/src/components/charts/gap-confidence-trend.tsx
frontend/src/components/search/global-search.tsx
frontend/src/components/layout/breadcrumb.tsx
frontend/src/pages/__tests__/gap-detail.test.tsx
frontend/src/components/charts/__tests__/gap-*.test.tsx
frontend/src/components/__tests__/search.test.tsx
```

### Files Modified (Existing)

```
backend/db/models.py                    — 3 migrations worth of column additions
backend/db/crud.py                       — gap CRUD functions with filter/sort/dedup
backend/pipeline/persistence.py          — truth persistence, dedup check
backend/api/routes/gaps.py              — 6 new endpoints
backend/api/routes/search.py            — new route
backend/api/schemas.py                  — gap feedback + export schemas
backend/api/app.py                      — register search router
frontend/src/App.tsx                    — add /gaps/:id route
frontend/src/api/gaps.ts                — new API functions
frontend/src/api/types.ts              — updated ResearchGap type
frontend/src/pages/gaps-explorer.tsx   — search, filters, sort, export, clusters tab
frontend/src/pages/gap-detail.tsx      — new page
frontend/src/pages/dashboard.tsx       — gap analytics section
frontend/src/components/gaps/gap-card.tsx — click navigation
frontend/src/components/layout/app-shell.tsx — global search in header
frontend/src/components/layout/sidebar.tsx — no change needed (already has Gaps)
```

---

*Plan generated from consolidated analysis of Gap Analysis Deep Study, UX Journey Report, and Comprehensive Study Report. 10 batches, 6 waves, ~98 new tests, 18 new files, ~16 modified files.*
