# F1 Closeout — Frontend Architecture Program

## Status

```
F1       CLOSED — truthful API boundaries, route integrity, query/mutation
                  lifecycle, product-flow integration, runtime error
                  observability, and final architecture reconciliation
```

## Wave summary

| Wave | Mission | Status |
|---|---|---|
| F0 | Restore clean TypeScript build (101→0 errors, no suppressions) | CLOSED |
| F1.0 | Audit frontend architecture baseline | CLOSED |
| F1.1 | Canonical API boundary (contract layer, transport split, unchecked budget) | CLOSED |
| F1.2 | Route and identity integrity (strict route-ID parser, lazy gap-papers) | CLOSED |
| F1.3 | Truthful query lifecycle (useResource, scoped retry, independent resources) | CLOSED |
| F1.4 | Mutation integrity (retry:false, pending states, cache invalidation, cache-owned) | CLOSED |
| F1.5 | Critical product-flow integration (golden journey, gap A/B isolation, ingest persistence) | CLOSED |
| F1.6 | Runtime error observability (governed endpoint, two-tier boundary, global observers, lazy recovery) | CLOSED |
| F1.7 | Final architecture reconciliation (inventory, ownership seal, ratchet match) | CLOSED |

## Key architectural achievements

### Transport layer (F1.1)
- Split `apiFetch` into `apiFetchJson` (returns `unknown`), `apiFetchVoid`, `apiFetchUnchecked<T>` (legacy adapter with documented cast)
- Introduced `JsonContract<T>` / `VoidContract` discriminated union with `callContract()` overloads and runtime `ResponseDecoder<T>` validation
- Unchecked caller budget ratcheted from 78 → 58 (20 callers migrated to contracts)
- 21 contract-backed endpoints with complete decoders

### Route integrity (F1.2)
- `parseRouteId(raw): RouteIdResult` with strict canonical positive-decimal grammar `/^[1-9]\d*$/`
- All detail pages validate ID before any network request fires
- Shared production route registry (`createRoutes(pages)`) — no test-owned replicas

### Query lifecycle (F1.3)
- `useResource` discriminated union (`loading|ready|error+retry|empty`)
- Independent resource isolation — a failure in one widget does not collapse others
- Scoped retry via `WidgetError` with explicit retry buttons

### Mutation integrity (F1.4 + F1.5c)
- Explicit `retry: false` on all non-idempotent mutations
- `MutationCache` with cache-owned `meta.invalidateQueries` / `meta.invalidatePrefixes`
- Mutation completion authority survives component unmount (F1.5c)

### Product-flow integration (F1.5)
- Golden research journey: dashboard → run → idea → gap → matched papers
- Gap A/B cache isolation: routed cross-route transition, late mutation cannot corrupt adjacent gap
- Truthful ingest persistence: POST writes to vector store, GET reads from same store

### Runtime error observability (F1.6)
- Governed `POST /api/v1/diagnostics/runtime-error` (anonymous, rate-limited, body-capped, origin-checked)
- Synchronous never-throw reporter with canonical incident deduplication (WeakMap + TTL'd fingerprint)
- Two-tier boundary (root full-screen + route AppShell-preserved)
- HMR-safe global observers (Symbol-keyed ownership)
- Lazy-route guarded recovery (one reload via sessionStorage marker)
- Sentry automatic capture disabled — single governed transport

### Architecture reconciliation (F1.7)
- 58 unchecked callers — exact manifest with file, endpoint, material classification
- 10 ownership-uniqueness responsibilities — each with exactly one production owner
- Query/mutation key reconciliation — 14 matches, 3 documented intentional mismatches
- 29-test architecture seal enforcing all structural invariants

## Final verification

### Five-run frontend stability
```
Run 1:  122 files, 984 tests, 0 failures
Run 2:  122 files, 984 tests, 0 failures
Run 3:  122 files, 984 tests, 0 failures
Run 4:  122 files, 984 tests, 0 failures
Run 5:  122 files, 984 tests, 0 failures
```

### Backend suite
```
320 passed, 4 skipped (includes diagnostics endpoint, body-limit middleware,
literature persistence integration tests)
```

### Ratchet reconciliation
```
TypeScript errors                          0 (ts-budget.json baseline 0)
ESLint warnings                           63 (baseline preserved)
Unchecked API callers                     58 (exact manifest in f1_7_architecture_inventory.json)
Raw fetch in pages/components              0
Test-owned route replicas                  0
Runtime observer owners                    1
Sentry runtime transports                  0
Architecture seal tests                   29 (all green)
New suppressions                           0
Working tree                               clean
```

## F1 completion gate

```
architecture inventory entries without disposition          0
material responses accepted through unchecked transport      0
  (all 58 are residual pre-F1.7 callers frozen at F1.1b;
   no F1.7-touched response is unchecked)
raw production fetch callers                                 0
untracked generic transport helpers                           0
FormData callers absent from inventory                        0
unchecked count differing from approved manifest              0

duplicate production route registries                         0
duplicate production QueryClient policies                     0
duplicate production mutation-cache policies                  0
test-owned principal architecture replicas                    0

critical mutations without declared key effects               0
invalidations targeting incorrect identities                  0
query-key ownership conflicts                                 0

critical routes outside production boundaries                 0
parallel runtime-error transports                             0
duplicate global observer ownership                           0

TypeScript errors                                             0
frontend test failures                                        0 (984 pass)
backend test failures                                         0 (320 pass + 4 skipped)
new ESLint warnings                                           0 (63 total)
new suppressions                                              0
unchecked budget                                              58
five-run frontend instability                                 0
working tree                                                  clean
```
