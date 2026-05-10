"""Pipeline stages — composable units following the ActivationPipeline pattern."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generator

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.ingestion.chunker import DocumentChunk  # noqa: F401 — re-exported by stages
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal  # noqa: F401 — used by ProposalSynthesisStage

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider
    from backend.pipeline.result import PipelineResult

logger = logging.getLogger(__name__)


@contextmanager
def _override_provider(
    service: object, override: LLMProvider | None
) -> Generator[None, None, None]:
    """Temporarily swap a service's _provider with the override."""
    if not override or not hasattr(service, "_provider"):
        yield
        return
    saved = service._provider  # type: ignore[attr-defined]
    try:
        service._provider = override  # type: ignore[attr-defined]
        yield
    finally:
        service._provider = saved  # type: ignore[attr-defined]


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
        # Parallel query fan-out — all queries fire concurrently
        query_results = await asyncio.gather(
            *(self._search.search_all(q, limit_per_source=20) for q in queries),
            return_exceptions=True,
        )
        all_papers = []
        for query, result in zip(queries, query_results, strict=True):
            if isinstance(result, Exception):
                logger.warning("Query '%s' failed: %s", query[:50], result)
            else:
                all_papers.extend(result)
                logger.info("Found %d papers for query: %s", len(result), query)

        # Deduplicate papers — cross-source duplicates have different IDs
        seen = set()
        unique = []
        for p in all_papers:
            # Use DOI if available, otherwise normalized title
            key = p.doi if getattr(p, 'doi', None) else p.title.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(p)

        # G6: Fuzzy dedup for near-duplicate titles
        from difflib import SequenceMatcher
        fuzzy_unique = []
        for paper in unique:
            is_dup = any(
                SequenceMatcher(
                    None,
                    paper.title.lower().strip(),
                    existing.title.lower().strip(),
                ).ratio() > 0.85
                for existing in fuzzy_unique
            )
            if not is_dup:
                fuzzy_unique.append(paper)
        if len(fuzzy_unique) < len(unique):
            logger.info(
                "Fuzzy dedup removed %d near-duplicates (%d → %d)",
                len(unique) - len(fuzzy_unique), len(unique), len(fuzzy_unique),
            )
        unique = fuzzy_unique

        ctx.all_papers = unique
        ctx.result.papers_found = len(unique)
        logger.info("Total unique papers: %d (from %d total)", len(unique), len(all_papers))

        if not all_papers:
            logger.warning("No papers found. Proceeding with domain knowledge only.")
            # Don't halt — gap analysis can work from domain alone
            return True
        return True


class IngestionStage(PipelineStage):
    def __init__(self, store, bm25, embedding, kg=None, provider=None):
        self._store = store
        self._bm25 = bm25
        self._embedding = embedding
        self._kg = kg
        self._provider = provider

    @property
    def name(self) -> str:
        return "ingestion"

    async def execute(self, ctx: StageContext) -> bool:
        # Deduplicate papers by ID — same paper can appear across multiple queries
        seen_ids = set()
        unique_papers = []
        for paper in ctx.all_papers:
            if paper.id not in seen_ids:
                seen_ids.add(paper.id)
                unique_papers.append(paper)
        ctx.all_papers = unique_papers
        logger.info("Ingestion: %d unique papers (from %d total)", len(unique_papers), len(ctx.all_papers))

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

            # Extract relationships between papers (Fix #4)
            try:
                from backend.pipeline.knowledge.relationship_extractor import extract_relationships
                rels = await extract_relationships(ctx.all_papers, ctx.provider_override or self._provider)
                for rel in rels:
                    self._kg.add_relationship(rel)
                if rels:
                    self._kg.save()
                    logger.info("Added %d paper relationships to Knowledge Graph", len(rels))
            except Exception as e:
                logger.warning("Relationship extraction failed (non-fatal): %s", e)

        return True


