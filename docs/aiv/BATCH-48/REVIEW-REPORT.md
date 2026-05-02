# BATCH-48 REVIEW REPORT
**Reviewer:** Reviewer Agent
**Date:** 2026-05-03

## Verdict: APPROVE_WITH_NOTES

Blueprint is well-structured and tasks are achievable. One **critical data-model mismatch** between the Blueprint's `GlobalSearchResult` type and the actual BATCH-47 backend response must be corrected before execution. Several minor inaccuracies also need cleanup.

---

## Findings

### CHK-01: File Existence
**PASS** — All referenced files exist and match Blueprint descriptions.

| File | Status | Notes |
|:---|:---|:---|
| `frontend/src/App.tsx` | EXISTS | 19 static page imports confirmed |
| `frontend/src/api/types.ts` | EXISTS | No `GlobalSearch*` types yet — as expected |
| `frontend/src/components/layout/app-shell.tsx` | EXISTS | Simple shell with sidebar, header, main area |
| `frontend/src/api/search.ts` | DOES NOT EXIST | Correctly marked NEW in Blueprint |
| `frontend/src/components/search/global-search-dialog.tsx` | DOES NOT EXIST | Correctly marked NEW in Blueprint |
| `backend/api/routes/search.py` | EXISTS | Mounted at `/api/v1/search` with API-key auth |

---

### CHK-02: Data Model Accuracy
**FAIL — Critical mismatch requires correction before execution.**

The Blueprint defines this frontend type:
```typescript
interface GlobalSearchResult {
  id: number;
  type: "idea" | "gap" | "paper" | "run";
  title: string;
  snippet: string;
  score: number;
}
```

But the **actual BATCH-47 backend** (`GET /api/v1/search/`) returns a **grouped response**:
```json
{
  "query": "...",
  "results": {
    "ideas":   { "total": N, "items": [{ "id", "title", "domain", "overall_score" }] },
    "gaps":    { "total": N, "items": [{ "id", "title", "gap_type", "confidence" }] },
    "papers":  { "total": N, "items": [{ "id", "title", "year", "venue" }] },
    "runs":    { "total": N, "items": [{ "id", "status", "domain", "created_at" }] }
  },
  "total": N
}
```

Specific issues:
1. **Not a flat array** — Backend returns results grouped by type in nested objects, not a flat `GlobalSearchResult[]`
2. **No `snippet` field** — Backend does not return any snippet/highlight text
3. **No `score` field** — Backend has no relevance scoring (uses ILIKE pattern match)
4. **Different fields per type** — Ideas have `domain`/`overall_score`, gaps have `gap_type`/`confidence`, papers have `year`/`venue`, runs have `status`/`created_at`
5. **`types` param format** — Backend accepts comma-separated string (`"ideas,gaps,papers,runs"`), not an array. The Blueprint's `types?: string[]` will need to be joined before sending.

**Action required:** The Lead must either:
- **(A)** Update the Blueprint's frontend types to match the actual backend response shape, or
- **(B)** Enhance the backend search route to return the flat, uniform format the Blueprint describes (adding `snippet`, `score`, `type` fields).

Option A is faster and aligns with "no backend changes" scope. Option B is better UX but expands scope.

---

### CHK-03: Code Pattern Compatibility
**PASS with notes.**

- **App.tsx patterns** — Standard React Router `<Routes>/<Route>` structure. Wrapping in `<Suspense>` at the `<AppShell>` level inside `<ProtectedRoute>` is compatible and correct.
- **LoginPage correctly identified** as needing to stay eagerly loaded (it renders outside `ProtectedRoute`).
- **`webpackChunkName` magic comments** — The project uses **Vite** (Rollup-based). These webpack-specific comments are **ignored by Vite**. The existing `vite.config.ts` uses `manualChunks` for specific vendor splits. Lazy imports will auto-generate chunk names from file paths (e.g., `dashboard-[hash].js`). This is cosmetic — not a blocker — but the Lead should note it or remove the misleading comments.
- **App-shell structure** — The `AppShell` component has a sidebar + header area + main content. Adding a search button in the header row (the `h-14` div with the collapse toggle) is straightforward.
- **Auth requirement** — The search endpoint requires API key auth (`dependencies=_auth`). The frontend API client must include auth headers (likely already handled by a shared API client/fetch wrapper).

---

### CHK-04: Task Scope
**PASS with minor correction.**

