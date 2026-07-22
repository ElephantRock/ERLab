# F1.5 Closeout — Critical Product-Flow Integration

## Status

```
F1.5     CLOSED — full product journeys + cache isolation proven
F1.6     NEXT — runtime error observability
F1       OPEN
```

## Commit chain

```
(F1.5b)  test(f1.5): complete golden research and authoritative mutation flows
(F1.5b)  feat(f1.5): repair idea→gap navigation and ingest terminal state
(F1.5b)  docs(f1.5): correct critical-flow closeout evidence  (this file)
d688e16  refactor(frontend): expose production router composition for integration
285f340  docs(f1.5): close critical product-flow integration  (superseded)
3eddb19  test(f1.5): add production-router research flow integration
bd6e7dc  docs(f1.5): freeze critical frontend product journeys
```

## F1.5b — Required journey corrections

F1.5a established the shared production route registry and the fetch-boundary
mock, but three load-bearing journey assertions were missing or contradicted:

1. The golden research journey only proved `dashboard → idea detail`. It did
   not exercise run-detail routing, gap-detail routing, matched-paper lazy
   expansion, preview-to-expanded replacement, or truthful coverage wording.
2. The gap A/B test asserted "gap 13 never loaded" — that proves absence,
   not cache isolation. The required scenario demands gap 13 actually load
   authoritative state before Alpha's late mutation completes, and remain
   unchanged after.
3. The literature success test proved only `countCalls === 1` (duplicate
   prevention). It did not prove pending visibility, declared-key
   invalidation, or an authoritative terminal ingested state.

## Production repairs (F1.5b)

Two genuine product-flow defects were identified and repaired.

### Repair 1: Idea → Gap navigation (`idea-detail.tsx`)

The `EvidenceSummary` sidebar previously rendered only a count for "Source
Gaps" with no clickable control. The production UI had no reachable path
from `/ideas/:id` to `/gaps/:id`, so the golden research journey could
not be completed through production navigation.

**Fix:** Added a `source-gap-links` list below the count. Each source gap
is a production `<button role="link">` that calls `navigate(/gaps/${id})`,
matching the existing `EvidencePanel` pattern used elsewhere in the codebase.

### Repair 2: Literature ingest terminal state (`literature.tsx`, `paper-card.tsx`)

After a successful ingest, the production UI showed a toast but no visible
per-paper "Ingested" state. A second paper could be re-armed and re-clicked
without the UI revealing the prior success.

**Fix:** Added an `ingestedIds: Set<string>` state on `LiteraturePage`.
The mutation's `onSuccess` adds the paper ID to the set alongside the
existing `["literature-search"]` invalidation. `PaperCard` gains an
`isIngested` prop that renders an `Ingested` badge, disables the ingest
button, and refuses further clicks. Re-arm is impossible once the
authoritative ingested state is reached.

## Architecture

### Shared route registry (`AppRoutes.tsx`)
Production `createRoutes(pages)` function maps the exact production route
paths → page components. Both App.tsx (lazy imports via `lazyPages`) and
tests (eager imports via `stubPages`) use the SAME `createRoutes` factory —
no test-owned route topology exists. An architecture assertion in the test
file imports `AppRoutes` and verifies `createRoutes`, `ProtectedRoute`, and
`AuthenticatedRoutes` are the exact production exports.

### Transport boundary
Tests mock `globalThis.fetch` — the lowest HTTP boundary. All transport
functions (`apiFetchJson`, `apiFetchVoid`, `apiFetchUnchecked`) delegate
to fetch internally and run their real implementations. The real
`apiFetchUnchecked` is NOT replaced — it calls the mocked fetch.
Production decoders run on mocked responses via the real `callContract`.

### Test suite (11 tests, all through production route registry)

