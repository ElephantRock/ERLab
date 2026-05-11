# CODEBASE STATE

Last Updated:       2026-05-11
Updated By:          Craft Agent — via BATCH-176 Rate Limit Resilience
Framework Version:  5.3
Phase:              BATCH-176 COMPLETE — INTERNAL ALPHA — PHASE 10 COMPLETE

───────────────────────────────────────────────────────────
VERIFIED MODULE MAP
───────────────────────────────────────────────────────────

  Module:              backend.pipeline.generation.models
  Exports:             IdeaCandidate, ResearchIdea, Critique
  Key distinction:     IdeatorAgent.generate_ideas() returns list[IdeaCandidate].
                       TreeSearchStage._convert_to_research_ideas() converts to list[ResearchIdea]
                       before assigning to PipelineResult.ideas.
  Verified in:         BATCH-75

  Module:              backend.pipeline.generation.tree_search
  Exports:             TreeSearchEngine, TreeSearchConfig, TreeNode
  Key note:            TreeSearchEngine.search() returns list[IdeaCandidate].
                       Uses AgentOrchestrator.generate_ideas() wrapper (n_ideas param).
  Verified in:         BATCH-75

  Module:              backend.pipeline.generation.agent_orchestrator
  Exports:             AgentOrchestrator
  Key note:            Has generate_ideas() wrapper for TreeSearchEngine compatibility.
                       Accepts both n_ideas and num_ideas params.
  Verified in:         BATCH-75

  Module:              backend.pipeline.stages
  Exports:             PipelineStage, StageContext, ProposalDeepeningStage (Phase 8), ...
  Key note:            ProposalDeepeningStage added in B114. Runs after synthesis.
                       Template mode enriches proposals with architecture, toy example,
                       failure modes, success criteria. Stored in proposal.metadata JSON.
  Verified in:         BATCH-114

  Module:              backend.pipeline.orchestrator
  Exports:             PipelineOrchestrator
  Key note:            _STAGE_ORDER has 16 entries. GapReflectionStage at idx 3,
                       IdeaReflectionStage at idx 5, EvaluationStage at idx 11.
                       _build_stages() wires all 16 with thinking_provider fallback.
                       Preflight checks run before API accepts pipeline runs (B172).
  Verified in:         BATCH-172

  Module:              backend.pipeline.verification.reference_verifier
  Exports:             ReferenceVerifier, VerificationReport, CitationCheck
  Key note:            Extracts author-year citations from proposals, cross-references
                       against corpus. Strips unverifiable citations with [Citation needed].
  Verified in:         BATCH-112

  Module:              backend.pipeline.verification.proposal_deepener
  Exports:             ProposalDeepener, DeepenedProposal
  Key note:            Template mode produces architecture, toy example, failure modes,
                       success criteria. LLM mode available with provider.
  Verified in:         BATCH-114

  Module:              backend.pipeline.verification.pipeline_evaluator
  Exports:             PipelineEvaluator, PipelineEvaluationReport, GapEvaluation
  Key note:            Computes gap recall, precision, idea novelty rate, quality score.
                       Uses keyword overlap for gap matching.
  Verified in:         BATCH-116

  Module:              backend.pipeline.verification.gold_standards
  Exports:             GOLD_STANDARD_GAPS, get_gold_gaps
  Key note:            4 domains (AI/NLP, AI/Reasoning, Biomedical, CS), 8 gaps each.
                       get_gold_gaps() has prefix matching + AI/NLP fallback.
  Verified in:         BATCH-116

  Module:              backend.pipeline.gap_analysis.deduplicator
  Exports:             GapDeduplicator, MergedGap
  Key note:            Word-overlap similarity with 0.6 threshold. Tracks source_run_ids
                       and occurrence_count. Single-run and multi-run modes.
  Verified in:         BATCH-117

  Module:              backend.pipeline.evaluation.plan_generator
  Exports:             EvaluationPlanGenerator, EvaluationPlan, DatasetRecommendation,
                       BaselineMethod, MetricTarget, AblationExperiment
  Key note:            Template mode produces 3 datasets, 3 baselines, 4 metrics, 3 ablations.
  Verified in:         BATCH-115

  Module:              backend.pipeline.preflight
  Exports:             run_preflight, PreflightReport, PreflightResult, CheckSeverity
  Key note:            8 preflight checks before pipeline acceptance: settings, LLM provider,
                       embedding provider, local LLM, database, export dir, strategy, domain.
                       Returns 503 on FATAL, 200 on OK/WARNING.
  Verified in:         BATCH-172

  Module:              backend.pipeline.gap_analysis.gap_analyzer
  Key note:            GAP_ANALYSIS_PROMPT now includes CITATION INTEGRITY (MANDATORY)
                       section. _format_paper_summaries includes author names.
  Verified in:         BATCH-113

  Module:              backend.pipeline.generation.prompts.ideator_system.md
  Key note:            Now includes CITATION INTEGRITY, CONCRETE ARCHITECTURE REQUIREMENTS,
                       FAILURE MODE ANALYSIS, MEASURABLE SUCCESS CRITERIA sections.
  Verified in:         BATCH-118

