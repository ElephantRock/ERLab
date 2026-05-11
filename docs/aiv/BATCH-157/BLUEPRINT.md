BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-157
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

Wire the existing ReflectionStage into the pipeline as two reflection
points: (1) after gap analysis, reflect on gap quality and regenerate
if score < 0.6; (2) after idea generation, reflect on idea quality
and regenerate if score < 0.6. Max 2 retries per reflection point.
This creates an iterative self-improvement loop.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────

What the code MUST do:
  - Create a `GapReflectionStage` in stages.py that:
    (a) Runs after `gap_analysis` in the pipeline
    (b) Uses existing ReflectionStage.reflect_gaps() to evaluate gap quality
    (c) If score < threshold (0.6), uses reflect_with_retry to regenerate gaps
    (d) Max 2 retries per reflection cycle
    (e) Stores reflection results in pipeline result metadata
  - Create an `IdeaReflectionStage` in stages.py that:
    (a) Runs after `idea_generation` in the pipeline
    (b) Uses existing ReflectionStage.reflect_ideas() to evaluate idea quality
    (c) If score < threshold, uses reflect_with_retry to regenerate ideas
    (d) Max 2 retries per reflection cycle
    (e) Stores reflection results in pipeline result metadata
  - Register both stages in _STAGE_ORDER
  - Wire strategy presets for reflection stages

What the code MUST NOT do:
  - MUST NOT modify the existing ReflectionStage class
  - MUST NOT modify gap_analyzer.py or ideator_agent.py core logic
  - MUST NOT add new database tables or migrations
  - MUST NOT block pipeline if reflection fails (graceful fallback, auto-pass)
  - MUST NOT run reflection when disabled in strategy preset

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────

  Tests: python -m pytest backend/tests/test_pipeline/test_batch157_reflection_loop.py -v -p no:asyncio

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: All 2,579 pre-existing tests MUST pass.
  HB-02: Reflection failure MUST NOT block pipeline. Auto-pass on error.
  HB-03: Max 2 retries (3 total iterations: initial + 2 retries).
  HB-04: Reflection score clamped to [0.0, 1.0].
  HB-05: Reflection uses the THINKING provider (local LM Studio).

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────

  A-01: Gap reflection uses reflect_gaps(). Idea reflection uses reflect_ideas().
  A-02: Gap reflection goes AFTER gap_analysis, BEFORE idea_generation.
  A-03: Idea reflection goes AFTER idea_generation, BEFORE novelty_checking.
  A-04: Stage names: gap_reflection, idea_reflection.
  A-05: Default threshold: 0.6. Configurable via strategy params.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

No new backend data models. Uses existing:
  - `backend/pipeline/reflection/reflector.py` — ReflectionStage, ReflectionResult

Storage: pipeline result metadata, not per-proposal metadata.

Existing modules referenced:
  - `backend/pipeline/reflection/reflector.py` — ReflectionStage (exists, B80)
  - `backend/pipeline/reflection/prompts/gap_reflection.md` — exists
  - `backend/pipeline/reflection/prompts/idea_reflection.md` — exists
  - `backend/pipeline/stages.py` — PipelineStage, StageContext
  - `backend/pipeline/orchestrator.py` — _STAGE_ORDER (14 → 16)
  - `backend/providers/provider_factory.py` — get_thinking_provider()

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline: 2,579
  Delta:    +12
  Total:    2,591

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: GapReflectionStage (5 tests)
  - Create GapReflectionStage in stages.py
  - Register after gap_analysis in _STAGE_ORDER
  Files: stages.py, orchestrator.py, presets.py

TASK-02: IdeaReflectionStage (5 tests)
  - Create IdeaReflectionStage in stages.py
  - Register after idea_generation in _STAGE_ORDER
  Files: stages.py, orchestrator.py, presets.py

TASK-03: Strategy Presets (2 tests)
  - Wire both stages into all 4 presets
  - deep_research + academic_proposal: enabled
  - fast_scan + literature_review: disabled
  Files: presets.py

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: GapReflectionStage reflects on gaps with retry loop.
  BAC-02: IdeaReflectionStage reflects on ideas with retry loop.
  BAC-03: Both registered in _STAGE_ORDER at correct positions.
  BAC-04: All 2,579 pre-existing tests pass (HB-01).
  BAC-05: CHANGELOG.md + STATE.md updated.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

[Post-review]

═══════════════════════════════════════════════════════════