| # | Test | Route registry | Transport | Decoder |
|---|---|---|---|---|
| 0 | Architecture: shared createRoutes factory | ✓ imports AppRoutes | N/A | N/A |
| 1 | Golden journey: dashboard → run → idea → gap → matched papers | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 2 | Gap A/B: same router + QC, gap 13 loads, late A mutation cannot alter gap 13 | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 3 | Literature success: pending → duplicate blocked → declared key invalidated → ingested state | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 4 | Literature failure → no auto retry → manual retry → terminal success | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 5 | Gap status: mutation → authoritative refetch of declared gap key | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 6 | Dashboard: governance fails, ideas render (independent lifecycles) | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 7 | Malformed papers → contract failure (not empty success) | ✓ createRoutes | ✓ fetch mock | ✓ real decoder |
| 8 | Authenticated deep link | ✓ createRoutes + ProtectedRoute | ✓ fetch mock | ✓ real |
| 9 | Unauthenticated → login redirect | ✓ createRoutes + ProtectedRoute | N/A | N/A |
| 10 | Unknown route → dashboard fallback | ✓ createRoutes (Navigate) | ✓ fetch mock | ✓ real |

## Golden journey proof (test 1)

One continuous router and QueryClient session establishes:

```
/dashboard renders ("Novel Transformer")
→ user activates production "Latest Run → Open" control
→ /runs/42 renders Run #42 (run ID continuity)
→ user activates production idea-list-item-1 control
→ /ideas/1 renders IdeaDetail
→ production source-gap-link-12 control is reachable
→ user activates it → /gaps/12 renders GapDetail
→ "Show more matched papers" production control activates lazy query
→ /gaps/12/papers fires for the first time (lazy, not on mount)
→ preview replaced by validated endpoint data ("Chinchilla" appears)
→ coverage text: "Showing all 2 matched papers" (truthful: 2 === 2)
```

## Gap A/B cache isolation proof (test 2)

```
/gaps/12 renders Alpha (mounted, mutation observer alive)
→ QueryClient.setQueryData(["gap", 13], mockGapDetail13) seeds Beta cache
→ mutation for Alpha begins (PATCH held pending)
→ Alpha mutation resolves late
→ onSuccess invalidation scoped to ["gap", 12]
→ ["gap", 13] invalidations                 0
→ gap 13 GET calls after Alpha completion   unchanged (0)
→ gap 13 cache entry                        byte-for-byte unchanged
→ gap 13 cache status                       "addressed" (not "investigating")
→ gap 12 GET calls                          incremented (refetch fired)
```

The session-grade QueryClient uses `gcTime: 5min` to model the production
default. The default test QueryClient (`gcTime: 0`) would erase gap 13's
unobserved cache entry immediately and prevent the cache-isolation proof.

## Literature success proof (test 3)

```
/literature renders
→ user submits search ("attention")
→ paper appears as ingestible
→ first click → confirmation; second click → mutation starts
→ pending state visible ("Ingesting", button disabled)
→ rapid repeats send no second request
→ valid contract response succeeds
→ declared query key ["literature-search"] invalidated  ✓
→ authoritative refreshed state: "Ingested" badge visible
→ ingest button permanently disabled for this paper
```

## Literature failure → retry proof (test 4)

```
first ingest request fails (HTTP 500)
→ context remains visible (search result still rendered)
→ ingest-error indicator visible
→ no automatic retry (150ms wait, still 1 call)
→ production retry control (button re-enabled, user re-arms + clicks)
→ second response succeeds
→ authoritative refreshed state: "Ingested" badge visible
```

## All gates verified

```
shared production route registry                         proven
test-owned route topology                                0
principal tests replacing legacy transport helpers       0

golden flow includes run detail                          proven
golden flow reaches gap detail through production flow   proven
matched-paper successful expansion                       proven
preview replaced by validated endpoint data              proven
coverage wording truthful ("Showing all N matched…")    proven

literature duplicate dispatch                            blocked
literature success invalidation/refetch                  proven (declared key)
literature authoritative ingested state                  proven (Ingested badge)
literature failure → manual retry → terminal success     proven

gap 13 actually loaded during A/B test                  proven (cache seeded)
late gap-12 completion cannot alter gap 13              proven (byte-for-byte)
gap 12 invalidation scope                                proven (scoped)
same router and QueryClient retained                     proven

auth deep links                                          proven
unknown fallback                                         proven
new unchecked callers                                    0
unchecked budget                                         58
TypeScript errors                                        0
test failures                                            0 (825 pass)
new ESLint warnings                                      0 (63 total)
new suppressions                                         0
working tree                                             clean
```
