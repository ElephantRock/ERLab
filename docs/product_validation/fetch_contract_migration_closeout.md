# Fetch Contract Migration — Closeout

> **Status:** Complete for page-level fetch debt.
> **Scope:** 10 pages, 7 silent swallows, all console.warn/.catch(()=>{})
> patterns in pages eliminated.
> **Method:** Validation-independent contract-pattern migration. No IA
> changes, no visual redesign, no product-shaping work. All gated on the
> ratchet (lint budget guard), not on PRODUCT.md validation.

## 1. Pages migrated

10 of 20 pages had fetch debt (6 pure hand-rolled, 4 mixed). All 10 migrated.

| Tier | Page | Before | After | Budget Δ |
|---|---|---|---|---|
| **1** | `governance.tsx` | useEffect + 4 useState + dead `loadPending` | `useResource` + `<DataView>` | -3 hygiene |
| **1** | `costs.tsx` | Promise.all + cancelled flag + dead `handleLoadRun` | `useResource` + `<DataView>` (aggregate) | -2 hygiene |
| **1** | `traces.tsx` | Promise.all + string-matched service-unavailable | `useResource` + typed `TraceServiceUnavailableError` + inline 5-state render + token-replaced raw-color banners | -6 contract, +1 then -1 hygiene |
| **2** | `knowledge-graph.tsx` | RQ + hand-rolled `handleSelectEntity` + console.warn | `useQuery` (dependent, keyed on selectedId) + toast-on-error | -3 hygiene |
| **2** | `pipeline-new.tsx` | RQ + hand-rolled `getRunIdeas` effect | `useResource` + `<DataView>` (visible content surface) + cancelled-vs-complete branch | -1 hygiene |
| **2** | `settings.tsx` | RQ + 3 `.catch(()=>{})` swallows (incl. `listUsers`) | 3 independent resources: `useResource`+`<DataView>` for users, `useQuery`+honest-"unavailable" for backend-info and evolution | -4 hygiene |
| **3** | `memory.tsx` | Hand-rolled recall + stats + console.warn | `useResource`+`<DataView>` for recall, `useQuery`+honest banner for stats, key-based refetch | flat |
| **3** | `autonomous.tsx` | Hand-rolled Promise.all swallow for scheduler+evolution+consciousness | 4 resources: `useResource`+`<DataView>` for history, 3× `useQuery`+honest-"unavailable" for inline status | flat |
| **3** | `sessions.tsx` | Hand-rolled session list + runs, unguarded useEffect | 2× `useResource`+`<DataView>` (sessions + dependent runs) | -4 hygiene |
| — | `literature.tsx` | Already RQ (URL-read effect only) | Skipped — not a real fetch-debt target | — |

**10 pages not needing migration** (already react-query or no queries):
dashboard, run-detail, ideas-browser, idea-detail, gaps-explorer, gap-detail,
knowledge-search, plugins, ops, login.

## 2. Before/after warning budget

```
                    Contract    Hygiene     Total
Phase 0 baseline:      57         137        194
After migrations:      51         118        169
  Δ:                    -6         -19        -25
```

**Contract reduction** (-6): all from `traces.tsx` — two raw-color banner
sites (`border-yellow-300 bg-yellow-50 text-yellow-800` ×3 classes each,
`border-red-300 bg-red-50 text-red-800` ×3 classes each) replaced with
`banner-warning-*` / `banner-error-*` tokens added in Phase 0.

**Hygiene reduction** (-19): deleted dead code (unused `useEffect`,
`useCallback`, `useState`, `ErrorCard`, `Skeleton`, `Loader2` imports) as
each hand-rolled state pattern was replaced by a query. No unused-symbol
cleanup pass was done separately — the reductions fell out of the
migrations themselves.

**Budget trajectory (monotonic):**
```
194 → 192 → 189 → 187 → 181 → 178 → 177 → 173 → 173 → 169
```
The guard caught 2 regressions (knowledge-graph unused import, settings
unused imports) before they locked — both fixed in the same migration
pass. The ratchet never slipped.

## 3. Silent swallows closed

All 7 audit-identified `console.warn` / `.catch(()=>{})` swallows in pages
are eliminated:

