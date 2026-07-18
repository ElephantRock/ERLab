# P0.4 Baseline — Reproducible Backend Gate

> **Status:** Baseline captured. Gate is NOT reproducibly green.
> P0.4A0 remains blocked until the pre-existing defects below are
> resolved or explicitly scoped out.

This document records the P0.4-pre baseline established after the
`knowledge.py:259` syntax repair. It is the canonical reference for
every subsequent P0.4 wave's regression gate.

The contract (`docs/p0_4_entry_contract.md` §1.1) required an exact
command, exact commit, exact counts, and the execution environment.
The prior "285 passing" assertion is not used; it was not reproducible
on the prior head and is not reproducible here either.

## Execution environment

```text
Repair commit        b3ac7d9
Git commit tested    b3ac7d9 (this commit, after the syntax repair)
Branch               feat/quarantine-and-frontend-redesign
Working-tree status  clean at test time (repair committed; tests run on the committed tree)
OS                   win32 10.0.26200 x64
Python version       3.12.1
pytest version       9.1.1
```

## Reproducible result

```text
exact command        python -m pytest backend/tests --tb=no -q
tests collected      3992
tests passed         3978
tests failed         11
tests skipped        25
tests deselected     0
collection errors    3 (all in test_persistence/test_proposal_persistence.py)
duration             ~156 s
exit code            1
```

This result was reproduced three times consecutively with `--tb=no`,
`--tb=no`, and `--tb=line` — each run reported the same 11 failures,
same 3 errors, same 3978 passes. The deterministic subset of the gate
is well-defined.

A single earlier run with `--tb=short` produced 27 failures. The 16
additional failures did not reproduce in three subsequent runs. They
are recorded as **non-deterministic** in §3 below and are not part of
the deterministic baseline count. The deterministic 11 + 3 is the
authoritative gate state.

## Deterministic failures (reproduce on every run)

All 11 deterministic failures and all 3 errors are **pre-existing**
defects unrelated to the `knowledge.py:259` syntax repair. None are
repair-caused.

### Class A — production API shape drift (test-suite defects)

Production code changed its return-type or accepted-input contract;
the corresponding tests were not updated. These tests fail in
isolation and in the full suite; they are independent of test order.

| # | Test | Failure | Source |
|---|---|---|---|
| A1 | `test_literature/test_crossref_source.py::TestCrossRefSearch::test_basic_search_returns_results` | `TypeError: object of type 'SourceSearchOutcome' has no len()` | `crossref_source.py` now returns a wrapper object; test still calls `len(results)` |
| A2 | `test_crossref_source.py::test_paper_fields_parsed_correctly` | same | same |
| A3 | `test_crossref_source.py::test_html_tags_stripped_from_abstract` | same | same |
| A4 | `test_crossref_source.py::test_paper_without_title_skipped` | same | same |
| A5 | `test_crossref_source.py::test_limit_respected` | same | same |
| A6 | `test_crossref_source.py::test_empty_response` | same | same |
| A7 | `test_crossref_source.py::test_network_error_returns_empty` | same | same |
| A8 | `test_crossref_source.py::test_http_error_returns_empty` | same | same |
| A9 | `test_crossref_source.py::test_null_abstract_handled` | same | same |
| A10 | `test_pipeline/test_batch174_core_stages.py::TestLiteratureSearchStage::test_populates_all_papers` | `assert False is True`; warning logged: `Query 'test query' returned unexpected type: <class 'unittest.mock.AsyncMock'>` | `stages.py:302` rejects the test's mock because the production type-check expects a concrete result type |

### Class B — schema-required field missing in test construction

The P0.2 provenance work added `provenance_version` as a NOT NULL
column on `pipeline_runs` (migration `020_provenance_contract_gating`).
These tests construct `PipelineRun(...)` without that field.

