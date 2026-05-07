
───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: None (standalone — existing SSE infrastructure)
  Required by: BATCH-84 (research journal needs progress messages)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-06
  Batches since update:    0-2
  Reconciliation audit:    [x] N/A

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  ~2,011 (post BATCH-78)
  Expected delta (all Tasks):      +40 new tests
  Expected total at Batch close:   ~2,051

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-79/TASK-01 — ProgressReporter + Event Model
  Priority:          Critical
  Description:       Create ProgressReporter class and ProgressEvent model.
                     Wire into StreamingManager.
  Files in scope:
    - backend/pipeline/streaming/events.py (MODIFY)
    - backend/pipeline/streaming/progress_reporter.py (NEW)
    - backend/pipeline/streaming/manager.py (MODIFY — handle ProgressEvent)
  Depends on:        None
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-79-01-01 | unit | ProgressReporter.emit() calls callback with correct ProgressEvent | Callback never called, events lost | Emit event, assert callback received ProgressEvent | assert callback.called AND callback.call_args[0][0].message == "test" |
    | TEST-79-01-02 | unit | ProgressEvent has correct event_type, stage, step, message fields | Missing fields cause frontend parse errors | Create ProgressEvent, assert all fields populated | assert event.event_type == "progress" AND event.stage == "ingestion" |
    | TEST-79-01-03 | unit | progress_pct is clamped to 0.0-1.0 | Progress > 1.0 causes frontend crash | Set progress_pct=1.5, assert clamped to 1.0 | assert ProgressEvent(progress_pct=1.5).progress_pct == 1.0 |
    | TEST-79-01-04 | unit | ProgressReporter.stage_start emits event with total_steps | stage_start missing total_steps, frontend can't show progress | Call stage_start("ingestion", 5), assert total_steps in event | assert event.details["total_steps"] == 5 |
    | TEST-79-01-05 | unit | StreamingManager broadcasts ProgressEvent to SSE subscribers | Events emitted but never reach SSE stream | Emit ProgressEvent, assert SSE queue received it | assert sse_queue.get_nowait() == progress_event |
  Acceptance Criteria:
    AC-01-01: ProgressReporter emits ProgressEvent with all required fields
    AC-01-02: ProgressEvent is broadcast via StreamingManager to SSE clients
    AC-01-03: progress_pct is clamped to [0.0, 1.0]
    AC-01-04: stage_start includes total_steps metadata
  Traceability:
    AC-01-01 → TEST-79-01-01, TEST-79-01-02
    AC-01-02 → TEST-79-01-05
    AC-01-03 → TEST-79-01-03
    AC-01-04 → TEST-79-01-04

TASK-02: BATCH-79/TASK-02 — Stage Integration + Frontend Activity Log
  Priority:          High
  Description:       Wire ProgressReporter into ingestion, gap_analysis,
                     ideation, and synthesis stages. Create frontend
                     activity log component.
  Files in scope:
    - backend/pipeline/ingestion/ingestion_stage.py (MODIFY)
    - backend/pipeline/gap_analysis/gap_analyzer.py (MODIFY)
    - backend/pipeline/generation/ideator_agent.py (MODIFY)
    - backend/pipeline/synthesis/proposal_synthesizer.py (MODIFY)
    - backend/pipeline/stages.py (MODIFY — pass reporter to stages)
    - frontend/src/components/pipeline/activity-log.tsx (NEW)
    - frontend/src/pages/run-detail.tsx (MODIFY — add activity log)
    - frontend/src/hooks/usePipelineProgress.ts (MODIFY)
  Depends on:        TASK-01
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-79-02-01 | integration | IngestionStage emits "Searching arXiv..." progress message | No messages emitted during ingestion | Run ingestion stage, assert reporter received arXiv search message | assert any("arxiv" in e.message.lower() for e in events) |
    | TEST-79-02-02 | integration | GapAnalyzer emits "Clustering papers..." progress message | No messages during gap analysis | Run gap analysis, assert clustering message | assert any("cluster" in e.message.lower() for e in events) |
    | TEST-79-02-03 | integration | IdeatorAgent emits "Generating idea N of M..." progress message | No messages during ideation | Run ideation, assert idea generation message | assert any("idea" in e.message.lower() for e in events) |
    | TEST-79-02-04 | unit | Existing stage_start/stage_complete events still emitted | New progress events replace old events, breaking backward compat | Run pipeline, assert both old and new event types present | assert "stage_start" in event_types AND "stage_complete" in event_types |
    | TEST-79-02-05 | unit | Messages do NOT contain API keys or internal prompts | Sensitive data leaked to frontend | Search all emitted messages for API key patterns, assert none found | assert not any("sk-" in e.message for e in events) |
  Acceptance Criteria:
    AC-02-01: Ingestion, gap_analysis, ideation, synthesis emit granular progress messages
    AC-02-02: Existing stage_start/stage_complete events unchanged
    AC-02-03: No sensitive data in progress messages
    AC-02-04: Frontend activity-log.tsx renders messages with timestamps
    AC-02-05: Activity log auto-scrolls to latest message
  Traceability:
    AC-02-01 → TEST-79-02-01, TEST-79-02-02, TEST-79-02-03
    AC-02-02 → TEST-79-02-04
    AC-02-03 → TEST-79-02-05
    AC-02-04 → manual (frontend)
    AC-02-05 → manual (frontend)

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Pipeline emits granular progress messages visible in frontend
  BAC-02: Existing SSE events unchanged (backward compatible)
  BAC-03: No sensitive data in progress messages
  BAC-04: CHANGELOG.md updated with BATCH-79 entry
  BAC-05: All documents archived under /docs/aiv/BATCH-79/