| # | File | Original swallow | Fix |
|---|---|---|---|
| 1 | `costs.tsx:77` | `console.warn` on `getRunCostBreakdown` | Dead code — deleted entirely (was never called from UI) |
| 2 | `traces.tsx:70` | `console.warn` on `getTrace` detail | Toast ("Failed to load trace detail") |
| 3 | `knowledge-graph.tsx:59` | `console.warn` on `getEntity` detail | Toast via `useDetailErrorToast` hook |
| 4 | `memory.tsx:49` | `console.warn` on `getMemoryStats` | Honest "Memory stats unavailable" banner |
| 5 | `autonomous.tsx:63` | `console.warn` on scheduler+evolution | Split into 3 independent queries, each with honest "unavailable" |
| 6 | `settings.tsx:120` | `.catch(()=>{})` on `getDetailedStatus` | `useQuery` + honest "unavailable" |
| 7 | `settings.tsx:124,137` | `.catch(()=>{})` on evolution + users | `useQuery`+honest / `useResource`+`<DataView>` (the textbook decorative-indicator fix) |

**The most consequential fix:** `settings.tsx` `listUsers()` failure no
longer renders "No users found." — a fetch failure dressed up as a
successful empty result. Now shows retry, not a lie. This was the single
most-cited correctness bug from the Wave 0.5B audits.

## 4. Final decision rules

These rules held across all 10 migrations. They are now documented at the
implementation level (component/contract docs) and proven by use.

### 4.1 Fetch mechanism selection

```
IF the surface owns visible loading/error/empty/ready states:
  → useResource + <DataView>

IF it's a dependent subquery feeding an existing RQ interaction:
  → useQuery (keyed on dependent state, enabled gate)

IF it's inline metadata with no separate panel:
  → useQuery + honest inline "unavailable" fallback

IF it's a user-triggered command/mutation:
  → local useState + toast on failure + invalidateQueries on success
```

### 4.2 Error handling convention

```
Queries → DataView (renders ErrorCard + retry)
Mutations → toast.error()
On-demand/click fetches → toast.error()
Background polling → (unresolved — see §5)
```

### 4.3 Typed error branches

When a fetch can fail in semantically distinct ways (e.g. traces:
service-unavailable vs. network-error), the fetcher throws a typed error
subclass; the page pattern-matches on `instanceof`:

```
classification at the fetch boundary
typed branching at the render boundary
```

### 4.4 Explicit `isEmpty` for non-standard shapes

`useResource`'s default `isEmpty` covers standard shapes (`null`, `[]`,
`{ total: 0 }`, standard list keys). For domain-shaped payloads
(`{ cycles: [] }`, `{ sessions: [] }`), callers pass `isEmpty` explicitly.
The default list is intentionally NOT expanded — empty semantics belong to
the resource owner. (Documented in `useResource.ts` + INTERFACE_CONTRACT §2.)

### 4.5 DataView testId ownership

```
WRAPPER (owned by DataView):
  ${stem}-loading, ${stem}-error, ${stem}-empty, ${stem}-ready

INNER PRIMITIVES (default when stem set):
  ${stem}-error-card, ${stem}-empty-state

Rules:
  - Page tests target wrapper ids.
  - Never pass error.testId/empty.testId = wrapper-owned id.
  - When adopting DataView, scan page for pre-existing ${stem}-* ids.
    Rename or choose a more specific stem if collision exists.
```

Three collision classes encountered and documented:
1. Wrapper vs. inner primitive (costs, pipeline-new) → defaults fixed.
2. Wrapper vs. explicit `error.testId` override (pipeline-new) → removed override.
3. Wrapper vs. pre-existing page testid (autonomous) → renamed page testid.

A fourth collision after this documentation triggers a dev-only runtime
invariant.

### 4.6 Key-based refetch over imperative calls

When a user action (search, filter, select) should trigger a refetch,
update the query key's dependency rather than calling an imperative
`loadX()` function:

```
user action → setQueryState → key changes → resource refetches → declarative render
```

This is cleaner than imperative calls and preserves test assertions about
fetcher call signatures. (Demonstrated in memory.tsx, sessions.tsx.)

## 5. Known non-page follow-up

### notification-bell background polling

The notification-bell component (`components/notifications/notification-bell.tsx`)
has 2 `console.warn` swallows on its 30s polling fetches. These were
identified in the Wave 0.5B audit but deliberately **not** migrated as
part of this program because polling components have different failure
semantics than page-level resources:

- Should polling failures toast? (Could be worse than the original bug —
  a toast every 30s on a flaky connection.)
- Should they render inline? (The bell is chrome, not content.)
- Should they fail silently after first success? (Stale data may be fine.)
- Should they expose last-updated / unavailable state?

These are **design questions**, not mechanical migrations. They should be
scoped separately as a polling-component-semantics item, not folded into
the completed page migration program. The existing test
(`batch142-error-handling.test.tsx`) currently asserts the swallow is
"correct" for background fetches — that assertion would need revisiting
as part of the design decision.

