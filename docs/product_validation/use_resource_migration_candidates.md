# `useResource` Migration Candidates

> **Purpose:** page-by-page table of current fetch mechanisms, so Phase 3–5
> migration is mechanical rather than investigative. Validation-independent:
> the data contract is correct regardless of who the user is.
>
> **Correction to earlier estimate:** the prior audit said "11 hand-rolled
> pages." The machine audit finds **6 pure hand-rolled + 4 mixed = 10 pages**
> with fetch debt; the other 10 pages are already react-query or have no
> queries. The earlier figure over-counted.

## Summary counts

| Mechanism | Count | Pages |
|---|---|---|
| **Pure react-query** | 9 | dashboard, run-detail, ideas-browser, idea-detail, gaps-explorer, gap-detail, knowledge-search, plugins, ops |
| **Mixed** (RQ + hand-rolled stragglers) | 4 | pipeline-new, settings, knowledge-graph, literature |
| **Pure hand-rolled** | 6 | memory, costs, governance, traces, sessions, autonomous |
| **No queries** (mutation-only / static) | 1 | login |
| **Total** | 20 | |

**True migration surface: 10 pages** (6 pure hand-rolled + 4 mixed). Three
of the mixed pages are mostly RQ with small stragglers — the easiest wins.

## Page-by-page table

| # | Page | Lines | Mechanism | Error pattern | Empty pattern | Retry | Unmount-safe | Risk |
|---|---|---|---|---|---|---|---|---|
| 1 | dashboard | ~552 | react-query (7q) | `isError` flagged, not surfaced | implicit `?? []` | yes | n/a | **low** |
| 2 | pipeline-new | ~547 | mixed | `ErrorCard` for trigger+ideas | explicit "No ideas" | no | n/a | **medium** |
| 3 | run-detail | ~541 | react-query (2q+1m) | `runError` → "not found" card | handled inline | yes | n/a | **low** |
| 4 | ideas-browser | ~321 | react-query (1q) | full `isError` UI + retry | `EmptyState` (filter-aware) | yes | n/a | **low** |
| 5 | idea-detail | ~778 | react-query (1q+1m) | "not found" card | not-found card | yes | n/a | **low** |
| 6 | gaps-explorer | ~306 | react-query (2q) | `ErrorCard` | `EmptyState` | yes | n/a | **low** |
| 7 | gap-detail | ~262 | react-query (1q) | "not found" card | not-found card | yes | n/a | **low** |
| 8 | knowledge-search | ~148 | react-query (2q) | `ErrorCard` | `EmptyState` | yes | n/a | **low** |
| 9 | settings | ~481 | mixed | `setError` for connection; **`.catch(()=>{})` swallows 3 fetches** | implicit `?? "—"` | no | **yes** (`cancelled`) | **medium** |
| 10 | memory | ~243 | hand-rolled | stats `console.warn` (swallowed); recall `setError` | explicit empty | no | **no** | **medium** |
| 11 | costs | ~166 | hand-rolled | `setError` + `ErrorCard` | inline | no | **yes** | **low** |
| 12 | governance | ~125 | hand-rolled | `setError` + `ErrorCard` | `EmptyState` | no | **yes** | **low** |
| 13 | traces | ~204 | hand-rolled | `setError` + inline; "service unavailable" branch | `EmptyState` | no | **yes** | **medium** |
| 14 | sessions | ~196 | hand-rolled | `setError` + inline | `EmptyState` | no | **no** | **medium** |
| 15 | literature | ~107 | mixed (RQ + URL-read effect) | `ErrorCard` | `EmptyState` | yes | n/a | **low** |
| 16 | knowledge-graph | ~184 | mixed | RQ ok; entity-detail `console.warn` (swallowed) | inline | partial | no (entity) | **medium** |
| 17 | autonomous | ~325 | hand-rolled | history `setError`; scheduler `console.warn` (swallowed) | `EmptyState` | no | **no** | **medium** |
| 18 | plugins | ~162 | react-query (1q+1m) | `isLoading` only (no error UI) | inline | yes | n/a | **low** |
| 19 | ops | ~327 | react-query (1q) | `ErrorCard` w/ `error.message` | implicit | yes | n/a | **low** |
| 20 | login | ~201 | none (mutation-only) | inline form error | n/a | no | n/a | **low** |

## Mixed pages — the partial adopters (easiest wins)

1. **`pipeline-new.tsx`** — sidebar uses clean RQ (`systemStatus`, `estimate`).
   The hand-rolled straggler is the `useEffect` at **lines 93–109** fetching
   `getRunIdeas(runId)` on `isComplete`. Clean single-query conversion
   candidate. Rest of page is mutation/event-driven — legitimately stays
   `useState`.
2. **`settings.tsx`** — RQ used only for an isolated nested
   `SettingsModelSection` (its own QueryClient, lines 52–67). Main page's
   **two `useEffect`s at lines 95–130 and 133–139** hand-roll
   `testConnection`, `getDetailedStatus`, `getEvolutionStatus`, `listUsers`.
   Already uses a `cancelled` flag — low regression risk.
