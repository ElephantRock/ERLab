"""Pipeline stages — composable units following the ActivationPipeline pattern."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.pipeline.ingestion.chunker import DocumentChunk  # noqa: F401 — re-exported by stages

if TYPE_CHECKING:
    from backend.pipeline.result import PipelineResult

logger = logging.getLogger(__name__)


@dataclass
class StageContext:
    """Shared mutable state passed between stages."""

    result: PipelineResult
    all_papers: list = field(default_factory=list)
    db_run_id: int | None = None
    params: dict = field(default_factory=dict)
    domain: str = "AI/NLP"
    run_id: str = ""
    search_queries: list[str] | None = None
    max_gaps: int = 5
    rounds: int = 2
    ideas_per: int = 3
    export_format: str | None = "markdown"
    provider_override: Any = None  # LLMProvider override for model routing


class PipelineStage(ABC):
    """Base class for pipeline stages."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def execute(self, ctx: StageContext) -> bool:
        """Execute the stage. Return False to halt the pipeline."""
        ...


class LiteratureSearchStage(PipelineStage):
    def __init__(self, search, hooks):
        self._search = search
        self._hooks = hooks

    @property
    def name(self) -> str:
        return "literature_search"

    async def execute(self, ctx: StageContext) -> bool:
        queries = ctx.search_queries or [
            f"{ctx.domain} recent advances",
            f"{ctx.domain} open problems",
        ]
        all_papers = []
        for query in queries:
            papers = await self._search.search_all(query, limit_per_source=20)
            all_papers.extend(papers)
            logger.info("Found %d papers for query: %s", len(papers), query)

        ctx.all_papers = all_papers
        ctx.result.papers_found = len(all_papers)
        logger.info("Total unique papers: %d", len(all_papers))

        if not all_papers:
            logger.warning("No papers found. Pipeline cannot continue.")
            return False
        return True


class IngestionStage(PipelineStage):
    def __init__(self, store, bm25, embedding, kg=None):
        self._store = store
        self._bm25 = bm25
        self._embedding = embedding
        self._kg = kg

    @property
    def name(self) -> str:
        return "ingestion"

    async def execute(self, ctx: StageContext) -> bool:
        chunks = []
        for paper in ctx.all_papers:
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

        added = await self._store.add_papers(ctx.all_papers, chunks)
        logger.info("Added %d chunks to knowledge base", added)

        all_ids, all_texts, all_metas = [], [], []
        for paper, paper_chunks in zip(ctx.all_papers, chunks, strict=True):
            for j, chunk in enumerate(paper_chunks):
                all_ids.append(f"{paper.id}_chunk_{j}")
                all_texts.append(chunk.text)
                all_metas.append(
                    {
                        "paper_id": paper.id,
                        "paper_title": paper.title[:500],
                        "source": paper.source,
                    }
                )
        if all_ids:
            self._bm25.add_documents(all_ids, all_texts, all_metas)
            logger.info("Synced %d documents to BM25 index", len(all_ids))

        # Write to Knowledge Graph
        if self._kg:
            from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
            from backend.pipeline.knowledge.truth import TruthValue

            for paper in ctx.all_papers:
                entity = KnowledgeEntity(
                    id=f"paper:{paper.id}",
                    entity_type=EntityType.PAPER,
                    name=paper.title,
                    properties={
                        "source": paper.source,
                        "year": paper.year,
                        "citation_count": paper.citation_count,
                    },
                    truth=TruthValue.from_observation(frequency=0.9),
                )
                self._kg.add_entity(entity)
            self._kg.save()
            logger.info("Added %d paper entities to Knowledge Graph", len(ctx.all_papers))

        return True


