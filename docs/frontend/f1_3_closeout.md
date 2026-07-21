# F1.3 Closeout — Query Lifecycle and Swallowed-Failure Remediation

## Status

```
F1.3     CLOSED — read failures are visible as failures
F1       OPEN
```

## Commit chain

```
de30b8e  test(f1.3): add query lifecycle adversarial coverage
5f4adc2  feat(f1.3): repair remaining material read failure states
5c74352  feat(f1.3): make dashboard and settings lifecycle truthful
6ee7342  docs(f1.3): inventory swallowed frontend query failures
```

## Inventory disposition (26 entries)

### Repaired in F1.3 (14 entries)

| ID | Severity | File | Repair |
|---|---|---|---|
| H-1 | HIGH | dashboard.tsx | 4 independent resource lifecycles with WidgetError + scoped retry |
| H-2 | HIGH | dashboard.tsx | same (runs + ideas + governance + ops each independent) |
| M-1 | MEDIUM | settings.tsx | detailedStatusError renders "Failed to load backend status" |
| M-2 | MEDIUM | settings.tsx | evolutionStatusError renders "Failed to load evolution status" |
| M-3 | MEDIUM | settings.tsx | usersError renders "Failed to load users" |
| M-4 | MEDIUM | plugins.tsx | isError + refetch + "Failed to load plugins" with Retry |
| M-5 | MEDIUM | gaps-explorer.tsx | clustersError + "Failed to load clusters" distinct from empty |
| M-6 | MEDIUM | knowledge-graph.tsx | 3 queries get isError + scoped error indicators |
| M-7 | MEDIUM | autonomous.tsx | console.warn → schedulerError state + visible card |
| M-8 | MEDIUM | notification-bell.tsx | console.warn → fetchError + badge "!" + dropdown failure |
| M-9 | MEDIUM | app-shell.tsx | isError destructured (failure = absence, acceptable for header) |
| M-10 | MEDIUM | comment-thread.tsx | isError + refetch + "Failed to load comments" |
| M-11 | MEDIUM | revision-history-drawer.tsx | isError + refetch + "Failed to load revision history" |
| M-12 | MEDIUM | stage-model-editor.tsx | certError + overridesError banners |

### Deferred to F1.7 (3 entries)

| ID | Severity | File | Reason |
|---|---|---|---|
| L-1 | LOW | run-detail.tsx | secondary ideas query (parent query drives the page) |
| L-2 | LOW | traces.tsx | on-demand trace-detail click (non-material subquery) |
| L-3 | LOW | estimate-card.tsx | pre-run cost estimate (informational, non-blocking) |

### Benign / not a swallow (9 entries)

L-4 through L-12: defensive null-guards (`?? []`), formatDate try/catch,
localStorage parse guard, Sentry init try/catch. Not read-path swallows;
no repair needed.

## All gates verified

```
dashboard failures converted to empty/zero                  0
settings failures represented as effective defaults         0
plugin failures represented as no plugins                   0
gaps failures represented as no gaps                        0
graph failures represented as empty graph                   0
material read failures handled only by console              0
contract failures represented as successful empty state     0
independent resources collapsed into one failure result     0
new unchecked response callers                              0 (budget: 78)
TypeScript errors                                            0
test failures                                                0 (760 pass)
new ESLint warnings                                          0 (63 total, down from 70)
new suppressions                                             0
working tree                                                 clean
inventory entries with no disposition                        0
```

## Adversarial tests (4 new)

- All four resources succeed → no error widgets
- One resource fails → widget-error visible, other three keep data
- All four fail → multiple widget-errors, NOT calm empty dashboard
- Failed resource NOT rendered as zero count → error says "Failed"

## Posture

```
F1.3     CLOSED
F1.4     NEXT — mutation integrity (H5 literature ingest, M8 gap-detail pending)
F1       OPEN
```
