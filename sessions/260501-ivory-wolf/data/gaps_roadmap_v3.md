# Elephant Rock — Gaps Roadmap v3 (Post-Competitive Analysis)

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**Trigger:** Competitive landscape analysis revealed 12 systemic gaps vs. AI Scientist, Google Co-Scientist, Elicit  
**AIV Framework:** v5.1 — Plan → Review → Execute → Verify  
**Scope:** 12 gaps → 10 batches (BATCH-48 → BATCH-57)

---

## Gap Inventory

| # | Gap | Source | Severity | Batch |
|:--|:---|:---|:---|:---|
| G1 | No frontend code splitting — all 20 pages eagerly loaded | Performance audit | HIGH | BATCH-48 |
| G2 | No global search UI — backend `/search` exists (BATCH-47) but no frontend | UX gap | HIGH | BATCH-48 |
| G3 | No notification system UI — webhooks fire silently, no user-visible alerts | UX gap | HIGH | BATCH-49 |
| G4 | No experiment execution — AI Scientist can run code, we cannot | Competitive (AI Scientist) | HIGH | BATCH-49 |
| G5 | No i18n translations — only English locale, infrastructure exists | UX gap | MEDIUM | BATCH-50 |
| G6 | No WebSocket support — SSE exists for pipeline, but no bidirectional channel | Architecture | MEDIUM | BATCH-50 |
| G7 | No frontend build/deploy in CI — CI only tests backend, no frontend build step | DevOps | MEDIUM | BATCH-51 |
| G8 | No nginx reverse proxy config — Docker Compose lacks production web server | DevOps | MEDIUM | BATCH-51 |
| G9 | No accessibility audit/tests — no axe-core, no a11y CI gate | Quality | MEDIUM | BATCH-52 |
| G10 | No error monitoring — no Sentry/Datadog, errors vanish into logs | Observability | MEDIUM | BATCH-52 |
| G11 | No plugin SDK documentation — API exists, no public docs | Competitive moat | LOW | BATCH-53 |
| G12 | No E2E fix — 1 smoke test fails (needs live API key) | Quality | LOW | BATCH-53 |

---

## Phase 1: Frontend Performance & UX (BATCH-48)

### BATCH-48: Code Splitting + Global Search UI

**Tasks:**

**TASK-01: Frontend code splitting with React.lazy()**
- Convert all 20 page imports in `App.tsx` to `React.lazy()` dynamic imports
- Wrap routes in `<Suspense>` with skeleton fallback
- Add route-based chunk naming via Vite magic comments (`/* webpackChunkName: "dashboard" */`)
- Expected: Initial bundle drops from ~800KB to ~200KB (only Dashboard + shell loads eagerly)
- Test: verify all 20 routes still render, measure chunk sizes

**TASK-02: Global Search UI with Ctrl+K shortcut**
- Create `frontend/src/components/search/global-search-dialog.tsx` — a command palette
  - `Cmd+K` / `Ctrl+K` keyboard shortcut opens a modal
  - Debounced search input queries `GET /api/v1/search?q={query}`
  - Results grouped by type: Ideas, Gaps, Papers, Runs
  - Click navigates to detail page (`/ideas/:id`, `/gaps/:id`, etc.)
  - Recent searches stored in localStorage
- Add search API client: `frontend/src/api/search.ts` with `globalSearch(query, types?)` function
- Add types for search results in `frontend/src/api/types.ts`
- Wire into `AppShell` (always accessible from any page)
- Tests: dialog opens/closes, search API call, result navigation, keyboard shortcut

---

## Phase 2: Notifications & Experiment Execution (BATCH-49)

### BATCH-49: Notification Center + Sandboxed Experiment Runner

**Tasks:**

**TASK-01: Frontend notification center**
- Create `frontend/src/components/notifications/notification-bell.tsx` — bell icon in AppShell header
- Create `frontend/src/components/notifications/notification-list.tsx` — dropdown list
- Add notification polling via SSE: `GET /api/v1/notifications/stream`
- Add backend `backend/api/routes/notifications.py`:
  - `GET /api/v1/notifications/` — list notifications (paginated, filterable by read/unread)
  - `GET /api/v1/notifications/stream` — SSE stream for real-time notifications
  - `PATCH /api/v1/notifications/{id}/read` — mark as read
  - `POST /api/v1/notifications/read-all` — mark all as read
