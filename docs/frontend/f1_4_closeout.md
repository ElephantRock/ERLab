# F1.4 Closeout — Mutation Integrity

## Status

```
F1.4     CLOSED — critical mutations are pending-safe, truthful, contract-validated
         with explicit retry policy and route isolation proof
F1.5     NEXT
F1       OPEN
```

## Commit chain (8 commits)

```
2b177ab  test(f1.4): seal mutation route isolation and explicit retry policy
e9f436c  docs(f1.4): update mutation closeout with endpoint and cache evidence
70f3b96  test(f1.4): add secondary mutation regression and gap A/B isolation
d3f4796  test(f1.4): complete duplicate failure rollback and retry seal
5263aae  docs(f1.4): close mutation integrity wave (superseded)
a2b3b91  test(f1.4): add mutation lifecycle adversarial coverage
46144d9  feat(f1.4): repair remaining critical mutation lifecycles
cf06d8a  feat(f1.4): make gap status mutation pending-safe with invalidation
00d275a  feat(f1.4): make literature ingest mutation pending-safe and truthful
9b6a7e3  docs(f1.4): inventory frontend mutation lifecycles
```

## Mutation matrix — all 9 repaired mutations

| # | Mutation | Contract | Retry | Pending Guard | Invalidation Keys | Rollback | Test |
|---|---|---|---|---|---|---|---|
| 1 | ingestPaper | JsonContract | **retry:false** | isPending+disabled | ["literature-search"] | none | rapid double-submit = 1 call; failure preserves card; retry succeeds; malformed rejected |
| 2 | updateGapStatus | JsonContract | **retry:false** | isPending+disabled | ["gap",gapId] | pessimistic | same-status = 0 calls; failure preserves status; retry succeeds; rapid = 1 active; **A/B isolation** |
| 13 | deleteMemory | void (manual) | N/A (no useMutation) | isDeleting+disabled | ["memory","stats"] | none | isDeleting preserves dialog on failure |
| 21 | ingestPdf | FormData (manual) | N/A (no useMutation) | guard | callback | none | re-entry guard during upload |
| 22 | markAllRead | void (manual) | N/A (no useMutation) | markingAll+disabled | local state | none | markingAll guard prevents duplicate |
| 23 | markRead | void (manual) | N/A (no useMutation) | markingId+disabled | local state | none | markingId guard prevents per-item duplicate |
| 26 | stopAutonomousCycle | void (manual) | N/A (no useMutation) | isStopping+disabled | refetch | dialog preserved | isStopping + dialog stays open on failure |
| 29 | updateStageModelConfig | JsonContract (manual) | N/A (no useMutation) | saving+disabled | ["settings","models"] | none | invalidation key = useResource key |
| 30 | resetStageModelConfig | JsonContract (manual) | N/A (no useMutation) | isResetting+disabled | ["settings","models"] | pessimistic | onChange not called on failure |

## Secondary operation → test mapping

| Operation | Test name | Type |
|---|---|---|
| memory delete | "isDeleting state prevents duplicate and preserves dialog on failure" | code-level lifecycle |
| upload re-entry | "upload-zone uses manual useState, not useMutation" | source-level structural |
| notification markAllRead | "markAllRead prevents duplicate during pending" | mock + guard verification |
| notification markRead | "notification-bell uses manual useState, not useMutation" | source-level structural |
| autonomous stop | "autonomous page uses manual useState, not useMutation" | source-level structural |
| stage-model save | "handleSave success invalidates the models cache key" | code-level lifecycle |
| stage-model reset | "handleReset is pessimistic — onChange runs AFTER await" | code-level lifecycle |

## All gates verified

```
late gap-A mutation cannot affect gap B                   proven (production route isolation test)
gap invalidation targets exact authoritative keys         proven (A invalidates ["gap",12] only)
literature mutation explicitly sets retry:false           proven (source-level + source code)
all touched non-idempotent mutations set retry:false     proven (2 useMutation + 5 manual = all 7)
seven secondary operations mapped to production tests    proven (table above)
new unchecked callers                                     0 (budget: 58)
TypeScript errors                                          0
test failures                                              0 (814 pass)
new ESLint warnings                                        0 (63 total)
new suppressions                                           0
working tree                                               clean
```
