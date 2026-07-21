# F1.0 — Frontend Runtime Contract Audit

> Prove that the existing frontend consumes backend contracts truthfully,
> handles all lifecycle states safely, and completes the principal ERLab
> user workflows without stale types, dropped fields, hidden runtime errors,
> or fabricated status.

This is the **F1.0 inventory** — a read-only audit of every production
route, API endpoint, type, and lifecycle-state posture. It is the input to
F1.1–F1.7 (the repair phases). No code changes in F1.0.

## Methodology

Audit performed by tracing the router config (`src/App.tsx`), every page in
`src/pages/`, every API module in `src/api/`, and cross-checking each
frontend type against the backend (route handlers in
`backend/api/routes/`, request schemas in `backend/api/schemas.py`, models
in `backend/db/models.py`).

**Provenance baseline:** the backend has no formal response-schema layer.
Responses are ad-hoc dicts built in route handlers (only request models and
a handful of Pydantic models are formal). Therefore almost every frontend
response type is `manually-mirrored`. No OpenAPI codegen exists.

## Headline numbers

```
production routes                   20 (+ 1 fallback)
production pages                    20
api client functions                76  (75 via central apiFetch; 1 health probe via raw fetch)
api type declarations               ~110 across src/api/
generated (OpenAPI) types            0
ad-hoc fetch in src/api/*            1 (intentional testConnection health probe)
JSON.parse(...) as X on API resp     0
```

## Architecture (current, pre-F1.1)

```
apiFetch (src/api/client.ts)         — single fetch wrapper; auth headers, error normalization, NO response validation
  ├─ apiFetchBlob / apiFetchFormData / sseFetch  — variants
useResource (src/lib/useResource.ts) — wraps useQuery into a discriminated ResourceState union
DataView (src/components/ui/data-view.tsx) — renders the four ResourceState cases
pages/components                     — consume api functions directly (mixed: useQuery, useResource, manual useEffect)
```

The architecture is **partially centralized**: `apiFetch` is the single
fetch wrapper (good), but pages inconsistently use `useResource` (the
discriminated-union pattern), raw `useQuery`, or manual `useEffect`. The
typed-client layer is missing — types live in `src/api/types.ts` but are
purely compile-time with no runtime validation.

## Severity-ranked findings (input to F1.1–F1.7)

### HIGH severity

| # | Finding | Location | F1 phase |
|---|---|---|---|
| H1 | `stage-model-selector.tsx` makes 3 raw `fetch()` calls to `/settings/models` (GET/PUT/DELETE), bypassing `apiFetch` entirely — no auth headers (`X-API-Key`/JWT), no `ApiError` normalization, uses `import.meta.env.VITE_API_URL` instead of `getApiUrl()`. **Will fail auth in any deployment with auth enabled.** | `components/pipeline/stage-model-selector.tsx:44,83,101` | F1.1 |
| H2 | `getConsciousnessState()` calls `/pipeline/autonomous/consciousness` — **endpoint does not exist**. Function is dead code; page imports the type but hardcodes `"idle"` and never calls it. | `api/autonomous.ts:46`, `pages/autonomous.tsx:29` | F1.1 |
| H3 | `submitGapFeedback`/`updateGapStatus` return type `{ gap: ResearchGap }` advertises 14 fields; backend returns only `{id, user_rating, user_notes}` / `{id, status}`. Consumers reading `gap.title` etc. from these responses get `undefined`. | `api/gaps.ts:32,38` vs `backend/api/routes/gaps.py:520,538` | F1.1 |
| H4 | Dashboard has **zero error UI across 4 resources** — `governance.data.pending ?? []` and `ops.data.quality_trends?.common_failures ?? []` swallow failed queries as empty arrays. A backend outage renders as a calm dashboard with zero action items. | `pages/dashboard.tsx:56-57,166-182` | F1.3 |
| H5 | `ingestMutation` in literature page has `onSuccess` but **no `onError` and no pending UI** on the ingest button. Failed ingest is completely silent. | `pages/literature.tsx:39-44` | F1.4 |
| H6 | `/gaps/:id/papers` navigation from `gap-detail.tsx:237` — route is **not registered**; clicking "View All Matched Papers" hits the `*` fallback and redirects to `/`. | `pages/gap-detail.tsx:237` | F1.2 |

### MEDIUM severity

| # | Finding | Location | F1 phase |
|---|---|---|---|
| M1 | `proposal-review-panel.tsx:71` casts `raw as EnsembleReview` with only a `typeof === "object"` guard — shape mismatches surface as runtime undefined-field errors, not typed failures. | `components/ideas/proposal-review-panel.tsx:71` | F1.1 |
| M2 | Settings page: three `.catch(() => {})` swallows on `getDetailedStatus`, `getEvolutionStatus`, `listUsers`. Detailed-status/evolution/users sections silently stay at "—"/"Disabled"/empty-table defaults on failure. | `pages/settings.tsx:117,121,134` | F1.3 |
| M3 | Plugins page: list query has **no error UI** (only loading). Failed `listPlugins` falls through to "No plugins found". | `pages/plugins.tsx:36` | F1.3 |
| M4 | Duplicate `IngestResponse` (knowledge vs literature — two different shapes), `StageInfo` (3 declarations: UI-only, backend mirror, divergent backend mirror), `TruthInfo.source_count` vs `ResearchGap.truth.evidence_count` (same concept, two field names). | see audit JSON | F1.1 |
| M5 | `gaps-explorer.tsx` clusters query: `clusterData?.clusters?.length ?` falls to "No cluster data available" with no error path. | `pages/gaps-explorer.tsx:244` | F1.3 |
| M6 | `RunDetail` hook-local interface duplicates `PipelineRunDetail` (subset). | `hooks/usePipelineProgress.ts:12` | F1.1 |
| M7 | `console.warn` swallows: traces `handleTraceClick` (`traces.tsx:70`), autonomous scheduler/evolution load (`autonomous.tsx:62`), notifications fetches (`notification-bell.tsx:40,51`). Failed fetches render nothing with no user signal. | multiple | F1.3 |
| M8 | `gap-detail.tsx` status update mutation: inline `try/catch` with toast, **no pending state** — select remains interactive during request (double-submit risk). | `pages/gap-detail.tsx:101-104` | F1.4 |
| M9 | `apiFetch` returns `undefined as T` on 204 — callers expecting a body get undefined with no type warning. | `api/client.ts:79` | F1.1 |

