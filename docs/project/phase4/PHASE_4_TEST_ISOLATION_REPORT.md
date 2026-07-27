# Phase 4 / WP-4G — Backend Test-Isolation Report

> **Status:** 4G complete. Corrected canonical selector passes with zero failures.
> **Old canonical command:** `pytest -p no:asyncio -m "not slow and not integration"` —
> **INVALID for this repository** (disables required async support).
> **Corrected canonical command:** `pytest -m "not slow and not integration"`.

## Method

Systematic-debugging discipline: root-cause investigation before any fixes.
Decisive experiments, set comparison, and within-file bisect; no guesswork.

## Preserved failed-node-ID sets

```
Phase 4 baseline (at 4G start, old command):   138 failed, 4643 passed, 47 skipped
4G checkpoint (old command, after 4B-4H):      141 failed, 4688 passed, 47 skipped
```

Exact set comparison (baseline → checkpoint):
```
unchanged: 138
new:       3   (test_phase3_paper_synthesis_timeout.py — all 3)
removed:   0
```

The 3 new failures were a real 4C regression (signature-contract break:
`source_ids` added to `_synthesize_paper_for_proposal`; three tests monkey-
patched it with the old 6-arg signature). Fixed in `d5c112a` with proven root
cause. The earlier "+3 is nondeterministic pollution" attribution was wrong;
the set comparison corrected it.

## Decisive experiment — the 138 baseline failures were NOT pollution

```
pytest -p no:asyncio -m "not slow and not integration"   → 141 failed, 4688 passed
pytest         -m "not slow and not integration"         →   3 failed, 4826 passed
```

**138 of the 141 failures vanish when the asyncio plugin is enabled.** The
`-p no:asyncio` flag is the *cause* of 138 failures, not test-isolation
pollution, not global-state leaks, not production defects.

The flag was a workaround for **GOTCHA-001** (trio-mode failures, ~196 tests in
the BATCH-75 era). The trio risk is now gone: `trio` not installed, **0
`@pytest.mark.trio` markers** in the suite, **0 trio-related failures** in
default mode. The flag had no remaining upside and was silently breaking every
async test in the canonical run.

The plan's 4G investigation candidates (`get_settings` caches, env mutations,
DB globals, vector-store state, module reloads, singleton services, background
tasks, caplog state, temp paths) are **not implicated** in the 138. They were
inspected as instructed; only **caplog state** was implicated, and only for the
2 genuine pollution failures (not the 138).

## Old command recorded as invalid

```
Old selector:
  pytest -p no:asyncio -m "not slow and not integration"
  Status: invalid for this repository because it disables required async support.
  The 138 async-flag "failures" it produced were never real defects.

Corrected selector:
  pytest -m "not slow and not integration"
  Initial measured result: 3 failed
```

## The 3 real failures (visible in both modes)

### Real failure #1 — stale frontend-route assertion

```
failing node ID:    backend/tests/test_pipeline/test_batch171_alpha.py::
                    TestInternalAlphaReadiness::test_06_frontend_routes_complete
polluting predecessor: none (fails in isolation; genuine test/code mismatch)
leaked state:       none — a stale assertion, not pollution
root cause:         the test asserted 'dashboard' in frontend/src/App.tsx, but
                    the frontend redesign (this branch) moved the route table to
                    AppRoutes.tsx and renders Dashboard at path '/'. The literal
                    'dashboard' route-name check and the wrong file were both stale.
repair:             updated test to read AppRoutes.tsx and assert the actual
                    current route paths ('/', '/pipeline/new', '/ideas',
                    '/gaps', '/settings'). Did NOT restore the obsolete route.
focused regression: the updated test itself (it now pins the current route
                    contract against future drift).
commit:             1a41c17
```

### Real failure #2 — caplog pollution (2 tests)

```
failing node IDs:
  backend/tests/test_pipeline/test_phase3_gap_analysis_diagnosis.py::
    test_malformed_output_produces_diagnostic[asyncio]
  backend/tests/test_pipeline/test_phase3_gap_analysis_diagnosis.py::
    test_empty_provider_output_distinguishable_from_parser_failure[asyncio]
polluting predecessor (bisect-proven):
  backend/tests/test_pipeline/test_discovery_execution_linkage.py::
    test_migration_018_preserves_legacy
  backend/tests/test_pipeline/test_discovery_execution_linkage.py::
    test_migration_018_round_trip
  (both independently pollute; alembic migration tests)
leaked state:       global logging configuration. alembic/env.py:39 called
                    logging.config.fileConfig(config_file_name) with the default
                    disable_existing_loggers=True. fileConfig() then DISABLED
                    every logger created before the migration ran — including
                    backend.pipeline.gap_analysis.gap_analyzer — so caplog
                    could not capture that logger's warnings in any later test.
                    Verified directly:
                      fileConfig('alembic.ini')               → logger.disabled = True
                      fileConfig('alembic.ini',
                        disable_existing_loggers=False)        → logger.disabled = False
root cause:         production global-state defect. alembic reconfigures global
                    logging during migrations and disables pre-existing loggers.
                    The plan's 'logging handlers and caplog state' candidate,
                    with a demonstrated production boundary.
repair:             env.py passes disable_existing_loggers=False explicitly;
                    alembic.ini documents the intent with the matching key (the
                    kwarg is required because Python's fileConfig does not read
                    the ini key in this version).
focused regression: backend/tests/test_pipeline/test_phase4_logging_isolation.py
                    ::test_alembic_migration_does_not_disable_preexisting_logger
                    — runs a real migration and proves a pre-existing logger
                    stays enabled.
commit:             1a41c17
```

## Per-cluster verification (all touched clusters pass independently AND in full)

| Cluster | Independent run | After 4G |
|---|---|---|
| test_pipeline (whole dir) | 2 failed before fix | **2794 passed, 0 failed, 7 skipped** |
| All 18 previously-failing files | 138 async-flag failures | **pass** (async plugin enabled) |
| test_phase3_gap_analysis_diagnosis | 7 passed (isolation) | **pass** (caplog restored) |
| test_batch171_alpha | 1 stale-assertion failure | **pass** (route contract updated) |

## Final corrected canonical selector result

```
Command:  pytest -m "not slow and not integration"
Result:   4830 passed, 47 skipped, 37 deselected, 327 warnings
Real pytest exit code: 0
Failed: 0
```

**4G exit condition met: zero failures.**

## Production-code changes in 4G

- `alembic/env.py` — `fileConfig(..., disable_existing_loggers=False)` (the
  real global-state defect repair).
- `alembic.ini` — `disable_existing_loggers = False` documents the intent.
- `Makefile`, `.github/workflows/{ci,nightly}.yml` — corrected canonical command.
- `backend/tests/test_pipeline/test_batch173_verification.py` — corrected
  subprocess invocation (was inconsistent with canonical command).
- `backend/tests/test_pipeline/test_batch171_alpha.py` — updated stale
  frontend-route assertion to current contract.
- `docs/project/ERLAB_CURRENT_STATE_REPORT.md`, `erlab_current_state_inventory.json`
  — current-state docs updated.
- `backend/tests/test_pipeline/test_phase4_logging_isolation.py` — new
  focused regression.

No tests excluded. No `xfail` added. No assertions loosened. No unrelated state
cleared globally. The one production global-state defect (alembic disabling
loggers) was repaired at the demonstrated boundary.

## Exit condition

```
pytest -m "not slow and not integration"
```
passes with zero failures. (Old `-p no:asyncio` variant retired as invalid.)

---

*End of WP-4G.*