- **TASK-01 (Code Splitting)**: Well-defined and achievable. The import count in the Blueprint says "20 static imports" and "Verify all 20 routes" — the actual count is **19 page imports** (18 to lazy-load + 1 LoginPage to keep static). The Lead should correct "20" → "19" (or "18 lazy + 1 static").
- **TASK-02 (Global Search UI)**: Achievable but the data model mismatch (CHK-02) must be resolved first. The component spec (debounce, keyboard shortcuts, localStorage, grouping, navigation) is thorough and well-scoped.
- Both tasks declare "no new dependencies" which is correct — shadcn Dialog/Input and lucide-react icons already exist in the project.

---

### CHK-05: Dependencies
**PASS.**

| Dependency | Status |
|:---|:---|
| TASK-01 ↔ TASK-02 | **Independent** — can execute in parallel or any order |
| TASK-02 → BATCH-47 search backend | **Confirmed** — route exists at `/api/v1/search/`, returns results across ideas/gaps/papers/runs |
| TASK-02 → shadcn Dialog/Input | **Already available** — project uses shadcn/ui |
| TASK-02 → React Router (navigation) | **Already available** — `useNavigate` hook |

No missing or incorrect dependency chains identified.

---

### CHK-06: Test Requirements
**PASS with enhancement needed for TASK-02.**

**TASK-01 tests** — Sufficient:
- All 18 lazy routes render correctly ✅
- Chunk requests fire on navigation ✅
- LoginPage renders without Suspense wrapper ✅

**TASK-02 tests** — Sufficient coverage but must be updated after CHK-02 fix:
- Dialog open/close keyboard shortcuts ✅
- API called with correct params ✅
- Results rendered grouped by type ✅
- Result click navigates to correct page ✅
- Recent searches persisted in localStorage ✅

**Missing test suggestions for the Lead:**
- Search with empty query (should not call API / should show empty state)
- Debounce timing test (rapid typing should only trigger one call)
- Focus trap accessibility test when dialog is open
- Test that search works on all pages (not just dashboard)

---

## Notes

1. **Import count**: Blueprint says "20 static imports" and "20 routes" — actual is 19 page imports across 18 lazy-eligible routes + 1 login route + 1 catch-all redirect. Minor but should be corrected for accuracy.

2. **Vite chunk naming**: `/* webpackChunkName: "dashboard" */` comments are inert in Vite. Vite auto-names chunks from file paths. Either remove these comments or note that chunk names will be auto-generated.

3. **No LoadingScreen component exists**: The Blueprint says to create a `LoadingScreen` component. The existing `ProtectedRoute` already has an inline loading spinner. The Lead could either extract it or create a new one — just flagging that there's an existing pattern to consider.

4. **Search auth**: The backend search endpoint uses `verify_api_key` dependency. The frontend `globalSearch()` function must send the API key header. The Lead should verify the shared API client already handles this (likely does, since other endpoints also require auth).

5. **Backend search uses ILIKE**: The search is case-insensitive pattern matching, not full-text search. No relevance scoring exists. The Blueprint's `score` field cannot be populated without backend changes.

---

## Recommendations for Lead

### Before execution:

1. **[CRITICAL] Fix CHK-02 data model** — Align `GlobalSearchResult` / `GlobalSearchResponse` types with the actual BATCH-47 backend response. Recommended approach:
   ```typescript
   // Matches actual backend
   export interface GlobalSearchResponse {
     query: string;
     results: {
       ideas?: { total: number; items: IdeaSearchItem[] };
       gaps?: { total: number; items: GapSearchItem[] };
       papers?: { total: number; items: PaperSearchItem[] };
       runs?: { total: number; items: RunSearchItem[] };
     };
     total: number;
   }
   ```

2. **[MINOR] Correct import count** — Change "20 static imports" to "19 page imports (18 to lazy-load + LoginPage static)".

3. **[MINOR] Remove or annotate webpackChunkName comments** — Vite ignores them. Either remove or add a note that they're aspirational.

4. **[SUGGESTED] Add debounce test** — Include a test verifying the 300ms debounce behavior.

5. **[SUGGESTED] Note existing loading pattern** — The `ProtectedRoute` inline spinner can inform the `LoadingScreen` design for consistency.

---

*REVIEW REPORT — BATCH-48 — AIV Framework v5.1 — Reviewer Agent*
