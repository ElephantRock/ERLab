# F1.5 — Critical Product-Flow Integration Specification

## Mission

> Prove that ERLab's principal frontend research workflows function truthfully
> across the production router, real page components, query and mutation hooks,
> runtime contracts, and cache boundaries.

## Production route graph

```
/login                         LoginPage (not lazy)
/* → ProtectedRoute → AppShell → ErrorBoundary → Suspense
  /                            DashboardPage
  /pipeline/new                PipelineNewPage
  /runs/:id                    RunDetailPage
  /ideas                       IdeasBrowserPage
  /ideas/:id                   IdeaDetailPage
  /gaps                        GapsExplorerPage
  /gaps/:id                    GapDetailPage
  /knowledge                   KnowledgeSearchPage
  /settings                    SettingsPage
  /costs                       CostsPage
  /memory                      MemoryBrowserPage
  /governance                  GovernancePage
  /traces                      TracesPage
  /sessions                    SessionsPage
  /literature                  LiteraturePage
  /knowledge-graph             KnowledgeGraphPage
  /autonomous                  AutonomousPage
  /plugins                     PluginsPage
  /ops                         OpsPage
  *                            Navigate to /
```

All pages lazy-loaded except LoginPage. ProtectedRoute checks `user` from auth context.

## Journey A — Research inspection

```
auth posture:       authenticated (user object present)
starting route:     /
production controls:
  - dashboard renders active-run card or quick-start
  - CompactProposalRow onClick navigates to /ideas/:id
  - active-run card "Watch progress" navigates to /runs/:id
  - latest-run card "Open" navigates to /runs/:id
routes traversed:   / → /runs/:id → (via IdeaListItem) /ideas/:id
                    / → (via idea) /ideas/:id → (no production link to gaps)
API operations:     listRuns, listIdeas, getPending, getOpsDashboard,
                    getRunDetail, getRunIdeas, getIdea
query keys:         ["runs",{limit:5}], ["ideas",{limit:6}],
                    ["governance-pending"], ["ops-dashboard",7],
                    ["run",runId], ["run",runId,"ideas"], ["idea",ideaId]
terminal success:   idea detail page renders with proposal content
material failures:  dashboard partial failure, run not found, idea not found
```

Note: no production control links from run-detail to gaps directly.
Gap detail is reached via: `/gaps/:id` (direct URL or via ideas/gaps pages).

## Journey B — Literature ingestion

```
auth posture:       authenticated
starting route:     /literature
production controls:
  - search input → form submit → searchLiterature
  - PaperCard "Ingest" → "Confirm Ingest" → ingestPaper mutation
routes traversed:   /literature (single page, no navigation)
API operations:     searchLiterature (GET /literature/search),
                    ingestPaper (POST /literature/ingest via JsonContract)
query keys:         ["literature-search", query] (invalidated on success)
terminal success:   toast "Ingested: ..." + paper card resets,
                    search results refetch showing ingested status
material failures:  ingest failure (visible error on card), duplicate submit blocked
```

## Journey C — Gap progression

```
auth posture:       authenticated
starting route:     /gaps/:id (e.g., /gaps/12)
production controls:
  - gap-status-select onChange → statusMutation.mutate(next)
  - "Show more matched papers" → getGapPapers(gapId) via callContract
routes traversed:   /gaps/12 → (navigate to) /gaps/13 (while mutation 12 pending)
API operations:     getGap, updateGapStatus, getGapPapers
query keys:         ["gap",gapId] (invalidated on mutation success),
                    ["gap-papers",gapId] (lazy, keyed by gapId)
terminal success:   select shows updated status after refetch,
                    matched papers show coverage wording
material failures:  status mutation failure (toast + status preserved),
                    gap A/B late-mutation isolation
```

## Integration harness boundary

Mock at the transport boundary (`apiFetchJson` / `apiFetchVoid`), NOT at
domain-client boundary. Production decoders run on mocked payloads.

```
production page → production client → callContract → apiFetchJson
                                                  → deterministic mocked HTTP response
```

Allowed mocks (documented):
- `apiFetchJson` / `apiFetchVoid` / `apiFetchUnchecked` (transport)
- `apiFetchBlob` (binary downloads)
- `sseFetch` (SSE connection)
- `toast` (sonner — non-visual in test)
- Graph canvas / entity detail (browser-only rendering)
- Auth: mock `getMe` to resolve to test user OR bypass ProtectedRoute
  by rendering pages directly inside MemoryRouter with Route matches

## Test suite (10 tests)

```
golden research inspection flow
literature ingest success flow
literature ingest failure → manual retry flow
gap status success → authoritative refetch flow
same-router gap A/B late-mutation isolation
dashboard partial-failure flow
malformed matched-papers response → contract failure
authenticated protected deep link
unauthenticated protected deep link
unknown route fallback
```
