# BATCH-39 BLUEPRINT — Gap API Search, Filter & Sort

**Batch ID:** BATCH-39  
**Blueprint Version:** 1.0  
**Cycle Mode:** STANDARD  
**Lead Programmer:** Lead Agent  
**Date Issued:** 2026-05-02  
**Review SLA:** 30 min | **Execution SLA per Task:** 60 min | **Partial Sign-Off SLA:** 15 min  
**Task Sequencing:** Sequential  

---

## BATCH GOAL

Add search, filter, sort, and enriched response fields to the gaps API and mirror those capabilities in the frontend Gaps Explorer.

---

## SCOPE STATEMENT

**MUST do:**
1. Add search, gap_type, min_confidence, sort_by, sort_order query params to GET /gaps/
2. Add backend CRUD functions for filtered/sorted gap queries
3. Include truth and related_clusters in gap API responses
4. Add search input, gap_type filter, confidence slider, sort dropdown to Gaps Explorer
5. Update frontend API client (gaps.ts) and types (types.ts)

**MUST NOT do:**
- Add new database tables or columns (done in BATCH-38)
- Create a gap detail page (that's BATCH-40)
- Modify the pipeline stage execution

---

## HARD BOUNDARIES

- **HB-01:** All new query params MUST be optional with defaults matching current behavior when absent
- **HB-02:** SQL injection prevention — parameterized queries only (SQLAlchemy ORM handles this)
- **HB-03:** Frontend shows "N gaps found" matching API total
- **HB-04:** No existing test may break — baseline is 1,436 backend + 286 frontend

---

## DATA MODELS

### Current GET /gaps/ route (backend/api/routes/gaps.py)
- Params: run_id (int|None), limit (int, default=20), offset (int, default=0)
- Response: { gaps: [{id, title, description, gap_type, confidence, potential_impact, idea_count}], total, run_id }

### New query parameters:
- search: str | None — case-insensitive substring match on title and description
- gap_type: str | None — must be one of: methodological, empirical, theoretical, cross-domain
- min_confidence: float | None — minimum confidence threshold (0.0-1.0)
- sort_by: str — one of: confidence (default), date, type. Whitelisted per AR-01.
- sort_order: str — asc or desc (default: desc)

### New response fields per gap:
- truth: { frequency: float, confidence: float, evidence_count: int } | null
- related_clusters: list[int] | null

### ResearchGapDB columns (post BATCH-38):
- truth_frequency (Float, default=0.5)
- truth_confidence (Float, default=0.5)
- truth_evidence_count (Integer, default=0)
- related_clusters (Text, nullable)

### Frontend ResearchGap type (frontend/src/api/types.ts):
- Current: { id, title, description, gap_type, confidence, potential_impact, idea_count }
- Add: truth?: { frequency: float, confidence: float, evidence_count: int }, related_clusters?: number[]

### Frontend Gaps Explorer (frontend/src/pages/gaps-explorer.tsx):
- Current: pagination only, no search/filter/sort
- Add: search input, gap_type select (4 options + "All"), confidence slider, sort dropdown

### Ideas Browser pattern to mirror (frontend/src/pages/ideas-browser.tsx):
- Search input + Sort select + Min score slider + Domain filter + Pagination

---

## AUTHORITY RULES

- **AR-01:** Sort columns MUST be validated against whitelist: {confidence, date, type}. Invalid values → ignore (use default).
- **AR-02:** gap_type filter MUST be validated against known types: {methodological, empirical, theoretical, cross-domain}.

---

## DEPENDENCY MAP

- **Depends on:** BATCH-38 (truth + related_clusters columns must exist) ✅
- **Blocks:** BATCH-40

---

## TEST BASELINE

- Baseline: 1,436 backend + 286 frontend = 1,722
- Expected delta: +14 (8 backend + 6 frontend)
- Expected total: 1,736

---

## TASK LIST

### TASK-01: Backend Gap Filter/Sort/Search API

**Files in scope:**
- backend/api/routes/gaps.py
- backend/db/crud.py (add search_gaps function)

**Tests:** backend/tests/test_api/test_batch39_task01.py
- TEST-39-01-01: search='transfer' returns only matching gaps
- TEST-39-01-02: gap_type='methodological' filters correctly
- TEST-39-01-03: min_confidence=0.7 excludes low-confidence gaps
- TEST-39-01-04: sort_by='confidence' returns descending order
- TEST-39-01-05: sort_by='date' returns newest first
- TEST-39-01-06: Response includes truth and related_clusters
- TEST-39-01-07: SQL injection treated as literal string (HB-02)
- TEST-39-01-08: Default params reproduce current behavior (HB-01)

**AC:**
- AC-01-01: GET /gaps/ with no new params returns same result as before
- AC-01-02: All filter/sort params are optional
- AC-01-03: Invalid sort_by values ignored

### TASK-02: Frontend Gaps Explorer Search/Filter/Sort

**Files in scope:**
- frontend/src/pages/gaps-explorer.tsx
- frontend/src/api/gaps.ts
- frontend/src/api/types.ts

**Tests:** frontend/src/pages/__tests__/batch39-gaps-filter.test.tsx
- TEST-39-02-01: Search input renders and updates on type
- TEST-39-02-02: Gap type filter renders with 4 options
- TEST-39-02-03: Confidence slider renders with label
- TEST-39-02-04: Sort dropdown renders with score/date/type options
- TEST-39-02-05: Filters passed as query params to API
- TEST-39-02-06: "N gaps found" displays total from API (HB-03)

**AC:**
- AC-02-01: Gaps Explorer mirrors Ideas Browser UX pattern
- AC-02-02: All 286 frontend tests pass

---

## BATCH-LEVEL ACCEPTANCE CRITERIA

- BAC-01: GET /gaps/ supports search, gap_type, min_confidence, sort_by, sort_order
- BAC-02: Gaps Explorer has search, filter, sort controls
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-39/

---

## LEAD RESPONSE TO REVIEW REPORT

**Verdict:** APPROVE (Inline Review by Lead — 0 flags)

### Lead Decisions:
- All CHK-00 through CHK-17: PASS
- No flags, no observations requiring action
- Blueprint cleared for execution

### Lead Authorization:
The Blueprint is cleared for execution. The Assistant may proceed.
