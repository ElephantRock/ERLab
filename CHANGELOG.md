# Changelog

All notable changes to the Elephant Rock Research Platform are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2026-05-11] BATCH-175 — End-to-End Pipeline Integration Test

### Added
- 11 E2E integration tests in `test_batch175_e2e_integration.py`
- `_OrchestratorUnderTest` subclass that bypasses real service creation and injects mocks
- Full 16-stage pipeline run via `asyncio.run(orchestrator.run())` with all services mocked
- Verifies all stages execute in correct `_STAGE_ORDER` sequence
- Verifies `PipelineResult` has papers, gaps, ideas, and proposals after full run
- Verifies `stage_report` has 16 entries with `status="executed"`
- Regression test confirms batch172-174 tests still pass
- Doc checks confirm STATE.md and CHANGELOG.md are updated

### Changed
- Test baseline: 2,815 → 2,826 (+11 tests)
- No source code changes in backend/pipeline/ or backend/api/

## [2026-05-11] BATCH-174 — Functional Test Suite for All 16 Pipeline Stages

### Added
- 25 functional tests across 3 test files covering all 16 pipeline stages
- `test_batch174_core_stages.py` — 10 tests for stages 0-8 (LitSearch, Ingestion, GapAnalysis, GapReflection, IdeaGeneration, IdeaReflection, NoveltyChecking, FeasibilityScoring, MechanicalMetrics)
- `test_batch174_synthesis_stages.py` — 11 tests for stages 9-15 (ProposalSynthesis, AdversarialReview, Evaluation, PaperSynthesis, CitationAudit, ProposalDeepening, Export)
- `test_batch174_verification.py` — 4 meta-tests (batch pass, regression, STATE.md, CHANGELOG)
- Each test: instantiate stage with mocks, create StageContext, asyncio.run(), assert output

### Changed
- Test baseline: 2,790 → 2,815 (+25 tests)
- No source code changes in backend/pipeline/

## [2026-05-11] BATCH-173 — Stage Observability + Graceful Degradation

### Added
- `StageReport` dataclass in `backend/pipeline/result.py` with name, status, elapsed_s, error, skip_reason fields
- `PipelineResult.stage_report` field (list[StageReport]) for per-stage observability
- Orchestrator tracks all 16 stages: executed, skipped_by_strategy, skipped_by_gate, skipped_by_error, not_reached
- Graceful degradation: stages that throw exceptions no longer halt the pipeline
- `stage_report_json` column on `PipelineRun` DB model for persistence
- `_persist_stage_report()` helper method on PipelineOrchestrator
- Run detail API (`/runs/detail/{id}`) includes `stage_report` in response
- Backward compatible: pre-B173 runs return empty `stage_report` list
- 21 new tests across 3 test files (stage_report, api_expose, verification)

### Changed
- `backend/pipeline/orchestrator.py` — stage loop now appends StageReport entries for each skip/execute path
- `backend/api/routes/pipeline.py` — run detail endpoint includes stage_report from DB
- `backend/db/models.py` — PipelineRun has stage_report_json column

### Test baseline: 2,769 → 2,790 (+21)

## [2026-05-11] BATCH-172 — Wire Dead Stages + Preflight Validation

### Added
- `GapReflectionStage` wired at index 3 in `PipelineOrchestrator._build_stages()`
- `IdeaReflectionStage` wired at index 5 in `PipelineOrchestrator._build_stages()`
- `EvaluationStage` wired at index 11 in `PipelineOrchestrator._build_stages()`
- All 3 stages use `thinking_provider` with `self._provider` fallback
- Preflight validation runs before API accepts pipeline runs (`/run` endpoint)
- API returns 503 with detailed fatal checks on preflight failure
- API returns 200 with preflight summary on success
- `backend/pipeline/preflight.py` — 8 checks: settings, LLM, embedding, local LLM, database, export dir, strategy, domain
- 26 new tests across 4 test files (wiring, preflight, strategies, verification)
- Updated `docs/aiv/STATE.md` with BATCH-172 verification info

### Changed
- `backend/pipeline/orchestrator.py` — `_build_stages()` now returns 16 stages (was 13)
- `backend/api/routes/pipeline.py` — `trigger_run()` runs preflight before `asyncio.create_task()`
- All 4 strategy presets verified to correctly enable/disable new stages

### Test baseline: 2,743 → 2,769 (+26)

## [2026-05-11] BATCH-151 — Docker Deployment + AI Honesty Badge

### Added
- `Dockerfile.backend` — Multi-stage Python backend image (non-root, health check, Alembic migrations)
- `Dockerfile.frontend` — Multi-stage Node.js + Nginx frontend image (Vite build, SPA routing)
- `docker-entrypoint.sh` — Entrypoint script: migrations → uvicorn
- `.env.docker` — Example Docker environment variables (EROCK_ keys)
- `backend/pipeline/constants.py` — `AI_HONESTY_BADGE` constant for all export formats
- AI honesty badge appended to all proposal exports: Markdown, LaTeX, BibTeX, md_to_latex
- 19 new tests covering Docker files, compose config, and badge consistency