═══════════════════════════════════════════════════════════
```

---

## BATCH-80: ITERATIVE REFLECTION LOOP

### AIV v5.3 STANDARD CYCLE

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-80
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-06
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Add an iterative reflection loop after gap analysis and ideation.
The LLM evaluates its own output against a rubric and decides
whether to retry with feedback or proceed.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - After gap_analysis, LLM evaluates: "Do these gaps cover the domain?"
  - After ideation, LLM evaluates: "Are these ideas truly novel?"
  - Each evaluation returns a 0-1 score with written justification
  - If score < threshold (configurable, default 0.6), regenerate with feedback
  - Max 3 reflection iterations per stage
  - Reflection results are stored in pipeline run metadata

What the code MUST NOT do:
  - Must NOT make reflection mandatory (configurable on/off per strategy)
  - Must NOT slow down fast_scan strategy
  - Must NOT change the gap or idea data models

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m ruff check backend/ && python -m pytest --co -q

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Reflection loop MUST have a max iteration count (default 3).
         It MUST NOT loop infinitely.
  HB-02: Reflection MUST be disabled for fast_scan strategy.
  HB-03: Each reflection iteration MUST be logged with input score,
         feedback, and output score for audit.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
  # New: backend/pipeline/reflection/__init__.py
  # New: backend/pipeline/reflection/reflector.py
  @dataclass
  class ReflectionResult:
      score: float                # 0.0 to 1.0
      passed: bool                # score >= threshold
      justification: str
      feedback: str               # feedback for next iteration
      iteration: int

  class ReflectionStage:
      def __init__(self, provider: BaseLLMProvider, threshold: float = 0.6,
                   max_iterations: int = 3)
      async def reflect_gaps(self, gaps: list, query: str) -> ReflectionResult
      async def reflect_ideas(self, ideas: list, gaps: list) -> ReflectionResult
      async def reflect_with_retry(self, content, reflect_fn, regenerate_fn) -> tuple

  # Modified: backend/pipeline/orchestrator.py
  # - After gap_analysis, call reflect_gaps
  # - After ideation, call reflect_ideas
  # - On failed reflection, regenerate with feedback

  # Modified: backend/pipeline/strategies/presets.py
  # - deep_research: reflection enabled, threshold=0.6, max_iterations=3
  # - fast_scan: reflection disabled
  # - academic_proposal: reflection enabled, threshold=0.7, max_iterations=5

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: BATCH-76 (strategy architecture)
  Required by: BATCH-89 (gap queue), BATCH-96 (planning agent)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-06
  Batches since update:    0-3
  Reconciliation audit:    [x] N/A

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  ~2,051 (post BATCH-79)
  Expected delta (all Tasks):      +35 new tests
  Expected total at Batch close:   ~2,086

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-80/TASK-01 — ReflectionStage Implementation
  Priority:          Critical
  Description:       Create ReflectionStage with reflect_gaps, reflect_ideas,
                     and reflect_with_retry methods. Include prompt templates.
  Files in scope:
    - backend/pipeline/reflection/__init__.py (NEW)
    - backend/pipeline/reflection/reflector.py (NEW)
    - backend/pipeline/reflection/prompts/gap_reflection.md (NEW)
    - backend/pipeline/reflection/prompts/idea_reflection.md (NEW)
  Depends on:        None
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-80-01-01 | unit | reflect_gaps returns ReflectionResult with score and justification | Returns None or incomplete result | Call reflect_gaps with mock gaps, assert ReflectionResult | assert result.score >= 0.0 AND result.score <= 1.0 |
    | TEST-80-01-02 | unit | reflect_with_retry stops after max_iterations | Loops infinitely on persistent low scores | Set max_iterations=2, mock reflect to always return score=0.3, assert stops at 2 | assert final_result.iteration == 2 |
    | TEST-80-01-03 | unit | reflect_with_retry returns immediately when score >= threshold | Wastes iterations on already-good output | Mock reflect to return score=0.9, assert 1 iteration only | assert final_result.iteration == 1 |
    | TEST-80-01-04 | unit | Reflection feedback is passed to regenerate function | Regenerate doesn't receive feedback, producing same output | Check regenerate_fn call args include feedback string | assert "feedback" in regenerate_fn.call_args |
    | TEST-80-01-05 | error | Reflection handles LLM timeout gracefully | Timeout crashes entire pipeline | Mock provider to raise TimeoutError, assert default pass | assert result.passed is True (fail-open) |
    | TEST-80-01-06 | unit | ReflectionResult has iteration counter | No way to know how many iterations ran | Check iteration field after 2-iteration reflection | assert result.iteration == 2 |
  Acceptance Criteria:
    AC-01-01: ReflectionStage evaluates gaps and ideas with 0-1 score
    AC-01-02: reflect_with_retry respects max_iterations
    AC-01-03: reflect_with_retry returns immediately on high score
    AC-01-04: Feedback is passed to regeneration function
    AC-01-05: LLM timeout is handled gracefully (fail-open)
  Traceability:
    AC-01-01 → TEST-80-01-01
    AC-01-02 → TEST-80-01-02
    AC-01-03 → TEST-80-01-03
    AC-01-04 → TEST-80-01-04
    AC-01-05 → TEST-80-01-05

TASK-02: BATCH-80/TASK-02 — Orchestrator Integration + Strategy Config
  Priority:          High
  Description:       Wire reflection into orchestrator after gap analysis
                     and ideation. Configure per-strategy (enabled/disabled,
                     threshold, max iterations).
  Files in scope:
    - backend/pipeline/orchestrator.py (MODIFY)
    - backend/pipeline/strategies/presets.py (MODIFY)
  Depends on:        TASK-01
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-80-02-01 | integration | deep_research runs reflection after gap_analysis | No reflection in deep_research | Run pipeline with deep_research, assert reflection events | assert any(e.stage == "reflection" for e in events) |
    | TEST-80-02-02 | integration | fast_scan does NOT run reflection | fast_scan runs reflection, slowing it down | Run pipeline with fast_scan, assert no reflection events | assert not any(e.stage == "reflection" for e in events) |
    | TEST-80-02-03 | integration | Reflection iterations are logged in pipeline run metadata | No audit trail of reflection decisions | Run pipeline, check metadata, assert reflection log present | assert "reflection_log" in run_metadata |
    | TEST-80-02-04 | unit | academic_proposal has higher threshold (0.7) than deep_research (0.6) | Same threshold for all strategies | Check presets, assert different thresholds | assert academic.threshold > deep.threshold |
  Acceptance Criteria:
    AC-02-01: deep_research and academic_proposal use reflection
    AC-02-02: fast_scan skips reflection
    AC-02-03: Reflection iterations logged in run metadata
    AC-02-04: Per-strategy reflection config (threshold, max_iterations)
  Traceability:
    AC-02-01 → TEST-80-02-01
    AC-02-02 → TEST-80-02-02
    AC-02-03 → TEST-80-02-03
    AC-02-04 → TEST-80-02-04

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Reflection loop improves gap/idea quality (measured by score delta)
  BAC-02: fast_scan is not affected by reflection
  BAC-03: Reflection iterations capped and logged
  BAC-04: CHANGELOG.md updated with BATCH-80 entry
  BAC-05: All documents archived under /docs/aiv/BATCH-80/

═══════════════════════════════════════════════════════════
```

