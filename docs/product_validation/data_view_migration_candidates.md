# `<DataView>` Migration Candidates — Render-State Inventory

> **Purpose:** every loading, error, and empty-state render pattern, mapped
> to the sanctioned `<DataView>` primitive (which composes `Skeleton`,
> `ErrorCard`, `EmptyState`). Validation-independent.
>
> **Headline finding:** `<DataView>` and `useResource` have **zero
> production consumers** today. Every page either hand-rolls the four
> states inline in JSX or (worse) silently swallows the error/empty case.
> The convention is `INTERFACE_CONTRACT.md §2`: **mutations → toast;
> queries → `<DataView>`/`useResource`.**

## Summary table

| Pattern | Count | Sanctioned replacement |
|---|---|---|
| `<Skeleton>` shared (LOADING) | ~18 files / 40+ sites | `<DataView>` `loading.lines` (auto via `useResource` loading) |
| `<Loader2 animate-spin>` on QUERY loaders | 8 full-page/panel sites | `<DataView>` loading (Skeleton); Loader2 stays for MUTATION buttons (~18 sites, keep) |
| Plain "Loading…" text | 9 sites | `<DataView>` loading (Skeleton) |
| Bespoke animate-spin div | 1 (`App.tsx` Suspense) | Keep (Suspense boundary) |
| `<ErrorCard>` shared | 10 sites | `<DataView>` `error` branch (auto) |
| Inline error div/Card, QUERY | ~7 sites | `<ErrorCard>` → `<DataView>` |
| `toast.error` MUTATION | ~26 sites | **Keep** (correct per contract) |
| `console.warn` swallow, QUERY | **7 sites** | `useResource` → `<DataView>` error + retry |
| `setError` inline, QUERY | ~9 pages | `useResource` error → `<DataView>` |
| Empty `.catch(()=>{})`, QUERY | **3 sites** (settings) + 1 minor | `useResource` (surfaces error) |
| `<EmptyState>` shared | 10 sites | `<DataView>` `empty` config |
| Inline empty div/Card | ~17 sites | `<EmptyState>` → `<DataView>` `empty` |
| Render-null on empty | 5 sites | `<DataView>` `empty` (or keep for truly-optional chrome) |
| `length===0 ? empty : list` ternary | ~12 list pages | `<DataView>` render-prop |

## LOADING patterns

### 1. `<Skeleton>` (shared) — QUERY sites
`dashboard.tsx` (159,198,276,431,452), `costs.tsx:88-90`, `ops.tsx:67`,
`governance.tsx:82-84`, `gaps-explorer.tsx:231`, `ideas-browser.tsx:193`,
`knowledge-search.tsx:100`, `literature.tsx:81`, `plugins.tsx:119`,
`traces.tsx:84-86`, `run-detail.tsx:147-148`, `idea-detail.tsx:91-95`,
`gap-detail.tsx:40-43`, plus settings/governance-panel/global-search-dialog
inline skeletons. **All migrate to `<DataView>` loading (content-shaped).**

### 2. `<Loader2 animate-spin>` — split by purpose
- **MUTATION buttons (keep as-is, ~18 sites):** export-dialog, share-dialog,
  feedback-form, fix-section-button, governance-panel, revision-history,
  autonomous-form, run-config-form, stage-progress, stage-model-editor,
  run-detail export/resume buttons, autonomous scheduler buttons, plugins install.
- **QUERY loaders (migrate to `<DataView>`, 8 sites):**
  `autonomous.tsx:128`, `sessions.tsx:59,141`, `knowledge-graph.tsx:149`,
  `memory.tsx:172`, `revision-history-drawer.tsx:78`.

### 3. Plain "Loading…" text — QUERY sites (all migrate)
`App.tsx:48` (auth check), `comment-thread.tsx:56`, `estimate-card.tsx:46`,
`autonomous.tsx:129`, `memory.tsx:173`, `pipeline-new.tsx:463`,
`sessions.tsx:60,142`, `stage-model-selector.tsx:100`.

