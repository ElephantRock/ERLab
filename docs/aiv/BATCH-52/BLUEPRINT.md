# BATCH-52 BLUEPRINT — Accessibility Audit + Error Monitoring

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**AIV Framework:** v5.1  
**Phase:** 5 — Quality & Observability

---

## TASK-01: Accessibility Testing with axe-core

### Target Files (NEW)
- `frontend/src/test/a11y-test-utils.ts` — Helper for a11y testing
- `frontend/src/pages/__tests__/a11y.test.tsx` — Page-level a11y audit

### Target Files (MODIFY)
- `frontend/package.json` — Add jest-axe dependency

### Specification

1. Install `jest-axe` package: `npm install --save-dev jest-axe`
2. Create `a11y-test-utils.ts`:
   ```typescript
   import { axe, toHaveNoViolations } from "jest-axe";
   import { render } from "@testing-library/react";
   expect.extend(toHaveNoViolations);
   
   export async function checkA11y(ui: React.ReactElement) {
     const { container } = render(ui);
     const results = await axe(container);
     expect(results).toHaveNoViolations();
   }
   ```
3. Create a11y tests for key pages (Dashboard, Ideas, Gaps, Settings, Login, Knowledge Search)
   - Each test renders the page with necessary providers and checks for WCAG 2.1 AA violations
4. Fix any violations found (aria-labels, focus management, color contrast)

### Tests
- 6+ page-level a11y tests

---

## TASK-02: Error Monitoring Integration (Sentry)

### Backend Target Files (NEW)
- `backend/monitoring/__init__.py`
- `backend/monitoring/sentry.py` — Sentry SDK initialization

### Backend Target Files (MODIFY)
- `backend/config.py` — Add `sentry_dsn` config param
- `backend/api/app.py` — Initialize Sentry on startup if DSN configured

### Frontend Target Files (NEW)
- `frontend/src/lib/sentry.ts` — Sentry React SDK init

### Frontend Target Files (MODIFY)
- `frontend/src/main.tsx` — Import sentry init
- `frontend/src/components/error-boundary.tsx` — Wire Sentry error capture

### Specification

#### Backend
1. Add `sentry_dsn: str = ""` to config (empty = disabled)
2. Create `backend/monitoring/sentry.py`:
   ```python
   import sentry_sdk
   from sentry_sdk.integrations.fastapi import FastApiIntegration
   
   def init_sentry(dsn: str) -> None:
       if dsn:
           sentry_sdk.init(dsn=dsn, integrations=[FastApiIntegration()], traces_sample_rate=0.1)
   ```
3. Call `init_sentry(settings.sentry_dsn)` in `app.py` startup

#### Frontend
1. Create `frontend/src/lib/sentry.ts`:
   ```typescript
   import * as Sentry from "@sentry/react";
   
   export function initSentry() {
     const dsn = import.meta.env.VITE_SENTRY_DSN;
     if (dsn) {
       Sentry.init({ dsn, tracesSampleRate: 0.1 });
     }
   }
   ```
2. Call `initSentry()` in `main.tsx` before React render
3. Update `ErrorBoundary` to capture errors with Sentry

### Config
- `EROCK_SENTRY_DSN` env var (backend)
- `VITE_SENTRY_DSN` env var (frontend)
- Both default to empty string — Sentry disabled unless configured

### Tests
- Backend: Sentry init with/without DSN (+2 tests)
- Frontend: ErrorBoundary captures error (+1 test)

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| jest-axe installed | package.json dependency |
| 6+ a11y tests pass | vitest output |
| No WCAG 2.1 AA violations on tested pages | Test assertions |
| Sentry SDK initialized (backend) | Code review |
| Sentry SDK initialized (frontend) | Code review |
| Sentry disabled when DSN empty | Test |
| All existing tests pass | pytest + vitest |

---

*BLUEPRINT — BATCH-52 — AIV Framework v5.1 — Lead Agent*