---

## BATCHES 81–100 — SUMMARY BLUEPRINTS

The remaining 20 batches follow the same AIV v5.3 STANDARD pattern.
Below are the condensed specifications. Full blueprints will be expanded
at batch execution time.

---

### BATCH-81: MULTI-DIMENSIONAL PROPOSAL EVALUATION
**Depends on**: BATCH-77 | **Tasks**: 2 | **Priority**: Critical  
**T1-03 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create ProposalEvaluator with 5 dimensions (Novelty, Feasibility, Completeness, Rigor, Clarity). Each dimension 0-1 score with justification. | `backend/pipeline/evaluation/proposal_evaluator.py` (NEW), `backend/pipeline/evaluation/prompts/evaluation.md` (NEW) |
| TASK-02 | Store evaluation JSON alongside proposals. Add radar chart to idea-detail.tsx. Wire into orchestrator after synthesis. | `backend/pipeline/persistence.py` (MODIFY), `frontend/src/pages/idea-detail.tsx` (MODIFY), `frontend/src/components/ideas/evaluation-radar.tsx` (NEW) |

**Tests**: +40 | **Key Hard Boundary**: Evaluation MUST NOT modify proposal content

---

### BATCH-82: KNOWLEDGE LIBRARY (PERSISTENT RESEARCH MEMORY)
**Depends on**: BATCH-76 | **Tasks**: 3 | **Priority**: High  
**T2-03 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create KnowledgeLibrary class that indexes papers, gaps, ideas from completed runs into persistent ChromaDB collection per domain. | `backend/pipeline/knowledge/library.py` (NEW), `backend/pipeline/knowledge/library_indexer.py` (NEW) |
| TASK-02 | On pipeline start, query existing knowledge first. New papers added incrementally. Dedup against existing entries. | `backend/pipeline/orchestrator.py` (MODIFY), `backend/pipeline/literature/search_service.py` (MODIFY) |
| TASK-03 | Frontend knowledge library page: browse past papers/gaps/ideas by domain, search across runs. | `frontend/src/pages/knowledge-library.tsx` (NEW), `frontend/src/api/client.ts` (MODIFY) |

