# Laboratory — Unwired Research Subsystems

This directory contains pipeline subsystems that are **coded and tested** but **not wired into the production orchestrator**. They represent research explorations, prototypes, and future capabilities.

## Status: QUARANTINED

These modules are **not imported by the production pipeline**. They do not affect runtime behavior. They are kept here because:

1. They contain valid implementations that may be activated in future phases
2. Their tests still pass and document intended behavior
3. Deleting them would lose institutional knowledge

## Re-activation Process

To activate a laboratory module:
1. Move it back to its production location (e.g., `backend/pipeline/monitoring/`)
2. Wire it into `orchestrator.py` or the appropriate stage
3. Add it to `STAGE_CONTRACTS` if it's a stage
4. Run functional tests to verify integration

## Contents

| Module | LOC | Purpose | Blocks On |
|:--|:--|:--|:--|
| See individual subdirectories for details | | | |

## Production Modules (NOT quarantined)

The following modules ARE wired and active:
- All 17 stage implementations in `stages.py`
- `novelty/novelty_checker.py` (enhanced with NoveltyProfile)
- `novelty/models.py` (NEW — NoveltyProfile + DownstreamDirectives)
- `knowledge/vector_store.py` (enhanced with zero-vector rejection)
- `knowledge/bm25_index.py`
- `knowledge/retriever.py` (TwoStageRetriever)
- `monitoring/doom_loop.py`
- `monitoring/ccw.py`
- `monitoring/cost_estimator.py`
- `monitoring/effort_probe.py`
- `monitoring/contracts.py` (NEW — output contracts)
- `dag/pipeline.yaml` + `dag/config.py` + `dag/trimmer.py`
