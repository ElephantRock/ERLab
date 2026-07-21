# F1.3.0 — Query Lifecycle Swallowed-Failure Inventory

> Ensure read failures remain visible as failures, successful empty
> responses remain distinguishable from outages, and independent resources
> can fail without silently fabricating a calm or empty product state.

## Summary

```
HIGH severity (material product data swallowed)     2
MEDIUM severity (secondary data swallowed)         12
LOW severity (cosmetic/debug/minor)                12
TOTAL occurrences                                   26
```

Source-level count can be rechecked at closeout by re-running the audit.

## Existing infrastructure

`useResource` (src/lib/useResource.ts) returns a discriminated union:
`loading | ready | error | empty`. The `error` branch carries `retry()`.
Pages using `useResource` + `DataView` are clean (the error branch
renders an error card automatically). The inventory targets pages that
either don't use `useResource`, or use it but don't surface the `error`
branch.

## HIGH severity

### H-1/H-2: dashboard.tsx — all four resources collapsed

All four dashboard resources (`listRuns`, `listIdeas`, `getPending`,
`getOpsDashboard`) use `useResource` but their `error` states are
collapsed into empty arrays via ternary fallback. A backend outage
renders as a calm dashboard with zero action items — indistinguishable
from a fresh install. Repair: F1.3.2 (four independent lifecycles).

## MEDIUM severity (F1.3 targets)

| ID | File | Pattern | Operation | Repair phase |
|---|---|---|---|---|
| M-1 | settings.tsx:115 | `.catch(() => {})` | getDetailedStatus | F1.3.3 |
| M-2 | settings.tsx:119 | `.catch(() => {})` | getEvolutionStatus | F1.3.3 |
| M-3 | settings.tsx:130 | `.catch(() => {})` | listUsers | F1.3.3 |
| M-4 | plugins.tsx:18 | no `isError` check | listPlugins | F1.3.4 |
| M-5 | gaps-explorer.tsx:73 | no `isError` check | GET /gaps/clusters | F1.3.4 |
| M-6 | knowledge-graph.tsx:40 | no `isError` (×3) | getWorldModel/Stats/Entities | F1.3.4 |
| M-7 | autonomous.tsx:51 | console.warn | getSchedulerStatus/EvolutionStatus | F1.3.6 |
| M-8 | notification-bell.tsx:35 | console.warn (×2) | getNotifications | F1.3.6 |
| M-9 | app-shell.tsx:34 | no `isError` | listRuns (active-run pill) | F1.3.4 |
| M-10 | comment-thread.tsx:19 | no `isError` | listComments | F1.3.4 |
| M-11 | revision-history-drawer.tsx:47 | no `isError` | getSectionRevisions | F1.3.4 |
| M-12 | stage-model-editor.tsx:57 | no `isError` (×2) | getCertification/getOverrides | F1.3.4 |

## LOW severity (deferred to F1.7)

L-1 run-detail ideas query, L-2 traces handleTraceClick, L-3 estimate-card.
L-4 through L-12 are benign null-guards/formatDate/localStorage/Sentry —
not actual read-path swallows. Listed for completeness.

## Already clean (confirmed by code inspection)

costs.tsx, memory.tsx, governance.tsx, ops.tsx, literature.tsx,
knowledge-search.tsx, gap-detail.tsx, pipeline-new.tsx, sessions.tsx,
ideas-browser.tsx.

Full machine-readable data: `f1_3_query_lifecycle_inventory.json`.