- Add `backend/db/models.py`: `NotificationDB` model (id, user_id, type, title, message, read, created_at)
- Add migration `005_notifications.py`
- Wire pipeline events → notification creation (pipeline.completed, pipeline.failed, idea.generated, gap.found)
- Tests: backend CRUD, SSE stream, read/unread toggle, frontend bell rendering

**TASK-02: Sandboxed experiment execution**
- Add `backend/pipeline/experiment/` directory with:
  - `runner.py` — executes Python code snippets in Docker/WASM sandbox
  - `models.py` — ExperimentResult dataclass (stdout, stderr, exit_code, artifacts, metrics)
  - `validator.py` — validates experiment code against governance policies (no network, no filesystem writes)
- Add `backend/api/routes/experiments.py`:
  - `POST /api/v1/experiments/run` — submit code + inputs, returns ExperimentResult
  - `GET /api/v1/experiments/{id}` — get result
  - `GET /api/v1/experiments/{id}/artifacts/{name}` — download artifact
- Wire into pipeline: after ProposalSynthesisStage, optionally run validation experiments
- Use existing `backend/pipeline/sandboxing/` (Docker backend) for isolation
- Add `experiment_enabled` config flag (default: False)
- Tests: sandboxed execution, timeout handling, governance validation, API endpoints

---

## Phase 3: Internationalization & Real-time (BATCH-50)

### BATCH-50: i18n Locales + WebSocket Infrastructure

**Tasks:**

**TASK-01: Add Chinese (zh) and Spanish (es) translations**
- Create `frontend/src/i18n/zh.json` with full Chinese translations
- Create `frontend/src/i18n/es.json` with full Spanish translations
- Update `frontend/src/i18n/config.ts` to register zh and es resources
- Update `frontend/src/components/i18n/language-switcher.tsx` to show 3 options
- Replace all hardcoded strings in pages/components with `t()` calls (survey-based — top 10 pages)
- Tests: language switching, missing key fallback, locale detection

**TASK-02: WebSocket infrastructure for bidirectional communication**
- Add `backend/api/ws.py` — WebSocket endpoint at `/api/v1/ws`
- Implement connection manager: authenticate, subscribe to channels (pipeline:{id}, user:{id})
- Message types: `pipeline.progress`, `pipeline.completed`, `idea.generated`, `notification.new`
- Add `frontend/src/hooks/useWebSocket.ts` — React hook for WebSocket connections
- Wire into RunDetailPage for real-time stage progress (replace polling)
- Fallback to SSE if WebSocket connection fails
- Add `websocket_enabled` config flag (default: True)
- Tests: connection manager, channel subscription, message routing, fallback behavior

---

## Phase 4: DevOps & Production (BATCH-51)

### BATCH-51: Frontend CI + nginx Production Config

**Tasks:**

**TASK-01: Frontend build & test in CI**
- Add frontend job to `.github/workflows/ci.yml`:
  - Node.js 20 setup with npm cache
  - `npm ci` → `npm run lint` → `npm run build` → `npm test`
  - Upload frontend build artifact
- Add separate step for backend + frontend combined build
- Add coverage upload for both frontend and backend
- Tests: CI workflow runs end-to-end

**TASK-02: nginx reverse proxy + production Dockerfile**
- Create `nginx/nginx.conf` — reverse proxy configuration:
  - `/api/` → backend:8000
  - `/` → frontend static files
  - WebSocket upgrade for `/api/v1/ws`
  - gzip compression for static assets
  - Security headers (X-Frame-Options, CSP, HSTS)
- Create `frontend.Dockerfile` — multi-stage build:
  - Stage 1: Node.js build (`npm run build`)
  - Stage 2: nginx serving static files
- Update `docker-compose.yml`:
  - Add `frontend` service with `frontend.Dockerfile`
  - Add `nginx` service as reverse proxy
  - Remove direct port exposure on `app` and `frontend`
  - Expose only `nginx:80` and `nginx:443`
- Add `docker-compose.prod.yml` override for production (HTTPS, resource limits)
- Tests: docker-compose config validation, nginx config test

---

## Phase 5: Quality & Observability (BATCH-52)

### BATCH-52: Accessibility Audit + Error Monitoring

**Tasks:**

