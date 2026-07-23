# F1.7 — Final Frontend Architecture Inventory

```
F1.7     CLOSED — final frontend architecture inventory + ratchet reconciliation
F1       CLOSED — all load-bearing responsibilities single-owner, transport sealed,
                  contract layer migrated, query/mutation keys reconciled
```

- **Audit commit:** `872d0a7`
- **Frozen ratchet baseline:** `a27fd77` (F1.1b — transport and runtime-contract seal)
- **Companion artifact:** `f1_7_architecture_inventory.json` (machine-readable, same wave)

---

## 1. Scope and methodology

F1.7 is the closeout inventory for the entire F1 frontend wave. It does not
introduce new code. Its job is to freeze the final architecture into a single
auditable record so that every load-bearing responsibility has exactly one
owner, every transport path is dispositioned, and every ratchet counter is
reconciled to its baseline.

The inventory was produced by enumerating four surfaces of the codebase:

1. **Transport layer** — every call site that reaches the backend, classified by
   whether it goes through the contract layer (`callContract`), the residual
   unchecked transport (`apiFetchUnchecked`), or the FormData transport
   (`apiFetchFormData`).
2. **Ownership** — every load-bearing frontend responsibility (route table,
   query client, mutation cache, error boundaries, observers, diagnostic
   transport, lazy-route factory, auth guard) attributed to exactly one
   production module.
3. **Query/mutation keys** — every react-query key reconciled against the
   mutations that should invalidate it, flagging matches, intentional
   mismatches, and out-of-band state.
4. **Ratchet counters** — every non-zero baseline counter (TypeScript errors,
   ESLint warnings, unchecked callers, raw fetch, test replicas, observer
   owners, Sentry transports) reconciled against its frozen baseline.

Each entry below carries an explicit **disposition**: `approved`, `intentional`,
`at_baseline`, or `sealed`. The final disposition is **0 open items**.

---

## 2. Transport layer reconciliation

The frontend has exactly three ways to reach the backend, all rooted in
`src/api/clients/client.ts`:

| Transport              | Entry point            | Contract-validated | Count |
|------------------------|------------------------|--------------------|------:|
| `callContract`         | contract layer         | yes                | 33+   |
| `apiFetchUnchecked`    | residual transport     | no (frozen)        | 58    |
| `apiFetchFormData`     | multipart transport    | no (FormData)      | 1     |

### 2.1 The 58 unchecked callers

`apiFetchUnchecked` is the pre-contract transport. Before F1.1 the entire
frontend reached the backend through it. F1.1 introduced `callContract`; F1.2
and F1.3 migrated the high-traffic and read paths; F1.3a migrated 19 reads;
F1.4 migrated the mutation hotspots; F1.6 added the diagnostics contract.

The 58 remaining `apiFetchUnchecked` call sites are **not a backlog**. They are
the **F1.1b ratchet baseline**, frozen at commit `a27fd77` as the explicitly
approved residual surface. The ratchet's contract is one-way: the count may
never increase. It has not — the manifest in the companion JSON enumerates
exactly 58 entries, matching the baseline with zero drift.

All 58 are `material=true`. They span 22 service modules and one hook:

- **auth** (3): register, login, me
- **autonomous** (3): stop, scheduler start, pipeline stop — runs/mutation
- **collaboration** (3): comments, share, shared-by-token — ideas
- **costs** (5): summary, by-provider, by-stage, by-model, run — diagnostics
- **exports** (1): plugins install — config/mutation
- **gaps** (1): list — research-gaps (detail path migrated to contract)
- **governance** (5): approve, deny, decision, decisions, timeline
- **ideas** (5): get, feedback, refine, section refine, section restore
- **knowledge-graph** (2): entity, subgraph
- **knowledge** (2): search, stats (ingest is the FormData exception)
- **literature** (1): search (ingest migrated to contract in F1.4.1)
- **memory** (3): stats, recall, delete
- **notifications** (2): mark-read, read-all
- **pipeline** (7): run, run detail, delete, run ideas, resume, estimate, autonomous
- **search** (1): cross-domain
- **sessions** (1): runs/sessions
- **settings** (7): catalog, assignments, stages, overrides PUT/validate/DELETE/DELETE-all
- **status** (1): diagnostics
- **traces** (3): summary, trace, metrics
- **usePipelineProgress** (2): run-detail polling, runs-list polling

These remain on `apiFetchUnchecked` because each one has a specific reason:
FormData bodies, streaming-shaped responses, internal polling cadences, or
endpoints whose backend shape is not yet captured in a contract module. None of
them bypass Auth, CSRF, or the shared `baseURL` wiring — they all inherit that
from `client.ts`. They bypass only the request/response decoder pair.

