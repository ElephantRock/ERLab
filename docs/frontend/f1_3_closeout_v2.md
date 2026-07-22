# F1.3 Closeout — Query Lifecycle and Swallowed-Failure Remediation

## Status

```
F1.3      CLOSED — read failures are visible, material reads runtime-validated
F1.4      AUTHORIZED
F1        OPEN
```

## Commit chain

```
6133750  test(f1.3): seal malformed-response and retry behavior
408b076  fix(f1.3): contract all lifecycle-remediated read paths
8f43cef  docs(f1.3): close query lifecycle remediation (superseded by this doc)
de30b8e  test(f1.3): add query lifecycle adversarial coverage
5f4adc2  feat(f1.3): repair remaining material read failure states
5c74352  feat(f1.3): make dashboard and settings lifecycle truthful
6ee7342  docs(f1.3): inventory swallowed frontend query failures
```

## Endpoint matrix — every F1.3-touched read (19 operations)

All 19 F1.3-touched reads migrated from `apiFetchUnchecked` to `callContract`
with runtime `JsonContract<T>` decoders.

| surface | operation | endpoint | transport | contract ID | decoder | before | after |
|---|---|---|---|---|---|---|---|
| dashboard | listRuns | GET /pipeline/runs | callContract | pipeline.listRuns | COMPLETE | unchecked | contract |
| dashboard | listIdeas | GET /ideas | callContract | ideas.listIdeas | COMPLETE | unchecked | contract |
| dashboard | getPending | GET /governance/pending | callContract | governance.getPending | COMPLETE | unchecked | contract |
| dashboard | getOpsDashboard | GET /ops/dashboard | callContract | ops.getOpsDashboard | MATERIAL | unchecked | contract |
| settings | getDetailedStatus | GET /status/detailed | callContract | status.getDetailedStatus | COMPLETE | unchecked | contract |
| settings | getEvolutionStatus | GET /status/evolution | callContract | autonomous.getEvolutionStatus | COMPLETE | unchecked | contract |
| settings | listUsers | GET /auth/users | callContract | auth.listUsers | COMPLETE | unchecked | contract |
| plugins | listPlugins | GET /plugins/ | callContract | plugins.listPlugins | COMPLETE | unchecked | contract |
| gaps-explorer | getGapClusters | GET /gaps/clusters | callContract | gaps.getGapClusters | COMPLETE | unchecked | contract |
| knowledge-graph | getGraphStats | GET /kg/stats | callContract | kg.getGraphStats | COMPLETE | unchecked | contract |
| knowledge-graph | getEntities | GET /kg/entities | callContract | kg.getEntities | COMPLETE | unchecked | contract |
| knowledge-graph | getWorldModel | GET /kg/world-model | callContract | kg.getWorldModel | COMPLETE | unchecked | contract |
| autonomous | getAutonomousHistory | GET /pipeline/autonomous/history | callContract | autonomous.getHistory | COMPLETE | unchecked | contract |
| autonomous | getSchedulerStatus | GET /pipeline/scheduler/status | callContract | autonomous.getSchedulerStatus | COMPLETE | unchecked | contract |
| notifications | getNotifications | GET /notifications/ | callContract | notifications.getNotifications | COMPLETE | unchecked | contract |
| comments | listComments | GET /ideas/{id}/comments | callContract | collaboration.listComments | COMPLETE | unchecked | contract |
| revisions | getSectionRevisions | GET /ideas/{id}/sections/{key}/revisions | callContract | ideas.getSectionRevisions | COMPLETE | unchecked | contract |
| cert-editor | getCertification | GET /settings/certification | callContract | settings.getCertification | COMPLETE | unchecked | contract |
| cert-editor | getOverrides | GET /settings/overrides | callContract | settings.getOverrides | COMPLETE | unchecked | contract |

Decoder completeness: COMPLETE = every declared field of the return type
is validated. MATERIAL = deeply-nested type where top-level material
fields are validated and the full object is returned (one case:
OpsDashboard).

## Test count reconciliation

```
F1.3 entry (commit 6ee7342):  756 tests
F1.3a closeout (commit 6133750): 782 tests (+26)
  +4 dashboard lifecycle tests (de30b8e)
  +22 contract adversarial tests (6133750)
```

## Unchecked budget

```
F1.3 entry:  78 callers
F1.3a closeout: 59 callers (-19)
```

Every F1.3-touched read is now on the contract path. The remaining 59
unchecked callers are in non-F1.3-touched API functions (pipeline triggers,
idea mutations, literature search, etc.) and are ratcheted by the
api-unchecked-budget CI guard.

## All closeout gates verified

```
F1.3-touched reads using apiFetchUnchecked<T>    0
incomplete decoders                              0
malformed HTTP-200 payloads rendered as success  0
settings failures showing effective defaults     0
dashboard failures converted to empty/zero       0
plugin failures represented as no plugins         0
gaps failures represented as no gaps              0
graph failures represented as empty graph         0
material read failures handled only by console    0
contract failures represented as empty success    0
independent dashboard resources collapsed         0
new unchecked response callers                    0 (budget: 59, down from 78)
TypeScript errors                                  0
test failures                                      0 (782 pass)
new ESLint warnings                                1 (64 total, from vi import)
new suppressions                                   0
working tree                                       clean
inventory entries with no disposition              0
```