**Tests**: +45 | **Key Hard Boundary**: Knowledge library MUST NOT delete or modify past run data

---

### BATCH-83: SOUL.md + ERROR ANALYSIS AS KNOWLEDGE
**Depends on**: None | **Tasks**: 2 | **Priority**: High  
**T2-05, T2-08 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create SOUL.md defining Elephant Rock's research philosophy. Create SoulLoader that injects philosophy into all LLM prompts. | `SOUL.md` (NEW), `backend/pipeline/soul_loader.py` (NEW), `backend/pipeline/orchestrator.py` (MODIFY) |
| TASK-02 | Create ErrorKnowledgeStore that logs rejection reasons, low scores, and quality check failures. Query at pipeline start to avoid repeating mistakes. | `backend/pipeline/knowledge/error_store.py` (NEW), `backend/db/models.py` (MODIFY — failure_log table) |

**Tests**: +30 | **Key Hard Boundary**: SOUL.md MUST be human-readable markdown, not code

---

### BATCH-84: RESEARCH JOURNAL PER PIPELINE RUN
**Depends on**: BATCH-79 | **Tasks**: 2 | **Priority**: High  
**T1-04 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create JournalWriter that accumulates stage notes during pipeline execution. Generates notes.md and README.md at run completion. | `backend/pipeline/journal/__init__.py` (NEW), `backend/pipeline/journal/writer.py` (NEW), `backend/pipeline/journal/templates/` (NEW) |
| TASK-02 | Wire JournalWriter into orchestrator. Add journal download/view to run-detail.tsx. Persist as markdown files. | `backend/pipeline/orchestrator.py` (MODIFY), `backend/api/routes/pipeline.py` (MODIFY), `frontend/src/pages/run-detail.tsx` (MODIFY) |

**Tests**: +30 | **Key Hard Boundary**: Journal MUST NOT expose internal prompts or API keys

---

### BATCH-85: MORE SEARCH ENGINES
**Depends on**: None | **Tasks**: 3 | **Priority**: High  
**T2-02 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Implement SemanticScholarSource with API key support, pagination, rate limiting. | `backend/pipeline/literature/semantic_scholar.py` (MODIFY — currently stub) |
| TASK-02 | Implement PubMedSource and GoogleScholarSource (via SerpAPI). | `backend/pipeline/literature/pubmed_source.py` (NEW), `backend/pipeline/literature/google_scholar_source.py` (NEW) |
| TASK-03 | Create MultiSourceSearcher that fans out queries across all engines and merges/deduplicates results. | `backend/pipeline/literature/multi_source.py` (NEW), `backend/pipeline/literature/search_service.py` (MODIFY) |

**Tests**: +50 | **Key Hard Boundary**: Each source MUST fail independently without crashing pipeline

---

### BATCH-86: CROSS-ENGINE RELEVANCE FILTER
**Depends on**: BATCH-85 | **Tasks**: 2 | **Priority**: Medium  
**T2-04 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create RelevanceFilter that uses LLM to score paper relevance 0-1, deduplicates by DOI/title similarity, returns top-K. | `backend/pipeline/literature/relevance_filter.py` (NEW) |
| TASK-02 | Wire into MultiSourceSearcher as post-search step. Configurable threshold. | `backend/pipeline/literature/multi_source.py` (MODIFY) |

**Tests**: +25 | **Key Hard Boundary**: Filter MUST NOT remove papers that match the query exactly

---

