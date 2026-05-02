# CHANGELOG — BATCH-31

## [BATCH-31] — 2026-05-02

### Added
- **SSE Header Auth (TASK-01)**: Fetch-based SSE with `X-API-Key` header replaces legacy `sseUrl()` query-param auth. Backend SSE endpoint validates auth headers explicitly (defence-in-depth). **HB-01: No API keys in URLs.**
- **Responsive Design (TASK-02)**: Mobile bottom nav, collapsible sidebar, responsive grid breakpoints (mobile/tablet/desktop). Pages usable at 375px width.

### Changed
- `frontend/src/api/client.ts`: `sseUrl()` → `sseFetch()` with header-based auth
- `frontend/src/hooks/useSSE.ts`: `EventSource` → fetch-based SSE via `sseFetch()`
- `frontend/src/components/layout/sidebar.tsx`: Added `MobileBottomNav` component
- `frontend/src/components/layout/app-shell.tsx`: Responsive layout with mobile support
- `frontend/src/globals.css`: Responsive breakpoints and bottom nav styles
- `frontend/src/pages/dashboard.tsx`: Added `dashboard-grid` responsive class
- `backend/api/routes/pipeline.py`: Explicit auth header validation on SSE endpoint

### Tests
- `backend/tests/test_api/test_batch31_sse_auth.py`: 4 tests (TEST-31-01-01 through 04)
- `frontend/src/components/layout/__tests__/responsive.test.tsx`: 6 tests (TEST-31-02-01 through 04)
- Updated `frontend/src/api/__tests__/client.test.ts`: 3 sseFetch tests replace sseUrl tests

### Compliance
- **HB-01**: ✅ No API keys in URLs. All credentials travel via HTTP headers.