### 4. Bespoke spinner
`App.tsx:34` Suspense fallback — keep (it's the route-level Suspense boundary,
legitimately bespoke).

## ERROR patterns

### 6. `<ErrorCard>` (shared) — QUERY sites (correct, just wrap in DataView)
`costs.tsx:100`, `governance.tsx:94`, `gaps-explorer.tsx:235`,
`knowledge-search.tsx:104`, `literature.tsx:85`, `ops.tsx:74`,
`autonomous.tsx:147`, `governance-panel.tsx:163`, `model-status-panel.tsx:48`,
`pipeline-new.tsx:289,462`.

### 7. Inline error (hand-rolled ErrorCard) — QUERY sites
`ideas-browser.tsx:197-223` (richer than ErrorCard — has Retry + "Start New
Run"), `memory.tsx:178-189`, `sessions.tsx:66-72`, `idea-detail.tsx:101-107`
(404), `gap-detail.tsx:48-61` (404), `run-detail.tsx:153-167` (404),
`traces.tsx:99-113`.

### 8. `toast.error` — MUTATION sites (~26 total)
All correct per contract. Inventory-only. Highest counts: fix-section-button
(3), stage-model-editor (3), notification-bell (2), governance (2),
run-detail (2); the rest 1 each.

### 9. `console.warn` swallow — QUERY sites (the high-value targets)
| File:line | What's swallowed | Symptom |
|---|---|---|
| `notification-bell.tsx:40` | unread-count fetch | badge silently shows 0 |
| `notification-bell.tsx:51` | notifications list | dropdown silently empty |
| `autonomous.tsx:63` | scheduler + evolution | panel silently blank |
| `costs.tsx:77` | per-run cost drill-down | run row silently missing |
| `knowledge-graph.tsx:59` | entity detail | detail panel silently empty |
| `memory.tsx:49` | memory stats | stats header silently absent |
| `traces.tsx:70` | trace detail | click silently does nothing |

### 10. `setError` inline — QUERY sites
`autonomous.tsx`, `costs.tsx`, `governance.tsx`, `sessions.tsx`,
`memory.tsx`, `traces.tsx`, `pipeline-new.tsx`, `login.tsx` (auth — OK),
`usePipelineProgress.ts`, `estimate-card.tsx`, `stage-model-selector.tsx`.

### 11. Empty `.catch(()=>{})` — QUERY sites
**`settings.tsx:120,124,137`** (detailedStatus, evolutionStatus, users) —
the most consequential: `listUsers` failure renders as "No users found"
(settings.tsx:426), the textbook decorative-indicator. Plus
`stage-model-selector.tsx:92` (minor, best-effort reset).

## EMPTY patterns

### 12. `<EmptyState>` (shared) — QUERY sites (correct)
`autonomous.tsx:305`, `gaps-explorer.tsx:277`, `governance.tsx:104`,
`ideas-browser.tsx:293`, `knowledge-search.tsx:106`, `literature.tsx:87`,
`sessions.tsx:79`, `traces.tsx:158`, `proposal-review-panel.tsx:86,107`,
`quality-check-panel.tsx:73`.

### 13. Inline empty (hand-rolled EmptyState) — ~17 sites
`dashboard.tsx:180-186,441-446`, `memory.tsx:221-226`, `plugins.tsx:124-127`,
`knowledge-graph.tsx:176-181`, `settings.tsx:425-426`, `run-detail.tsx:513-516`,
`comment-thread.tsx:57-60`, `governance-panel.tsx:169-173`,
`revision-history-drawer.tsx:83-85`, `evaluation-card.tsx:57`,
`entity-detail.tsx:100-101`, `notification-bell.tsx:130-133`,
`activity-log.tsx:44`, `tree-visualization.tsx:183-188`,
`global-search-dialog.tsx:148-151,174-177`, `cost-breakdown-table.tsx:31-35`.

### 14. Render-null on empty (the "decorative indicator")
`domain-breakdown.tsx:24`, `run-status-chart.tsx:26`,
`quality-check-panel.tsx:32`, `remediation-banner.tsx:33`,
`model-status-panel.tsx:74`, `dashboard.tsx:451` (`hasChartData` gates the
whole Analytics section — omitted rather than empty-stated).

### 15. `length===0 ? empty : list` ternary — ~12 list pages
The prime `<DataView>` render-prop targets: ideas-browser, gaps-explorer,
governance, knowledge-search, literature, memory, plugins, autonomous,
costs, run-detail, settings, sessions.

---

## HIGHEST-PRIORITY: "Empty-as-success" anti-pattern

Sites where a **failed or empty fetch renders as if successful** — the user
sees blank/zero/absent with no signal anything went wrong. These are the
PRODUCT.md "decorative indicator" anti-pattern; `useResource`+`<DataView>`
makes them structurally impossible.

### Tier 1 — Failed fetch silently renders as success (data loss invisible)

| # | File:line | Symptom | Migration fix |
|---|---|---|---|
| 1 | `settings.tsx:120` | detailedStatus swallow → settings renders with no detailed status, no error | `useResource` → error state with retry |
| 2 | `settings.tsx:124` | evolutionStatus swallow → evolution panel silently absent | same |
| 3 | `settings.tsx:137` | `listUsers` swallow → renders "No users found" when really the fetch failed | same — the textbook case |
| 4 | `autonomous.tsx:63` | scheduler/evolution swallow → panel blank; `error` state never set for this fetch | same |
| 5 | `notification-bell.tsx:40,51` | failed notifications fetch indistinguishable from "no notifications" | same |
| 6 | `costs.tsx:77` | per-run drill-down swallow → run's cost row never appears | same |
| 7 | `memory.tsx:49` | stats swallow → stats header absent while rest of page loads | same |
| 8 | `traces.tsx:70` | trace detail swallow → click silently does nothing | same |
| 9 | `knowledge-graph.tsx:59` | entity detail swallow → click silently shows nothing | same |
| 10 | `estimate-card.tsx:53` | `if (error || !estimate) return null` → failed estimate makes card vanish | same |

### Tier 2 — Empty result renders as decorative/blank, not honest empty
11. `dashboard.tsx:451` — `{hasChartData && (...)}` omits Analytics section.
12. `domain-breakdown.tsx:24`, `run-status-chart.tsx:26` — `return null` on empty.
13. `remediation-banner.tsx:33`, `quality-check-panel.tsx:32` — `return null`.

### Migration fix (all Tier 1)
Replace `useEffect + fetch + .catch(()=>{})` with
`useResource(["key"], fetcher)`, then render through
`<DataView resource={res} empty={...}>{data => ...}</DataView>`. The error
case becomes `<ErrorCard>` + "Try again" wired to `resource.retry`; the
empty case becomes an honest `<EmptyState>` — exactly INTERFACE_CONTRACT
§2. The 7 `console.warn` swallows (#9) and 3 settings empty-catches (#11)
collapse into the same single migration per file.

### Note on `notification-bell` polling
The `console.warn` on the 30s polling fetch (line 40) is currently tested
as "correct" in `batch142-error-handling.test.tsx` for *background* fetches.
The contract's goal (`useResource.ts:20-22`) is that errors surface as
`{status:"error", retry}` reachable from render. For a background-poll
fetch the right pattern may be a subtle: surface the error but don't
interrupt — e.g. a small "reconnecting…" state on the bell rather than a
full `<ErrorCard>`. Decide during the notification-bell migration; the test
updates to assert error-reachability, not swallow.

## Cross-reference

- The fetch-mechanism side (which `useEffect`s to convert) is in
  `use_resource_migration_candidates.md`. The two audits are complementary:
  migrate `useResource` and adopt `<DataView>` together per page, otherwise
  the page is half-migrated.
- The status-indicator overlaps (some "empty-as-success" sites are also
  decorative-status sites) are cross-referenced in
  `status_indicator_source_map.md`.