3. **`knowledge-graph.tsx`** — stats/entities/world-model use RQ. Hand-rolled
   bit is `handleSelectEntity` (lines 52–63): click handler calling
   `getEntity(id)` into local state with `console.warn` swallow. Convert to
   `enabled: !!selectedId` query keyed `["kg-entity", selectedId]`.
4. **`literature.tsx`** — already fully RQ for search + ingest mutation. The
   non-RQ effect (lines 21–27) is a URL-param read, not a fetch. **Reference
   template**, not a real migration target.

## Unmount-safety audit (state-after-unmount bug)

- **Correctly guarded** (`cancelled` flag): settings, costs, governance, traces.
- **Not guarded** (latent bug — fetch racing navigation):
  - `memory.tsx:78` (`loadStats`/`loadMemories`)
  - `sessions.tsx:21-33` (`load()`), `:35` (`handleSelectSession`)
  - `autonomous.tsx:38-41` (`loadHistory`/`loadSchedulerAndEvolution`)
  - These three get unmount-safety **for free** once migrated to RQ.
- **Dead code:** `governance.tsx` declares BOTH `loadPending` (line 24,
  never called) and an inline duplicate in the effect (line 39). Delete
  during migration.

## Retry / error-visibility gaps

- **No retry on any hand-rolled page.** RQ migration gives 3 retries +
  refetch-on-focus by default.
- **Silently swallowed errors** (the high-value migration targets —
  `useResource` makes these structurally impossible):
  - `memory.tsx:49` — `getMemoryStats` swallowed; stats header silently absent.
  - `settings.tsx:120, 124, 137` — 3 fetches `.catch(()=>{})` (detailedStatus, evolutionStatus, users).
  - `autonomous.tsx:63` — `getSchedulerStatus`+`getEvolutionStatus` swallowed.
  - `knowledge-graph.tsx:59` — `getEntity` detail swallowed.
  - `costs.tsx:77` — per-run cost drill-down swallowed.

## Migration order (lowest-risk first)

### Tier 1 — Low risk, high value (do first)
Single clean query, minimal local state, usually already unmount-safe.
Essentially a 1:1 `useEffect → useResource` swap.

1. **governance.tsx** — one query, `cancelled`-guarded, `ErrorCard`/`EmptyState` ready. Deletes dead `loadPending`.
2. **costs.tsx** — one `Promise.all` of 4 calls; guarded; `ErrorCard` in place.
3. **traces.tsx** — one `Promise.all`; guarded; preserve "service unavailable" branch.
4. (Reference: `gap-detail`, `idea-detail`, `run-detail` are already RQ.)

### Tier 2 — Medium (mixed / partial adopters)
Migrate the hand-rolled stragglers, leave mutation/event logic in `useState`.

5. **pipeline-new.tsx** — convert just `getRunIdeas` effect to `enabled: isComplete && !!runId` query.
6. **settings.tsx** — convert 4 mount-fetches to queries keyed off `apiUrl`/role. Keep "Test Connection" as imperative `refetch`.
7. **knowledge-graph.tsx** — convert `handleSelectEntity` to `enabled` query.

### Tier 3 — Medium (pure hand-rolled, no unmount guard)
Migrating these fixes the latent setState-after-unmount bug as a bonus.

8. **sessions.tsx** — two queries: `["sessions"]` always-on, `["runs", selectedSession]` `enabled: !!selectedSession`.
9. **autonomous.tsx** — `getAutonomousHistory` + scheduler/evolution (currently swallowed). Expose the swallowed errors via `isError`. Actions stay as mutations that invalidate.
10. **memory.tsx** — `recallMemories` + `getMemoryStats` keyed off `[activeQuery, typeFilter]`. `deleteMemory` becomes a mutation that invalidates both.

### Tier 4 — Skip
- **login.tsx** — no list/detail queries; auth mutations live in `useAuth`. The raw `fetch` for forgot-password could move to `api/auth` but isn't a `useResource` concern.

## Notes for the migration

- **Dominant shape needed:** "keyed list query with filters" (ideas, gaps,
  memory, sessions-runs) and "id-keyed detail query" (run, idea, gap,
  kg-entity). `useResource(key, fetcher)` maps cleanly onto all 6 hand-rolled pages.
- **Pages coupling query + invalidating mutation** (governance approve/deny,
  memory delete, autonomous start/stop, plugins install, idea-detail refine):
  keep those as `useMutation` + `invalidateQueries`. Use `plugins.tsx` and
  `idea-detail.tsx` as the reference pattern — they're already idiomatic.
- **Two non-trivial RQ idioms already in the codebase** to reuse:
  `run-detail.tsx:69-72` conditional `refetchInterval` on status;
  `idea-detail.tsx` mutation-with-invalidation.

## What this audit does NOT cover (cross-reference)

- The render-state side (loading skeletons, error cards, empty states) is
  in `data_view_migration_candidates.md`.
- The fetch mechanism is only half the migration; the other half is
  replacing the inline loading/error/empty JSX with `<DataView>`. The two
  should be done together per page — migrating `useResource` without
  adopting `<DataView>` leaves the page half-migrated.
