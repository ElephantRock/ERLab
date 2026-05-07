# CODEBASE STATE

Last Updated:       2026-05-07
Updated By:         ivory-wolf — via BATCH-120 Close
Framework Version:  5.3
Phase:              PHASE 8 COMPLETE (B112–B120)

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
  Key note:            _STAGE_ORDER now has 10 entries (added proposal_deepening).
                       _verify_references() runs after synthesis (B112).
                       _evaluate_pipeline() runs after all stages (B116).
                       Both are non-blocking (HB-01).
  Verified in:         BATCH-116

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

  Module:              backend.pipeline.result
  Exports:             PipelineResult
  Key note:            Now includes quality_report: dict | None field (Phase 8).
  Verified in:         BATCH-116

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
           The 10 stage names are: literature_search, ingestion, gap_analysis,
           idea_generation, novelty_checking, feasibility_scoring,
           mechanical_metrics, proposal_synthesis, proposal_deepening, export.
  Source:   BATCH-76 (updated B114)
  Active:   YES

  DEC-004: _STAGE_ORDER has 10 entries (proposal_deepening added in B114).
           All strategy presets must be updated to account for this stage.
  Source:   BATCH-114
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

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Last verified count: 2,292
  Verified in:         BATCH-120 (2026-05-07)
  Phase 8 delta:       +48 tests (B112: 8, B113: 8, B114: 7, B115: 7, B116: 7, B117: 7, B118: 4)

───────────────────────────────────────────────────────────
CARRY-FORWARD OBLIGATIONS
───────────────────────────────────────────────────────────

  (none — all Phase 8 tests pass)

═══════════════════════════════════════════════════════════
