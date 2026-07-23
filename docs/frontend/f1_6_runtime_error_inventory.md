# F1.6.0 — Runtime Error Inventory

## Scope

F1.6 concerns unexpected frontend runtime failures — those outside the
normal query and mutation lifecycle already repaired in F1.3–F1.5.

```text
render exception
lazy route import failure
unexpected event-handler exception
unhandled promise rejection
global window error
third-party visualization crash
authentication composition failure
error-reporting transport failure
```

Expected API, contract, query, and mutation failures remain handled by
their existing local lifecycle UI (`WidgetError`, `ErrorCard`,
`toast.error`) and must NOT be misclassified as application crashes.

## Current state at audit (commit `f983a5c`)

The codebase has a single `ErrorBoundary` class component
(`src/components/error-boundary.tsx`) mounted in two places:

- `main.tsx` — outer mount, inside `BrowserRouter > AuthProvider >
  SettingsProvider > QueryClientProvider`
- `App.tsx` — inner mount, inside `AppShell > ProtectedRoute`

That boundary:

- Catches React render errors from descendants only
- Calls `Sentry.captureException(error)` in a try/catch that swallows
  init failures ("Sentry not initialized — ignore")
- Logs `error` and `info.componentStack` to `console.error` (the
  componentStack is NEVER sent to Sentry — no scope, no tags)
- Renders a full-viewport fallback with the **raw `error.message`** and
  a single **Reload** button
- On reload: `setState({hasError:false})` then unconditional
  `window.location.reload()` (the state reset is redundant)

There are NO global listeners for `window.error` or `unhandledrejection`
in application code.

The `QueryClient` has NO `QueryCache.onError` and the `MutationCache`
has NO `onError` — failed queries/mutations are silent at the
observability layer (they land in `query.error` / `mutation.error` and
surface through `WidgetError` / `ErrorCard` / `toast.error`).

`initSentry()` in `src/lib/sentry.ts` reads
`import.meta.env.VITE_SENTRY_DSN` and is essentially dormant (only one
capture site, no scope/context/user/route, no `release`/`beforeSend`,
no transport wrapper, no evidence the DSN is set in any env file).

The 19 lazy-loaded routes in `AppRoutes.tsx` are wrapped in a single
`<Suspense fallback={<LoadingScreen />}>` with no error state. A failed
dynamic import bubbles to the inner `ErrorBoundary`, which hard-reloads
— almost certainly repeating the failure if the deployment manifest is
broken, producing a reload loop.

The `/login` route and everything above the outer boundary (providers)
have NO error catching. A provider crash produces a blank screen.

## Surface-by-surface findings

The machine-readable inventory lives at
`f1_6_runtime_error_inventory.json`. Disposition summary:

| # | Surface | Risk | Disposition |
|---|---|---|---|
| 1 | React render errors | blank-screen, sensitive payload, over-broad fallback | F1.6.2: two-tier boundary, synchronous report, allowlisted message |
| 2 | Lazy-route import failures | reload loop | F1.6.3: `lazyRoute` wrapper, `LazyRouteError`, guarded reload |
| 3 | Event-handler exceptions | silent | F1.6.2: `window.error` observer |
| 4 | Unhandled promise rejections | silent, sensitive payload | F1.6.2: `unhandledrejection` observer, never transmit raw reason |
| 5 | Global window errors | silent | F1.6.2: `window.error` observer, deduplicate against boundary |
| 6 | Third-party component crashes | over-broad fallback | F1.6.2: `RouteErrorBoundary` preserves AppShell |
| 7 | Auth/provider composition failures | blank-screen | F1.6.2: `RootErrorBoundary` wraps providers |
| 8 | Reporting transport failures | silent | F1.6.1: `sendRuntimeErrorReport` + `reportRuntimeError` (synchronous, never throws) |

## Classifications

```text
protected               0
blank_screen_risk       surfaces 1, 7
console_only            surfaces 3, 4, 5
silent                  surfaces 4, 8
over_broad_fallback     surface 1
duplicate_reporting     surfaces 1, 5, 6
sensitive_payload_risk  surfaces 1, 4
no_recovery_path        surfaces 3, 7
```

Every surface has a final disposition. No open questions.

## Pre-existing exclusion — expected handled failures

These must NOT be misclassified as crashes by F1.6:

- `ApiError` (4xx/5xx transport failures) flowing through `useResource`
  → `WidgetError` / `ErrorCard`
- `ApiContractError` (decoder mismatch on 2xx) flowing through
  `useResource` → scoped error UI
- Mutation failures already presented via `toast.error(...)` in the
  mutation's `onError`
- `AbortError` / intentional cancellation (the only SSE-handled case at
  `client.ts:314-318`)

F1.6 filters `AbortError` by name at the observer layer. `ApiError` /
`ApiContractError` are NOT blanket-suppressed: if one reaches a global
observer (indicating an unhandled programming path), it IS reported.
Lifecycle tests prove expected failures never reach global observers
because TanStack catches them into `query.error` / `mutation.error`
locally.

## Reserved hook from prior wave

`extractCorrelationId(headers: Headers)` at
`src/api/contracts/common.ts:391-393` reads `X-Request-ID`. Currently
dead code (the transport discards response headers). F1.6.1 wires this
into the transport so correlation IDs can be attached to runtime
reports when available.

## Goal state after F1.6

```text
F1.6.1  governed backend endpoint + frontend contract + sanitizer
        synchronous reporter + canonical incident registry
F1.6.2  two-tier production boundary (root + route)
        HMR-safe global observers
F1.6.3  lazy-route classification + guarded reload
        Sentry automatic capture disabled (single transport)
F1.6.4  adversarial + architectural seal
F1.6.5  closeout + five-run verification
```