### LOW severity

| # | Finding | Location |
|---|---|---|
| L1 | `Paper` type omits `embedding: list[float] \| None` from backend model. | `api/literature.ts:11` |
| L2 | Ad-hoc `fetch` in `login.tsx` forgot-password (public endpoint, bypasses apiFetch). Low impact. | `pages/login.tsx:30-38` |
| L3 | Various `as Record<string, unknown>` narrows on untyped `run.config` / `proposal_sections` blobs. | `pages/run-detail.tsx:259`, `pages/idea-detail.tsx:777` |
| L4 | `placeholder.tsx` is dead (not routed). | `pages/placeholder.tsx` |
| L5 | `AuthUser.role` narrowed to `"admin"\|"user"` union; backend `UserResponse.role: str` is wider. | `api/auth.ts:7` |

## Zero-finding categories (explicit)

```
generated (OpenAPI) types             0
ad-hoc fetch inside src/api/*         0  (only the intentional testConnection health probe)
JSON.parse(...) as X on API responses 0  (JSON.parse appears only on SSE streams + localStorage)
```

These three are clean. The central `apiFetch` boundary holds for the API
surface itself; the bypasses are isolated to `components/` and `pages/`.

## Per-page lifecycle posture summary

| Page | Loading | Empty | Failure | Notes |
|---|:---:|:---:|:---:|---|
| dashboard | ⚠️ | ✅ | ❌ | H4 — no error UI on any of 4 resources |
| pipeline-new | ✅ | ✅ | ✅ | strongest posture |
| run-detail | ✅ | ✅ | ✅ | minor: ideas query silent on failure |
| idea-detail | ✅ | ✅ | ✅ | via DataView |
| ideas-browser | ✅ | ✅ | ✅ | via DataView |
| gaps-explorer | ✅ | ✅ | ⚠️ | clusters query has no error path |
| gap-detail | ✅ | ✅ | ✅ | M8 — mutation has no pending state |
| knowledge-search | ✅ | ✅ | ✅ | |
| settings | ✅ | n/a | ⚠️ | M2 — 3 silent `.catch(() => {})` swallows |
| literature | ✅ | ✅ | ✅ | H5 — ingest mutation silent on error |
| memory | ✅ | ✅ | ✅ | |
| costs | ✅ | ✅ | ✅ | via DataView |
| governance | ✅ | ✅ | ✅ | manual useEffect (pre-dates useResource) |
| traces | ✅ | ✅ | ✅ | M7 — trace-detail click swallowed |
| sessions | ✅ | ✅ | ✅ | via DataView |
| knowledge-graph | ✅ | ✅ | ⚠️ | main queries have no error UI |
| autonomous | ✅ | ✅ | ⚠️ | M7 — scheduler/evolution load swallowed |
| plugins | ✅ | ✅ | ❌ | M3 — no error UI on list query |
| ops | ✅ | n/a | ✅ | per-section error rendering |
| login | ✅ | n/a | ✅ | |

**5 pages have missing/partial failure posture** (dashboard, gaps-explorer
clusters, settings, knowledge-graph, plugins). **2 mutations lack error
handling** (literature ingest, gap-detail status). **1 mutation lacks
pending state** (gap-detail status).

## Type classification summary

```
backend-derived         6   (request schemas + AuthUser/AuthResponse + literature Paper/Author)
manually-mirrored      ~95  (the bulk — backend ad-hoc dict shapes)
locally-extended        2   (PipelineRunDetail, IdeaDetail — extend a base)
generated               0
stale                   1   (Paper omits embedding — L1)
unknown/dead            2   (ConsciousnessState, ConsciousnessStateInfo — H2)
```

The `manually-mirrored` majority is the core F1.1 target: without a
generated or centrally-validated boundary, every drift is a silent bug
(e.g. H3, M4). F1.1 will establish one authoritative boundary with
schema-validation tests against backend fixtures.

## Repair plan (F1.1–F1.7 mapping)

```
F1.1  H1 (stage-model-selector bypass), H2 (dead consciousness endpoint),
      H3 (gap-feedback return-type lie), M1 (EnsembleReview cast),
      M4 (duplicate types), M6 (RunDetail dup), M9 (204 cast)
      → central typed client + schema-validation tests
F1.2  H6 (missing /gaps/:id/papers route), String(runId) contract test
F1.3  H4 (dashboard error UI), M2/M3/M5/M7 (silent swallows)
F1.4  H5 (literature ingest mutation), M8 (gap-detail pending state)
F1.5  critical product-flow integration tests
F1.6  runtime error observability (error boundary)
F1.7  architecture seal (the 10 zero-count assertions) + five-run closeout
```

L1–L5 are deferred to F1.7 cleanup unless they block a higher-phase fix.

## Audit reproducibility

This audit was performed by reading the router, pages, and API modules at
HEAD `3bcb620` (F0 closeout). Full machine-readable data (routes, pages,
api functions, type classifications, red flags with file:line) is in the
companion `f1_runtime_contract_audit.json`.
