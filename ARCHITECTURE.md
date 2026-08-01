# Architecture

## System overview

ERLab is a FastAPI + SQLAlchemy + SQLite backend with a React/TypeScript frontend.

```
frontend (Vite/React)  →  FastAPI (uvicorn)  →  Pipeline Orchestrator
                                                      ↓
                            ┌─────────────────────────────────────────────┐
                            │  literature_search → ingestion → gap_analysis │
                            │  → idea_generation → feasibility → proposals  │
                            │  → adversarial_review → evaluation            │
                            │  → experiment_execution → paper_synthesis     │
                            │  → citation_audit → export                    │
                            └─────────────────────────────────────────────┘
```

## Evidence-bound paper composition (Phases 11-14)

The core architectural boundary established by the roadmap:

```
LLM (provider)
  → motivation, related work, interpretation,
    limitations, connective prose

Deterministic evidence layer
  → experiment identity (from spec)
  → methods facts (from spec)
  → observed values (from experiment manifest)
  → metric direction (from marker semantics)
  → RESULT attribution (from frozen RESULT map)
  → artifact-grounded claims (feature importance)
  → canonical titles (from spec)
```

The LLM cannot generate [RESULT-N] markers, empirical values, or achievement claims.

## Key modules

| Module | Purpose |
|--------|---------|
| `backend/pipeline/synthesis/typed_claim_composer.py` | Phase 13 typed empirical composition with semantic slots |
| `backend/pipeline/evaluation/deterministic_finalizer.py` | Deterministic title, result, and feature-importance renderers |
| `backend/pipeline/evaluation/paper_gate_evaluator.py` | Pure gate evaluator (no side effects) |
| `backend/pipeline/evaluation/claim_alignment.py` | Experiment-proposal semantic alignment |
| `backend/pipeline/evaluation/claim_result_validator.py` | Claim-to-RESULT semantic validation |
| `backend/pipeline/evaluation/revision_directive.py` | Immutable evidence-bound revision directives |
| `backend/pipeline/evaluation/targeted_remediator.py` | Phase 10 targeted section repair |
| `backend/pipeline/experiment/specification.py` | Experiment spec with model_family + hyperparameters |
| `backend/pipeline/experiment/empirical_runner.py` | Checked-in analysis execution |
| `backend/pipeline/experiment/paper_recovery.py` | Phase 6-7 persisted-result recovery |
| `backend/db/models.py` | PaperRevision, PaperSourceMarker, ExperimentResult |
| `alembic/versions/035_paper_revisions.py` | Paper revision history table |

## Data model

```
PipelineRun
  └─ Ideas → Proposals → PaperSourceMarkers (SOURCE-N)
                         → ExperimentResults → ExperimentManifest
                         → PaperRevisions (rev 0=original, 1=attempt, 2=deterministic)
                         → Paper (paper_md + paper_meta_json with RESULT/SOURCE maps)
```

## Experiment specifications

Checked-in JSON files in `data/datasets/<name>/spec_<id>.json` define:
- dataset identity (name, version, SHA-256)
- split (method, seed, fractions)
- analysis (entrypoint, method, declared_metrics, model_family, hyperparameters)
- metrics (directions, tolerances)
- research question and intent

## Evaluation gates

1. **Provenance** — [SOURCE-N] markers resolve to source papers
2. **Scope alignment** — paper title/abstract overlap with research intent
3. **Conclusion support** — empirical claims backed by [RESULT-N]
4. **Experiment alignment** — title/abstract/conclusion center the executed method
5. **Claim-result alignment** — RESULT marker roles match surrounding claims