### Changed
- `docker-compose.yml` — Simplified from Postgres+Redis+App+Nginx to Backend+Frontend with SQLite
- `nginx/nginx.conf` — Updated upstream to `backend:8000` service name

### Test baseline: 2,480 → 2,499 (+19)

## [2026-05-11] BATCH-152 — Cross-Model Adversarial Review

### Added
- `backend/pipeline/evaluation/adversarial_reviewer.py` — AdversarialReviewer class with AdversarialReviewScore dataclass
- `backend/pipeline/evaluation/prompts/adversarial_review.md` — Critical adversarial review prompt template
- AdversarialReviewStage: scores proposals on Soundness, Novelty, Feasibility, Clarity (1-10)
- Revision loop: rejected proposals (score < 7.0) re-synthesized with revision notes (max 2 rounds)
- Provider isolation: uses thinking provider (local LM Studio) for review, generation provider (cloud) for synthesis
- Strategy presets: deep_research enables adversarial review, fast_scan disables it
- 16 new tests covering scoring, clamping, revision loop, max rounds, provider mismatch, preset loading

### Changed
- `_STAGE_ORDER` now 11 entries (added `adversarial_review` after `proposal_synthesis`)
- `strategies/presets.py` fixed pre-existing drift (added `proposal_deepening` + `adversarial_review`)

### Test baseline: 2,499 → 2,515 (+16)

## [2026-05-11] BATCH-153 — Full Paper Synthesis (LaTeX Output)

### Added
- `backend/pipeline/synthesis/paper_synthesizer.py` — PaperSynthesizer + PaperSynthesisResult dataclass
- `backend/pipeline/synthesis/prompts/paper_synthesis_system.md` — Academic paper synthesis prompt
- `backend/pipeline/export/venue_templates.py` — VenueTemplate dataclass with IEEE, ACM, NeurIPS, Generic presets
- PaperSynthesisStage: generates full academic papers from proposals (3,000-5,000 words)
- LaTeX export API: `GET /api/export/latex/{run_id}?venue=generic`
- LatexExporter extended with venue template support
- 21 new tests covering paper synthesis, venue templates, LaTeX export, API, presets

### Changed
- `_STAGE_ORDER` now 12 entries (added `paper_synthesis` after `adversarial_review`)
- `strategies/presets.py` — paper_synthesis enabled for deep_research + academic_proposal
- `latex_exporter.py` — venue parameter for template selection
- `api/routes/export.py` — new LaTeX endpoint

### Test baseline: 2,515 → 2,536 (+21)

## [2026-05-11] BATCH-154 — Citation & Claim Audit (3-Axis)

### Added
- `backend/pipeline/verification/citation_claim_auditor.py` — CitationClaimAuditor with 3-axis verification
- `backend/pipeline/verification/prompts/citation_audit.md` — Context verification prompt
- CitationAuditStage: verifies every [SOURCE-X] citation existence, context accuracy, and quantitative faithfulness
- Trust score system: 0.0-1.0 per proposal based on citation verification results
- Timeout handling: partial results returned after 60s per proposal

### Changed
- `_STAGE_ORDER` now 13 entries (added `citation_audit` after `paper_synthesis`)
- `reference_verifier.py` extended with [SOURCE-X] pattern support
- Strategy presets: deep_research + academic_proposal enable audit; fast_scan + literature_review disable

### Test baseline: 2,536 → 2,551 (+15)

## [2026-05-11] BATCH-155 — Search Engine Expansion

### Added
- PubMed source wired into SearchService (toggleable via `pubmed_enabled`)
- CrossRef source wired into SearchService (toggleable via `crossref_enabled`)
- 5 concurrent search sources: Semantic Scholar, arXiv, OpenAlex, PubMed, CrossRef
- RelevanceFilter integrated into search pipeline (post-dedup, embedding-based scoring)
- Health check: `SearchService.health_check()` reports per-source status and latency
- Config settings: `pubmed_api_key`, `pubmed_enabled`, `crossref_enabled`
- 16 new tests covering source wiring, filter integration, health checks

### Changed
- `search_service.py` — _default_sources() now returns up to 5 sources
- `config.py` — 3 new search settings fields
- `.env.example` — PubMed and CrossRef settings added

### Test baseline: 2,551 → 2,567 (+16)

## [2026-05-11] BATCH-156 — Multi-Dimensional Proposal Evaluation

### Added
- `EvaluationStage`: scores proposals on Novelty, Feasibility, Completeness, Rigor, Clarity
- `frontend/src/components/ideas/radar-chart.tsx` — Pure SVG 5-point radar chart
- RadarChart + EvaluationCard wired into idea-detail page
- 12 new tests covering stage registration, metadata storage, fallback, presets

### Changed
- `_STAGE_ORDER` now 14 entries (added `evaluation` after `adversarial_review`)
- Strategy presets: deep_research + academic_proposal enable; fast_scan + literature_review disable
- `idea-detail.tsx` imports EvaluationCard and RadarChart

### Test baseline: 2,567 → 2,579 (+12)

## [2026-05-11] BATCH-157 — Iterative Reflection Loop