| # | Test | Failure | Source |
|---|---|---|---|
| B1 | `test_persistence/test_proposal_persistence.py::TestProposalPersistence::test_persist_proposals_creates_db_row` | `IntegrityError: NOT NULL constraint failed: pipeline_runs.provenance_version` | Test fixture omits the now-required field |
| B2 | `test_persistence/test_proposal_persistence.py::TestProposalPersistence::test_persist_proposals_upsert_idempotent` | same | same |
| B3 | `test_persistence/test_proposal_persistence.py::TestProposalPersistence::test_persist_proposals_with_no_matching_idea` | same | same |

### Class C — single test logic or environment issue

| # | Test | Failure | Notes |
|---|---|---|---|
| C1 | `test_routing/test_cost_router.py::TestCostAwareRouter::test_health_check_failover[asyncio]` | assertion failure inside failover logic | Passes in isolation (`1 passed in 0.21s`). Deterministic in the full suite. **Classification: test-ordering interference** — a fixture or global state set by an earlier test destabilizes this one. |

## Non-deterministic observations (NOT in the baseline count)

A single `--tb=short` run produced 16 additional failures that have
not reproduced in three subsequent runs. They are recorded here for
completeness; they do not contribute to the deterministic baseline.

The 16 additional tests that failed in the `--tb=short` run but not
in subsequent runs:

```text
backend/tests/test_api/test_async_pipeline.py::test_trigger_run_returns_202
backend/tests/test_api/test_async_pipeline.py::test_trigger_run_accepts_full_params
backend/tests/test_api/test_async_pipeline.py::test_cancel_run_unknown_returns_404
backend/tests/test_api/test_async_pipeline.py::test_autonomous_cycle_returns_202
backend/tests/test_api/test_autonomous_endpoint.py::test_autonomous_returns_202_with_cycle_id
backend/tests/test_api/test_autonomous_endpoint.py::test_autonomous_accepts_request_body
backend/tests/test_api/test_batch26_autonomous.py::test_stop_autonomous_cycle_stops_running
backend/tests/test_api/test_batch26_autonomous.py::test_autonomous_history_returns_cycles
backend/tests/test_api/test_batch26_autonomous.py::test_stop_nonexistent_cycle_returns_404
backend/tests/test_api/test_batch55_task01.py::test_55_01_01_pipeline_failure_updates_db_status_to_failed
backend/tests/test_api/test_batch55_task01.py::test_55_01_02_pipeline_failure_sets_error_message
backend/tests/test_api/test_batch55_task01.py::test_55_01_03_pipeline_failure_sets_completed_at
backend/tests/test_api/test_ops_dashboard.py::TestGetDashboard::test_run_health_has_expected_fields
backend/tests/test_api/test_ops_dashboard.py::TestGetDashboard::test_model_usage_returns_gracefully_on_no_receipts
backend/tests/test_api/test_ops_dashboard.py::TestGetDashboard::test_empty_database_returns_zeros_not_errors
backend/tests/test_pipeline/test_vector_scope.py::test_same_domain_prior_runs
```

Each of these was verified to **pass in isolation**. They surface as
non-deterministic failures under specific full-suite execution
conditions. Possible causes (not yet investigated):

```text
shared fixture state leaked across modules
global service-registry or app-state mutation
unbounded asyncio task lifetime in earlier tests
database session leak across module boundaries
```

The `batch55_task01` group is a partial exception — it attempts a
live LM Studio embedding call (`All connection attempts failed`),
so it carries an environment-dependent component on top of the
ordering issue.

## Classification summary

```text
Repair-caused failures                          0
Pre-existing but previously masked by collection failure
                                                11  (Class A: 10, Class C: 1)
                                                3   (Class B errors)
Test-suite defects                             13  (Class A + B)
Test-ordering / shared-state interference       1   (Class C1, deterministic in-suite)
Environment-dependent                           0   (deterministic subset)
Non-deterministic full-suite-only failures     16   (observed once in 4 runs)
```

Every deterministic failure exists independently of P0.4-pre and
independently of the syntax repair. None of them are caused by the
`knowledge.py:259` fix.

## What this baseline establishes

1. **The collection blocker is removed.** `pytest backend/tests`
   now completes (exit code 1 from failures, not exit code 2 from
   collection interruption).
