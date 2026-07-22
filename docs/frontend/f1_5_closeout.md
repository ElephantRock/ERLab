# F1.5 Closeout — Critical Product-Flow Integration

## Status

```
F1.5     CLOSED — full product journeys + cache-isolation + authoritative state
F1.6     NEXT — runtime error observability
F1       OPEN
```

## Commit chain

```
(F1.5c)  fix(f1.5): preserve mutation completion authority across navigation
(F1.5c)  feat(f1.5): expose persisted ingestion state via /literature/ingested
(F1.5c)  test(f1.5): prove routed gap isolation and backend-derived ingest state
(F1.5c)  docs(f1.5): correct final integration closeout evidence  (this file)
bd58ab6  test(f1.5): complete golden research and authoritative mutation flows (F1.5b)
d688e16  refactor(frontend): expose production router composition for integration
bd6e7dc  docs(f1.5): freeze critical frontend product journeys
```

## F1.5c — Two production-level corrections

F1.5b closed the golden journey but left two mutation-seal gaps:

1. The gap A/B test cache-seeded gap 13 rather than routing to it, and
   did not exercise the case where Alpha's mutation completes AFTER
   GapDetailContent(12) unmounts. Investigation revealed that
   `useMutation`'s component-level `onSuccess` is bound to the
   component observer — unmounting the component suppresses the
   callback, so declared invalidations were silently lost and the
   cache drifted from backend truth.

2. The literature "Ingested" badge was driven by a local `Set<string>`
   populated in the mutation's `onSuccess`. This did not survive
   reload/remount and could disagree with the next backend read.

## Production repair 1 — Cache-owned mutation side-effects

**Files:** `src/main.tsx`, `src/lib/mutation-cache.ts`, plus 8 production
useMutation sites migrated to declare `meta.invalidateQueries`.

**Defect:** When a component invoking `useMutation` unmounted before
`mutationFn` resolved (e.g. user navigated away mid-PATCH), the observer
was removed and `onSuccess` never fired. Declared `queryClient.invalidateQueries`
calls were silently lost; the cache became stale.

**Fix:** Added a global `MutationCache` in `main.tsx` whose `onSuccess`
handler is bound to the `Mutation` instance in the cache (not to any
component observer). Each mutation that needs post-success invalidation
declares its targets via `meta.invalidateQueries` (exact keys) and
`meta.invalidatePrefixes` (prefix keys). The cache handler reads these
and performs the invalidation regardless of component mount state.

Component-level `onSuccess`/`onError` remain for UX feedback (toasts) —
losing a toast on unmount is acceptable; losing a cache invalidation is not.

The QueryClient↔MutationCache construction cycle is broken with a getter
closure: `buildMutationCacheForClient(() => queryClientRef)` captures the
client by reference and resolves it lazily when a mutation succeeds (by
which time the assignment has run).

**Migrated mutations** (all now declare `meta.invalidateQueries`):
- `gap-detail.tsx` → `["gap", gapId]`
- `literature.tsx` → `["literature-search"]` (prefix) + `["literature-ingested"]`
- `idea-detail.tsx` → `["idea", ideaId]`
- `plugins.tsx` → `["plugins"]`
- `comment-thread.tsx` → `["comments", ideaId]`
- `feedback-form.tsx` → `["idea", ideaId]`
- `fix-section-button.tsx` → `["idea", ideaId]` + `["section-revisions", ideaId, sectionKey]`
- `governance-panel.tsx` → `["governance-timeline", ideaId]`
- `revision-history-drawer.tsx` → `["section-revisions", ideaId, sectionKey]` + `["idea", ideaId]`
- `stage-model-editor.tsx` (3 mutations) → `["model-overrides"]`

## Production repair 2 — Backend-derived ingest terminal state

**Files:** `backend/api/routes/literature.py`, `frontend/src/api/literature.ts`,
`frontend/src/pages/literature.tsx`.

**Defect:** The "Ingested" badge was driven by a local `Set<string>` that
did not survive reload and was not derived from backend data.

**Fix:** Added `GET /literature/ingested` to the backend, which queries the
vector store's metadata for unique `paper_id` values. The frontend calls
this via a new contract-validated `listIngestedPapers()` (`["literature-ingested"]`
query). The badge now derives from the response: `ingestedIds = new Set(ingestedData?.ids ?? [])`.

The mutation's `meta.invalidateQueries: [["literature-ingested"]]` triggers
an authoritative refetch on success, so the badge reflects backend truth
and survives reload/remount.

## Architecture assertion

