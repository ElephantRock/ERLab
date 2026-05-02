# BATCH-48 BLUEPRINT — Code Splitting + Global Search UI

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**AIV Framework:** v5.1  
**Status:** DRAFT  
**Phase:** 1 — Frontend Performance & UX

---

## Objective

Reduce initial frontend bundle size from ~800KB to ~200KB via route-level code splitting, and deliver a Ctrl+K global search command palette wired to the existing `GET /api/v1/search` endpoint (built in BATCH-47).

---

## TASK-01: Frontend Code Splitting with React.lazy()

### Target Files
- `frontend/src/App.tsx` — Convert 20 static imports to `React.lazy()` dynamic imports

### Specification

1. Replace all static page imports in `App.tsx`:
   ```tsx
   // BEFORE
   import DashboardPage from "./pages/dashboard";
   // AFTER
   const DashboardPage = React.lazy(() => import("./pages/dashboard"));
   ```

2. Wrap the `<Routes>` block inside `<Suspense fallback={<LoadingScreen />}>`:
   - Create `LoadingScreen` component: centered spinner with "Loading…" text
   - Use existing Tailwind classes for styling

3. Add Vite magic comment for meaningful chunk names:
   ```tsx
   const DashboardPage = React.lazy(() => import(
     /* webpackChunkName: "dashboard" */ "./pages/dashboard"
   ));
   ```

4. Keep `LoginPage` as static import (must render before auth check)

### Constraints
- No new dependencies
- Must not break any existing route
- LoginPage remains eagerly loaded (auth gate needs it)

### Expected Outcome
- Initial JS bundle drops to shell + LoginPage + LoadingScreen only
- Each page loads on-demand when its route is visited
- Vite produces ~20 named chunks

### Tests Required
- Verify all 20 routes still render correctly
- Verify lazy loading works (chunk requests happen on navigation)
- Verify LoginPage renders without Suspense

---

## TASK-02: Global Search UI with Ctrl+K Shortcut

### Target Files (NEW)
- `frontend/src/components/search/global-search-dialog.tsx` — Command palette component
- `frontend/src/api/search.ts` — Search API client

### Target Files (MODIFY)
- `frontend/src/api/types.ts` — Add `GlobalSearchResult`, `GlobalSearchResponse` types
- `frontend/src/components/layout/app-shell.tsx` — Wire in search trigger button + keyboard listener

### Specification

#### Backend API (already exists from BATCH-47)
- `GET /api/v1/search/?q={query}&types={types}` — Global search across ideas, gaps, papers, runs

#### Frontend: API Client (`api/search.ts`)
```typescript
export interface GlobalSearchResult {
  id: number;
  type: "idea" | "gap" | "paper" | "run";
  title: string;
  snippet: string;
  score: number;
}

export async function globalSearch(query: string, types?: string[]): Promise<GlobalSearchResult[]> {
  // Build query params, call GET /api/v1/search/
}
```

#### Frontend: Command Palette (`global-search-dialog.tsx`)
- Opens on `Ctrl+K` (Windows/Linux) or `Cmd+K` (Mac)
- Full-screen overlay with semi-transparent backdrop
- Search input auto-focused on open
- Debounced API calls (300ms) as user types
- Results grouped by type with section headers
- Each result shows: icon (type-dependent), title, snippet (highlighted match)
- Click navigates to detail page and closes dialog
- Escape closes dialog
- Recent searches stored in localStorage (max 10)
- Empty state: "Start typing to search…" prompt
- Loading state: skeleton results

#### Frontend: Integration (`app-shell.tsx`)
- Add search icon button in header bar
- Global `keydown` listener for Ctrl+K / Cmd+K
- Render `GlobalSearchDialog` at shell level (always available)

### Constraints
- No new dependencies (use existing shadcn Dialog + Input primitives)
- Must work on all pages
- Must be accessible (focus trap when open, aria attributes)

### Expected Outcome
- Users can search across all entities from any page
- Ctrl+K shortcut provides instant access
- Results navigate to correct detail pages

### Tests Required
- Dialog opens on Ctrl+K, closes on Escape
- Search API called with correct params
- Results rendered grouped by type
- Click on result navigates to correct page
- Recent searches persisted in localStorage

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| All 20 routes use lazy loading | `App.tsx` has no static page imports (except LoginPage) |
| Suspense wrapper renders loading state | Manual check — LoadingScreen appears briefly on navigation |
| Global search dialog opens on Ctrl+K | Test assertion |
| Search queries `/api/v1/search/` | Test assertion |
| Results navigate to detail pages | Test assertion |
| No new dependencies | Check package.json unchanged |
| All existing tests pass | `npm test` + `pytest` |

---

*BLUEPRINT — BATCH-48 — AIV Framework v5.1 — Lead Agent*
