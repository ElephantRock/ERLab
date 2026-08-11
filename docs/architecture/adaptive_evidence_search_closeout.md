# Adaptive Evidence Search — Closeout

## Status: CLOSED

| Item                        | Evidence                                            |
| --------------------------- | --------------------------------------------------- |
| AES-0                       | Latent enrichment `seen` invariant repaired         |
| AES-1                       | Bounded evidence-aware planner proven               |
| AES-2                       | Governed execution/refactor proven behavior-neutral |
| AES-3                       | Bounded adaptive loop activated                     |
| AES-4                       | Causal + durable provenance lifecycle reconciled    |
| Search expansion            | max 2 rounds × 3 queries                            |
| Evidence admission          | unchanged                                           |
| DB schema                   | unchanged                                           |
| Existing citation traversal | unchanged                                           |
| Final status                | CLOSED                                              |

## Commit chain

| Commit    | Scope                                                        |
| --------- | ------------------------------------------------------------ |
| `29df75d` | AES-0: initialize `seen` before enrichment branches         |
| `3b538d3` | AES-1: evidence-aware adaptive query planner                |
| `9f6a3c4` | AES-2: unify governed literature query execution            |
| `8dcdac9` | AES-3: bounded adaptive literature search loop              |
| (this)    | AES-4: controlled causal/provenance lifecycle proof         |

## What was built

ERLab's literature search stage now inspects retrieved literature
and generates follow-up search queries targeting uncovered aspects.
Each adaptive query goes through the same governed execution path
as initial queries: same `SearchQuery` persistence, same
`SearchQueryExecution` recording, same `PaperDiscovery` provenance,
same reconciliation.

The adaptive loop is bounded: at most 2 rounds × 3 queries × 10
results per source. It stops on planner convergence (returns []),
zero new unique papers, duplicate-only output, or max_rounds.
Planner failure preserves the initial corpus — adaptive search is
fail-soft.

## What was proven

The AES-4 lifecycle test exercises real `LiteratureSearchStage`,
real `LLMQueryGenerator.generate_adaptive_queries`, real
`SearchService` with a deterministic source adapter, real
`PipelinePersistence.persist_search_results`, and real
`reconcile_run_search` against a temporary SQL database.

The causal proof demonstrates:

```
Q0 → A, B discovered
    ↓
A, B appear in planner digest (round 1)
    ↓
planner generates Q1
    ↓
Q1 becomes a governed SearchQuery (generation_origin=adaptive)
    ↓
real governed source execution
    ↓
C discovered
    ↓
A, B, C appear in planner digest (round 2)
    ↓
planner converges → []
    ↓
corpus persisted → reconciliation = reconciled
```

The convergence proof demonstrates that a round which only
rediscovers existing papers merges discovery routes but terminates
because `new_unique_count == 0`.

## Final test counts

```
AES-0: 3 tests (seen invariant regression)
AES-1: 18 tests (planner + query hygiene)
AES-2: 12 tests (batch execution + candidate merge)
AES-3: 16 tests (loop activation + behavior + config)
AES-4: 5 tests (causal lifecycle + convergence + config)
Total AES suite: 54 tests

Full gate suite: 102+ tests pass
Ruff: 1960 (below 1963 baseline)
```