### Added
- GapReflectionStage: reflects on gap quality after gap_analysis, max 2 retries
- IdeaReflectionStage: reflects on idea quality after idea_generation, max 2 retries
- Iterative self-improvement loop using existing ReflectionStage (from B80)
- 12 new tests covering both stages, fallback behavior, strategy presets

### Changed
- `_STAGE_ORDER` now 16 entries (added gap_reflection + idea_reflection)
- Strategy presets: deep_research + academic_proposal enable; fast_scan + literature_review disable

### Test baseline: 2,579 → 2,591 (+12)

## [2026-05-11] BATCH-158 — Knowledge Library Persistence

### Added
- Post-run knowledge indexing: ExportStage indexes papers/gaps/ideas into SQLite
- Pre-run knowledge query: LiteratureSearchStage merges existing papers from library
- Knowledge query API: `GET /api/v1/search/knowledge/{domain}`
- Cross-run memory — future runs benefit from past runs
- 14 new tests covering library operations, integration, API

### Changed
- `stages.py` — ExportStage adds post-run indexing; LiteratureSearchStage adds pre-run query
- `api/routes/search.py` — new knowledge endpoint

### Test baseline: 2,591 → 2,605 (+14)

## [2026-05-11] BATCH-159 — 5-State Verification + Staged Confidence Deepening

### Added
- VerificationState enum: 5 states (SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE, CONTRADICTED, UNVERIFIED)
- TrustTier gates in CitationClaimAuditor: LOW_TRUST and FABRICATED warnings
- Temporal decay module: exponential decay for citation confidence (3-year half-life)
- CitationCheck.decayed_confidence field applied during verification
- 14 new tests covering all three subsystems

### Changed
- `reference_verifier.py` — CitationCheck gets verification_state + decayed_confidence
- `citation_claim_auditor.py` — compute_trust_tiers() + trust_gate_warnings

### Test baseline: 2,605 → 2,619 (+14)

## [2026-05-11] BATCH-160 — Local Document Ingestion

### Added
- Generic DocumentParser: PDF, TXT, CSV, MD, DOCX with graceful fallbacks
- Extended upload API: POST /ingest accepts all 5 formats (50MB limit)
- Documents list endpoint: GET /api/v1/knowledge/documents
- Pipeline integration: locally uploaded docs injected into LiteratureSearchStage
- 12 new tests covering parser, API validation, pipeline integration

### Changed
- `api/routes/knowledge.py` — extended ingest endpoint + documents list
- `pipeline/stages.py` — LiteratureSearchStage merges local uploads

### Test baseline: 2,619 → 2,631 (+12)

## [2026-05-11] BATCH-161 — Recursive Deep Research (Tree Exploration)

### Added
- CitationExplorer: bidirectional citation graph traversal via S2 + OpenAlex
- TreeNode + TreeExplorationResult models for tree exploration state
- Configurable breadth x depth with API cooldown between requests
- Tree exploration wired into LiteratureSearchStage (deep_research + academic_proposal)
- Backward traversal finds foundational papers cited by seed papers
- 12 new tests covering explorer, result model, preset wiring

### Changed
- `stages.py` — LiteratureSearchStage runs CitationExplorer when strategy enables it
- `presets.py` — deep_research + academic_proposal enable citation_explore

### Test baseline: 2,631 → 2,643 (+12)

## [2026-05-11] BATCH-162 — Research Journal & AI Honesty Labeling

### Added
- Journal API: `GET /api/v1/pipeline/runs/{run_id}/journal` returns notes + readme
- AI honesty disclaimer in notes.md and README.md journal output
- `StageContext.journal` field for per-stage journaling
- Journal hooks in LiteratureSearchStage and ExportStage
- 10 new tests

### Changed
- `journal/writer.py` — AI honesty labeling in both outputs
- `stages.py` — journal hooks in key stages
- `api/routes/pipeline.py` — new journal endpoint

### Test baseline: 2,643 → 2,653 (+10)

## [0.140.0-prealpha] — 2026-05-10

### Security
- **BATCH-140 — CORS + Security Defaults Hardening**
  - Added `EROCK_ENV` toggle (`development` | `production`, default: `development`).
  - Production mode: CORS defaults to empty, debug forced off, JWT must be non-default.
  - Development mode: identical to pre-batch behavior (backward compatible).
  - 10 new tests covering dev/prod CORS, debug, and JWT enforcement.

## [0.139.0-prealpha] — 2026-05-10

### Changed
- **BATCH-139 — Externalize Compaction Budgets & Constraint Config**
  - Added compaction stage budgets (`compaction_stage_budgets`), paper limits
    (`compaction_paper_limits`), and abstract char limits
    (`compaction_abstract_chars_tight`, `compaction_abstract_chars_loose`)
    to config.py as JSON-string fields with sensible defaults.
  - Added constraint config fields (`constraint_max_size`,
    `constraint_max_growth_pct`, `constraint_min_sections`,
    `constraint_allow_empty`) to config.py.
  - Replaced hardcoded `DEFAULT_BUDGETS`, `DEFAULT_PAPER_LIMITS`, and
    abstract char limits (80/150) in budget_manager.py with settings reads
    and JSON parse fallback for graceful degradation.
  - Replaced hardcoded `ConstraintConfig` values in orchestrator.py with
    settings reads from `self._settings`.
  - 13 new tests (budgets: 10, constraints: 3).

