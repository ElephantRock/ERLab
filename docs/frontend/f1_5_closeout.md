# F1.5 Closeout — Critical Product-Flow Integration

## Status

```
F1.5     CLOSED — production product flows tested through real router + cache
F1.6     NEXT — runtime error observability
F1       OPEN
```

## Commit chain

```
3eddb19  test(f1.5): add production-router research flow integration
bd6e7dc  docs(f1.5): freeze critical frontend product journeys
```

## Integration harness

Mock boundary: transport layer (`apiFetchJson`/`apiFetchVoid`/`apiFetchUnchecked`).
Production runs: pages, clients, `callContract`, decoders, `QueryClient`, router.

The transport mock routes by path + method, supports status injection and
malformed-payload injection. A single shared `QueryClient` per test ensures
real cache behavior across route transitions.

Documented mocks:
- `apiFetchJson`/`apiFetchVoid`/`apiFetchUnchecked` (transport)
- `apiFetchBlob` (binary)
- `toast` (sonner — non-visual)
- `ProtectedRoute` (inline mock for auth test #9)

## Test suite (10 tests)

| # | Test | Seams covered |
|---|---|---|
| 1 | Golden research flow: dashboard → idea detail | router, page, client, query, cache |
| 2 | Literature ingest success: confirm → mutation → transport | page, mutation, contract, cache |
| 3 | Literature ingest failure → retry | page, mutation, failure, retry |
| 4 | Gap status success → refetch | page, mutation, query, invalidation |
| 5 | Gap A/B same-router late-mutation isolation | router, cache, mutation, query keys |
| 6 | Dashboard partial failure (governance fails, ideas render) | query, cache, error rendering |
| 7 | Malformed matched-papers → contract failure | contract, decoder, error rendering |
| 8 | Authenticated deep link /gaps/12 | router, page, auth posture |
| 9 | Unauthenticated deep link → redirect to /login | ProtectedRoute, auth gate |
| 10 | Unknown route → fallback to dashboard | router, fallback |

## All gates verified

```
critical journeys without frozen specifications          0
critical tests bypassing the production router            0
critical tests mocking domain API clients                 0
critical tests bypassing runtime decoders                 0
critical tests recreating production lifecycle logic      0
route transitions asserting URL only                      0
cross-route identity mismatches                           0
late gap-A mutation affecting gap B                       0
duplicate literature ingestion requests                   0
mutation success leaving authoritative views stale        0
partial dashboard failure erasing successful resources    0
malformed responses represented as success                0
protected data rendered without authenticated posture     0
new unchecked callers                                     0 (budget: 58)
TypeScript errors                                          0
test failures                                              0 (824 pass)
new ESLint warnings                                        0 (63 total)
new suppressions                                           0
working tree                                               clean
```