### 2.2 The FormData boundary

There is exactly one FormData caller in the codebase:

```
src/api/services/knowledge.ts:19
  apiFetchFormData<IngestResponse>("/knowledge/ingest", formData)
```

This is `material=true` and `active=material` (not deprecated, not a candidate
for removal). It cannot be expressed by `callContract` because `callContract`'s
signature is JSON-typed; multipart upload requires a parallel transport. The
`apiFetchFormData` helper lives alongside `apiFetchUnchecked` in `client.ts` and
inherits the same Auth, CSRF, and `baseURL` wiring. This is the sole FormData
boundary and is dispositioned `approved`.

### 2.3 Raw fetch in pages

Zero. Every `fetch()` in the codebase is internal to the `client.ts` transport
layer. Verified by grep across `src/pages/`, `src/components/`, and
`src/hooks/`. No page, component, or hook calls `fetch()` directly.

---

## 3. Contract-backed endpoints

The contract layer (`callContract`) was introduced in F1.1 and grown across six
sub-waves. The following endpoints have migrated off `apiFetchUnchecked` and
onto contract modules with request/response decoders:

- **gaps** — `getGap`, `getGapClusters`, `updateGapStatus` (F1.4.2), `submitGapFeedback`
- **gap-papers** — `getGapPapers`
- **models** — `getModels`, `getStages`, `updateOverrides`, `validateOverrides`, `removeOverride`, `clearOverrides`
- **ideas** — `listIdeas`, `getIdea`, `refineIdea`
- **dashboard** — `getOpsDashboard`, `getPending`, `getCostsSummary`
- **literature** — `ingestPaper` (POST, contract-validated, F1.4.1), `listIngested` (GET, contract-validated)
- **diagnostics** — `runtimeError` (POST, contract-validated, F1.6.1)
- **F1.3a reads** — 19 reads migrated in the F1.3a read-path sweep

Every contract method goes through a typed decoder, so shape mismatches between
client and server surface as `ApiContractError` at the boundary rather than as
runtime `undefined`-access crashes deeper in the UI.

---

## 4. Ownership uniqueness

Ten load-bearing responsibilities were audited for single-owner status. Each
has exactly one production owner. Tests are permitted to construct their own
*hosts* (e.g. a `QueryClient`) but must reuse production *policies* (e.g.
`buildMutationCacheForClient`) so that no policy is duplicated.

| Responsibility           | Owner module                                              | Callers | Status  |
|--------------------------|-----------------------------------------------------------|--------:|---------|
| route_registry           | `src/AppRoutes.tsx` `createRoutes`                        | 1       | sealed  |
| query_client             | `src/main.tsx` QueryClient factory                        | 1       | sealed  |
| mutation_cache           | `src/lib/mutation-cache.ts` `buildMutationCache`          | 1       | sealed  |
| root_boundary            | `src/components/error-boundary.tsx` `RootErrorBoundary`   | 1       | sealed  |
| route_boundary           | `src/components/route-error-boundary.tsx` `RouteErrorBoundary` | 1 | sealed  |
| observer_installer       | `src/lib/runtime-observers.ts` `installRuntimeObservers`  | 1       | sealed  |
| diagnostic_reporter      | `src/lib/runtime-error-reporter.ts` `reportRuntimeError`  | 1       | sealed  |
| diagnostic_transport     | `src/api/clients/diagnostics-client.ts` `sendRuntimeErrorReport` | 1 | sealed |
| lazy_route_wrapper       | `src/lib/lazy-route.tsx` `lazyRoute`                      | 1       | sealed  |
| protected_route          | `src/AppRoutes.tsx` `ProtectedRoute`                      | 1       | sealed  |

Two notes on the subtler entries:

- **query_client vs mutation_cache.** Tests do construct their own
  `QueryClient` instances, but they do so via the F1.5c pattern: the test
  builder reuses production `buildMutationCacheForClient`. So the *policy* has
  one owner; only the *host* is test-local. The `test_owned_query_client_policy_replicas`
  counter is therefore 0.
- **root_boundary vs route_boundary.** These are two different boundaries with
  two different jobs, not duplicates. `RootErrorBoundary` is full-screen and
  mounted once in `main.tsx`. `RouteErrorBoundary` is AppShell-preserving and
  mounted once inside the App layout so that route-render failures keep the
  chrome (nav, sidebar) visible.

---

## 5. Query/mutation key reconciliation

Every react-query key in the app was reconciled against the mutations that
should invalidate it. Three categories emerged.

### 5.1 Matched keys (exact invalidation)