## [0.139.0-prealpha] — 2026-05-10

### Changed
- **BATCH-139 — Token Budget & Threshold Externalization**
  - Externalized all 5 stage token budgets into config.py as JSON string
    (`EROCK_COMPACTION_STAGE_BUDGETS`) with graceful malformed-JSON fallback.
  - Externalized paper limits per stage (`EROCK_COMPACTION_PAPER_LIMITS`).
  - Externalized abstract char limits (`EROCK_COMPACTION_ABSTRACT_CHARS_TIGHT/LOOSE`).
  - Externalized constraint config (`EROCK_CONSTRAINT_MAX_SIZE`, `MAX_GROWTH_PCT`,
    `MIN_SECTIONS`, `ALLOW_EMPTY`) into config.py from orchestrator.py.
  - Pipeline quality-vs-cost tuning is now possible via `.env` edits only.
  - 13 new tests including malformed JSON fallback coverage.

## [0.138.0-prealpha] — 2026-05-10

### Changed
- **BATCH-138 — Configuration Centralization**
  - Externalized CrossRef, OpenAlex, Semantic Scholar API URLs into
    config.py (`EROCK_CROSSREF_API_URL`, `EROCK_OPENALEX_API_URL`,
    `EROCK_SEMANTIC_SCHOLAR_API_URL`).
  - Externalized compaction fallback model (`EROCK_COMPACTION_FALLBACK_MODEL`).
  - All pipeline modules now read URLs/models from settings via lazy import
    pattern — no more hardcoded values in non-config source files.
  - Literature sources accept constructor `api_base` override for testability.
  - Removed all `getattr` URL fallbacks from provider_factory.py.
  - 28 new tests covering config defaults, env overrides, and constructor injection.

## [0.137.0-prealpha] — 2026-05-10

### Security
- **BATCH-137 — Credential Hygiene + Secret Hardening**
  - Removed `.env` from git tracking (`git rm --cached`). No secrets in repository.
  - Expanded `.env.example` from 12 → 20 documented fields covering all
    security-relevant settings (JWT, API keys, LM Studio, CORS, DB URL).
  - Added startup security warnings: alerts when default JWT secret used with
    `auth_enabled=True`, and when no LLM API key is configured.
  - Replaced hardcoded developer IP (`100.64.0.1`) in config defaults and
    provider factory with `localhost` / settings-based resolution.
  - 13 new tests verifying git hygiene, warning behavior, and IP absence.

## [0.76.0-prealpha] — 2026-05-06

### Added
- **Pipeline Strategy Architecture** (BATCH-76): Pluggable strategy system allowing
  the pipeline to run in 4 modes: `fast_scan` (2-5 min), `deep_research` (25 min),
  `academic_proposal` (45 min), `literature_review` (10 min).
- `backend/pipeline/strategies/` module with `PipelineStrategy` enum, `StageConfig`,
  `StrategyConfig` dataclasses, and `StrategyRegistry` singleton.
- Strategy selector dropdown in frontend pipeline configuration form.
- Strategy display in run detail page.
- `PipelineRunRequest.strategy` field with Pydantic regex validation.
- Orchestrator `strategy` parameter with stage skip logic for disabled stages.
- 31 new tests across 3 test files.

### Changed
- `PipelineOrchestrator.__init__()` accepts optional `strategy` parameter (default: "deep_research").
- Stage execution loop checks strategy config before existing gate logic.

### Fixed
- Reviewer flag CHK-17: Stage names corrected to match actual `_STAGE_ORDER`.

## [0.77.0-prealpha] — 2026-05-06

### Added
- **Fast Scan Pipeline Strategy** (BATCH-77): FastProposalSynthesizer produces
  abbreviated 3-section proposals (Abstract, Key Idea, Method Sketch) in < 5 min.
- `backend/pipeline/synthesis/fast_synthesizer.py` with timeout-aware LLM calls.
- `backend/pipeline/synthesis/prompts/fast_synthesis_system.md` prompt template.
- Orchestrator `_build_synthesis_stage()` selects fast/full synthesizer based on strategy.
- 13 new tests for fast_scan strategy.

### Changed
- fast_scan strategy uses FastProposalSynthesizer instead of full ProposalSynthesizer.

## [0.78.0-prealpha] — 2026-05-06

### Added
- **Thinking/Generation Model Split** (BATCH-78): Configurable `thinking_model` and
  `generation_model` settings for cost optimization (50-70% savings).
- `backend/pipeline/model_selection.py` with `ModelSelector` class.
- `get_thinking_provider()` and `get_generation_provider()` in provider_factory.
- 15 new tests.

### Changed
- `Settings` has 4 new fields: thinking_model, generation_model, thinking_model_max_tokens, generation_model_max_tokens.

## [0.79.0-prealpha] — 2026-05-06

### Added
- **Live Pipeline Progress** (BATCH-79): Granular SSE progress events with
  human-readable messages ("Searching arXiv for 'sparse attention'...").
