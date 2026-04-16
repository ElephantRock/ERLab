"""Pipeline orchestrator — coordinates all research pipeline stages."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime

from backend.config import get_settings
from backend.pipeline.export.export_service import ExportService
from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport, FeasibilityScorer
from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer
from backend.pipeline.gap_analysis.models import ClusterReport, ResearchGap
from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
from backend.pipeline.generation.impasse import ImpasseDetector
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.ingestion.chunker import DocumentChunk
from backend.pipeline.ingestion.pdf_service import PDFService
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.knowledge.vector_store import VectorStore
from backend.pipeline.literature.models import Paper
from backend.pipeline.literature.search_service import SearchService
from backend.pipeline.memory.extraction import extract_from_pipeline_result
from backend.pipeline.memory.service import MemoryService
from backend.pipeline.novelty.novelty_checker import NoveltyChecker, NoveltyReport
from backend.pipeline.self_improve.evolution import PipelineEvolver
from backend.pipeline.self_improve.frontier import ParetoFrontier
from backend.pipeline.self_improve.lessons import LessonExtractor
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer, ResearchProposal
from backend.providers.base import LLMProvider
from backend.providers.provider_factory import create_provider

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete output of a pipeline run."""
    ideas: list[ResearchIdea] = field(default_factory=list)
    novelty_reports: dict[int, NoveltyReport] = field(default_factory=dict)
    feasibility_reports: dict[int, FeasibilityReport] = field(default_factory=dict)
    proposals: dict[int, ResearchProposal] = field(default_factory=dict)
    gaps: list[ResearchGap] = field(default_factory=list)
    cluster_report: ClusterReport | None = None
    papers_found: int = 0
    export_paths: dict[int, str] = field(default_factory=dict)
    run_id: str = ""
    params_used: dict = field(default_factory=dict)


