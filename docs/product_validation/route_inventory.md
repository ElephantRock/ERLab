# Route Inventory — Phase 0 Baseline

> **Purpose:** the machine-grounded inventory of every route, its navigation
> home, and its desktop/mobile reachability. This is a *preparatory* artifact
> (Wave 0.5A): it does not depend on any `PRODUCT.md` validation answer, so
> it can proceed in parallel with researcher interviews.
>
> **Source of truth:** `frontend/src/App.tsx` (router) + `frontend/src/components/layout/sidebar.tsx` (nav).
> Captured at Phase 0 commit. Re-run the audit after Phase 1 IA migration.

## Legend

- **Route** — the `path` in `<Route>`.
- **Page** — the lazy-loaded component.
- **Nav group / Nav entry** — where (if anywhere) the sidebar exposes the route.
- **Desktop reachability** — reachable from the always-visible sidebar.
- **Mobile reachability** — reachable from the mobile bottom nav (`mobile: true`).
- **Orphan** — a real page with **no** navigation path to it (URL-only).
- **Detail-only** — a route reached only via in-app links (cards, tables), not via nav. This is acceptable for detail pages but a smell for any *list/landing* page.

## Inventory

| # | Route | Page | Nav group | Nav entry | Desktop | Mobile | Status |
|---|---|---|---|---|---|---|---|
| 1 | `/` | DashboardPage | Studio | Home | ✅ | ✅ | OK |
| 2 | `/pipeline/new` | PipelineNewPage | Studio | New Run | ✅ | ✅ | OK |
| 3 | `/ideas` | IdeasBrowserPage | Studio | Results | ✅ | ✅ | OK |
| 4 | `/governance` | GovernancePage | Studio | Review | ✅ | ❌ | Mobile-orphan |
| 5 | `/gaps` | GapsExplorerPage | Research | Gaps | ✅ | ❌ | Mobile-orphan |
| 6 | `/literature` | LiteraturePage | Research | Literature | ✅ | ❌ | Mobile-orphan |
| 7 | `/knowledge-graph` | KnowledgeGraphPage | Research | Knowledge Graph | ✅ | ❌ | Mobile-orphan |
| 8 | `/ops` | OpsPage | System | Operations | ✅ | ❌ | Mobile-orphan |
| 9 | `/settings` | SettingsPage | System | Settings | ✅ | ✅ | OK |
| 10 | `/costs` | CostsPage | Advanced | Costs | ✅ (collapsed group) | ❌ | Mobile-orphan |
| 11 | `/traces` | TracesPage | Advanced | Traces | ✅ (collapsed) | ❌ | Mobile-orphan |
| 12 | `/memory` | MemoryBrowserPage | Advanced | Memory | ✅ (collapsed) | ❌ | Mobile-orphan |
| 13 | `/autonomous` | AutonomousPage | Advanced | Autonomous | ✅ (collapsed) | ❌ | Mobile-orphan |
| 14 | `/plugins` | PluginsPage | Advanced | Plugins | ✅ (collapsed) | ❌ | Mobile-orphan |
| 15 | `/sessions` | SessionsPage | Advanced | Sessions | ✅ (collapsed) | ❌ | Mobile-orphan |
| 16 | `/knowledge` | KnowledgeSearchPage | — | — | ❌ | ❌ | **ORPHAN** |
| 17 | `/ideas/:id` | IdeaDetailPage | — | — | detail-only | detail-only | Detail (OK) |
| 18 | `/gaps/:id` | GapDetailPage | — | — | detail-only | detail-only | Detail (OK) |
| 19 | `/runs/:id` | RunDetailPage | — | — | detail-only | detail-only | Detail (OK) |
| 20 | `/login` | LoginPage | — | — | n/a | n/a | Auth gate |

## Findings

### 1. One true orphan route
**`/knowledge` (Knowledge Search)** has **no nav entry at all** — not desktop,
not mobile. A real, fully-built page that is reachable only by typing the URL
or via global search. This violates PRODUCT.md anti-pattern *The Orphan
Route* and must be assigned a nav home in Phase 1 regardless of validation
outcome (it's a correctness gap, not a design judgment).

### 2. Thirteen mobile-unreachable routes
The mobile bottom nav (`MOBILE_ITEMS`, `sidebar.tsx:79`) filters to
`mobile: true`, which is set on exactly **4** routes: Home, New Run, Results,
Settings. The other **13** (rows 4–8, 10–15) are unreachable on mobile except
by URL. This is the symptom flagged in the UI evaluation; the inventory
confirms it's 13, not 12.

Of those 13, the most consequential gaps for a researcher-on-mobile:
- **`/governance` (Review)** — the GOVERN loop step is unreachable on mobile.
- **`/gaps`** — the TRIAGE scan step is unreachable on mobile.
- **`/runs/:id`** — also detail-only, so a researcher cannot review a
  completed run on mobile at all.

### 3. "Advanced" group is collapsed by default
Six routes (Costs, Traces, Memory, Autonomous, Plugins, Sessions) live under
a `collapsedByDefault: true` group (`sidebar.tsx:63`). Even on desktop they
require an extra click to reveal. Two of them — **Autonomous** and
**Sessions** — are primary workflow surfaces (Autonomous is a top-level CLI
command; Sessions is cross-artifact refinement history), not "advanced"
features. Their placement is a discoverability regression that the IA
rework (Phase 1) should revisit — *subject to validation of governance
frequency and autonomous usage*.

### 4. Detail routes are correctly not in nav
`/ideas/:id`, `/gaps/:id`, `/runs/:id` are reached via in-app links
(dashboard cards, result tables), not via nav. This matches
`INTERFACE_CONTRACT.md §5` ("reading has no top-level destination — it's
reached *through* triage") and is correct as-is.

### 5. `/runs/:id` has no upstream landing page
There is no `/runs` list route in the router — runs are surfaced via the
dashboard's "recent runs" widget and via `/sessions`. A researcher wanting
"show me all my runs" has no canonical destination. Worth flagging for the
Phase 1 IA decision, though it may be intentional (runs are scoped to
sessions).

## Audit methodology (for re-running after Phase 1)

1. Extract every `<Route path="...">` from `App.tsx`.
2. Extract every `to: "..."` from `NAV_GROUPS` in `sidebar.tsx`.
3. Cross-reference: every route should appear in exactly one nav entry,
   except detail routes (`:id`) and the auth route (`/login`).
4. For mobile: every non-detail, non-auth route should either be
   `mobile: true` OR reachable via a mobile "More" sheet (planned in
   Phase 1).
5. Any route failing step 3 is an orphan; any non-detail route failing
   step 4 is a mobile-orphan.

The audit is mechanical and should be re-run as a CI check (a small test
asserting "every non-detail route has a nav entry") once Phase 1 ships the
new IA — preventing the orphan class from regenerating.