- `backend/pipeline/streaming/progress_reporter.py` with ProgressReporter class.
- `frontend/src/components/pipeline/activity-log.tsx` scrollable activity log.
- 12 new tests.

## [0.80.0-prealpha] — 2026-05-06

### Added
- **Iterative Reflection Loop** (BATCH-80): LLM evaluates gap/idea quality after
  gap analysis and ideation. If score < threshold, regenerates with feedback.
  Max 3 iterations. Disabled for fast_scan strategy.
- `backend/pipeline/reflection/` module with ReflectionStage and ReflectionResult.
- Prompt templates for gap and idea evaluation.
- 12 new tests.

## [0.83.0-prealpha] — 2026-05-06

### Added
- **SOUL.md Research Philosophy** (BATCH-83): Defines Elephant Rock's values:
  intellectual honesty, depth over breadth, rigor, constructive criticism, clarity.
  SoulLoader injects philosophy into all LLM system prompts.
- **Error Knowledge Store**: Append-only failure log. Records stage, reason,
  and suggestion for each quality failure. Future runs query to avoid mistakes.
- `SOUL.md` (2.7KB, 11 sections) + `backend/pipeline/soul_loader.py`.
- `backend/pipeline/knowledge/error_store.py` with ErrorKnowledgeStore.
- 10 new tests.

## [0.84.0-prealpha] — 2026-05-06

### Added
- **Research Journal** (BATCH-84): Every pipeline run generates notes.md
  (detailed stage log) and README.md (clean summary) in data/runs/{run_id}/.
  Inspired by simonw/research methodology.
- `backend/pipeline/journal/` module with JournalWriter.
  Sensitive data scrubbed from journal entries.
- 8 new tests.

## [0.85.0-prealpha] — 2026-05-06

### Added
- **More Literature Sources** (BATCH-85): PubMed (NCBI E-utilities),
  CrossRef (DOI metadata), and MultiSourceSearcher.
  No API keys required. Each source fails independently.
  Results merged and deduplicated by DOI + title.
- `backend/pipeline/literature/pubmed_source.py` — PubMedSource.
- `backend/pipeline/literature/crossref_source.py` — CrossRefSource.
- `backend/pipeline/literature/multi_source.py` — MultiSourceSearcher.
- 14 new tests.

## [0.86.0-prealpha] — 2026-05-06

### Added
- **Relevance Filter** (BATCH-86): Filters search results by embedding cosine
  similarity to the domain query. Configurable threshold (default 0.3).
  Guarantees minimum 5 papers (HB-01). Fail-open (HB-02).
- `backend/pipeline/literature/relevance_filter.py` with RelevanceFilter.
- 8 new tests.

## [0.87.0-prealpha] — 2026-05-06

### Added
- **SKILL.md Platform Manifest** (BATCH-87): Machine-readable YAML+Markdown
  defining capabilities, constraints, integrations, and pipeline stages.
- **Recursive Search** (BATCH-87): search_depth config in Settings.
  search_recursive() method uses follow-up queries from paper titles.
- `SKILL.md` at project root.
- `backend/config.py` — search_depth field.
- `backend/pipeline/literature/search_service.py` — search_recursive method.
- 6 new tests.

## [0.88.0-prealpha] — 2026-05-06

### Added
- **Gap Queue** (BATCH-88): Persistent SQLite-backed queue for research gaps.
  Gaps from previous runs can be queued with priority (HIGH/MEDIUM/LOW)
  for deeper investigation in future runs. Domain-filtered dequeue.
- `backend/pipeline/knowledge/gap_queue.py` with GapQueue and QueuedGap.
- 7 new tests.

## [0.89.0-prealpha] — 2026-05-06

### Added
- **Anti-Fabrication Guard** (BATCH-89): Heuristic-based content checker
  for proposals. Detects suspicious DOIs, unsupported statistics (≥95%),
  fabricated author names, generic claims. Fail-open (HB-01).
  Annotate-only — never modifies content (HB-02).
- `backend/pipeline/safety/anti_fabrication.py` with AntiFabricationGuard.
- 10 new tests.

## [0.90.0-prealpha] — 2026-05-07

### Added
- **Markdown-to-LaTeX Converter** (BATCH-90): Converts arbitrary markdown
  proposals to LaTeX source. Handles headings, bold, italic, code blocks,
  lists, tables, links. Graceful on malformed input. No external LaTeX needed.
- `backend/pipeline/export/md_to_latex.py` with MarkdownToLatexConverter.
- 8 new tests.

## [0.91.0-prealpha] — 2026-05-07

### Added
- **3-Tier Context Management** (BATCH-91): ContextManager with SYSTEM,
  DOMAIN, and TASK tiers. Token budget enforcement. Domain truncated
  before task. System never truncated (HB-02).
- `backend/pipeline/context/manager.py` with ContextManager, ContextBudget.
- 9 new tests.

## [0.92.0-prealpha] — 2026-05-07

### Added
- **Concurrency Safety Flags** (BATCH-92): StageConcurrency declares whether
  each pipeline stage is EXCLUSIVE, SAFE_TO_PARALLEL, or READ_ONLY.
  ConcurrencyManager resolves parallel execution waves.
  All 9 stages have default declarations.
