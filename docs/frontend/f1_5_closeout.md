# F1.5 Closeout — Critical Product-Flow Integration

## Status

```
F1.5     CLOSED — production product flows tested through shared router + cache
F1.6     NEXT — runtime error observability
F1       OPEN
```

## Commit chain

```
d688e16  refactor(frontend): expose production router composition for integration
285f340  docs(f1.5): close critical product-flow integration (superseded)
3eddb19  test(f1.5): add production-router research flow integration
bd6e7dc  docs(f1.5): freeze critical frontend product journeys
```

## Architecture

### Shared route registry (AppRoutes.tsx)
Production `createRoutes(pages)` function maps the exact production route
paths → page components. Both App.tsx (lazy imports) and tests (eager
imports) use the SAME route declarations — no test-owned route replicas.

### Transport boundary
Tests mock `globalThis.fetch` — the lowest HTTP boundary. All transport
functions (`apiFetchJson`, `apiFetchVoid`, `apiFetchUnchecked`) delegate
to fetch internally and run their real implementations. The real
`apiFetchUnchecked` is NOT replaced — it calls the mocked fetch.

Production decoders run on mocked responses. `callContract` validates
responses through the real `JsonContract<T>` decoders.

### Test suite (10 tests, all through production route registry)

| # | Test | Route registry | Transport | Decoder |
|---|---|---|---|---|
| 1 | Golden flow: dashboard → idea detail | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 2 | Literature: confirm → pending → exactly 1 request | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 3 | Literature: failure → retry succeeds | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 4 | Gap status: mutation → authoritative refetch | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 5 | Gap A/B: same router, late mutation isolation | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 6 | Dashboard: governance fails, ideas render | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 7 | Malformed papers → contract failure | ✓ createRoutes | ✓ fetch mock | ✓ real decoder |
| 8 | Authenticated deep link | ✓ createRoutes + ProtectedRoute | ✓ fetch mock | ✓ real |
| 9 | Unauthenticated → login redirect | ✓ createRoutes + ProtectedRoute | N/A | N/A |
| 10 | Unknown route → fallback | ✓ createRoutes (Navigate) | ✓ fetch mock | ✓ real |

## All gates verified

```
test-owned production route replicas                       0
principal tests replacing apiFetchUnchecked                0
production createRoutes mounted                            proven
golden flow (dashboard → idea detail)                     proven
literature success reaches transport boundary              proven
literature duplicate submission blocked                   proven
literature failure → production retry → success           proven
gap A/B uses one persistent router and QueryClient        proven
auth deep links use production ProtectedRoute             proven
unknown fallback uses production route composition        proven
new unchecked callers                                     0 (budget: 58)
TypeScript errors                                          0
test failures                                              0 (824 pass)
new ESLint warnings                                        0 (63 total)
new suppressions                                           0
working tree                                               clean
```