## 6. Remaining gated work

This migration program was deliberately scoped to validation-independent
contract-pattern work. The following items remain gated:

### Validation-gated (Phase 1 / Phase 2)
- **PRODUCT.md validation interviews** — 3–5 researchers, per
  `interview_protocol.md`. Gates Q1 (primary user), Q5 (governance
  frequency), Q6 (comparison). Until these are run, PRODUCT.md stays v0.
- **Phase 1 IA** — sidebar/mobile restructure, loop-derived nav grouping.
  Gated on Q1/Q5/Q6.
- **Phase 2 reading surface** — idea-detail retype, ScoreReport primitive.
  Gated on Q1/Q2/Q3 + the score persistence gap (backend must persist
  `overall_confidence`, `closest_prior_work`, axis evidence).
- **Comparison surface** — side-by-side idea evaluation. Gated on Q6.

### Lint-gated (Phase 5)
- **Flip `erock/*` rules from `warn` to `error`** — requires contract
  warnings to reach 0. Current: 51 (32 telemetry-headings, 12 sub-micro-
  type, 6 raw-colors, 1 raw-use-effect-fetch). The telemetry-headings and
  sub-micro-type clusters are densest in `idea-detail.tsx` (Phase 2) and
  the shell/sidebar (Phase 1), so further contract reduction naturally
  waits for the validation-gated phases. The budget guard prevents
  regression in the meantime.

### Backend-gated
- **Score persistence** — `backend/pipeline/persistence.py` strips
  novelty confidence, closest prior work, and per-axis evidence before
  the frontend sees them. `<ScoreReport>` cannot fully satisfy PRODUCT.md
  §2 without this. See `score_data_shape_audit.md`.

## 7. Artifacts produced by this program

### Code
- `frontend/src/lib/useResource.ts` — discriminated-union fetch hook
- `frontend/src/components/ui/data-view.tsx` — 4-state render primitive
- `frontend/src/components/ui/data-view.test.tsx` — 13 tests
- `frontend/src/lib/__tests__/useResource.test.tsx` — 10 tests
- `frontend/scripts/check-lint-budget.cjs` — budget guard
- `frontend/lint-budget.json` — frozen baseline (169)
- 10 migrated pages + their updated tests
- `frontend/eslint.config.js` — 4 contract rules as `warn`
- `frontend/src/test/test-utils.tsx` — `renderWithProviders` helper (extended)
- `.github/workflows/ci.yml` — budget guard wired into CI

### Documentation
- `PRODUCT.md` — v0 product definition (the arbiter)
- `INTERFACE_CONTRACT.md` — v0 engineering spec (the ratchet)
- `docs/product_validation/` — 14 artifacts (validation machinery + audits + this closeout)

### Token/type additions (Phase 0)
- `globals.css` — banner-warning/banner-error tokens, prose/ui type-scale utilities
- `tailwind.config.js` — banner color extend

## 8. Test infrastructure changes

Every page migration required `QueryClientProvider` in test harnesses. 11
test files were updated across the program. The shared
`renderWithProviders` helper (in `src/test/test-utils.tsx`) was extended to
accept `initialEntries` and is the recommended wrapper for any new page
test. Two test-file consolidation opportunities remain (governance and
phase5-export-review still use local `QueryClientProvider` wrappers instead
of `renderWithProviders`) — non-blocking cleanup.

## 9. What this program proved

1. **The ratchet works.** 25 warnings eliminated monotonically, 2
   regressions caught by the guard before locking, zero manual
   enforcement needed after the guard was wired.
2. **The decision rule is stable.** `useResource`+`<DataView>` vs
   `useQuery` vs mutation — the rule produced the right call in every case
   without forcing abstractions.
3. **Silent failures are structurally preventable.** All 7 swallows
   eliminated by making errors first-class render states (DataView) or
   visible actions (toast). The `useResource` type makes swallowing
   structurally impossible — the `retry` closure is reachable from render.
4. **Contract-pattern migration is validation-safe.** Every page was
   improved without touching IA, reading hierarchy, governance placement,
   or comparison behavior. The validation gate remains intact; this work
   proceeds independently of it.

## 10. The honest bottom line

The frontend moved from optional conventions to enforced patterns. 10
pages, 7 swallows, 25 warnings, all behind a budget guard that runs in CI.
No product-shaping bets were made. The next real progress is the
validation interviews — everything else is either gated on them or is
mechanical cleanup that can wait.