**TASK-01: Accessibility testing with axe-core**
- Install `@testing-library/jest-dom` + `jest-axe` in frontend
- Create `frontend/src/test/a11y-test-utils.ts` — helper function for a11y testing
- Add a11y tests for all 20 pages: `expect(container).toHaveNoViolations()`
- Fix any violations found (aria-labels, focus management, color contrast, keyboard navigation)
- Add a11y check to CI: fail on any WCAG 2.1 AA violations
- Tests: 20 page-level a11y tests passing

**TASK-02: Error monitoring integration (Sentry)**
- Add `backend/monitoring/` directory:
  - `sentry.py` — Sentry SDK initialization + FastAPI integration
  - `middleware.py` — Error capture middleware for unhandled exceptions
- Add `EROCK_SENTRY_DSN` config parameter (optional, disabled if empty)
- Add frontend Sentry integration:
  - `frontend/src/lib/sentry.ts` — Sentry React SDK init
  - Error boundary integration with existing `ErrorBoundary` component
- Add performance monitoring for API endpoints (optional, configurable)
- Tests: error capture, Sentry init with/without DSN, middleware

---

## Phase 6: Documentation & Quality (BATCH-53)

### BATCH-53: Plugin SDK Docs + E2E Smoke Fix

**Tasks:**

**TASK-01: Plugin SDK documentation**
- Create `docs/plugin-sdk.md` with:
  - Plugin architecture overview
  - Plugin manifest schema (plugin.json)
  - Hook system (available events)
  - API reference (CRUD, tool registration)
  - Step-by-step tutorial: "Build your first plugin"
  - Security model (sandboxing, permissions)
- Create `docs/examples/hello-plugin/` — minimal working plugin example
- Update `docs/index.md` to reference Plugin SDK
- Tests: verify example plugin loads correctly

**TASK-02: Fix E2E smoke test**
- Locate the failing E2E test in `backend/tests/`
- Replace live API key dependency with mock provider
- Ensure test runs without `OPENAI_API_KEY` or any external service
- Verify all 1,791 tests pass (1,480 backend + 310 frontend + 1 previously failing)
- Tests: 0 failures across entire test suite

---

## Batch Schedule

| Phase | Batch | Tasks | Backend Tests | Frontend Tests | Wave |
|:---|:---|:---|:---|:---|:---|
| 1 | BATCH-48 | 2 | +4 | +8 | W1 |
| 2 | BATCH-49 | 2 | +10 | +8 | W1 |
| 3 | BATCH-50 | 2 | +6 | +6 | W2 |
| 4 | BATCH-51 | 2 | +0 | +2 | W2 |
| 5 | BATCH-52 | 2 | +4 | +22 | W3 |
| 6 | BATCH-53 | 2 | +2 | +2 | W3 |

**Totals:** 6 phases, 6 batches, 12 tasks, ~26 backend tests, ~48 frontend tests

---

## Estimated Final Metrics After Roadmap

| Metric | Current | After |
|:---|:---|:---|
| Total tests | 1,790 | ~1,864 |
| Backend tests | 1,480 | ~1,506 |
| Frontend tests | 310 | ~358 |
| Failing tests | 1 | 0 |
| Frontend bundle size | ~800KB (eager) | ~200KB initial |
| i18n locales | 1 (en) | 3 (en, zh, es) |
| Real-time transport | SSE only | SSE + WebSocket |
| CI frontend coverage | None | Full build+test+lint |
| Production deployment | Dockerfile only | Full compose + nginx + HTTPS |
| A11y coverage | Ad-hoc | WCAG 2.1 AA CI gate |
| Error monitoring | None | Sentry (optional) |
| Plugin docs | None | Full SDK docs + example |
| Experiment execution | None | Docker/WASM sandboxed |

---

## Execution Order

```
W1: BATCH-48 (code split + search UI) ────┐
W1: BATCH-49 (notifications + experiments) │← parallelizable
                                            │
W2: BATCH-50 (i18n + WebSocket) ───────────┤
W2: BATCH-51 (CI + nginx) ─────────────────┤← depends on BATCH-48 for lazy routes
                                            │
W3: BATCH-52 (a11y + Sentry) ──────────────┤
W3: BATCH-53 (plugin docs + E2E fix) ──────┘← final verification
```

---

*Gaps Roadmap v3 — AIV Framework v5.1 — Lead Agent — 2026-05-02*