───────────────────────────────────────────────────────────
ARCHITECTURAL DECISIONS
───────────────────────────────────────────────────────────

  DEC-001: TreeSearchStage is the SOLE conversion point between IdeaCandidate
           and ResearchIdea.
  Source:   BATCH-75
  Active:   YES

  DEC-002: persist_ideas() is the SOLE point where ideas are written to the DB.
           Dedup happens here, not in crud.create_idea().
  Source:   BATCH-75
  Active:   YES

  DEC-003: Strategy stage names MUST match PipelineOrchestrator._STAGE_ORDER exactly.
           The 16 stage names are: literature_search, ingestion, gap_analysis,
           gap_reflection, idea_generation, idea_reflection, novelty_checking,
           feasibility_scoring, mechanical_metrics, proposal_synthesis,
           adversarial_review, evaluation, paper_synthesis, citation_audit,
           proposal_deepening, export.
  Source:   BATCH-76 (updated B172)
  Active:   YES

  DEC-004: _STAGE_ORDER has 16 entries (gap_reflection + idea_reflection added in B157).
           All strategy presets must be updated to account for new stages.
  Source:   BATCH-157
  Active:   YES

  DEC-015: KnowledgeLibrary wired into pipeline. Post-run indexing via
           ExportStage saves papers/gaps/ideas to SQLite (data/knowledge_library.db).
           Pre-run query via LiteratureSearchStage merges existing papers.
           Knowledge query API: GET /api/v1/search/knowledge/{domain}.
           Cross-run memory — Run #2 knows Run #1 existed.
  Source:   BATCH-158
  Active:   YES

  DEC-014: EvaluationStage uses the thinking provider to score proposals on
           5 dimensions: Novelty, Feasibility, Completeness, Rigor, Clarity.
           Scores 0.0-1.0 with written justifications. Frontend includes
           radar chart (pure SVG) and EvaluationCard on idea-detail page.
           Stage name: evaluation (after adversarial_review, before paper_synthesis).
  Source:   BATCH-156
  Active:   YES

  DEC-005: Quality evaluation (_evaluate_pipeline) runs after ALL stages complete,
           before self-improvement. Stores result in PipelineResult.quality_report.
  Source:   BATCH-116
  Active:   YES

  DEC-006: Reference verification (_verify_references) runs inside the
           proposal_synthesis persistence block, after proposals are saved.
           Non-blocking per HB-01.
  Source:   BATCH-112
  Active:   YES

  DEC-007: .env.example is the SOLE environment template tracked in git.
           .env is the SOLE source of runtime secrets. No .py file may
           contain real credentials. Startup warnings fire on insecure defaults.
  Source:   BATCH-137
  Active:   YES

  DEC-008: config.py is the SOLE location for default URL and model values.
           All pipeline modules read from settings via lazy import pattern
           (try/except with get_settings()). Constructor override params
           are allowed for testability.
  Source:   BATCH-138
  Active:   YES

  DEC-009: EROCK_ENV toggle governs security posture. development = permissive
           defaults (CORS *, no JWT enforcement). production = strict defaults
           (CORS empty, JWT mandatory, debug forced off). Production startup
           raises RuntimeError on default JWT secret regardless of auth_enabled.
  Source:   BATCH-140
  Active:   YES

  DEC-011: PaperSynthesisStage generates full academic papers from proposals
           using the generation provider (cloud). Papers are 3,000-5,000 words
           with academic structure (Abstract, Intro, Related Work, Methodology,
           Experiments, Discussion, Conclusion). Venue templates (IEEE, ACM,
           NeurIPS, Generic) control LaTeX formatting. Stage name: paper_synthesis.
           Runs after adversarial_review, before proposal_deepening.
  Source:   BATCH-153
  Active:   YES