The following keys are correctly invalidated by their corresponding mutations:

- run detail
- idea detail
- gap detail
- gap papers
- literature search
- literature ingested
- plugins
- comments
- section-revisions
- governance-timeline
- model-overrides
- knowledge-stats
- memory-stats
- settings/models

### 5.2 Mismatched keys (intentional, by design)

Three list-vs-detail stem splits are intentional and documented:

- **ideas list** is NOT invalidated by idea mutations (refine/feedback). List
  view shows lightweight summaries; detail mutations do not reshape the list,
  and list refresh is user-triggered via refetch to preserve scroll position.
- **gaps list** is NOT invalidated by gap status mutation. Status changes
  update the detail view; the explorer list reflects its own refetch cadence
  to avoid clobbering scroll position.
- **governance-pending** is NOT invalidated by governance decision mutation.
  The pending queue uses a coarse polling cadence to batch refreshes and stay
  in sync with the server-side state machine; immediate removal would desync.

### 5.3 Prefix-match coverage

The `["run", runId]` prefix is the one prefix-match invalidation in use:
mutating run detail invalidates run ideas via prefix match. This is explicit
and tested.

### 5.4 Out-of-band (no react-query)

Two surfaces manage state outside react-query entirely:

- **notification-bell** — `markRead`/`markAllRead` manage local state without
  touching the react-query cache.
- **gap-feedback-form** — `submitGapFeedback` is handled outside the react-query
  cache, using local form state plus `callContract`.

Both are ephemeral UI state with no cross-page cache contract to honor.

---

## 6. Ratchet reconciliation

| Counter                          | Current | Baseline | Status      |
|----------------------------------|--------:|---------|-------------|
| TypeScript errors                | 0       | 0        | at baseline |
| ESLint warnings                  | 63      | 63       | at baseline |
| Unchecked callers                | 58      | 58       | at baseline |
| Raw fetch in pages/components    | 0       | 0        | at baseline |
| Test-owned route replicas        | 0       | 0        | at baseline |
| Test-owned QueryClient policy replicas | 0  | 0        | at baseline |
| Test-owned error boundary replicas | 0     | 0        | at baseline |
| Runtime observer owners          | 1       | 1        | at baseline |
| Sentry runtime transports        | 0       | 0        | at baseline |

Every counter sits exactly on its frozen baseline. The ratchet contract is
one-way: counters may decrease but never increase. No drift was found.

The 63 ESLint warnings are the one non-zero baseline. They are frozen, not
fixed; net new warnings are blocked at PR review. The 58 unchecked callers are
the F1.1b baseline frozen at `a27fd77`, matching the manifest exactly.

---

## 7. Approved exceptions

| ID          | Item                                                       | Basis                                                          |
|-------------|------------------------------------------------------------|----------------------------------------------------------------|
| F1.7-EX-01  | 58 unchecked `apiFetchUnchecked` callers                   | F1.1b ratchet baseline at `a27fd77`; all material, no drift    |
| F1.7-EX-02  | `knowledge.ts:19` `apiFetchFormData` `"/knowledge/ingest"` | FormData multipart not expressible by JSON `callContract`      |
| F1.7-EX-03  | ideas list not invalidated by idea detail mutations        | list-vs-detail stem split by design                            |
| F1.7-EX-04  | gaps list not invalidated by gap status mutation           | list-vs-detail stem split by design                            |
| F1.7-EX-05  | governance-pending not invalidated by governance decision  | coarse polling stays in sync with server-side state machine    |
| F1.7-EX-06  | notification-bell and gap-feedback-form bypass react-query | ephemeral local UI state; no cross-page cache contract         |
| F1.7-EX-07  | 63 ESLint warnings                                         | frozen baseline; net new blocked at review                     |

---

## 8. Final disposition

Every entry in the inventory is dispositioned. There are **zero open items**.

- The 58 unchecked callers are `approved` residual (F1.1b baseline, no drift).
- The 1 FormData caller is `approved` (sole multipart boundary).
- The 0 raw-fetch-in-pages is `at baseline`.
- The 33+ contract-backed endpoints are `sealed` (migrated across F1.1-F1.6).
- The 10 ownership responsibilities are `sealed` (single owner each).
- The 14 matched query keys are `sealed`.
- The 3 intentional mismatches are `approved — intentional`.
- The 2 out-of-band surfaces are `approved — out-of-band`.
- All 7 ratchet counters are `at baseline`.
- All 7 exceptions are `approved`.

F1 is closed. The frontend's load-bearing architecture is single-owner,
transport-sealed, contract-backed where it matters, and ratchet-reconciled to
its frozen baselines.