Test imports `AppRoutes` and verifies `createRoutes`, `AuthenticatedRoutes`,
and `ProtectedRoute` are the exact production exports. No test-owned route topology.

## Test matrix (13 tests, all through production route registry)

| # | Test | Route registry | Transport | Decoder |
|---|---|---|---|---|
| 0 | Architecture: shared createRoutes factory | ✓ imports AppRoutes | N/A | N/A |
| 1 | Golden journey: dashboard → run → idea → gap → matched papers | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 2 | Gap A/B: routed /gaps/12 → /gaps/13 transition; late mutation survives unmount; back-nav shows authoritative update | ✓ createRoutes + NavigateProbe | ✓ fetch mock | ✓ real |
| 3 | Literature success: pending → duplicate blocked → both declared keys invalidated → backend-derived ingested state | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 3b | Literature terminal state survives remount (fresh QC) | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 4 | Literature failure → no auto retry → manual retry → terminal success | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 5 | Gap status: mutation → authoritative refetch of declared gap key | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 6 | Dashboard: governance fails, ideas render (independent lifecycles) | ✓ createRoutes | ✓ fetch mock | ✓ real |
| 7 | Malformed papers → contract failure (not empty success) | ✓ createRoutes | ✓ fetch mock | ✓ real decoder |
| 8 | Authenticated deep link | ✓ createRoutes + ProtectedRoute | ✓ fetch mock | ✓ real |
| 9 | Unauthenticated → login redirect | ✓ createRoutes + ProtectedRoute | N/A | N/A |
| 10 | Unknown route → dashboard fallback | ✓ createRoutes (Navigate) | ✓ fetch mock | ✓ real |

Plus 2 new literature API unit tests + 3 new backend tests for the
`/literature/ingested` endpoint.

## Gap A/B cache-isolation proof (test 2)

```
/gaps/12 mounts → production router navigates to /gaps/13 (same router)
→ GapDetailContent(12) unmounts
→ GET /gaps/13 executes (real routing, not cache seeding)
→ gap 13 renders authoritative backend status ("addressed")
→ Alpha's late PATCH resolves
→ MutationCache onSuccess fires (cache-scoped, not component-scoped)
→ ["gap", 12] invalidated                                  ✓
→ ["gap", 13] invalidated                                  ✗ (0)
→ gap 13 GET count unchanged                               ✓
→ gap 13 rendered status remains "addressed"               ✓
→ navigate back to /gaps/12
→ gap 12 GET fires (invalidation survived unmount)         ✓
→ gap 12 renders authoritative updated status              ✓
```

The session-grade QueryClient uses `gcTime: 5min` (matches production
default) AND installs the production MutationCache via
`buildMutationCacheForClient`, so the test exercises the same
cache-owned invalidation contract the production app uses.

## Literature authoritative state proof (tests 3 + 3b)

```
initial literature-ingested query fires (baseline state)
→ paper appears as ingestible
→ user confirms → mutation starts → pending visible
→ rapid repeats send no second request
→ POST succeeds
→ MutationCache onSuccess invalidates BOTH:
    ["literature-search"]   (prefix — refresh all cached searches)
    ["literature-ingested"] (exact — authoritative badge source)
→ literature-ingested GET fires again (refetch)
→ second response lists ss-1 as ingested
→ "Ingested" badge appears, derived from backend response
→ ingest button permanently disabled for this paper

REMOUNT TEST (fresh QueryClient):
→ seed backend with ss-1 already ingested
→ first mount: badge appears from backend data
→ unmount entirely → local component state destroyed
→ re-mount with FRESH QueryClient (simulates reload)
→ badge reappears — proving backend-derived, not local
```

## All gates verified

```
shared production route registry                         proven
test-owned route topology                                0
principal tests replacing legacy transport helpers       0

complete golden research journey                         proven
matched-paper success and malformed paths                proven

same-router /gaps/12 → /gaps/13 transition               proven
GET /gaps/13 during pending gap-12 mutation              proven
late gap-12 completion invalidates gap 12                proven
late gap-12 completion cannot alter gap 13               proven
gap-12 success invalidation survives page unmount        proven (MutationCache)
back-nav to /gaps/12 shows authoritative updated state   proven

literature success causes authoritative refetch          proven (both keys)
terminal ingest state derived from backend data          proven
terminal state survives remount/reload                   proven
local client state represented as backend authority      0

auth deep links                                          proven
unknown fallback                                         proven
new unchecked callers                                    0
unchecked budget                                         58
TypeScript errors                                        0
test failures                                            0 (828 pass)
new ESLint warnings                                      0 (63 total)
new suppressions                                         0 (2 prefer-const with justification)
working tree                                             clean
```