### BATCH-87: SKILL.md EXTENSIBLE RESEARCH SKILLS
**Depends on**: BATCH-83 | **Tasks**: 2 | **Priority**: Medium  
**T2-06 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create SkillLoader that parses SKILL.md files (YAML frontmatter + steps). Create skills/ directory with 3 default skills: Systematic Review, Proposal Writing, Literature Mapping. | `backend/pipeline/skills/loader.py` (NEW), `skills/systematic_review.md` (NEW), `skills/proposal_writing.md` (NEW), `skills/literature_mapping.md` (NEW) |
| TASK-02 | Wire skills into orchestrator. User selects skill at pipeline start. Skill modifies stage parameters and prompts. Frontend skill selector. | `backend/pipeline/orchestrator.py` (MODIFY), `frontend/src/pages/pipeline-new.tsx` (MODIFY) |

**Tests**: +25 | **Key Hard Boundary**: Skills MUST NOT execute arbitrary code (declarative only)

---

### BATCH-88: RECURSIVE BREADTH × DEPTH LITERATURE SEARCH
**Depends on**: BATCH-85 | **Tasks**: 2 | **Priority**: Medium  
**T3-01 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create RecursiveLiteratureSearcher with breadth and depth params. Uses OpenAlex citations API to follow citation chains. | `backend/pipeline/literature/recursive_search.py` (NEW) |
| TASK-02 | Wire into deep_research and academic_proposal strategies. Add breadth/depth params to strategy config. | `backend/pipeline/strategies/presets.py` (MODIFY), `backend/pipeline/orchestrator.py` (MODIFY) |

**Tests**: +25 | **Key Hard Boundary**: Recursive depth MUST be capped at 3 levels to prevent infinite expansion

---

### BATCH-89: ROUND-ROBIN GAP QUEUE
**Depends on**: BATCH-80 | **Tasks**: 2 | **Priority**: Medium  
**T3-02 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create GapQueue with round-robin scheduling. Each gap gets N exploration rounds. Tracks which gaps have been explored and how deeply. | `backend/pipeline/gap_analysis/gap_queue.py` (NEW) |
| TASK-02 | Wire into gap analysis stage for deep_research strategy. Replaces single-shot gap generation with iterative exploration. | `backend/pipeline/gap_analysis/gap_analyzer.py` (MODIFY) |

**Tests**: +20 | **Key Hard Boundary**: GapQueue MUST respect max_total_gaps limit (default 10)

---

### BATCH-90: ANTI-FABRICATION + CLAIM VERIFIER
**Depends on**: BATCH-81 | **Tasks**: 2 | **Priority**: High  
**T3-03 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create ClaimExtractor that pulls claims from proposals. Create ClaimVerifier that checks each claim against the paper corpus using embeddings. Flag unverified claims. | `backend/pipeline/evaluation/claim_extractor.py` (NEW), `backend/pipeline/evaluation/claim_verifier.py` (NEW) |
| TASK-02 | Wire into synthesis post-processing. Unverified claims are flagged in proposal metadata. Frontend shows verification status per claim. | `backend/pipeline/synthesis/proposal_synthesizer.py` (MODIFY), `frontend/src/pages/idea-detail.tsx` (MODIFY) |

**Tests**: +30 | **Key Hard Boundary**: Flagged claims MUST NOT be silently removed — only marked

---

### BATCH-91: LATEX/PDF EXPORT
**Depends on**: None | **Tasks**: 2 | **Priority**: Medium  
**T3-04 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create LaTeXExporter with domain templates (NLP, CV, systems, theory). Jinja2 template rendering. | `backend/pipeline/export/latex_exporter.py` (MODIFY), `backend/pipeline/export/templates/nlp.tex` (NEW), `backend/pipeline/export/templates/systems.tex` (NEW), `backend/pipeline/export/templates/generic.tex` (NEW) |
| TASK-02 | Add PDF compilation endpoint. Frontend export dialog with template selection and format choice (Markdown/LaTeX/PDF). | `backend/api/routes/exports.py` (MODIFY), `frontend/src/components/export/export-dialog.tsx` (MODIFY) |

**Tests**: +20 | **Key Hard Boundary**: LaTeX export MUST NOT require external LaTeX installation (use Jinja2 template only)

---

### BATCH-92: SANDBOXED CODE EXECUTION
**Depends on**: None | **Tasks**: 2 | **Priority**: Medium  
**T3-05 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Wire up existing docker_backend.py with memory/time limits. Create ExperimentRunner that executes generated code in sandbox, captures stdout/stderr. | `backend/pipeline/experiment/runner.py` (MODIFY), `backend/pipeline/sandboxing/docker_backend.py` (MODIFY) |
| TASK-02 | Wire into experiment stage. Store execution results (stdout, stderr, exit code, timing) in DB. Display in idea-detail.tsx. | `backend/pipeline/experiment/experiment_generator.py` (MODIFY), `frontend/src/pages/idea-detail.tsx` (MODIFY) |

**Tests**: +25 | **Key Hard Boundary**: Sandbox MUST enforce memory limit (256MB) and time limit (60s)

---

