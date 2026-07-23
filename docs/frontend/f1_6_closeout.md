# F1.6 Closeout — Runtime Error Observability

## Status

```
F1.6     CLOSED — governed runtime error reporting with sanitized transport,
                  two-tier boundary, HMR-safe observers, and lazy-route recovery
F1.7     NEXT — final frontend architecture inventory + ratchet reconciliation
F1       OPEN
```

## Commit chain

```
(F1.6.5)  docs(f1.6): close runtime error observability wave  (this file)
(F1.6.4)  test(f1.6): seal recovery sanitization and deduplication
(F1.6.2)  feat(f1.6): install two-tier production boundary with HMR-safe observers
(F1.6.1)  feat(f1.6): add synchronous reporter with identity-based deduplication
(F1.6.1)  feat(f1.6): add governed runtime-error diagnostic endpoint
(F1.6.0)  docs(f1.6): inventory frontend runtime failure handling
```

## Architecture

### Transport (single governed path)

```
Frontend reportRuntimeError(error, context)
  → synchronous: register incident → return canonical event_id
  → asynchronous: sanitize → sendRuntimeErrorReport (fire-and-forget)
  → transport failure swallowed (never throws, never rejects)

Backend POST /api/v1/diagnostics/runtime-error
  → ASGI body-limit middleware (8 KiB, pre-parser, chunked-safe)
  → strict Pydantic schema (extra=forbid, server re-sanitization)
  → per-IP rate limit (10/min), origin allowlist
  → structured structlog warning (NO raw body/stack logged)
  → 202 {"status":"accepted","event_id":"<echoed>"}

Frontend ack postcondition: ack.event_id === report.event_id
  (validated in sendRuntimeErrorReport, not the static decoder)
```

Sentry browser automatic capture is DISABLED (`defaultIntegrations:false`,
`integrations:[]`). Zero production `Sentry.captureException` /
`captureMessage` call sites. Zero `Sentry.ErrorBoundary` usage. The
backend endpoint is the single governed transport.

### Deduplication (category-independent)

```
Primary:   WeakMap<Error, IncidentRecord>
           → same Error identity wins across channels
           → GC'd with the Error (no permanent suppression)

Fallback:  category-INDEPENDENT fingerprint
           (error name + route pathname + safe top frame + 5s bucket)
           → TTL'd (expiresAt metadata) + size-capped (200 max)
           → cleared on route change (location.key observer)

Result:    render_error caught by boundary + global_error fired by
           window observer for the SAME incident → ONE transport call
```

### Two-tier boundary

```
main.tsx
└── RootErrorBoundary (full-screen fallback)
    └── router/providers/AppShell
        └── RouteErrorBoundary (AppShell preserved; keyed on location.key)
            └── AuthenticatedRoutes (lazy-loaded via lazyRoute)
```

### Global observers (dedicated module)

```
lib/runtime-observers.ts
  installRuntimeObservers(): () => void
  → Symbol.for("erock.runtimeObservers") on globalThis (typed, no `as any`)
  → first install adds 2 listeners; repeat adds 0; teardown removes exactly 2
  → HMR: import.meta.hot.dispose(() => uninstall())
  → AbortError filtered; ApiError IS reportable
  → fire-and-forget (reportRuntimeError is synchronous, never throws)
```

### Lazy-route recovery

```
lazyRoute(loader)
  → import succeeds → LoadedRouteWrapper mounts → useEffect clears marker
  → import fails → throws LazyRouteError (category=lazy_route_error)

Route boundary:
  → !hasLazyRetried → "Reload and retry" (markLazyRetry + window.location.reload)
  → hasLazyRetried → persistent fallback (no loop)

Marker keyed by build+route (never permanent "unknown" — falls back to "dev")
```

## Implementation qualifications (frozen at authorization)

All four qualifications from the review are implemented and tested:

| Qualification | Implementation | Evidence |
|---|---|---|
| Total-function reporter | `fallbackEventId` generated first; entire orchestration in try/catch | Reporter test: "never throws when registerIncident/sanitizer/transport throws" |
| Real TTL on incident registry | `expiresAt` metadata; lazy eviction + hard size cap (200) | Registry test: "expired fingerprint removed", "size cap enforced" |
| Synchronous composite fingerprint key | FNV-1a 32-bit hash of bounded string; NO async Web Crypto | Architecture test: "synchronous composite key (no async hashing)" |
| Real build identifier for lazy-retry | `VITE_BUILD_HASH` → falls back to `'dev'` (never permanent `'unknown'`) | lazy-route-retry test: marker lifecycle |

## Sanitization security invariant

The payload NEVER contains:
- raw `Error.message`
- `error.stack`
- rejection reasons
- request/response bodies, headers, tokens
- research content fragments

Diagnostic utility comes ONLY from:
- `event_id` (client-generated, echoed by backend)
- `category` (4-value enum)
- `error_name` (normalized class name, safe charset, ≤128)
- `route` (pathname only — query/fragment stripped)
- `component_stack` (sanitized: filename-only, credentials stripped, ≤4096)
- `build_version`, `occurred_at`

The adversarial test injects bearer tokens, api_key query params, credential
URLs, 10KB stacks, and research-content fragments into both `Error.message`
and `error.stack` — and asserts NONE survive into the dispatched payload.

## Test matrix

| Phase | File | Tests | Coverage |
|---|---|---|---|
| F1.6.0 | inventory docs | — | 8 surfaces, all dispositioned |
| F1.6.1 | test_diagnostics.py (backend) | 14 | schema, body-limit, chunked, rate-limit, origin, logging |
| F1.6.1 | diagnostics.test.ts | 5 | contract, decoder, ack postcondition |
| F1.6.1 | runtime-error-sanitizer.test.ts | 25 | allowlisted messages, path stripping, sensitive-value stripping |
| F1.6.1 | runtime-error-registry.test.ts | 12 | identity dedup, fingerprint dedup, TTL, size cap, route clear |
| F1.6.1 | runtime-error-reporter.test.ts | 19 | total function, AbortError filter, fire-and-forget |
| F1.6.2 | error-boundary.test.tsx | 10 | root/route fallbacks, retry, route transition, lazy |
| F1.6.2 | runtime-observers.test.ts | 10 | install/uninstall idempotency, filtering |
| F1.6.3 | lazy-route.test.tsx | 8 | wrapper, marker lifecycle, LoadedRouteWrapper clear |
| F1.6.3 | sentry.test.ts | 4 | disablement verification |
| F1.6.4 | f1-6-adversarial.test.tsx | 15 | render/global/sanitization/dedup/lazy/root |
| F1.6.4 | f1-6-architecture.test.ts | 21 | source-level structural invariants |

## Five-run stability verification

```
Run 1:  121 files, 954 tests, 0 failures
Run 2:  121 files, 954 tests, 0 failures
Run 3:  121 files, 954 tests, 0 failures
Run 4:  121 files, 954 tests, 0 failures
Run 5:  121 files, 954 tests, 0 failures
```

Zero flakiness across all five runs.

## All gates verified

```
inventoried runtime-error surfaces without disposition       0
critical routes outside a production boundary                 0
unexpected render failures producing blank screens            0
lazy failures producing permanent Suspense fallback           0
global runtime failures with no bounded reporting path        0
expected query/mutation failures misclassified as crashes     0
duplicate reports for one logical failure                     0
runtime reports containing secrets or research payloads       0
boundary fallback without recovery action                     0
observability transport failure crashing the application      0

synchronous reporter-internal failures propagated             0
incident records surviving beyond their TTL                   0
unbounded fingerprint-registry growth                         0
same Error permanently suppressed                             0
async hashing in synchronous incident registration            0
production retry markers using permanent unknown build        0

new unchecked callers                                         0
unchecked budget                                              58
TypeScript errors                                             0
frontend test failures                                        0 (954 pass)
backend test failures                                         0 (320 pass + 4 skipped)
new ESLint warnings                                           0 (63 total)
new suppressions                                              0
working tree                                                  clean
```
