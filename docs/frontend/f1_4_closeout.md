# F1.4 Closeout — Mutation Integrity

## Status

```
F1.4     CLOSED — critical mutations are pending-safe, truthful, contract-validated
F1.5     NEXT
F1       OPEN
```

## Commit chain

```
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
| 1 | ingestPaper | JsonContract | none | isPending+disabled | ["literature-search"] | none | F1.4a-1 (5 tests) |
| 2 | updateGapStatus | JsonContract | none | isPending+disabled | ["gap",gapId] | pessimistic | F1.4a-2 (3 tests) |
| 13 | deleteMemory | void | none | isDeleting+disabled | ["memory","stats"] | none | F1.4a-3 |
| 21 | ingestPdf | FormData | none | guard | callback | none | F1.4a-3 |
| 22 | markAllRead | void | none | markingAll+disabled | local state | none | F1.4a-3 |
| 23 | markRead | void | none | markingId+disabled | local state | none | F1.4a-3 |
| 26 | stopAutonomousCycle | void | none | isStopping+disabled | refetch | dialog preserved | F1.4a-3 |
| 29 | updateStageModelConfig | JsonContract | none | saving+disabled | ["settings","models"] | none | F1.4a-3 |
| 30 | resetStageModelConfig | JsonContract | none | isResetting+disabled | ["settings","models"] | pessimistic | F1.4a-3 |

## Test evidence (18 tests in mutation-lifecycle.test.tsx)

### Literature ingest — production PaperCard (5 tests)
- rapid double-submit dispatches exactly one request
- failure preserves paper card + shows ingest-error
- manual retry succeeds after failure
- malformed HTTP-200 response triggers contract decoder
- PaperCard unit: confirm flow, isIngesting disabled, ingestError visible

### Gap status failure behavior (3 tests)
- failure preserves prior confirmed status (no optimistic update)
- retry can recover after failure
- rapid different selections produce only one active mutation

### Secondary regressions (5 tests)
- memory delete: isDeleting preserves dialog on failure
- gap A/B cache isolation: query keys distinct by ID
- notification markAllRead: markingAll guard prevents duplicate
- stage-model save: invalidation key matches useResource key
- stage-model reset: pessimistic — onChange not called on failure

### Retry policy + matrix (5 tests)
- QueryClient default mutation retry = undefined/0 (no auto-retry)
- All 9 repaired mutations have explicit disposition in matrix test

## All gates verified

```
inventory entries without disposition                    0
critical mutations without pending posture                0
critical mutations permitting duplicate submission        0
silent mutation failures                                  0
non-idempotent mutations with automatic retry             0
failed mutations clearing valid user input                 0
failed mutations corrupting successful cached data         0
successful mutations leaving authoritative views stale     0
optimistic mutations without rollback                      0
mutation responses accepted without runtime validation     0
new unchecked callers                                     0 (budget: 58)
TypeScript errors                                          0
test failures                                              0 (808 pass)
new ESLint warnings                                        0 (63 total)
new suppressions                                           0
working tree                                               clean
```