### BATCH-93: 3-TIER CONTEXT MANAGEMENT
**Depends on**: BATCH-78 | **Tasks**: 2 | **Priority**: Medium  
**T3-06 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create ContextManager with 3 strategies: microcompact (summarize), memory_flush (compact to key points), truncation (remove oldest). Integrated into prompt construction. | `backend/pipeline/context/context_manager.py` (NEW), `backend/pipeline/context/compaction.py` (NEW) |
| TASK-02 | Wire into each stage's prompt construction. Track token usage. Trigger compaction when approaching model context limit. | `backend/pipeline/orchestrator.py` (MODIFY), `backend/pipeline/stages.py` (MODIFY) |

**Tests**: +25 | **Key Hard Boundary**: Context MUST NOT silently drop the current stage's input

---

### BATCH-94: TOOL CONCURRENCY WITH SAFETY FLAGS
**Depends on**: BATCH-93 | **Tasks**: 2 | **Priority**: Low  
**T3-07 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Add safe_parallel flag to tool definitions. Create ToolExecutor that runs read-only tools in parallel, mutations sequentially. | `backend/pipeline/tools/tool_executor.py` (NEW), `backend/pipeline/tools/registry.py` (MODIFY) |
| TASK-02 | Apply to literature search (parallel across engines) and knowledge graph queries. Measure speedup. | `backend/pipeline/literature/multi_source.py` (MODIFY) |

**Tests**: +20 | **Key Hard Boundary**: Mutation tools MUST NEVER run in parallel

---

### BATCH-95: MCP SERVER + TEXTGRAD
**Depends on**: BATCH-76 | **Tasks**: 3 | **Priority**: Medium  
**T3-08, T3-09 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Complete MCP server implementation. Register tools: start_pipeline, get_run_status, get_gaps, get_ideas, get_proposals. | `backend/pipeline/tools/mcp/server.py` (NEW), `backend/pipeline/tools/mcp/tools.py` (NEW) |
| TASK-02 | Create PromptEvolutionEngine. After each run, compute "loss" from evaluation scores. Generate prompt variants. Store version history. | `backend/pipeline/self_improve/prompt_evolution.py` (NEW), `backend/pipeline/self_improve/prompt_store.py` (NEW) |
| TASK-03 | Wire MCP server as startup service. Wire prompt evolution into batch close. | `backend/api/app.py` (MODIFY) |

**Tests**: +30 | **Key Hard Boundary**: TextGrad MUST NOT modify prompts without explicit user approval

---

### BATCH-96: PLANNING AGENT
**Depends on**: BATCH-80, BATCH-95 | **Tasks**: 2 | **Priority**: Medium  
**T3-10 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create PlanningAgent that takes research question + time budget, outputs a stage execution plan. Re-plans after each stage based on results. | `backend/pipeline/agents/planning_agent.py` (NEW), `backend/pipeline/agents/planning_prompts.md` (NEW) |
| TASK-02 | Wire into orchestrator as optional pre-planning stage. Planning agent decides which stages to run, skips unnecessary ones. | `backend/pipeline/orchestrator.py` (MODIFY), `backend/pipeline/strategies/presets.py` (MODIFY) |

**Tests**: +25 | **Key Hard Boundary**: Planning agent MUST NOT skip synthesis stage for any strategy

---

### BATCH-97: DOMAIN PROMPTS + BUDGET/TIME CONTROLS
**Depends on**: BATCH-83 | **Tasks**: 3 | **Priority**: High  
**T4-01, T4-04 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create domain-specific prompt variants: CS/NLP, biology, medicine, social science, engineering. Domain selector in pipeline config. | `backend/pipeline/synthesis/prompts/domains/` (NEW — 5 domain prompt files) |
| TASK-02 | Add budget and time controls to pipeline config. Max time (5/15/30/60 min), max cost ($0.50/$1/$5/$10). Pipeline degrades gracefully. | `backend/config.py` (MODIFY), `backend/pipeline/orchestrator.py` (MODIFY) |
| TASK-03 | Frontend budget/time selector in pipeline-new.tsx. Display actual cost and time after run. | `frontend/src/pages/pipeline-new.tsx` (MODIFY), `frontend/src/pages/run-detail.tsx` (MODIFY) |

**Tests**: +30 | **Key Hard Boundary**: Pipeline MUST stop at budget limit, even mid-stage

---

