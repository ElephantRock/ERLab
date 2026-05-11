# Plan: Run Elephant Rock 16-Stage Deep Research Pipeline

## Goal
Run the actual Elephant Rock Research Platform `deep_research` pipeline on these three seed papers:

1. https://arxiv.org/pdf/2603.06365 — ESAA-Security
2. https://arxiv.org/pdf/2602.23193 — ESAA
3. https://arxiv.org/pdf/2503.11951 — SagaLLM

Target pipeline stages:

1. literature search
2. ingestion
3. gap analysis
4. gap reflection
5. idea generation
6. idea reflection
7. novelty checking
8. feasibility
9. metrics
10. proposal synthesis
11. adversarial review
12. evaluation
13. paper synthesis
14. citation audit
15. proposal deepening
16. export

---

## Current Blocker

`backend/api/routes/pipeline.py` is currently empty in the working tree.

Git reports:

- `backend/api/routes/pipeline.py | 1094 deletions(-)`
- `backend/api/app.py` still imports and includes `pipeline.router`

This likely breaks API/frontend pipeline launch.

---

## Execution Strategy

### Step 1 — Stabilize pipeline entrypoint

Restore `backend/api/routes/pipeline.py` from `HEAD` unless the deletion was intentional.

Validation:

- Confirm the route module exposes `router = APIRouter()`.
- Confirm `/api/v1/pipeline/run`, `/api/v1/pipeline/runs`, `/api/v1/pipeline/resume/{id}`, and progress endpoints exist.
- Confirm frontend API expectations still match backend routes.

### Step 2 — Verify strategy wiring

Inspect and validate:

- `backend/pipeline/orchestrator.py`
- `backend/pipeline/strategies/presets.py`
- `backend/pipeline/stages.py`

Specifically check that `deep_research` enables or routes all 16 intended stages.

Known drift to verify:

- `_STAGE_ORDER` includes `gap_reflection`, `idea_reflection`, and `evaluation`.
- `_build_stages()` appears to construct 13 stage objects, not all 16 named stages.
- Determine whether reflection/evaluation stages are embedded inside other stage logic or currently missing from stage execution.

### Step 3 — Prepare seed-paper ingestion

Use the three arXiv PDFs as seed documents.

Options:

1. Direct document ingestion into the platform knowledge base.
2. Local PDF files already fetched into session `long_responses/` copied/referenced into an ingestion path.
3. If the platform expects domain/search input only, run with domain/query centered on:
   - event-sourced autonomous agents
   - agent governance
   - LLM workflow transaction guarantees
   - AI-generated code security audits

Preferred: direct ingestion of the three PDFs before or during pipeline execution so the pipeline reasons over the exact requested papers.

### Step 4 — Run deep_research

Run via the most reliable entrypoint:

Priority order:

1. Python orchestrator directly, if API remains unstable.
2. CLI `erock generate` with `--strategy deep_research`, if CLI supports seed docs or search queries.
3. API `/api/v1/pipeline/run`, after route restoration.

Suggested research domain:

> Event-sourced and transactionally governed multi-agent LLM systems for security-auditable software engineering workflows

Suggested search queries:

- `event sourcing autonomous agents LLM software engineering`
- `LLM agent transaction guarantees saga compensation multi-agent planning`
- `AI generated code security audit event sourced architecture`
- `agent assisted security audits reproducible evidence`

### Step 5 — Monitor and collect artifacts

Track:

- run ID
- checkpoints under `data/checkpoints/`
- run artifacts under `data/runs/`
- exported Markdown/JSON/LaTeX outputs
- logs and warnings
- citation audit results
- proposal deepening outputs

### Step 6 — Validate completion against the 16 stages

Produce a stage completion table:

| Stage | Expected | Executed? | Evidence |
|---|---:|---:|---|
| literature_search | yes | TBD | run/checkpoint/log |
| ingestion | yes | TBD | run/checkpoint/log |
| gap_analysis | yes | TBD | run/checkpoint/log |
| gap_reflection | yes | TBD | run/checkpoint/log |
| idea_generation | yes | TBD | run/checkpoint/log |
| idea_reflection | yes | TBD | run/checkpoint/log |
| novelty_checking | yes | TBD | run/checkpoint/log |
| feasibility_scoring | yes | TBD | run/checkpoint/log |
| mechanical_metrics | yes | TBD | run/checkpoint/log |
| proposal_synthesis | yes | TBD | run/checkpoint/log |
| adversarial_review | yes | TBD | run/checkpoint/log |
| evaluation | yes | TBD | run/checkpoint/log |
| paper_synthesis | yes | TBD | run/checkpoint/log |
| citation_audit | yes | TBD | run/checkpoint/log |
| proposal_deepening | yes | TBD | run/checkpoint/log |
| export | yes | TBD | run/checkpoint/log |

If the codebase cannot actually execute all 16 due to stage construction drift, report that precisely and identify which stages are implemented versus configured-only.

### Step 7 — Final deliverable

Deliver an Elephant Rock Research Platform output bundle summary:

- Run metadata
- Pipeline completion table
- Generated gaps
- Reflected gaps, if present
- Generated ideas
- Refined/reflected ideas, if present
- Novelty and feasibility results
- Mechanical metrics
- Proposal synthesis
- Adversarial review
- Evaluation
- Paper synthesis
- Citation audit
- Deepened proposal
- Export path(s)
- Any platform/code blockers found

---

## Acceptance Criteria

The task is complete only if one of the following is true:

### Success

- A `deep_research` run completes through export.
- All available stage artifacts are collected.
- A stage-by-stage evidence table is produced.

### Partial Success

- The platform runs but does not execute all 16 declared stages.
- The final report explains exactly which stages are missing, skipped, embedded, or failed.

### Blocked

- The platform cannot run due to code/configuration breakage.
- The final report identifies the blocker, exact file/line evidence, and the smallest corrective action.
