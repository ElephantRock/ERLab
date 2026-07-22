# F1.4.0 — Frontend Mutation Inventory

> Ensure every critical frontend mutation has truthful pending, success, and
> failure behavior; prevents accidental duplicate execution; and updates
> cached product state only through explicit invalidation.

## Summary

```
Total mutations found             33
Truthful                          18
Missing pending state              7
Silent failure                     1
Duplicate-execution risk           3
Stale-cache risk                   3
Unsafe optimistic update           1
```

## High-priority defects (F1.4 repair targets)

### H5: Literature ingest (mutation 1)
- No pending UI on the ingest button
- No onError handler — failure is completely silent
- `ingestMutation.isPending` consumed nowhere
- Duplicate-click risk on slow networks

### M8: Gap status mutation (mutation 2)
- `<select>` stays enabled during mutation — rapid changes fire multiple PUTs
- No query invalidation after success — refetch silently reverts the dropdown
- No pending indication on the control

### Mutation 13: Memory delete
- Confirm "Delete" button has no disabled state — user can click repeatedly

### Mutation 21: Upload zone (ingestPdf)
- Drop area not disabled during upload — user can drop another file mid-flight

### Mutations 22/23: Notification mark-read/mark-all-read
- No pending UI on the "Mark all as read" link
- No per-item pending state when marking individual notifications

### Mutation 26: Autonomous stop cycle
- Confirm dialog cleared BEFORE await — failures lose retry context
- No per-action pending UI

### Mutation 29/30: Stage model selector save/reset
- Save: no success feedback, no cache invalidation
- Reset: triple defect — no pending UI + optimistic local mutation without rollback + no cache invalidation

## Truthful mutations (no repair needed)

18 mutations across idea refinement, feedback, comments, share links,
governance decisions, plugin install, auth (login/register/forgot),
pipeline trigger/cancel/resume, exports, autonomous start/scheduler,
and stage-model-editor save/remove/clear.

All have: pending UI (button disabled + spinner/label), duplicate
prevention, toast on success/failure, appropriate cache invalidation.

## No-mutation pages (confirmed read-only)

dashboard, costs, ops, sessions, traces, knowledge-graph,
knowledge-search, gaps-explorer, ideas-browser.

## Disposition plan

| ID | Severity | Repair phase |
|---|---|---|
| 1 (H5) | HIGH | F1.4.1 — contract + lifecycle |
| 2 (M8) | HIGH | F1.4.2 — lifecycle + invalidation |
| 13 | MEDIUM | F1.4.3 — pending state |
| 21 | MEDIUM | F1.4.3 — duplicate prevention |
| 22 | MEDIUM | F1.4.3 — pending state |
| 23 | MEDIUM | F1.4.3 — pending state |
| 26 | MEDIUM | F1.4.3 — pending + dialog fix |
| 29 | MEDIUM | F1.4.3 — cache invalidation + feedback |
| 30 | HIGH | F1.4.3 — rollback + pending + cache |
| 3-12,14-20,24-25,27-28,31-33 | OK | No repair (truthful) |

Full machine-readable data: `f1_4_mutation_inventory.json`.