2. **The P0.3.5 closeout's 271-passing canonical gate is unchanged**
   — that narrower file-scoped gate sidesteps every failing module
   here and remains green at its own scope.
3. **The previously claimed 285-passing baseline is not the actual
   backend-wide count.** The actual backend-wide count at this commit
   is **3978 passing of 3992 collected, plus 11 deterministic
   failures and 3 errors**, all pre-existing.

## P0.4-pre completion gate

Per `docs/p0_4_entry_contract.md` §1.1, P0.4-pre requires:

```text
governed knowledge-search route imports successfully
  with the duplicate argument removed          ✓ (b3ac7d9)
complete backend/tests suite collects without error
  from a clean tree                            ✓ (5 -> 0 collection errors)
passes from a clean tree                       ✗ (11 deterministic failures
                                                 + 3 deterministic errors)
exact execution environment, command, counts,
  duration, tested commit, working-tree posture
  recorded                                     ✓ (this document)
```

P0.4-pre is **partially complete**:

```text
collection-blocker repair                      COMPLETE
reproducible baseline capture                  COMPLETE
reproducibly green gate                        NOT COMPLETE
```

## Decision required

Per `docs/p0_4_entry_contract.md` and the user directive on P0.4-pre
failure handling:

```text
do not begin P0.4A0
do not revise the expected count to hide failures
do not fold unrelated repairs into the syntax-fix commit
```

Three paths forward, in increasing scope:

1. **Resolve the pre-existing defects first, then re-baseline.** This
   is the strict reading of the completion gate. It requires repairing
   10 crossref tests (return-type contract update), 1 batch174 test
   (mock type drift), 3 persistence tests (add `provenance_version`),
   and investigating the 1 deterministic-in-suite cost_router failure
   and the 16 non-deterministic full-suite failures.

2. **Scope the P0.4 baseline to a defined subset and proceed.** This
   would inherit the P0.3.5 closeout pattern (file-scoped canonical
   gate) but add the P0.4-relevant modules as they land. The
   pre-existing defects become tracked outside the P0.4 gate. This
   narrows the completion claim in line with §13.2 of the contract.

3. **Treat the crossref and batch174 clusters as a single tracked
   repair wave (call it P0.4-pre.1) before proceeding.** The
   persistence and cost_router issues go into a separate follow-up.

P0.4A0 is blocked pending the choice.

## Reproduction

```bash
# Clean tree at b3ac7d9
python -m py_compile backend/api/routes/knowledge.py
python -c "from backend.api.app import app"
python -m pytest backend/tests --tb=no -q
# expected: 11 failed, 3978 passed, 25 skipped, 3 errors, ~156s, exit 1
```

---

# Sealed baseline — P0.4-pre closeout

The red baseline above is preserved as evidence of what the syntax
repair uncovered. It is **superseded** as the active baseline by the
green baseline below. Both observations remain documented per the
P0.4-pre directive: "Do not overwrite the red baseline captured at
4b58406."

## P0.4-pre.1 — contract-drifted test repairs

Commit `623106c` — `test: align pre-P0.4 tests with provenance and
search outcome contracts`. No production code changed. All 13
deterministic defects in the red baseline (Class A + Class B) repaired
by updating stale test expectations to match current production
contracts:

```text
crossref (9 failures)       test calls updated to access outcome.results
                            and assert outcome.status / attempt_count /
                            error_detail on the error paths; no __len__
                            or list-like compatibility added to
                            SourceSearchOutcome
batch174 (1 failure)        mock updated from search.search_all to
                            search.search_all_with_provenance, returning
                            SearchBatchOutcome(candidates, executions)
                            per the governed production contract
proposal_persistence (3)    PipelineRun fixture given explicit
                            provenance_version='pre_provenance'
```

Result at `623106c`: **1 failed, 3991 passed, 25 skipped, 0 errors**
— only the cost_router ordering failure remained.

## P0.4-pre.2 — cost_router production defect