- `backend/pipeline/concurrency.py` with ConcurrencyManager, StageConcurrency.
- 8 new tests.

## [0.93.0-prealpha] — 2026-05-07

### Added
- **MCP Tool Registry** (BATCH-93): Standardized tool calling for pipeline
  stages. MCPToolRegistry with register/call/list. Built-in tools:
  search, code_exec, file_read. Timeout enforcement (HB-01).
- `backend/pipeline/tools/tool_registry.py` with MCPToolRegistry.
- 8 new tests.

## [0.94.0-prealpha] — 2026-05-07

### Added
- **Planning Agent** (BATCH-94): Pre-execution planner that creates
  ExecutionPlan with time/token estimates per stage, blocker identification,
  and strategy-aware adjustments.
- `backend/pipeline/planning/agent.py` with PlanningAgent, ExecutionPlan.
- 8 new tests.

## [0.95.0-prealpha] — 2026-05-07

### Added
- **Run Stats Dashboard** (BATCH-95): /api/pipeline/runs/stats endpoint
  returns aggregate statistics (total runs, by status, avg duration, ideas, gaps).
  Frontend RunStats component with 5 stat cards.
- `backend/api/routes/pipeline.py` — run_stats endpoint.
- `frontend/src/components/pipeline/run-stats.tsx` — RunStats component.
- 4 new tests.

## [0.96.0-prealpha] — 2026-05-07

### Added
- **Health Monitoring** (BATCH-96): HealthMonitor checks all pipeline subsystems
  (database, embedding, LLM, search). Returns structured HealthReport
  with HEALTHY/DEGRADED/UNHEALTHY status per component.
- `backend/pipeline/monitoring/health.py` with HealthMonitor, HealthReport.
- 8 new tests.

### Added
- **Multi-Dimensional Proposal Evaluation** (BATCH-81): Score proposals on
  Novelty, Feasibility, Completeness, Rigor, Clarity (0-1 each with justification).
- `backend/pipeline/evaluation/proposal_evaluator.py` with ProposalEvaluator.
- `frontend/src/components/ideas/evaluation-card.tsx` with visual score bars.
- 14 new tests.

## [0.82.0-prealpha] — 2026-05-06

### Added
- **Knowledge Library** (BATCH-82): Persistent research memory. Papers, gaps,
  and ideas from completed runs are indexed in SQLite. Future runs query
  existing knowledge first. Dedup by title hash.
- `backend/pipeline/knowledge/library.py` with KnowledgeLibrary class.
- `backend/pipeline/knowledge/library_indexer.py` with LibraryIndexer.
- 12 new tests.## [BATCH-75] - 2026-05-06 — Post-Real-Run Pipeline Hardening (AIV v5.3)

### Fixed
- **D1**: TreeSearchStage now converts IdeaCandidate → ResearchIdea before assigning
  to PipelineResult.ideas (HB-01 assertion added). `_build_tree_data()` uses getattr()
  guards for compatibility with both types.
- **D2**: `persist_ideas()` uses getattr() guards for all field accesses (domain,
  source_gap_ids, expected_contributions, novelty_rationale) — works with both
  IdeaCandidate and ResearchIdea objects.
- **D3**: `persist_ideas()` now checks for existing ideas with same (title, pipeline_run_id)
  before inserting — prevents duplicate rows from failed/retried runs.
- **D4**: `proposal_synthesizer.py` now stores `EnsembleReviewResult.model_dump()` instead
  of the raw Pydantic model in `proposal.sections["ensemble_review"]` — fixes JSON
  serialization error.
- **D5**: `arxiv_source.py` now retries on HTTP 429 with exponential backoff (5→15→30s),
  max 3 retries. Non-429 errors fail immediately.
- **D6**: Tree search re-enabled by default (no env var workaround needed).

### Verified
- Full pipeline run with tree search enabled: 25m 59s, 40 papers, 5 gaps, 2 ideas,
  2 proposals (35K+ chars each), real Ollama 768-dim embeddings, real z.ai LLM calls.

### Added
- `backend/tests/test_pipeline/test_tree_search_types.py` — 7 tests (IdeaCandidate→ResearchIdea conversion)
- `backend/tests/test_pipeline/test_persistence_hardening.py` — 12 tests (getattr guards + dedup)
- `backend/tests/test_pipeline/test_synthesis.py` extended — 4 tests (EnsembleReviewSerialization)
- `backend/tests/test_pipeline/test_arxiv_retry.py` — 4 tests (429 retry with backoff)
- `docs/aiv/STATE.md` — first codebase state file under AIV v5.3

### Test Delta
- Baseline: 1,869 → Final: 1,901 (+32 new tests, 0 unexpected failures)

## [BATCH-74] - 2026-05-05 — Remaining Pipeline Fixes (Reference-Repo Study)

### Fixed
- **Fix #4**: Knowledge graph relationship extraction — new `relationship_extractor.py`
  extracts CITES, USES_METHOD, EXTENDS, CONTRADICTS, BUILDS_ON, APPLIED_TO between papers
  during ingestion. O(n) comparisons (max 3 per paper).