───────────────────────────────────────────────────────────
KNOWN GOTCHAS
───────────────────────────────────────────────────────────

  GOTCHA-001: 196+ trio-mode tests fail because `trio` is not installed.
               Pre-existing. Run with `-p no:asyncio`.
  Status:      OPEN

  GOTCHA-002: Tree search expansion produces non-fatal warnings.
  Status:      OPEN — cosmetic, non-blocking

  GOTCHA-003: Pipeline takes 10-26 min for real runs.
  Status:      MITIGATED — expected behavior

  GOTCHA-004: ChromaDB stale zero-vector data from old runs.
  Status:      MITIGATED — validate_startup() warns

  GOTCHA-005: .env must be manually created from .env.example before
              first run. git clone alone won't produce a working .env.
  Status:      OPEN — expected behavior per DEC-007

  GOTCHA-006: Literature sources (crossref, openalex, semantic_scholar) use
              lazy import for settings (try/except). If imported before app
              init, they fall back to hardcoded defaults. This is intentional
              but means unit tests must mock get_settings explicitly.
  Status:      MITIGATED — constructor api_base override for testability

  GOTCHA-007: Docker-dependent tests (TEST-151-01-02, 01-04, 02-01) require
              Docker daemon running. Cannot execute in CI without Docker.
              These are `manual` type tests.
  Status:      OPEN — requires Docker daemon for verification

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Last verified count: 2,838
  Verified in:         BATCH-176 (2026-05-11)
  Phase 10 total:      +300 (23 batches, B151→B175)
  Breakdown:           2,499 + 16 + 21 + 15 + 16 + 12 + 12 + 14 + 14 + 12 + 12 + 10 + 26 + 21 + 25 + 11

───────────────────────────────────────────────────────────
CARRY-FORWARD OBLIGATIONS
───────────────────────────────────────────────────────────

  (none — all Phase 8 tests pass)

═══════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────
PHASE 9 MODULES (B121–B129)
───────────────────────────────────────────────────────────

  Module:              backend.pipeline.claims.models
  Exports:             ClaimType (enum), Claim (dataclass)
  Key note:            5 claim types: METHOD, RESULT, LIMITATION, FUTURE_WORK, COMPARISON.
                       20+ typed fields per claim with type-specific optional fields.
  Verified in:         BATCH-121

  Module:              backend.pipeline.claims.extractor
  Exports:             ClaimExtractor
  Key note:            Uses LLM structured_output with closed-book prompt.
                       Returns [] on failure (HB-01). Every claim has source_paper_id (HB-02).
  Verified in:         BATCH-121

  Module:              backend.pipeline.claims.store
  Exports:             ClaimStore
  Key note:            SQLAlchemy-based persistence with CRUD operations.
                       Idempotent store_claims (HB-01). Keyword fallback for similarity search.
                       Validates claim_type against enum on read (A-02).
  Verified in:         BATCH-122

  Module:              backend.pipeline.wiki.models
  Exports:             WikiEntry (dataclass)
  Key note:            30-field structured wiki entry for research papers.
  Verified in:         BATCH-123

  Module:              backend.pipeline.wiki.generator
  Exports:             WikiGenerator
  Key note:            LLM structured_output → WikiEntry. Returns empty entry on failure (HB-01).
  Verified in:         BATCH-123

  Module:              backend.pipeline.wiki.verifier
  Exports:             WikiVerifier
  Key note:            Keyword-overlap verification. Sets quality_score + unsupported_claims.
                       Does NOT modify original wiki (HB-02).
  Verified in:         BATCH-123

  Module:              backend.pipeline.curation.engine
  Exports:             CurationEngine, CurationRule
  Key note:            Rule-based paper filtering: must_include, must_exclude, semantic, max_papers.
                       Invalid rules skipped with warning (HB-02).
  Verified in:         BATCH-124

  Module:              backend.pipeline.claims.contradiction.detector
  Exports:             ContradictionDetector, ContradictionCandidate
  Key note:            Pairs RESULT claims with same dataset+metric but different values.
                       Heuristic verification: >10% difference = genuine.
  Verified in:         BATCH-125

  Module:              backend.pipeline.claims.method_problem
  Exports:             MethodProblemDetector, MethodProblemGap
  Key note:            Builds method×dataset matrix from claims. Flags unexplored combinations.
  Verified in:         BATCH-126

  Module:              backend.pipeline.claims.study_designer
  Exports:             StudyDesigner, StudyDesign, MVPExperiment, GoNoGoCriteria
  Key note:            Full study design from ideas/gaps with pseudocode, go/no-go, risk, timeline.
  Verified in:         BATCH-127

  Module:              backend.pipeline.ingestion.scheduler
  Exports:             IngestionScheduler, IngestionResult
  Key note:            Daily fetch→filter→extract→wiki pipeline. Configurable interval.
  Verified in:         BATCH-128

  Module:              backend.pipeline.claims.connection_agent
  Exports:             ConnectionAgent, PaperConnection
  Key note:            Finds builds_on/contradicts/complements relationships from claims.
                       Deduplicates connection pairs.
  Verified in:         BATCH-129

  Table:               research_claims (SQLAlchemy)
  Key note:            22 columns, claim_id unique, source_paper_id indexed.
                       Migration: alembic/versions/007_research_claims.py
  Verified in:         BATCH-122