class GapAnalysisStage(PipelineStage):
    def __init__(self, gap_analyzer, goal_manager, hooks, memory, kg=None):
        self._gap_analyzer = gap_analyzer
        self._goal_manager = goal_manager
        self._hooks = hooks
        self._memory = memory
        self._kg = kg

    @property
    def name(self) -> str:
        return "gap_analysis"

    async def execute(self, ctx: StageContext) -> bool:
        prior_gaps = await self._recall_prior_gaps(ctx.domain)
        gaps, cluster_report = await self._gap_analyzer.analyze(
            ctx.all_papers,
            domain=ctx.domain,
            max_gaps=ctx.max_gaps,
            prior_gaps=prior_gaps,
        )
        ctx.result.gaps = gaps
        ctx.result.cluster_report = cluster_report
        logger.info("Identified %d research gaps", len(gaps))

        # Write gaps to Knowledge Graph
        if self._kg:
            from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
            from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
            from backend.pipeline.knowledge.truth import TruthValue

            for gap in gaps:
                gap_entity = KnowledgeEntity(
                    id=f"gap:{gap.title[:60]}",
                    entity_type=EntityType.CONCEPT,
                    name=gap.title,
                    properties={
                        "gap_type": gap.gap_type,
                        "description": gap.description[:200],
                        "potential_impact": gap.potential_impact,
                    },
                    truth=TruthValue(frequency=gap.confidence, confidence=0.6),
                )
                self._kg.add_entity(gap_entity)
            self._kg.save()
            logger.info("Added %d gap entities to Knowledge Graph", len(gaps))

        if self._goal_manager and gaps:
            new_goals = self._goal_manager.create_from_gaps(gaps)
            logger.info("Created %d research goals from gaps", len(new_goals))

        for gap in gaps:
            await self._hooks.dispatch_sync_safe(
                "gap.found",
                {
                    "title": gap.title,
                    "confidence": gap.confidence,
                    "gap_type": gap.gap_type,
                },
            )
        return True

    async def _recall_prior_gaps(self, domain):
        if not self._memory:
            return None
        from backend.pipeline.memory.models import MemoryQuery, MemoryType

        results = await self._memory.recall(
            MemoryQuery(
                query=f"{domain} research gaps",
                memory_type=MemoryType.SEMANTIC,
                namespace="research_facts",
                top_k=20,
            )
        )
        return results if results else None


class IdeaGenerationStage(PipelineStage):
    def __init__(self, agent, hooks, dag_executor=None, dag_agents=None, provider=None, kg=None):
        self._agent = agent
        self._hooks = hooks
        self._dag_executor = dag_executor
        self._dag_agents = dag_agents
        self._provider = provider
        self._kg = kg

    @property
    def name(self) -> str:
        return "idea_generation"

    async def execute(self, ctx: StageContext) -> bool:
        if self._dag_executor is not None:
            return await self._execute_dag(ctx)
        return await self._execute_sequential(ctx)

    async def _execute_sequential(self, ctx: StageContext) -> bool:
        logger.info("Idea Generation (%d rounds, %d ideas/round)", ctx.rounds, ctx.ideas_per)
        ideas = await self._agent.run(
            gaps=ctx.result.gaps,
            context_papers=ctx.all_papers[:30],
            rounds=ctx.rounds,
            ideas_per_round=ctx.ideas_per,
        )
        ctx.result.ideas = ideas
        ctx.result.critique_history = self._agent.last_critique_history
        ctx.result.refinement_history = self._agent.last_refinement_history
        logger.info("Generated %d research ideas", len(ideas))

        # Write ideas to Knowledge Graph
        if self._kg and ideas:
            from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
            from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
            from backend.pipeline.knowledge.truth import TruthValue

            for idea in ideas:
                idea_entity = KnowledgeEntity(
                    id=f"idea:{idea.title[:60]}",
                    entity_type=EntityType.CONCEPT,
                    name=idea.title,
                    properties={
                        "proposed_method": idea.proposed_method[:200],
                        "domain": idea.domain,
                    },
                    truth=TruthValue(frequency=idea.score, confidence=0.5),
                )
                self._kg.add_entity(idea_entity)

                for gap_id in idea.source_gap_ids:
                    gap_eid = f"gap:{gap_id[:60]}"
                    if gap_eid in self._kg._entities:
                        self._kg.add_relationship(KnowledgeRelationship(
                            source_id=gap_eid,
                            target_id=f"idea:{idea.title[:60]}",
                            relation_type=RelationType.PROPOSES_METHOD,
                            truth=TruthValue.from_observation(frequency=idea.score),
                        ))

            self._kg.save()
            logger.info("Added %d idea entities to Knowledge Graph", len(ideas))

        for idea in ideas:
            await self._hooks.dispatch_sync_safe(
                "idea.generated",
                {
                    "title": idea.title,
                    "score": idea.score,
                },
            )
        return True

    async def _execute_dag(self, ctx: StageContext) -> bool:
        """Execute idea generation via the DAG executor."""
        from backend.pipeline.generation.agent_handlers import register_all_agents
        from backend.pipeline.generation.context_isolator import ContextIsolator
        from backend.pipeline.generation.models import ResearchIdea

        logger.info("Idea Generation via DAG (%d gaps)", len(ctx.result.gaps))

        isolator = ContextIsolator(ctx.result.gaps, ctx.all_papers[:30])

        # Register handlers for this run
        cleanup = register_all_agents(
            registry=self._dag_executor._registry,
            agents=self._dag_agents,
            isolator=isolator,
            provider=self._provider,
        )

        # Prepare input: one item per gap
        dag_input = [
            {"gap": gap, "papers": ctx.all_papers[:30], "n_ideas": ctx.ideas_per}
            for gap in ctx.result.gaps
        ]

        try:
            results = await self._dag_executor.execute(dag_input)
        finally:
            # Restore buffered taxonomies
            for _, buffered, restore in cleanup:
                restore()

        # Extract ResearchIdea objects from results
        ideas = [i for i in results if isinstance(i, ResearchIdea)]
        if not ideas:
            # Try extracting from dicts
            for r in results:
                if isinstance(r, dict) and "ideas" in r:
                    ideas.extend(r["ideas"])

        ctx.result.ideas = ideas
        logger.info("DAG generated %d research ideas", len(ideas))

        for idea in ideas:
            await self._hooks.dispatch_sync_safe(
                "idea.generated",
                {"title": idea.title, "score": idea.score},
            )
        return True