- **Fix #5**: Truth value revision — gap truth values now revised upward when ideas
  reference them via `TruthValue.revise()`. Confidence increases from 0.5 toward 0.99.
- **Fix #9**: Pipeline run watchdog — new `watchdog.py` + `updated_at` column on
  `pipeline_runs` + `POST /api/v1/pipeline/watchdog` endpoint. Detects runs stuck
  in 'running' beyond configurable timeout (default 30 min).
- **Fix #10**: Integration test skeleton — 6 integration tests exercising real
  (non-mocked) code paths under `backend/tests/integration/`.
- **Fix #11b**: Source reordering — OpenAlex placed first when no Semantic Scholar
  API key is configured, avoiding 429 rate limiting.
- **Previous (BATCH-73)**: Vector store dim mismatch, proposal synthesizer rewrite,
  pipeline halt-on-empty, tree search enabled, mechanical metrics fallback,
  self-improve dir creation, cross-source dedup, API null checks.

### New Files
- `backend/pipeline/knowledge/relationship_extractor.py`
- `backend/pipeline/execution/watchdog.py`
- `backend/tests/integration/test_pipeline_smoke.py`
- `backend/tests/test_pipeline/test_relationship_extraction.py`
- `backend/tests/test_pipeline/test_truth_revision.py`
- `backend/tests/test_pipeline/test_watchdog.py`
- `backend/tests/test_pipeline/test_source_reordering.py`
- `alembic/versions/006_watchdog_updated_at.py`

### Modified Files
- `backend/pipeline/stages.py` — relationship extraction in IngestionStage, truth
  revision in IdeaGenerationStage + TreeSearchStage
- `backend/pipeline/orchestrator.py` — provider passed to IngestionStage
- `backend/pipeline/persistence.py` — find_stale_runs, advance_stage updated_at
- `backend/pipeline/literature/search_service.py` — source reordering
- `backend/db/models.py` — PipelineRun.updated_at column
- `backend/api/routes/pipeline.py` — watchdog endpoint

### Stats
- 1,631 backend tests passing (+36 new from baseline 1,595)
- 195 pre-existing trio-mode failures (unchanged)

## [BATCH-73] - 2026-05-04 — Final Verification

### Verified
- 1,944 tests passing (1,601 backend + 343 frontend)
- 699 source files, 86,667 LOC
- 204 git commits, 67 total batches
- All platform capabilities verified functional

## [BATCH-72] - 2026-05-04 — Docker Production

### Verified
- Multi-stage Dockerfile (build + runtime, non-root user)
- docker-compose.yml + docker-compose.prod.yml (resource limits, restart policies)
- Health check on /api/v1/health
- nginx reverse proxy configuration

## [BATCH-71] - 2026-05-04 — i18n Expansion + RTL

### Added
- 6 new locale files: fr (Français), de (Deutsch), ja (日本語), ko (한국어), pt (Português), ar (العربية)
- `useRTL()` hook — sets document dir="rtl" for Arabic
- 9 total languages: en, zh, es, fr, de, ja, ko, pt, ar
- Updated existing locale files with expanded language list

## [BATCH-70] - 2026-05-04 — Plugin Marketplace

### Verified
- Plugin registry API (GET /plugins, POST /plugins/install)
- Plugin browse/search UI with install button
- 4 frontend tests passing

## [BATCH-69] - 2026-05-04 — WebSocket Real-Time

### Verified
- ConnectionManager with channel subscriptions
- Pipeline route broadcasts to WebSocket clients
- Frontend usePipelineProgress hook uses SSE for stage updates
- useWebSocket hook for bidirectional communication

## [BATCH-68] - 2026-05-04 — S2 API Key Guidance

### Added
- Startup warning when S2_API_KEY not configured
- .env.example with clear instructions and link to get free API key
- Existing retry with exponential backoff handles 429 errors

## [BATCH-67] - 2026-05-04 — UMAP/HDBSCAN Clustering

### Added
- Installed umap-learn 0.5.12 + hdbscan 0.8.42
- ClusterService now uses real UMAP + HDBSCAN (no KMeans fallback)
- `silhouette_score` and `davies_bouldin_index` fields on ClusterReport
- 3 new tests for clustering quality metrics

## [BATCH-66] - 2026-05-04 — Experiment Execution

### Added
- `ExperimentGenerator` — generates Python experiment code from idea candidates
- Code includes hypothesis test, baseline comparison, metric measurement
- Security validation via existing SecurityValidator (HB-01)
- `ExperimentResult` DB model (code_md, stdout, stderr, exit_code, success, execution_time)
- `POST /experiments/ideas/{id}/run-experiment` — full lifecycle endpoint
- `GET /ideas/{id}` now includes `experiment_results` field
- 7 new tests (4 generator + 3 API)

## [BATCH-65] - 2026-05-04 — Cross-Run Recombination

### Added
- `MethodDNAExtractor` — extracts structured method DNA (technique, domain, keywords) from ideas
- `POST /recombination/propose` — cross-run idea recombination endpoint
- Method DNA keyword extraction with stopword filtering
- Traceable recombined ideas via `source_idea_ids`
- 17 new tests (15 DNA + 2 API)

## [BATCH-64] - 2026-05-04 — Mechanical Metrics