### BATCH-98: UX POLISH (DARK MODE, KEYBOARD SHORTCUTS, NOTIFICATIONS)
**Depends on**: None | **Tasks**: 3 | **Priority**: Low  
**T4-06, T4-10, T4-11 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Add dark mode with CSS variables. Toggle in settings. Persist preference in localStorage. | `frontend/src/index.css` (MODIFY), `frontend/src/pages/settings.tsx` (MODIFY), `frontend/src/components/layout/app-shell.tsx` (MODIFY) |
| TASK-02 | Add keyboard shortcuts: j/k navigate, Enter open, Escape close, / search, ? help. | `frontend/src/hooks/useKeyboardShortcuts.ts` (NEW), integrate into pages |
| TASK-03 | Add notification system: pipeline completion email/push notification with summary. Notification preferences in settings. | `backend/api/routes/notifications.py` (MODIFY), `frontend/src/components/notifications/` (NEW) |

**Tests**: +25 | **Key Hard Boundary**: Dark mode MUST pass WCAG 2.1 AA contrast ratios

---

### BATCH-99: PIPELINE COMPARISON + VERSIONING + EXPORT
**Depends on**: None | **Tasks**: 3 | **Priority**: Low  
**T4-05, T4-07, T4-12 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Add pipeline comparison view: side-by-side diff of two runs' gaps, ideas, proposals. | `frontend/src/pages/pipeline-compare.tsx` (NEW), `backend/api/routes/pipeline.py` (MODIFY) |
| TASK-02 | Add proposal versioning: track revisions, show diff between versions, let users edit and regenerate sections. | `backend/db/models.py` (MODIFY — proposal_versions table), `backend/api/routes/ideas.py` (MODIFY) |
| TASK-03 | Add one-click export to Notion, Obsidian, and standalone markdown. | `backend/pipeline/export/notion_exporter.py` (NEW), `backend/pipeline/export/obsidian_exporter.py` (NEW) |

**Tests**: +30 | **Key Hard Boundary**: Export MUST NOT modify original proposal data

---

### BATCH-100: LITERATURE MONITORING + JOURNAL RANKINGS
**Depends on**: BATCH-85 | **Tasks**: 3 | **Priority**: Low  
**T5-09, T5-10 from additions list**

| TASK | Description | Files |
|:-----|:------------|:------|
| TASK-01 | Create LiteratureMonitor: user defines topic, system checks daily for new papers. Notifications when relevant papers appear. | `backend/pipeline/literature/monitor.py` (NEW), `backend/api/routes/literature.py` (MODIFY) |
| TASK-02 | Add journal quality scoring: impact factor, acceptance rate, domain relevance. Weight papers by source quality. | `backend/pipeline/literature/journal_scorer.py` (NEW) |
| TASK-03 | Frontend monitoring dashboard: topic subscriptions, new paper feed, relevance scores. | `frontend/src/pages/literature-monitor.tsx` (NEW) |

**Tests**: +30 | **Key Hard Boundary**: Monitor MUST NOT make pipeline API calls without user approval

═══════════════════════════════════════════════════════════

## APPENDIX A — ADDITION-TO-BATCH MAPPING

| Addition ID | Addition Name | Batch | Tier |
|:------------|:-------------|:------|:-----|
| T1-01 | Fast Path Mode | BATCH-77 | Critical |
| T1-02 | Iterative Reflection Loop | BATCH-80 | Critical |
| T1-03 | Multi-Dimensional Eval | BATCH-81 | Critical |
| T1-04 | Research Journal | BATCH-84 | Critical |
| T1-05 | Live Progress Messages | BATCH-79 | Critical |
| T2-01 | Strategy Architecture | BATCH-76 | High |
| T2-02 | More Search Engines | BATCH-85 | High |
| T2-03 | Knowledge Library | BATCH-82 | High |
| T2-04 | Relevance Filter | BATCH-86 | High |
| T2-05 | SOUL.md | BATCH-83 | High |
| T2-06 | SKILL.md Skills | BATCH-87 | High |
| T2-07 | Thinking/Model Split | BATCH-78 | High |
| T2-08 | Error Analysis | BATCH-83 | High |
| T3-01 | Recursive Literature Search | BATCH-88 | Significant |
| T3-02 | Round-Robin Gap Queue | BATCH-89 | Significant |
| T3-03 | Anti-Fabrication | BATCH-90 | Significant |
| T3-04 | LaTeX/PDF Export | BATCH-91 | Significant |
| T3-05 | Sandboxed Execution | BATCH-92 | Significant |
| T3-06 | Context Management | BATCH-93 | Significant |
| T3-07 | Tool Concurrency | BATCH-94 | Significant |
| T3-08 | MCP Server | BATCH-95 | Significant |
| T3-09 | TextGrad | BATCH-95 | Significant |
| T3-10 | Planning Agent | BATCH-96 | Significant |
| T4-01 | Domain Prompts | BATCH-97 | Valuable |
| T4-02 | Collaborative Annotations | DEFERRED (Phase 7) | Valuable |
| T4-03 | Citation Graph Visualization | DEFERRED (Phase 7) | Valuable |
| T4-04 | Budget/Time Controls | BATCH-97 | Valuable |
| T4-05 | Pipeline Comparison | BATCH-99 | Valuable |
| T4-06 | Email Notifications | BATCH-98 | Valuable |
| T4-07 | Proposal Versioning | BATCH-99 | Valuable |
| T4-08 | Batch Scheduling | DEFERRED (Phase 7) | Valuable |
| T4-09 | API Key Management UI | DEFERRED (Phase 7) | Valuable |
| T4-10 | Dark Mode | BATCH-98 | Valuable |
| T4-11 | Keyboard Shortcuts | BATCH-98 | Valuable |
| T4-12 | Export to Notion/Obsidian | BATCH-99 | Valuable |
| T5-01 | Judge-ML Dual Agent | DEFERRED (Phase 7) | Nice-to-Have |
| T5-02 | GPU Code Execution | DEFERRED (Phase 7) | Nice-to-Have |
| T5-03 | Reference Codebase Grounding | DEFERRED (Phase 7) | Nice-to-Have |
| T5-04 | Domain LaTeX Templates | DEFERRED (Phase 7) | Nice-to-Have |
| T5-05 | OR-Tools Integration | DEFERRED (Phase 7) | Nice-to-Have |
| T5-06 | Community Marketplace | DEFERRED (Phase 7) | Nice-to-Have |
| T5-07 | Multilingual Pipeline | DEFERRED (Phase 7) | Nice-to-Have |
| T5-08 | Real-Time Collaboration | DEFERRED (Phase 7) | Nice-to-Have |
| T5-09 | Literature Monitoring | BATCH-100 | Nice-to-Have |
| T5-10 | Journal Rankings | BATCH-100 | Nice-to-Have |

