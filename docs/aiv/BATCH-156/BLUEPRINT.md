BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-156
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (TASK-01→TASK-02→TASK-03)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────

Wire the existing ProposalEvaluator into the pipeline as a stage that
scores every proposal on 5 dimensions (Novelty, Feasibility, Completeness,
Rigor, Clarity). Store evaluation results in proposal metadata. Add a
radar chart component to the idea-detail page frontend to visualize the
5-dimension scores alongside the existing bar chart.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────

What the code MUST do:
  - Create an `EvaluationStage` in `backend/pipeline/stages.py` that:
    (a) Runs after `feasibility_scoring` in the pipeline (before mechanical_metrics)
    (b) Uses the existing ProposalEvaluator to score each proposal
    (c) Stores results in proposal.metadata["evaluation"] as a dict
    (d) Uses the thinking provider (local LM Studio) for evaluation
    (e) Only runs when strategy has evaluation enabled
  - Register the stage in `_STAGE_ORDER` after `feasibility_scoring`
  - Add a `RadarChart` component to `frontend/src/components/ideas/radar-chart.tsx`
    that renders a 5-point radar/spider chart using SVG (no external chart library)
  - Wire `EvaluationCard` + `RadarChart` into the `idea-detail.tsx` page
  - Ensure the idea-detail API response includes the evaluation data

What the code MUST NOT do:
  - MUST NOT modify the existing ProposalEvaluator class logic
  - MUST NOT modify the existing EvaluationCard component logic
  - MUST NOT add new database tables or migrations
  - MUST NOT install new npm packages (radar chart must use pure SVG)
  - MUST NOT block the pipeline if evaluation fails (graceful fallback)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────

  Backend:  python -c "from backend.config import get_settings; print('OK')"
  Tests:    python -m pytest backend/tests/test_pipeline/test_batch156_multidim_eval.py -v -p no:asyncio

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: All 2,567 pre-existing tests MUST pass after Batch close.
  HB-02: Evaluation stage MUST NOT block if LLM call fails.
         Return ProposalEvaluation with default scores (all 0.0).
  HB-03: All dimension scores MUST be clamped to [0.0, 1.0].
  HB-04: Radar chart MUST render with pure SVG — no external dependencies.
  HB-05: No TypeScript errors (`npx tsc --noEmit` must pass).

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

No new backend data models. Uses existing:
  - `backend/pipeline/evaluation/proposal_evaluator.py` — ProposalEvaluator, ProposalEvaluation, DimensionScore
  - 5 dimensions: novelty, feasibility, completeness, rigor, clarity
  - Each dimension: score (0.0-1.0) + justification (str)
  - overall: float (mean of 5 dimensions)

New frontend component:
  - `frontend/src/components/ideas/radar-chart.tsx` — RadarChartProps:
    - data: Array<{label: string, value: number}>
    - size?: number (default 200)
    - color?: string (default "blue")

Storage: proposal.metadata["evaluation"] = ProposalEvaluation.to_dict()
No new DB tables.

Existing modules referenced:
  - `backend/pipeline/stages.py` — PipelineStage, StageContext, _get_metadata/_set_metadata
  - `backend/pipeline/orchestrator.py` — _STAGE_ORDER (13 entries → 14)
  - `backend/pipeline/evaluation/proposal_evaluator.py` — ProposalEvaluator (exists, fully implemented)
  - `backend/providers/provider_factory.py` — get_thinking_provider()
  - `frontend/src/components/ideas/evaluation-card.tsx` — EvaluationCard (exists, not imported)
  - `frontend/src/pages/idea-detail.tsx` — Idea detail page (needs wiring)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────

  A-01: Evaluation uses the THINKING provider (local LM Studio) — this is
        an analysis task, not a generation task.
  A-02: Evaluation runs BEFORE mechanical_metrics so the metrics stage
        can incorporate evaluation scores if needed.
  A-03: Radar chart uses SVG polygon, not canvas. This ensures SSR compatibility
        and no additional dependencies.
  A-04: Stage name: `evaluation`. Must appear in _STAGE_ORDER after
        `feasibility_scoring` and before `mechanical_metrics`.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────

  Depends on:
    - Existing ProposalEvaluator (fully implemented in B81)
    - Existing EvaluationCard component (fully implemented)
    - BATCH-152 (thinking/generation provider split)

  Blocks:
    - BATCH-157 (Reflection Loop) — uses evaluation scores as feedback input

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────

  State file exists:       [X] YES
  Last Updated:            2026-05-11 (BATCH-155 Close)
  Batches since update:    0
  Reconciliation audit:    [X] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline at Blueprint issuance:  2,567 existing tests
  Expected delta (all Tasks):      +12 new tests
  Expected total at Batch close:   2,579

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-156/TASK-01
  Priority:          Critical
  Description:       Create `EvaluationStage` in stages.py and register
                     in orchestrator. Must:
                     (a) Extend PipelineStage
                     (b) For each proposal, run ProposalEvaluator
                     (c) Store results in proposal.metadata["evaluation"]
                     (d) Use thinking provider for evaluation (A-01)
                     (e) Graceful fallback on LLM failure (HB-02)
                     (f) Only run when strategy has evaluation enabled
                     (g) Register in _STAGE_ORDER after feasibility_scoring (A-04)
  Files in scope:
    - backend/pipeline/stages.py (MODIFY — add EvaluationStage)
    - backend/pipeline/orchestrator.py (MODIFY — _STAGE_ORDER 13→14)
    - backend/pipeline/strategies/presets.py (MODIFY — add evaluation stage)
  Depends on:        None
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-156-01-01   | unit   | evaluation in _STAGE_ORDER               | Stage never runs | Remove from list | "evaluation" in _STAGE_ORDER |
    | TEST-156-01-02   | unit   | Stage position after feasibility_scoring | Runs at wrong time | Check index | evaluation idx > feasibility_scoring idx |
    | TEST-156-01-03   | unit   | Evaluation stored in metadata            | Results lost | Run stage, check | proposal.metadata["evaluation"] has all 5 dims |
    | TEST-156-01-04   | unit   | Graceful fallback on LLM failure          | Pipeline crashes | Mock to raise | Default scores (all 0.0), no crash |
    | TEST-156-01-05   | unit   | Stage skipped when flag disabled          | Runs on fast_scan | Set flag false | Stage skips |
  Acceptance Criteria:
    AC-01-01: evaluation in _STAGE_ORDER at correct position (A-04)
    AC-01-02: Results stored in metadata
    AC-01-03: Graceful fallback (HB-02)
  Traceability:
    AC-01-01 → TEST-156-01-01, TEST-156-01-02
    AC-01-02 → TEST-156-01-03
    AC-01-03 → TEST-156-01-04