### Added
- `MechanicalMetricsCalculator` — 5 objective metrics (reference uniqueness, gap coverage, citation density, method specificity, prior art distance)
- All metrics computable without LLM calls, values in [0.0, 1.0]
- Metrics integrated into idea generation pipeline stage
- Metrics included in idea detail API response
- 28 new tests

## [BATCH-63] - 2026-05-04 — Tree Search Pipeline

### Added
- `TreeSearchStage` — replaces `IdeaGenerationStage` when `tree_of_thought_enabled=True`
- `tree_data_json` column on PipelineRun DB model
- `parent_idea_ids` column on Idea DB model
- `TreeVisualization` React component — interactive SVG with colored nodes
- Tree Search tab on Run Detail page
- 8 new tests (4 backend + 4 frontend)

## [BATCH-62] - 2026-05-04 — Tree Search Engine

### Added
- `TreeSearchEngine` with beam search (beam_width=3, max_depth=3)
- `IdeaRecombinator` — synthesizes child from two parent ideas with lineage
- Beam width hard cap at 10
- 13 new tests

## [BATCH-61] - 2026-05-04 — Per-Proposal Timeout

### Added
- Per-proposal timeout with graceful continuation (120s default, 300s cap)
- Placeholder proposal on timeout
- CLI `--resume RUN_ID` flag
- Intermediate idea persistence after idea_generation stage
- 9 new tests

## [BATCH-60] - 2026-05-04 — Test Stabilization

### Fixed
- Mocked @sentry/react in Vitest — 339 frontend tests pass (was 71 failing)
- Increased Vitest testTimeout to 15000ms
- Exponential backoff with jitter for S2 API 429 responses

## [BATCH-57] - 2026-05-03 — Schema Sync

### Fixed
- `ensure_schema_sync(engine)` for auto column migration in developer mode

## [BATCH-56] - 2026-05-03 — Pipeline Retest

### Fixed
- BATCH-55 fixes confirmed: background task error handling, eager loading

## [BATCH-55] - 2026-05-03 — Pipeline Background Task Fix

### Fixed
- `selectinload(PipelineRun.ideas)` prevents DetachedInstanceError
- Background task now sets `status=failed` on exception

## [BATCH-53] - 2026-05-03 — Plugin SDK + E2E Mock

### Added
- Plugin SDK documentation
- E2E mock test for pipeline

## [BATCH-52] - 2026-05-03 — Accessibility + Sentry

### Added
- WCAG 2.1 AA accessibility audit
- Sentry error monitoring integration

## [BATCH-51] - 2026-05-03 — Docker + nginx

### Added
- Multi-stage Dockerfile
- docker-compose.yml + docker-compose.prod.yml
- nginx reverse proxy configuration
- Frontend CI workflow

## [BATCH-50] - 2026-05-03 — i18n zh/es + WebSocket

### Added
- Chinese (zh) and Spanish (es) locale files
- i18next configuration with language detection
- WebSocket ConnectionManager infrastructure

## [BATCH-49] - 2026-05-03 — Notifications + Experiments

### Added
- Notification center with SSE pub/sub
- Sandboxed experiment execution (SecurityValidator + ExperimentRunner)

## [BATCH-48] - 2026-05-03 — Code Splitting + Search

### Added
- React.lazy() code splitting for all pages
- Global Search UI (Ctrl+K)

## [BATCH-47] - 2026-05-02 — Gap Lifecycle Tracking

### Added
- Gap status lifecycle: identified → validated → addressed → closed
- Gap search and filter API

## [BATCH-46] - 2026-05-02 — Gap Detail Page

### Added
- Gap detail page with feedback form
- Gap feedback API (user_rating, user_notes)

## [BATCH-45] - 2026-05-02 — Cross-Run Gap Dedup

### Added
- Content hash deduplication for research gaps
- Canonical gap ID assignment

## [BATCH-44] - 2026-05-02 — Gap Search/Filter API

### Added
- Gap search API with text, type, and confidence filters

## [BATCH-43] - 2026-05-02 — Gap Feedback System

### Added
- Gap feedback API endpoint
- User rating and notes on gaps

## [BATCH-42] - 2026-05-02 — Gap Explorer UI

### Added
- Gap Explorer page with cluster scatter visualization
- Gap cards with confidence and impact

## [BATCH-41] - 2026-05-02 — Idea Feedback

### Added
- Idea feedback form with rating and notes

## [BATCH-38] - 2026-05-02 — Truth Values + Cluster Reports

### Added
- OpenNARS TruthValue integration for gap confidence
- Cluster reports with TF-IDF labels
- Truth frequency, confidence, and evidence count fields

## [BATCH-07→37] - 2026-05-02 — Original Roadmap

### Added
- Complete research pipeline (9 stages)
- Multi-agent Ideator/Critic/Refiner architecture
- Borda Tournament scoring
- Knowledge Graph with Graph RAG
- 3-source literature search (OpenAlex, Semantic Scholar, Vector Store)
- 20 frontend pages, 51 components
- Full API layer with authentication
- Database persistence with Alembic migrations
- CLI interface
- Cost tracking and monitoring
