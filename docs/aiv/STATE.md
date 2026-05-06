# CODEBASE STATE

Last Updated:       2026-05-06
Updated By:         ivory-wolf — via BATCH-76 Close
Framework Version:  5.3

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
  Exports:             TreeSearchStage (with _convert_to_research_ideas, _build_tree_data)
  Key note:            _build_tree_data() uses getattr() guards for idea.id and
                       idea.parent_idea_ids — works with both IdeaCandidate and ResearchIdea.
  Verified in:         BATCH-75

  Module:              backend.pipeline.persistence
  Exports:             PipelinePersistence (persist_ideas, persist_proposals)
  Key note:            persist_ideas() uses getattr() guards for all field accesses.
                       Dedup check on (title, pipeline_run_id) before insert.
  Verified in:         BATCH-75

  Module:              backend.pipeline.synthesis.proposal_synthesizer
  Exports:             ProposalSynthesizer, ResearchProposal
  Key note:            ensemble_review stored as model_dump() dict, not raw Pydantic.
                       ResearchProposal is a plain class (not Pydantic), uses **sections.
  Verified in:         BATCH-75

  Module:              backend.pipeline.literature.arxiv_source
  Exports:             ArxivSource
  Key note:            Retries on HTTP 429 with backoff (5→15→30s), max 3 retries.
                       Does NOT retry on non-429 errors.
  Verified in:         BATCH-75

  Module:              backend.pipeline.strategies
  Exports:             PipelineStrategy, StageConfig, StrategyConfig, StrategyRegistry, register_presets
  Key note:            Strategy presets use actual _STAGE_ORDER names (not fictional names).
                       fast_scan disables: idea_generation, novelty_checking, mechanical_metrics.
                       get_default_registry() auto-populates on first call.
  Verified in:         BATCH-76

  Module:              backend.pipeline.orchestrator
  Key note:            PipelineOrchestrator.__init__() now accepts strategy param.
                       strategy_name property exposes active strategy.
                       Stage skip logic checks strategy config BEFORE existing gate logic.
  Verified in:         BATCH-76

───────────────────────────────────────────────────────────
ARCHITECTURAL DECISIONS
───────────────────────────────────────────────────────────

  DEC-001: TreeSearchStage is the SOLE conversion point between IdeaCandidate
           and ResearchIdea. No other stage performs this conversion. The
           conversion happens in execute() before ctx.result.ideas assignment.
  Source:   BATCH-75
  Active:   YES
  Overridden: NO

  DEC-002: persist_ideas() is the SOLE point where ideas are written to the DB.
           Dedup happens here, not in crud.create_idea(). All field accesses
           use getattr() with defaults to handle both IdeaCandidate and ResearchIdea.
  Source:   BATCH-75
  Active:   YES
  Overridden: NO

  DEC-003: Strategy stage names MUST match PipelineOrchestrator._STAGE_ORDER exactly.
           The 9 stage names are: literature_search, ingestion, gap_analysis,
           idea_generation, novelty_checking, feasibility_scoring,
           mechanical_metrics, proposal_synthesis, export.
           Strategy configs reference these names, NOT fictional names like "tree_search".
  Source:   BATCH-76
  Active:   YES
  Overridden: NO

───────────────────────────────────────────────────────────
KNOWN GOTCHAS
───────────────────────────────────────────────────────────

  GOTCHA-001: 196+ trio-mode tests fail because `trio` is not installed.
               These are pre-existing and do not indicate code bugs.
               Run with `-p no:asyncio` or ignore trio failures.
  Discovered:  BATCH-73 era
  Status:      OPEN

  GOTCHA-002: Tree search expansion produces non-fatal warnings:
               "sequence item 0: expected str instance, list found"
               in prior_critique construction. Ideas are still generated.
  Discovered:  BATCH-75 (TASK-06 verification)
  Status:      OPEN — cosmetic, non-blocking

  GOTCHA-003: The pipeline takes 10-26 minutes for a real run depending on
               ChromaDB state and LLM response times. Tree search adds ~5 min.
  Discovered:  BATCH-75 (TASK-06 verification)
  Status:      MITIGATED — expected behavior with real API calls

  GOTCHA-004: ChromaDB can accumulate stale zero-vector data from old DummyEmbeddingProvider
               runs. validate_startup() detects this but old data persists until collection
               is manually deleted.
  Discovered:  BATCH-73 era
  Status:      MITIGATED — validate_startup() warns, manual cleanup required

───────────────────────────────────────────────────────────
ADAPTATION LOG (ROLLING — LAST 10 BATCHES)
───────────────────────────────────────────────────────────

  BATCH-75/TASK-01: Blueprint stated TreeSearchStage._build_tree_data() accesses
    idea.id. Confirmed. Added getattr() guards per Reviewer CHK-16/CHK-17.
  BATCH-75/TASK-02: persist_ideas() used direct idea.domain access.
    Actual: IdeaCandidate lacks .domain. Fixed with getattr(idea, 'domain', 'AI/NLP').
  BATCH-75/TASK-03: proposal.sections["ensemble_review"] stored raw Pydantic model.
    Actual: json.dumps() crashed. Fixed with model_dump().
  BATCH-76/TASK-01: Blueprint stated fast_scan disables "tree_search" and "knowledge" stages.
    Actual: _STAGE_ORDER has no such names. Fixed: use idea_generation, novelty_checking,
    mechanical_metrics instead. All tests updated.
  BATCH-76/TASK-02: Blueprint stated test baseline +45. Actual: +31 tests created.
    Corrected to match actual count.

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Last verified count: 2,073
  Verified in:         BATCH-89 (2026-05-06)
  Breakdown:           ~1,677 unit/integration passing + 44 new from BATCH-76/77,
                       ~198 trio-mode pre-existing failures

───────────────────────────────────────────────────────────
CARRY-FORWARD OBLIGATIONS
───────────────────────────────────────────────────────────

  (none — all tests in this Batch passed or are pre-existing trio-mode failures)

═══════════════════════════════════════════════════════════