Commit `2273b37` — `test: isolate cost router health state across
backend suite`. The P0.4-pre directive permitted production changes
only when a test exposed a genuine production defect rather than a
stale expectation; this is that case.

Root cause: `CircuitBreaker.check()` is a raising guard (returns None
on closed, raises `CircuitOpenError` on open), as its docstring states
and as its only other call site (`resilient_provider.py:107`) honors.
But `cost_router.py:71` and `:108` used `if breaker and not
breaker.check():` — treating the return value as a boolean. Since
`not None` is always True, any registered breaker caused the candidate
to be skipped unconditionally. The test passed in isolation only
because no test had populated `_breakers`; in the full suite, an
earlier test's `provider_factory.py:343` `setdefault` registered a
breaker for `openai`, and the primary was always skipped.

Fix: both call sites use `check()` as a raising guard inside a
`try/except CircuitOpenError` block, matching the contract the rest
of the codebase already honors. Result at `2273b37`: **3992 passed,
25 skipped, 0 failed, 0 errors.**

## Sealed green baseline

```text
Repair commit (final)        2273b37
Git commit tested            2273b37
Branch                       feat/quarantine-and-frontend-redesign
Working-tree status          clean
OS                           win32 10.0.26200 x64
Python version               3.12.1
pytest version               9.1.1
```

### Sealed result

```text
exact command                python -m pytest backend/tests --tb=no -q
tests collected              3992
tests passed                 3992
tests failed                 0
tests skipped                25
tests deselected             0
collection errors            0
duration                     ~153 s
exit code                    0
consecutive green runs       4
                             (1 diagnostic --tb=short + 3 --tb=no)
```

### Consecutive run evidence

```text
diagnostic  python -m pytest backend/tests --tb=short -q   3992 passed, 25 skipped, 0 failed, ~156s
run 1       python -m pytest backend/tests --tb=no -q      3992 passed, 25 skipped, 0 failed, ~154s
run 2       python -m pytest backend/tests --tb=no -q      3992 passed, 25 skipped, 0 failed, ~153s
run 3       python -m pytest backend/tests --tb=no -q      3992 passed, 25 skipped, 0 failed, ~150s
```

All four runs returned exit code 0 with identical counts.

## Non-deterministic cluster — not reproduced

The 16-test non-deterministic cluster observed in the original red
baseline (one `--tb=short` run at `b3ac7d9`) **did not recur** in any
of the four sealing runs at `2273b37`. Per the directive, they are
retained here as:

```text
previously observed, currently unreproduced instability
```

They remain technical debt. If any of them recur in a future run,
capture the exact test IDs and first failure, classify
reproducibility, and block whatever wave is in progress until the
instability is resolved.

## P0.4-pre completion gate — PASSED

Per the revised gate in the directive:

```text
backend/tests collection errors                     0     ✓
deterministic test failures                          0     ✓
deterministic test errors                            0     ✓
three consecutive full-suite runs                    green ✓ (4 green)
working tree                                         clean ✓
red and green baseline evidence                      preserved ✓
```

**P0.4-pre is CLOSED at `2273b37`.** P0.4A0 is now unblocked.

## Commit chain for P0.4-pre

```text
2273b37  test: isolate cost router health state across backend suite     (P0.4-pre.2)
623106c  test: align pre-P0.4 tests with provenance and search outcome   (P0.4-pre.1)
b3ac7d9  fix: restore reproducible backend baseline before P0.4          (P0.4-pre.0)
4b58406  docs: capture P0.4-pre baseline and pre-existing defect classification
9a86aa2  docs: freeze P0.4A0 embedding-surface dispositions
69945c9  docs: P0.4 revised entry contract after repository-fit critique
```

## Reproduction (sealed)

```bash
# Clean tree at 2273b37
python -m py_compile backend/api/routes/knowledge.py
python -c "from backend.api.app import app"
python -m pytest backend/tests --tb=no -q
# expected: 3992 passed, 25 skipped, 0 failed, 0 errors, ~153s, exit 0
```