class PipelineOrchestrator:
    """Coordinates the full research idea generation pipeline."""

    def __init__(self, provider: LLMProvider | None = None):
        settings = get_settings()
        self._provider = provider or create_provider()
        self._settings = settings

        self._init_core_services(settings)
        self._init_memory(settings)
        self._init_self_improve(settings)
        self._init_autonomy(settings)
        self._init_governance(settings)

    # ── Subsystem Factories ──────────────────────────────────────────

    def _init_core_services(self, settings) -> None:
        """Core pipeline services: search, PDF, embedding, store, agents."""
        self._search = SearchService()
        self._pdf = PDFService(mode=settings.s1_parser_mode, s1_parser_url=settings.s1_parser_url)
        self._embedding = EmbeddingService(self._provider)
        self._store = VectorStore(settings.chroma_persist_dir, self._embedding)
        self._gap_analyzer = GapAnalyzer(self._provider)
        self._agent = AgentOrchestrator(self._provider)
        self._novelty = NoveltyChecker(self._provider, self._store)
        self._feasibility = FeasibilityScorer(self._provider)
        self._synthesizer = ProposalSynthesizer(self._provider)
        self._export = ExportService()
        self._impasse_detector = ImpasseDetector()

    def _init_memory(self, settings) -> None:
        """Persistent agent memory (Gap 1)."""
        self._memory: MemoryService | None = None
        if settings.memory_enabled:
            self._memory = MemoryService(settings.memory_persist_dir)

    def _init_self_improve(self, settings) -> None:
        """Self-improvement subsystem (Gap 2)."""
        self._evolver: PipelineEvolver | None = None
        self._lesson_extractor: LessonExtractor | None = None
        if settings.self_improve_enabled:
            frontier = ParetoFrontier(f"{settings.self_improve_persist_dir}/frontier.json")
            self._evolver = PipelineEvolver(frontier)
            self._lesson_extractor = LessonExtractor(self._provider)

    def _init_autonomy(self, settings) -> None:
        """Autonomy subsystem: state machine, budget, hooks, curiosity."""
        # Budget tracking (Gap 13)
        self._budget = None
        self._plan_verifier = None
        if settings.budget_enabled:
            from backend.pipeline.autonomy.budget import PlanVerifier, SimpleBudget
            self._budget = SimpleBudget(
                max_tokens=settings.budget_max_tokens,
                max_cost_usd=settings.budget_max_cost_usd,
                max_seconds=settings.budget_max_seconds,
            )
            self._plan_verifier = PlanVerifier()

        # Hook dispatch (Gap 13)
        from backend.pipeline.autonomy.hooks import HookDispatcher
        self._hooks = HookDispatcher()

        # Autonomous state machine + curiosity (Gap 11)
        self._state_machine = None
        self._curiosity = None
        if settings.autonomy_enabled:
            from backend.pipeline.autonomy.state_machine import ConsciousnessStateMachine
            from backend.pipeline.autonomy.curiosity import CuriosityDriver
            self._state_machine = ConsciousnessStateMachine(
                idle_timeout_seconds=settings.autonomy_idle_timeout_seconds,
            )
            self._curiosity = CuriosityDriver(self._provider)

    def _init_governance(self, settings) -> None:
        """Governance, world model, and goal management."""
        # Governance validation (Gap 15)
        self._governance_validator = None
        self._governance_audit = None
        if settings.governance_enabled:
            from backend.pipeline.governance.validator import OutputValidator
            from backend.pipeline.governance.events import GovernanceAuditLog
            self._governance_validator = OutputValidator(self._provider)
            self._governance_audit = GovernanceAuditLog(settings.governance_audit_path)

        # World model (Gap 8)
        from backend.pipeline.knowledge.world_model import WorldModel
        self._world_model = WorldModel(settings.world_model_path)

        # Goal manager (Gap 10)
        from backend.pipeline.autonomy.goals import GoalManager
        self._goal_manager = GoalManager(settings.goals_path)

    # ── Main Pipeline ────────────────────────────────────────────────

    async def run(
        self,
        domain: str = "AI/NLP",
        search_queries: list[str] | None = None,
        max_gaps: int = 5,
        generation_rounds: int | None = None,
        ideas_per_round: int | None = None,
        run_novelty: bool = True,
        run_feasibility: bool = True,
        run_synthesis: bool = True,
        export_format: str | None = "markdown",
    ) -> PipelineResult:
        """Execute the full pipeline from literature search to export."""
        result = PipelineResult()
        rounds = generation_rounds or self._settings.generation_rounds
        ideas_per = ideas_per_round or self._settings.ideas_per_round

        # Generate run ID
        run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        result.run_id = run_id

        # Self-improvement: propose evolved parameters
        params = {
            "generation_rounds": rounds,
            "ideas_per_round": ideas_per,
            "max_gaps": max_gaps,
        }
        if self._evolver:
            evolved = self._evolver.propose()
            if generation_rounds is None and "generation_rounds" in evolved:
                rounds = int(evolved["generation_rounds"])
            if ideas_per_round is None and "ideas_per_round" in evolved:
                ideas_per = int(evolved["ideas_per_round"])
            params.update(evolved)

        result.params_used = params

        # Budget: validate plan and start tracking
        if self._budget and self._plan_verifier:
            ok, msg = self._plan_verifier.validate(params, self._budget)
            if not ok:
                logger.warning("Budget validation failed: %s. Aborting.", msg)
                return result
            self._budget.start()

        # Hook: pipeline.start
        await self._hooks.dispatch_sync_safe("pipeline.start", {
            "run_id": run_id, "domain": domain, "params": params,
        })

        # ── Stage 1: Literature Discovery ──
        logger.info("=== Stage 1: Literature Discovery ===")
        t0 = time.time()
        queries = search_queries or [f"{domain} recent advances", f"{domain} open problems"]
        all_papers: list[Paper] = []
        for query in queries:
            papers = await self._search.search_all(query, limit_per_source=20)
            all_papers.extend(papers)
            logger.info("Found %d papers for query: %s", len(papers), query)

        result.papers_found = len(all_papers)
        logger.info("Total unique papers: %d", len(all_papers))
        self._record_stage("literature_search", t0)

        if not all_papers:
            logger.warning("No papers found. Pipeline cannot continue.")
            await self._hooks.dispatch_sync_safe("pipeline.complete", {
                "run_id": run_id, "status": "no_papers",
            })
            return result

        if self._should_stop():
            return result

        # ── Stage 2: Knowledge Base Ingestion ──
        logger.info("=== Stage 2: Knowledge Base Ingestion ===")
        t0 = time.time()
        chunks = []
        for paper in all_papers:
            text = f"{paper.title}\n\n{paper.abstract or ''}"
            paper_chunks = [
                DocumentChunk(
                    text=text,
                    paper_id=paper.id,
                    section="abstract",
                    chunk_index=0,
                )
            ]
            chunks.append(paper_chunks)

        added = await self._store.add_papers(all_papers, chunks)
        logger.info("Added %d chunks to knowledge base", added)
        self._record_stage("ingestion", t0)

        if self._should_stop():
            return result

        # ── Stage 3: Gap Analysis ──
        logger.info("=== Stage 3: Gap Analysis ===")
        t0 = time.time()
        prior_gaps = await self._recall_prior_gaps(domain)
        gaps, cluster_report = await self._gap_analyzer.analyze(
            all_papers, domain=domain, max_gaps=max_gaps, prior_gaps=prior_gaps,
        )
        result.gaps = gaps
        result.cluster_report = cluster_report
        logger.info("Identified %d research gaps", len(gaps))
        self._record_stage("gap_analysis", t0)

        # Goal manager: create goals from gaps
        if self._goal_manager and gaps:
            new_goals = self._goal_manager.create_from_gaps(gaps)
            logger.info("Created %d research goals from gaps", len(new_goals))

        # Hook: gap.found
        for gap in gaps:
            await self._hooks.dispatch_sync_safe("gap.found", {
                "title": gap.title, "confidence": gap.confidence,
                "gap_type": gap.gap_type,
            })

        if self._should_stop():
            return result

        # ── Stage 4: Multi-Agent Idea Generation ──
        logger.info("=== Stage 4: Idea Generation (%d rounds, %d ideas/round) ===", rounds, ideas_per)
        t0 = time.time()
        ideas = await self._agent.run(
            gaps=gaps,
            context_papers=all_papers[:30],
            rounds=rounds,
            ideas_per_round=ideas_per,
        )
        result.ideas = ideas
        logger.info("Generated %d research ideas", len(ideas))
        self._record_stage("idea_generation", t0)

        # Hook: idea.generated
        for idea in ideas:
            await self._hooks.dispatch_sync_safe("idea.generated", {
                "title": idea.title, "score": idea.score,
            })

        if self._should_stop():
            return result

        # ── Stage 5: Novelty Checking ──
        if run_novelty and ideas:
            logger.info("=== Stage 5: Novelty Checking ===")
            t0 = time.time()
            for idea in ideas:
                report = await self._novelty.check_novelty(idea)
                result.novelty_reports[id(idea)] = report
                logger.info("Novelty score for '%s': %.2f", idea.title[:50], report.overall_score)
            self._record_stage("novelty_checking", t0)

            # Hook: idea.scored
            for idea in ideas:
                nr = result.novelty_reports.get(id(idea))
                if nr:
                    await self._hooks.dispatch_sync_safe("idea.scored", {
                        "title": idea.title, "novelty_score": nr.overall_score,
                    })

        if self._should_stop():
            return result

        # ── Stage 6: Feasibility Scoring ──
        if run_feasibility and ideas:
            logger.info("=== Stage 6: Feasibility Scoring ===")
            t0 = time.time()
            for idea in ideas:
                novelty = result.novelty_reports.get(id(idea))
                report = await self._feasibility.score_feasibility(idea, novelty)
                result.feasibility_reports[id(idea)] = report
                logger.info("Feasibility score for '%s': %.1f/10", idea.title[:50], report.overall_score)
            self._record_stage("feasibility_scoring", t0)

        if self._should_stop():
            return result

        # ── Stage 7: Proposal Synthesis ──
        if run_synthesis and ideas:
            logger.info("=== Stage 7: Proposal Synthesis ===")
            t0 = time.time()
            for i, idea in enumerate(ideas):
                novelty = result.novelty_reports.get(id(idea))
                feasibility = result.feasibility_reports.get(id(idea))
                proposal = await self._synthesizer.synthesize(
                    idea=idea,
                    novelty_report=novelty,
                    feasibility_report=feasibility,
                    supporting_papers=all_papers[:10],
                )

                # Governance validation with reask loop
                if self._governance_validator:
                    validated_text, checks = await self._governance_validator.validate_with_reask(
                        proposal.text, output_type="proposal",
                    )
                    proposal.text = validated_text

                    # Record governance audit event
                    if self._governance_audit:
                        from backend.pipeline.governance.events import GovernanceAuditLog, GovernanceEvent
                        verdict = "accepted" if all(
                            c.verdict.value != "rejected" for c in checks
                        ) else "revised"
                        self._governance_audit.record(GovernanceEvent(
                            event_type=f"output.{verdict}",
                            stage="proposal_synthesis",
                            content_hash=GovernanceAuditLog.content_hash(proposal.text),
                            checks_summary=f"{len(checks)} checks, verdict={verdict}",
                        ))

                result.proposals[i] = proposal
                logger.info("Generated proposal for idea %d: %s", i + 1, idea.title[:50])
            self._record_stage("proposal_synthesis", t0)

        # ── Stage 8: Export ──
        if export_format and result.proposals:
            logger.info("=== Stage 8: Export ===")
            t0 = time.time()
            for i, proposal in result.proposals.items():
                path = await self._export.export(proposal, format=export_format)
                result.export_paths[i] = path
                logger.info("Exported proposal to: %s", path)
            self._record_stage("export", t0)

        # ── Post-pipeline: Self-improvement evaluation ──
        if self._evolver and result.ideas:
            avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
            avg_novelty = (
                sum(r.overall_score for r in result.novelty_reports.values()) / len(result.novelty_reports)
                if result.novelty_reports
                else 0.0
            )
            self._evolver.evaluate(
                params=params,
                run_id=run_id,
                avg_idea_score=avg_score,
                avg_novelty_score=avg_novelty,
                good_ideas=sum(1 for i in result.ideas if i.score >= 0.6),
            )

        # ── Post-pipeline: Lesson extraction for underperforming runs ──
        if self._lesson_extractor and result.ideas:
            avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
            if avg_score < 0.7:
                lessons = await self._lesson_extractor.extract(result, params)
                if lessons:
                    logger.info("Extracted %d lessons from run", len(lessons))

        # ── Post-pipeline: World model update ──
        if self._world_model and result.ideas:
            await self._world_model.update_from_run(result, self._provider)
            logger.info("World model updated")

        # ── Post-pipeline: Fire-and-forget memory extraction ──
        if self._memory:
            asyncio.create_task(
                self._background_memory_extraction(result, run_id)
            )

        # Hook: pipeline.complete
        await self._hooks.dispatch_sync_safe("pipeline.complete", {
            "run_id": run_id,
            "ideas_count": len(result.ideas),
            "gaps_count": len(result.gaps),
            "proposals_count": len(result.proposals),
        })

        logger.info("=== Pipeline Complete ===")
        return result

    # ── Autonomous Cycle ─────────────────────────────────────────────

    async def autonomous_cycle(
        self,
        domain: str = "AI/NLP",
        max_autonomous_runs: int | None = None,
    ) -> list[PipelineResult]:
        """Run autonomous research cycles using the consciousness state machine.

        Cycles through: IDLE → EXPLORING → FOCUSED → CONTEMPLATING → DREAMING → IDLE
        until max_autonomous_runs is reached.
        """
        if not self._state_machine:
            logger.warning("Autonomy not enabled. Set EROCK_AUTONOMY_ENABLED=true.")
            return []

        max_runs = max_autonomous_runs or self._settings.autonomy_max_autonomous_runs
        results: list[PipelineResult] = []

        for run_idx in range(max_runs):
            state = self._state_machine.current_state
            logger.info("Autonomous cycle %d/%d — state: %s", run_idx + 1, max_runs, state.value)

            if state.value == "idle":
                if self._state_machine.should_explore():
                    self._state_machine.transition("idle_timeout")
                    continue
                else:
                    logger.info("Idle — waiting for trigger. Ending autonomous cycle.")
                    break

            if state.value == "exploring":
                # Curiosity-driven search for new topics
                search_queries = None
                if self._curiosity:
                    suggestion = await self._curiosity.suggest_exploration_topic()
                    if suggestion:
                        search_queries = suggestion.get("search_queries")
                        self._curiosity.record_explored_topic(suggestion.get("topic", domain))
                        logger.info("Curiosity suggests: %s", suggestion.get("topic"))

                # Run pipeline with curiosity-driven queries
                result = await self.run(
                    domain=domain,
                    search_queries=search_queries,
                )
                results.append(result)

                # Transition based on results
                if result.gaps:
                    self._state_machine.transition("new_high_confidence_gap")
                else:
                    self._state_machine.transition("no_gaps_found")
                continue

            if state.value == "focused":
                # Run full pipeline on identified gaps
                result = await self.run(domain=domain)
                results.append(result)
                self._state_machine.transition("generation_complete")
                continue

            if state.value == "contemplating":
                # Analyze results — already done in post-pipeline hooks
                self._state_machine.transition("analysis_complete")
                continue

            if state.value == "dreaming":
                # Consolidate memory and update world model
                if self._memory:
                    await self._memory.consolidate()
                    await self._memory.apply_decay(self._settings.memory_decay_rate)
                    logger.info("Dreaming: memory consolidated and decayed")

                self._state_machine.transition("consolidation_complete")
                continue

        logger.info("Autonomous cycle complete. %d runs executed.", len(results))
        return results

    # ── Helpers ──────────────────────────────────────────────────────

    def _record_stage(self, stage_name: str, start_time: float) -> None:
        """Record stage timing for budget tracking."""
        elapsed = time.time() - start_time
        if self._budget:
            self._budget.record(stage_name, tokens=0, elapsed=elapsed)

    def _should_stop(self) -> bool:
        """Check budget policy — return True if pipeline should halt."""
        if not self._budget:
            return False
        from backend.pipeline.autonomy.budget import BudgetPolicy
        policy = self._budget.check_policy()
        if policy == BudgetPolicy.STOP:
            logger.warning("Budget STOP triggered. Halting pipeline.")
            return True
        if policy == BudgetPolicy.REPLAN:
            logger.warning("Budget REPLAN — 80%% budget used. Continuing with caution.")
        return False

    async def _background_memory_extraction(self, result: PipelineResult, run_id: str) -> None:
        """GAIA-style fire-and-forget memory extraction."""
        try:
            stored = await extract_from_pipeline_result(
                result, self._provider, self._memory, run_id=run_id,
            )
            logger.info("Background memory extraction: stored %d memories", stored)
        except Exception as e:
            logger.error("Background memory extraction failed: %s", e)

    async def _recall_prior_gaps(self, domain: str) -> list[ResearchGap] | None:
        """Recall prior gaps from memory for truth revision."""
        if not self._memory:
            return None
        from backend.pipeline.memory.models import MemoryQuery, MemoryType
        results = await self._memory.recall(MemoryQuery(
            query=f"{domain} research gaps",
            memory_type=MemoryType.SEMANTIC,
            namespace="research_facts",
            top_k=20,
        ))
        return None