class NoveltyCheckingStage(PipelineStage):
    def __init__(self, novelty_checker, hooks=None):
        self._novelty = novelty_checker
        self._hooks = hooks

    @property
    def name(self) -> str:
        return "novelty_checking"

    async def execute(self, ctx: StageContext) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True
        for i, idea in enumerate(ideas):
            report = await self._novelty.check_novelty(idea)
            ctx.result.novelty_reports[i] = report
            logger.info("Novelty score for '%s': %.2f", idea.title[:50], report.overall_score)

        if self._hooks:
            for i, idea in enumerate(ideas):
                nr = ctx.result.novelty_reports.get(i)
                if nr:
                    await self._hooks.dispatch_sync_safe(
                        "idea.scored",
                        {
                            "title": idea.title,
                            "novelty_score": nr.overall_score,
                        },
                    )
        return True


class FeasibilityScoringStage(PipelineStage):
    def __init__(self, feasibility_scorer):
        self._feasibility = feasibility_scorer

    @property
    def name(self) -> str:
        return "feasibility_scoring"

    async def execute(self, ctx: StageContext) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True
        for i, idea in enumerate(ideas):
            novelty = ctx.result.novelty_reports.get(i)
            report = await self._feasibility.score_feasibility(idea, novelty)
            ctx.result.feasibility_reports[i] = report
            logger.info(
                "Feasibility score for '%s': %.1f/10", idea.title[:50], report.overall_score
            )
        return True


class ProposalSynthesisStage(PipelineStage):
    def __init__(
        self, synthesizer, governance_validator=None, governance_audit=None, ref_validator=None
    ):
        self._synthesizer = synthesizer
        self._governance_validator = governance_validator
        self._governance_audit = governance_audit
        self._ref_validator = ref_validator

    @property
    def name(self) -> str:
        return "proposal_synthesis"

    async def execute(self, ctx: StageContext) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True
        for i, idea in enumerate(ideas):
            novelty = ctx.result.novelty_reports.get(i)
            feasibility = ctx.result.feasibility_reports.get(i)
            proposal = await self._synthesizer.synthesize(
                idea=idea,
                novelty_report=novelty,
                feasibility_report=feasibility,
                supporting_papers=ctx.all_papers[:10],
                gaps=ctx.result.gaps,
            )

            if self._governance_validator:
                proposal_md = proposal.to_markdown()
                validated_text, checks = await self._governance_validator.validate_with_reask(
                    proposal_md,
                    output_type="proposal",
                )
                proposal.sections["validated_text"] = validated_text

                if self._governance_audit:
                    from backend.pipeline.governance.events import (
                        GovernanceAuditLog,
                        GovernanceEvent,
                    )

                    verdict = (
                        "accepted"
                        if all(c.verdict.value != "rejected" for c in checks)
                        else "revised"
                    )
                    self._governance_audit.record(
                        GovernanceEvent(
                            event_type=f"output.{verdict}",
                            stage="proposal_synthesis",
                            content_hash=GovernanceAuditLog.content_hash(proposal_md),
                            checks_summary=f"{len(checks)} checks, verdict={verdict}",
                        )
                    )

            ctx.result.proposals[i] = proposal
            logger.info("Generated proposal for idea %d: %s", i + 1, idea.title[:50])

            # Reference validation
            if self._ref_validator:
                refs = proposal.sections.get("references", [])
                if isinstance(refs, list) and refs:
                    validation_results = await self._ref_validator.validate(refs)
                    proposal.sections["reference_validation"] = [
                        {"index": v.reference_index, "title": v.title, "status": v.status}
                        for v in validation_results
                    ]
                    unverified = sum(1 for v in validation_results if v.status == "unverified")
                    if unverified:
                        logger.info(
                            "Proposal %d: %d/%d references unverified",
                            i + 1,
                            unverified,
                            len(refs),
                        )
        return True


class ExportStage(PipelineStage):
    def __init__(self, export_service):
        self._export = export_service

    @property
    def name(self) -> str:
        return "export"

    async def execute(self, ctx: StageContext) -> bool:
        if ctx.export_format and ctx.result.proposals:
            for i, proposal in ctx.result.proposals.items():
                path = await self._export.export(proposal, format=ctx.export_format)
                ctx.result.export_paths[i] = path
                logger.info("Exported proposal to: %s", path)
        return True
