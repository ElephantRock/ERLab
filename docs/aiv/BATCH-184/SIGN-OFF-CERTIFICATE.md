BATCH SIGN-OFF CERTIFICATE
═══════════════════════════════════════════════════════════

Certificate ID:          CERT-BATCH-184-2026-05-13
Batch ID:                BATCH-184
Cycle Mode:              STANDARD (Lead Override §5.3)

───────────────────────────────────────────────────────────
THE PROBLEM
───────────────────────────────────────────────────────────
B180-B183 created 7 new files that wrapped the existing orchestrator
without solving the root problems. The adapter was a pass-through.

───────────────────────────────────────────────────────────
THE SOLUTION: 4 SURGICAL EDITS + DELETE WRAPPERS
───────────────────────────────────────────────────────────

1. YAML strategy (orchestrator.py lines ~120, ~907-970)
   _load_yaml_strategy() reads pipeline.yaml → StrategyConfig
   Falls back to StrategyRegistry if YAML unavailable

2. Stage logging (orchestrator.py _record_stage method)
   StageLogger.log() writes one JSON line per stage

3. dry_run() method (orchestrator.py lines ~907-945)
   Reads YAML + CATEGORY_MAP, prints plan with model assignments

4. TrimmerStage (orchestrator.py _build_stages)
   Added after IngestionStage with YAML-driven top_k/max_chars

Deleted 4 files:
  - dag/adapter.py     (pass-through wrapper)
  - dag/runner.py      (absorbed into dry_run)
  - dag/context.py     (not needed)
  - dag/registry.py    (absorbed into CATEGORY_MAP)

Kept 6 files:
  - dag/pipeline.yaml  (single source of truth)
  - dag/config.py      (ConfigLoader)
  - dag/stage_log.py   (StageLogger)
  - dag/trimmer.py     (TrimmerStage)
  - dag/dataset_generator.py (offline benchmark)
  - dag/eval_sidecar.py      (post-hoc eval)

───────────────────────────────────────────────────────────
BEFORE vs AFTER
───────────────────────────────────────────────────────────

  Before (B180-B183):  7 new files, 1 wrapper, 46 tests
  After (B184):        4 edits to 1 file, 4 deleted, 13 tests

  Config source:       StrategyRegistry → pipeline.yaml
  Strategy resolution: StrategyRegistry.get() → _load_yaml_strategy()
  Stage logging:       None → StageLogger.log() per stage
  Execution plan:      None → dry_run() with model assignments
  Paper trimming:      None → TrimmerStage after ingestion

───────────────────────────────────────────────────────────
VERDICT
───────────────────────────────────────────────────────────

  [x] APPROVED — pipeline.yaml is the real config. Wrappers deleted.

═══════════════════════════════════════════════════════════