TASK-02: BATCH-156/TASK-02
  Priority:          Critical
  Description:       Create RadarChart component in frontend. Must:
                     (a) Pure SVG polygon — no external libraries (HB-04)
                     (b) Accept data as Array<{label: string, value: number}>
                     (c) Render 5-point radar/spider chart
                     (d) Show labels at each vertex
                     (e) Color-code by score (green ≥ 0.8, yellow ≥ 0.6, orange ≥ 0.4, red < 0.4)
                     (f) Responsive sizing
  Files in scope:
    - frontend/src/components/ideas/radar-chart.tsx (NEW)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-156-02-01   | unit   | RadarChart renders SVG element           | No chart visible | Render component | SVG element in DOM |
    | TEST-156-02-02   | unit   | 5 dimension labels rendered              | Labels missing | Render with 5 dims | 5 label text elements |
    | TEST-156-02-03   | unit   | Polygon rendered with correct points     | Wrong shape | Check polygon points | Points match input values |
    | TEST-156-02-04   | unit   | Color changes with score                 | Wrong colors | Pass score=0.3 | Red color class applied |
  Acceptance Criteria:
    AC-02-01: RadarChart renders with pure SVG (HB-04)
    AC-02-02: 5 dimensions labeled correctly
  Traceability:
    AC-02-01 → TEST-156-02-01, TEST-156-02-03
    AC-02-02 → TEST-156-02-02

TASK-03: BATCH-156/TASK-03
  Priority:          High
  Description:       Wire EvaluationCard + RadarChart into idea-detail.tsx.
                     Wire strategy presets for evaluation stage.
                     Must:
                     (a) Import and render EvaluationCard on idea detail page
                     (b) Import and render RadarChart on idea detail page
                     (c) Read evaluation data from idea/proposal metadata
                     (d) Strategy presets: deep_research + academic_proposal enable
                         evaluation; fast_scan + literature_review disable
  Files in scope:
    - frontend/src/pages/idea-detail.tsx (MODIFY — add components)
    - backend/pipeline/strategies/presets.py (MODIFY — preset flags)
  Depends on:        TASK-02
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-156-03-01   | unit   | EvaluationCard imported in idea-detail   | Card not shown | Check import | EvaluationCard in component tree |
    | TEST-156-03-02   | unit   | RadarChart imported in idea-detail       | Chart not shown | Check import | RadarChart in component tree |
    | TEST-156-03-03   | unit   | deep_research enables evaluation         | Evaluation not run | Check flag | evaluation enabled in preset |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: EvaluationStage scores proposals on 5 dimensions.
  BAC-02: RadarChart renders SVG radar chart on idea detail page.
  BAC-03: All 2,567 pre-existing tests pass (HB-01).
  BAC-04: CHANGELOG.md updated with BATCH-156 entry.
  BAC-05: All documents archived under /docs/aiv/BATCH-156/.
  BAC-06: STATE.md updated with DEC-014 (evaluation stage), test count.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

[Completed by Lead after Phase I-B.]

Reviewer Report ID:       REVIEW-BATCH-156-2026-05-11
Review Cycle:             1 (§4.5 Fallback — Reviewer stalled)
Lead Decision:            [X] ACCEPT WITH MODIFICATIONS

  FLAG-01 → ACTION: Moved evaluation stage to AFTER adversarial_review (idx 8)
            and BEFORE paper_synthesis (idx 9). This evaluates full reviewed
            proposals, not bare ideas. A-04 updated accordingly.
            New position: ...feasibility_scoring → mechanical_metrics →
            proposal_synthesis → adversarial_review → evaluation →
            paper_synthesis → citation_audit → proposal_deepening → export

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-11 05:05

═══════════════════════════════════════════════════════════