───────────────────────────────────────────────────────────
PHASE 9 SUMMARY
───────────────────────────────────────────────────────────
  Batches:             B121–B129 (9 STANDARD + 1 SIMPLIFIED)
  New modules:         12 modules across 4 packages (claims, wiki, curation, ingestion)
  New files:           ~25 source files + 9 test files
  New tests:           69 (12+12+8+6+7+6+7+5+6)
  Total test baseline: 2,361 (was 2,292)
  Decision gates:      All passed (claims viable, wiki accurate, contradictions real)

───────────────────────────────────────────────────────────
BATCH-173 — Stage Observability + Graceful Degradation
───────────────────────────────────────────────────────────
  StageReport dataclass:   name, status, elapsed_s, error, skip_reason
  PipelineResult field:    stage_report: list[StageReport]
  Orchestrator tracking:   All 16 stages tracked (executed/skipped_by_strategy/skipped_by_gate/skipped_by_error/not_reached)
  Graceful degradation:    Stage errors no longer halt the pipeline
  DB persistence:          stage_report_json column on PipelineRun model
  API exposure:            /runs/detail/{id} includes stage_report (backward compatible)
  New files:              3 test files
  New tests:              21 (10+6+5)
  Total test baseline:    2,769 → 2,790 (+21)

───────────────────────────────────────────────────────────
BATCH-174 — Functional Test Suite for All 16 Pipeline Stages
───────────────────────────────────────────────────────────
  Scope:                  Functional tests for every pipeline stage
  Approach:               Instantiate with mocks, execute via asyncio.run(), verify output
  Stages covered:         All 16 (LitSearch, Ingestion, GapAnalysis, GapReflection,
                          IdeaGeneration, IdeaReflection, NoveltyChecking,
                          FeasibilityScoring, MechanicalMetrics, ProposalSynthesis,
                          AdversarialReview, Evaluation, PaperSynthesis,
                          CitationAudit, ProposalDeepening, Export)
  Source code changes:    NONE — only test files
  New files:              3 test files
  New tests:              25 (10+11+4)
  Total test baseline:    2,790 → 2,815 (+25)

───────────────────────────────────────────────────────────
BATCH-175 — End-to-End Pipeline Integration Test
───────────────────────────────────────────────────────────
  Scope:                  Full 16-stage pipeline run with mocked providers
  Approach:               Subclass PipelineOrchestrator, override __init__ to inject mocks,
                          call real run() method, verify all stages execute in order
  Stages executed:        All 16 (literature_search → export)
  Strategy:               _OrchestratorUnderTest bypasses super().__init__(),
                          manually sets all service attributes, builds stages with mocks
  Mock infrastructure:    MockSearchService, MockLLMProvider (via MagicMock),
                          all persistence/governance/observability disabled
  Verification:           11 tests — 7 pipeline output + 1 ordering + 1 regression + 2 doc checks
  Source code changes:    NONE — only test files
  New files:              1 test file (test_batch175_e2e_integration.py)
  New tests:              11 (7+1+1+2)
  Total test baseline:    2,815 → 2,826 (+11)

───────────────────────────────────────────────────────────
BATCH-176 — Rate Limit Resilience with Exponential Backoff
───────────────────────────────────────────────────────────
  Scope:                  LLM-level retry wrapper for 429/503 errors
  Approach:               retry_llm_call() wraps async LLM calls with exponential backoff.
                          Takes coro_factory (callable) not coroutine, so retries re-invoke.
  New module:             backend/providers/retry.py
  Key functions:          _is_rate_limit_error(exc), retry_llm_call(coro_factory, max_retries, base_delay)
  Config:                 llm_rate_limit_retries (default 3, env EROCK_LLM_RATE_LIMIT_RETRIES)
  StageReport:            retries_used field tracks LLM retries consumed per stage
  Orchestrator wiring:    _execute_stage_with_retry() wraps stage.execute(ctx) with retry_llm_call
                          _last_stage_retries tracks per-stage retry count
                          StageReport appends include retries_used for executed/skipped stages
  Error detection:        Checks status_code attribute, response.status_code, and string patterns (429, rate, 503, overloaded)
  Backoff:                Exponential: base_delay * 2^attempt (default 2.0s, so 2s → 4s → 8s)
  Zero overhead:          No sleep/retry on success path (retries_used=0)
  Source code changes:    retry.py (new), result.py, config.py, orchestrator.py
  New files:              1 source file + 1 test file
  New tests:              12
  Total test baseline:    2,826 → 2,838 (+12)