class GapAnalysisStage(PipelineStage):
    def __init__(self, gap_analyzer, goal_manager, hooks, memory, kg=None, faithfulness_checker=None):
        self._gap_analyzer = gap_analyzer
        self._goal_manager = goal_manager
        self._hooks = hooks
        self._memory = memory
        self._kg = kg
        self._faithfulness_checker = faithfulness_checker

    @property
    def name(self) -> str:
        return "gap_analysis"

    async def execute(self, ctx: StageContext) -> bool:
        with _override_provider(self._gap_analyzer, ctx.provider_override):
            return await self._execute_gap_analysis(ctx)

    async def _execute_gap_analysis(self, ctx: StageContext) -> bool:
        # Brief pause to let API rate limiter cool after ingestion burst
        # Reduced from 15s to 2s since gap analysis now uses local LM Studio
        await asyncio.sleep(2.0)

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

            # G3: Revise gap truth based on paper overlap
            if ctx.all_papers:
                for gap in gaps:
                    gap_eid = f"gap:{gap.title[:60]}"
                    # Count papers whose title/abstract overlap with gap description
                    overlap_count = 0
                    gap_words = set(gap.description.lower().split()[:20])
                    for paper in ctx.all_papers:
                        paper_text = f"{paper.title} {paper.abstract or ''}".lower()
                        if sum(1 for w in gap_words if w in paper_text) >= 3:
                            overlap_count += 1
                    if overlap_count > 0:
                        entity = self._kg._entities.get(gap_eid)
                        if entity and hasattr(entity, 'truth'):
                            from backend.pipeline.knowledge.truth import TruthValue
                            revised = entity.truth.revise(
                                TruthValue(
                                    frequency=min(0.95, 0.5 + overlap_count * 0.05),
                                    confidence=0.6,
                                    evidence_count=overlap_count,
                                )
                            )
                            entity.truth = revised
                            logger.debug(
                                "Revised gap truth for '%s': %d overlapping papers → confidence %.3f",
                                gap.title[:40], overlap_count, revised.confidence,
                            )
                self._kg.save()

        # Faithfulness check: verify gap claims against source papers
        if self._faithfulness_checker and gaps:
            try:
                reports = await self._faithfulness_checker.check_gap_claims(
                    gaps, ctx.all_papers,
                )
                unfaithful = [r for r in reports if not r.is_faithful]
                if unfaithful:
                    logger.warning(
                        "Faithfulness check: %d/%d gaps have unfaithful claims",
                        len(unfaithful), len(gaps),
                    )
                    for r in unfaithful:
                        logger.warning("  Unfaithful: %s — %s", r.claim[:60], r.explanation[:100])
            except Exception as e:
                logger.warning("Faithfulness check failed: %s", e)

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
    def __init__(self, agent, hooks, dag_executor=None, dag_agents=None, provider=None, kg=None, forest=None, reasoning_verifier=None):
        self._agent = agent
        self._hooks = hooks
        self._dag_executor = dag_executor
        self._dag_agents = dag_agents
        self._provider = provider
        self._kg = kg
        self._forest = forest
        self._reasoning_verifier = reasoning_verifier

    @property
    def name(self) -> str:
        return "idea_generation"

    async def execute(self, ctx: StageContext) -> bool:
        provider = ctx.provider_override or self._provider
        with _override_provider(self._agent, provider):
            if self._dag_executor is not None:
                return await self._execute_dag(ctx, provider)
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

                        # Fix #5: Revise gap truth upward when an idea addresses it
                        gap_entity = self._kg._entities[gap_eid]
                        if hasattr(gap_entity, 'truth') and gap_entity.truth:
                            revised = gap_entity.truth.revise(
                                TruthValue.from_observation(frequency=0.8)
                            )
                            gap_entity.truth = revised
                            logger.debug(
                                "Revised gap truth for '%s': confidence %.3f → %.3f, evidence %d → %d",
                                gap_entity.name[:40],
                                gap_entity.truth.confidence if hasattr(gap_entity, '_prev_conf') else 0.5,
                                revised.confidence,
                                gap_entity.truth.evidence_count if hasattr(gap_entity, '_prev_ev') else 1,
                                revised.evidence_count,
                            )

            self._kg.save()
            logger.info("Added %d idea entities to Knowledge Graph", len(ideas))

        # Reasoning verification on top ideas
        if self._reasoning_verifier and ideas and ctx.result.gaps:
            try:
                for idea in ideas[:5]:
                    gap = ctx.result.gaps[0] if ctx.result.gaps else None
                    if gap:
                        result = await self._reasoning_verifier.verify_idea_reasoning(idea, gap)
                        if not result.passed:
                            logger.warning(
                                "Idea '%s' failed reasoning verification: %s",
                                idea.title[:60], "; ".join(result.issues[:3]),
                            )
            except Exception as e:
                logger.warning("Reasoning verification failed: %s", e)

        for idea in ideas:
            await self._hooks.dispatch_sync_safe(
                "idea.generated",
                {
                    "title": idea.title,
                    "score": idea.score,
                },
            )
        return True

    async def _execute_dag(self, ctx: StageContext, provider=None) -> bool:
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
            provider=provider or self._provider,
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
        with _override_provider(self._feasibility, ctx.provider_override):
            return await self._execute_feasibility(ctx)

    async def _execute_feasibility(self, ctx: StageContext) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True
        from backend.config import get_settings
        settings = get_settings()
        for i, idea in enumerate(ideas):
            novelty = ctx.result.novelty_reports.get(i)
            report = await self._feasibility.score_feasibility(idea, novelty)
            # Counterfactual analysis (Gap 14)
            if settings.counterfactual_enabled:
                report = await self._feasibility.run_counterfactual(report)
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
        with _override_provider(self._synthesizer, ctx.provider_override):
            return await self._execute_synthesis(ctx)

    async def _execute_synthesis(self, ctx: StageContext) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True

        # Per-proposal timeout from settings (capped at 300s by HB-01)
        from backend.config import get_settings

        timeout = min(
            getattr(get_settings(), "per_proposal_timeout", 120.0),
            300.0,
        )

        for i, idea in enumerate(ideas):
            novelty = ctx.result.novelty_reports.get(i)
            feasibility = ctx.result.feasibility_reports.get(i)
            try:
                proposal = await asyncio.wait_for(
                    self._synthesizer.synthesize(
                        idea=idea,
                        novelty_report=novelty,
                        feasibility_report=feasibility,
                        supporting_papers=ctx.all_papers[:30],
                        gaps=ctx.result.gaps,
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Proposal synthesis timed out after %.1fs for idea %d: %s",
                    timeout, i + 1, idea.title[:50],
                )
                proposal = ResearchProposal(
                    title=idea.title,
                    abstract=f"Synthesis timed out after {timeout:.0f}s",
                    introduction="Timed out",
                    proposed_method=idea.proposed_method,
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


class TreeSearchStage(PipelineStage):
    """Pipeline stage that uses TreeSearchEngine for beam-search idea generation.

    Replaces IdeaGenerationStage when tree_of_thought_enabled=True (HB-01).
    The stage name is "idea_generation" so it occupies the same slot in
    STAGE_ORDER — all downstream persistence/checkpoint logic works unchanged.
    """

    # HB-03: Maximum serialized tree_data size in bytes (500KB)
    MAX_TREE_DATA_BYTES = 500 * 1024

    def __init__(
        self,
        engine: "TreeSearchEngine",
        hooks,
        provider=None,
        kg=None,
    ) -> None:
        self._engine = engine
        self._hooks = hooks
        self._provider = provider
        self._kg = kg

    @property
    def name(self) -> str:
        return "idea_generation"

    async def execute(self, ctx: StageContext) -> bool:
        logger.info(
            "TreeSearchStage: beam search (depth=%d, beam_width=%d)",
            self._engine.config.max_depth,
            self._engine.config.beam_width,
        )

        # Run beam search
        raw_ideas = await self._engine.search(
            gaps=ctx.result.gaps,
            context_papers=ctx.all_papers[:30],
        )

        # BATCH-75/TASK-01: Convert IdeaCandidate → ResearchIdea (HB-01)
        ideas = self._convert_to_research_ideas(raw_ideas)
        assert all(isinstance(i, ResearchIdea) for i in ideas), (
            "HB-01 violation: TreeSearchStage must assign only ResearchIdea to ctx.result.ideas"
        )

        ctx.result.ideas = ideas
        logger.info("TreeSearchStage: generated %d ideas via tree search", len(ideas))

        # Serialize tree structure into tree_data for frontend (AC-01-03)
        tree_data = self._build_tree_data(ideas)
        ctx.result.tree_data = self._enforce_size_limit(tree_data)  # HB-03

        # Write ideas to Knowledge Graph (same as IdeaGenerationStage)
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
                    },
                    truth=TruthValue(frequency=getattr(idea, 'overall_score', 0.5), confidence=0.5),
                )
                self._kg.add_entity(idea_entity)

                for gap_id in getattr(idea, 'source_gap_ids', []):
                    gap_eid = f"gap:{gap_id[:60]}"
                    if gap_eid in self._kg._entities:
                        self._kg.add_relationship(KnowledgeRelationship(
                            source_id=gap_eid,
                            target_id=f"idea:{idea.title[:60]}",
                            relation_type=RelationType.PROPOSES_METHOD,
                            truth=TruthValue.from_observation(frequency=getattr(idea, 'overall_score', 0.5)),
                        ))

                        # Fix #5: Revise gap truth upward when an idea addresses it
                        gap_entity = self._kg._entities[gap_eid]
                        if hasattr(gap_entity, 'truth') and gap_entity.truth:
                            revised = gap_entity.truth.revise(
                                TruthValue.from_observation(frequency=0.8)
                            )
                            gap_entity.truth = revised

            self._kg.save()
            logger.info("Added %d idea entities to Knowledge Graph (tree search)", len(ideas))

        # Dispatch hooks
        for idea in ideas:
            await self._hooks.dispatch_sync_safe(
                "idea.generated",
                {
                    "title": idea.title,
                    "score": getattr(idea, 'score', getattr(idea, 'overall_score', 0.0)),
                },
            )
        return True

    # ── BATCH-75/TASK-01: IdeaCandidate → ResearchIdea conversion ──────

    @staticmethod
    def _convert_to_research_ideas(candidates: list) -> list[ResearchIdea]:
        """Convert IdeaCandidate objects to ResearchIdea with safe defaults.

        Handles field mapping for fields that IdeaCandidate lacks
        (domain, round_generated, supporting_papers, source_gap_ids).

        Conversion map:
            title                     → title
            problem_statement         → problem_statement
            proposed_method            → proposed_method
            expected_contributions    → expected_contributions (default "")
            novelty_rationale         → novelty_rationale (default "")
            evaluation_approach       → evaluation_approach (default "")
            overall_score             → score
            parent_idea_ids           → source_gap_ids (best-effort; default [])
            (no equivalent)           → domain = "AI/NLP"
            (no equivalent)           → round_generated = 1
            (no equivalent)           → supporting_papers = []
        """
        results: list[ResearchIdea] = []
        for c in candidates:
            research_idea = ResearchIdea(
                title=c.title,
                problem_statement=c.problem_statement,
                proposed_method=c.proposed_method,
                expected_contributions=getattr(c, "expected_contributions", "") or "",
                novelty_rationale=getattr(c, "novelty_rationale", "") or "",
                evaluation_approach=getattr(c, "evaluation_approach", "") or "",
                domain="AI/NLP",
                round_generated=1,
                score=getattr(c, "overall_score", 0.0),
                supporting_papers=[],
                source_gap_ids=getattr(c, "parent_idea_ids", []) or [],
            )
            results.append(research_idea)
        return results

    def _build_tree_data(self, ideas: list) -> dict:
        """Build a serializable tree structure from generated ideas.

        The tree is reconstructed from the ideas' parent_idea_ids lineage
        fields, producing a flat node list with parent references that the
        frontend can render as an SVG tree.
        """
        nodes: list[dict] = []
        for idea in ideas:
            # BATCH-75/TASK-01: getattr guards — ResearchIdea lacks .id
            # and .parent_idea_ids (CHK-16/CHK-17)
            idea_id = getattr(idea, 'id', idea.title[:60])
            parent_ids = getattr(
                idea, 'parent_idea_ids',
                getattr(idea, 'source_gap_ids', [])
            )
            nodes.append({
                "id": idea_id,
                "title": idea.title,
                "score": getattr(idea, 'overall_score', getattr(idea, 'score', 0.0)),
                "proposed_method": idea.proposed_method[:200],
                "parent_ids": parent_ids or [],
            })

        return {
            "engine": "tree_search",
            "config": {
                "beam_width": self._engine.config.beam_width,
                "max_depth": self._engine.config.max_depth,
                "ideas_per_node": self._engine.config.ideas_per_node,
            },
            "nodes": nodes,
        }

    @classmethod
    def _enforce_size_limit(cls, tree_data: dict) -> dict | None:
        """Enforce 500KB limit on tree_data (HB-03).

        If serialized JSON exceeds the limit, truncate nodes to fit.
        Returns None if even an empty tree would exceed the limit (shouldn't happen).
        """
        serialized = json.dumps(tree_data, default=str)
        if len(serialized.encode("utf-8")) <= cls.MAX_TREE_DATA_BYTES:
            return tree_data

        # Try progressive truncation of nodes list
        nodes = tree_data.get("nodes", [])
        if isinstance(nodes, list):
            for trim_size in [len(nodes) // 2, len(nodes) // 4, 0]:
                tree_data_copy = dict(tree_data)
                tree_data_copy["nodes"] = nodes[:trim_size]
                serialized = json.dumps(tree_data_copy, default=str)
                if len(serialized.encode("utf-8")) <= cls.MAX_TREE_DATA_BYTES:
                    logger.warning(
                        "TreeSearchStage: tree_data truncated to %d nodes (HB-03: 500KB limit)",
                        trim_size,
                    )
                    return tree_data_copy

        logger.error("TreeSearchStage: tree_data exceeds 500KB even when empty — returning None")
        return None


class MechanicalMetricsStage(PipelineStage):
    """Compute objective mechanical metrics for each idea (BATCH-64).

    Runs after feasibility scoring so that all prior data (ideas, papers,
    gaps, novelty/feasibility reports) is available.  Metrics are stored
    on ``ctx.result.mechanical_metrics`` and merged into the novelty_report
    JSON during persistence — no schema change required.
    """

    def __init__(self):
        self._calculator = None

    @property
    def name(self) -> str:
        return "mechanical_metrics"

    async def execute(self, ctx: StageContext) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True

        from backend.pipeline.evaluation.mechanical_metrics import MechanicalMetricsCalculator

        if self._calculator is None:
            self._calculator = MechanicalMetricsCalculator()

        for i, idea in enumerate(ideas):
            try:
                # Build supporting_papers for this idea
                cited_ids = set(getattr(idea, "supporting_papers", []) or [])
                supporting = [p for p in ctx.all_papers if getattr(p, "id", None) in cited_ids]

                # Fallback: if no explicit supporting_papers, use all papers
                if not supporting:
                    supporting = ctx.all_papers[:30]

                metrics = self._calculator.compute_all(
                    idea=idea,
                    gaps=ctx.result.gaps,
                    supporting_papers=supporting,
                    all_domain_papers=ctx.all_papers,
                )
                ctx.result.mechanical_metrics[i] = metrics

                # Compute and log composite score (informational)
                novelty = ctx.result.novelty_reports.get(i)
                feasibility = ctx.result.feasibility_reports.get(i)
                llm_score = getattr(idea, "score", 0.0)
                nov_score = novelty.overall_score if novelty else 0.0
                feas_score = (feasibility.overall_score / 10.0) if feasibility else 0.0
                mech_avg = sum(metrics.values()) / len(metrics) if metrics else 0.0
                composite = 0.4 * llm_score + 0.3 * mech_avg + 0.3 * (nov_score + feas_score) / 2
                logger.info(
                    "Mechanical metrics for '%s': composite=%.3f, metrics=%s",
                    idea.title[:50], composite, metrics,
                )
            except Exception as e:
                logger.warning(
                    "Failed to compute mechanical metrics for idea %d: %s", i, e,
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


class ProposalDeepeningStage(PipelineStage):
    """Enriches proposals with architecture, toy examples, failure modes, and criteria."""

    def __init__(self, deepener=None):
        from backend.pipeline.verification.proposal_deepener import ProposalDeepener
        self._deepener = deepener or ProposalDeepener()

    @property
    def name(self) -> str:
        return "proposal_deepening"

    async def execute(self, ctx: StageContext) -> bool:
        """Deepen each proposal in template mode (no LLM needed).

        HB-01: All exceptions caught and logged. Pipeline continues.
        HB-02: Original proposal text is never overwritten.
        """
        try:
            if not ctx.result.proposals:
                logger.debug("No proposals to deepen — skipping")
                return True

            for idx, proposal in ctx.result.proposals.items():
                try:
                    idea_dict = {
                        "id": idx,
                        "title": getattr(proposal, 'title', f'Idea {idx}'),
                        "problem_statement": proposal.sections.get('introduction', '')[:500] if hasattr(proposal, 'sections') and isinstance(proposal.sections, dict) else '',
                        "proposed_method": proposal.sections.get('proposed_method', '')[:500] if hasattr(proposal, 'sections') and isinstance(proposal.sections, dict) else '',
                    }
                    deepened = await self._deepener.deepen(idea_dict)

                    # Store deepened content in proposal metadata (HB-02: don't overwrite text)
                    metadata = {}
                    if hasattr(proposal, 'metadata') and proposal.metadata:
                        try:
                            metadata = json.loads(proposal.metadata) if isinstance(proposal.metadata, str) else proposal.metadata
                        except (json.JSONDecodeError, TypeError):
                            metadata = {}

                    metadata["deepened"] = {
                        "architecture": deepened.architecture,
                        "toy_example": deepened.toy_example,
                        "failure_modes": deepened.failure_modes,
                        "success_criteria": deepened.success_criteria,
                    }

                    if hasattr(proposal, 'metadata'):
                        proposal.metadata = json.dumps(metadata) if not isinstance(metadata, str) else metadata

                    # Also append deepened content as actual proposal sections (for export)
                    if hasattr(proposal, 'sections') and isinstance(proposal.sections, dict):
                        if deepened.architecture:
                            proposal.sections["preliminary_architecture"] = deepened.architecture
                        if deepened.toy_example:
                            proposal.sections["minimal_working_example"] = deepened.toy_example
                        if deepened.failure_modes:
                            proposal.sections["failure_modes"] = deepened.failure_modes
                        if deepened.success_criteria:
                            proposal.sections["success_criteria"] = deepened.success_criteria

                    logger.info(
                        "Deepened proposal %d: '%s'",
                        idx,
                        getattr(proposal, 'title', 'untitled')[:60],
                    )
                except Exception as e:
                    # HB-01: Per-proposal failure is non-fatal
                    logger.warning("Failed to deepen proposal %d (non-fatal): %s", idx, e)

        except Exception as e:
            # HB-01: Overall stage failure is non-fatal
            logger.warning("Proposal deepening stage failed (non-fatal, HB-01): %s", e)

        return True