## APPENDIX B — PHASE 7 (DEFERRED ITEMS)

The following 12 items are deferred to Phase 7 (post-BATCH-100):

| ID | Name | Reason for Deferral |
|:---|:-----|:--------------------|
| T4-02 | Collaborative Annotations | Requires auth system + WebSocket infra |
| T4-03 | Citation Graph Visualization | Requires D3.js/vis.js + significant frontend work |
| T4-08 | Batch Scheduling | Requires background job system (Celery/RQ) |
| T4-09 | API Key Management UI | Requires encrypted key storage + security audit |
| T5-01 | Judge-ML Dual Agent | Research-heavy — requires validation |
| T5-02 | GPU Code Execution | Requires GPU infrastructure + Docker CUDA |
| T5-03 | Reference Codebase Grounding | Requires AST parsing + code embedding |
| T5-04 | Domain LaTeX Templates | Requires LaTeX expertise + template library |
| T5-05 | OR-Tools Integration | Requires optimization modeling + benchmarking |
| T5-06 | Community Marketplace | Requires user accounts + moderation system |
| T5-07 | Multilingual Pipeline | Requires translation layer + multilingual prompts |
| T5-08 | Real-Time Collaboration | Requires WebSocket + CRDT + presence system |

## APPENDIX C — EXECUTION ORDER WITH DEPENDENCIES

```
PHASE 6A — FOUNDATION (5 batches, ~180 tests)
  BATCH-76 ─→ BATCH-77 ─→ BATCH-78
     │              │
     ├──────────────┼──→ BATCH-79 (parallel)
     │
     └──→ BATCH-80

PHASE 6B — INTELLIGENCE (4 batches, ~160 tests)
  BATCH-77 ─→ BATCH-81
  BATCH-76 ─→ BATCH-82
  (standalone) ─→ BATCH-83
  BATCH-79 ─→ BATCH-84

PHASE 6C — COVERAGE (5 batches, ~200 tests)
  (standalone) ─→ BATCH-85 ─→ BATCH-86
                              BATCH-88
  BATCH-83 ─→ BATCH-87
  BATCH-80 ─→ BATCH-89

PHASE 6D — DEPTH (5 batches, ~150 tests)
  BATCH-81 ─→ BATCH-90
  (standalone) ─→ BATCH-91
  (standalone) ─→ BATCH-92
  BATCH-78 ─→ BATCH-93 ─→ BATCH-94

PHASE 6E — ADVANCED (5 batches, ~160 tests)
  BATCH-76 ─→ BATCH-95 ─→ BATCH-96
  BATCH-83 ─→ BATCH-97
  (standalone) ─→ BATCH-98
  (standalone) ─→ BATCH-99
  BATCH-85 ─→ BATCH-100
```

═══════════════════════════════════════════════════════════

*PHASE 6 MASTER ROADMAP — AIV Framework v5.3*
*20 batches (BATCH-76 through BATCH-100)*
*45 additions mapped, 33 executed in Phase 6, 12 deferred to Phase 7*
*Expected test count at Phase 6 close: ~2,751*
*Lead Programmer: ivory-wolf*
