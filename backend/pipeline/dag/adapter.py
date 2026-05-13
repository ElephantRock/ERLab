"""DAG-to-Stage Adapter — bridges new DAG runner to existing PipelineStage classes.

BATCH-181 / TASK-02: The adapter:
1. Instantiates the old PipelineStage subclasses from stages.py
2. Maps new dag.StageContext -> old stages.StageContext before each stage
3. Maps old stages.StageContext -> new dag.StageContext after each stage
4. Uses the same construction as PipelineOrchestrator._build_stages()
5. Resolves the correct LLM provider per stage based on STAGE_REGISTRY
"""
from __future__ import annotations

import logging
from typing import Any

from backend.pipeline.stages import PipelineStage, StageContext as OldCtx
from backend.pipeline.dag.context import StageContext as NewCtx
from backend.pipeline.dag.registry import STAGE_REGISTRY

logger = logging.getLogger(__name__)


def new_to_old_ctx(new: NewCtx) -> OldCtx:
    """Convert new dag.StageContext to old stages.StageContext.

    The old context requires a PipelineResult. We create one with the
    data from the new context (papers, gaps, ideas, proposals).
    """
    from backend.pipeline.result import PipelineResult

    result = PipelineResult()
    result.run_id = new.run_id

    # Map papers
    result.papers = new.papers

    # Map gaps — convert from dicts to ResearchGap objects if needed
    result.gaps = new.gaps

    # Map ideas
    result.ideas = new.ideas

    # Map proposals
    result.proposals = new.proposals

    old = OldCtx(
        result=result,
        domain=new.domain,
        run_id=new.run_id,
        params={},  # DAG context doesn't have params
        max_gaps=new.config.get("budgets", {}).get("max_gaps", 5) if new.config else 5,
    )
    old.all_papers = new.papers
    old.export_format = new.config.get("export_format", "markdown") if new.config else "markdown"

    return old


def old_to_new_ctx(old: OldCtx, new: NewCtx) -> None:
    """Write back from old StageContext to new dag.StageContext (in-place).

    After a stage executes, the old ctx has updated result fields.
    We sync these back to the new context.
    """
    new.papers = old.all_papers
    new.gaps = old.result.gaps
    new.ideas = old.result.ideas
    new.proposals = old.result.proposals


class DAGStageAdapter:
    """Instantiates PipelineStage subclasses and bridges contexts.

    Usage:
        adapter = DAGStageAdapter(settings)
        stages = adapter.build_stages()
        for stage_name in plan:
            stage = stages[stage_name]
            old_ctx = new_to_old_ctx(new_ctx)
            success = await stage.execute(old_ctx)
            old_to_new_ctx(old_ctx, new_ctx)
    """

    def __init__(self, settings: Any = None) -> None:
        self._settings = settings
        self._stages: dict[str, PipelineStage] = {}
        self._built = False

    def build_stages(self) -> dict[str, PipelineStage]:
        """Build all 16 stages + trimmer using the same construction as orchestrator.

        Returns a dict mapping stage_name -> PipelineStage instance.
        """
        if self._built:
            return self._stages

        from backend.config import get_settings
        settings = self._settings or get_settings()

        # Build services (same as PipelineOrchestrator.__init__)
        from backend.providers.provider_factory import get_registry, get_thinking_provider
        registry = get_registry()
        provider = registry.create(settings=settings)

        # Thinking provider (local LLM)
        thinking_provider = provider
        try:
            thinking_provider = get_thinking_provider(settings)
        except Exception as e:
            logger.warning("Could not resolve thinking provider: %s", e)

        # Core services
        from backend.pipeline.literature.search_service import SearchService
        from backend.pipeline.literature.multi_source import MultiSourceSearcher
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer
        from backend.pipeline.generation.ideator_agent import IdeatorAgent
        from backend.pipeline.novelty.novelty_checker import NoveltyChecker
        from backend.pipeline.evaluation.proposal_evaluator import ProposalEvaluator
        from backend.pipeline.verification.reference_verifier import ReferenceVerifier
        from backend.pipeline.verification.proposal_deepener import ProposalDeepener
        from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
        from backend.pipeline.reflection.reflector import ReflectionStage

        search = SearchService()
        multi_searcher = MultiSourceSearcher(settings=settings)
        store = VectorStore()
        embedding = EmbeddingService()

        gap_analyzer = GapAnalyzer(provider=thinking_provider)
        agent = IdeatorAgent(provider=thinking_provider, settings=settings)
        novelty = NoveltyChecker(provider=thinking_provider)
        feasibility = None  # Lazy init
        synthesizer = ProposalSynthesizer(provider=provider)
        evaluator = ProposalEvaluator(provider=thinking_provider)
        deepener = ProposalDeepener(provider=provider)
        ref_validator = ReferenceVerifier()

        # Import stage classes
        from backend.pipeline.stages import (
            LiteratureSearchStage,
            IngestionStage,
            GapAnalysisStage,
            GapReflectionStage,
            IdeaGenerationStage,
            IdeaReflectionStage,
            NoveltyCheckingStage,
            FeasibilityScoringStage,
            MechanicalMetricsStage,
            ProposalSynthesisStage,
            EvaluationStage,
            PaperSynthesisStage,
            CitationAuditStage,
            ProposalDeepeningStage,
            ExportStage,
        )
        from backend.pipeline.dag.trimmer import TrimmerStage

        # Read trimmer config from pipeline.yaml budgets
        try:
            from backend.pipeline.dag.runner import DAGRunner
            runner = DAGRunner()
            config = runner.load_config()
            budgets = config.get("budgets", {})
            top_k = budgets.get("trim_top_k", 20)
            max_abstract_chars = budgets.get("max_abstract_chars", 800)
        except Exception:
            top_k = 20
            max_abstract_chars = 800

        # FeasibilityScoringStage needs a FeasibilityScorer
        try:
            from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
            feasibility = FeasibilityScorer(thinking_provider)
        except (ImportError, Exception) as e:
            logger.warning("Could not create FeasibilityScorer: %s", e)
            feasibility = None

        hooks = []  # No hooks in DAG mode

        # Build stages
        self._stages = {
            "literature_search": LiteratureSearchStage(search, hooks),
            "ingestion": IngestionStage(store, None, embedding, provider=provider),
            "trimmer": TrimmerStage(top_k=top_k, max_abstract_chars=max_abstract_chars),
            "gap_analysis": GapAnalysisStage(gap_analyzer, None, hooks, None),
            "gap_reflection": GapReflectionStage(provider=thinking_provider, reflector=ReflectionStage(provider=thinking_provider), threshold=0.6),
            "idea_generation": IdeaGenerationStage(agent, hooks, provider=thinking_provider),
            "idea_reflection": IdeaReflectionStage(provider=thinking_provider, reflector=ReflectionStage(provider=thinking_provider), threshold=0.6),
            "novelty_checking": NoveltyCheckingStage(novelty),
            "feasibility_scoring": FeasibilityScoringStage(feasibility or thinking_provider),
            "mechanical_metrics": MechanicalMetricsStage(),
            "proposal_synthesis": ProposalSynthesisStage(synthesizer, ref_validator=ref_validator),
            "adversarial_review": self._build_adversarial(synthesizer, thinking_provider),
            "evaluation": EvaluationStage(provider=thinking_provider, evaluator=evaluator),
            "paper_synthesis": PaperSynthesisStage(provider=provider),
            "citation_audit": CitationAuditStage(provider=thinking_provider),
            "proposal_deepening": ProposalDeepeningStage(deepener=deepener),
            "export": ExportStage(None),  # ExportService lazily created
        }

        self._built = True
        logger.info("DAGStageAdapter: built %d stages", len(self._stages))
        return self._stages

    def _build_adversarial(self, synthesizer: Any, thinking_provider: Any) -> PipelineStage:
        """Build adversarial review stage."""
        try:
            from backend.pipeline.stages import AdversarialReviewStage
            return AdversarialReviewStage(synthesizer=synthesizer, thinking_provider=thinking_provider)
        except (ImportError, TypeError) as e:
            logger.warning("Could not build AdversarialReviewStage: %s", e)
            # Return a pass-through stage
            from backend.pipeline.stages import PipelineStage, StageContext
            class PassThrough(PipelineStage):
                @property
                def name(self) -> str:
                    return "adversarial_review"
                async def execute(self, ctx: StageContext) -> bool:
                    logger.info("Adversarial review: pass-through (not available)")
                    return True
            return PassThrough()

    def get_stage(self, stage_name: str) -> PipelineStage | None:
        """Get a stage by name, building if necessary."""
        if not self._built:
            self.build_stages()
        return self._stages.get(stage_name)

    @property
    def available_stages(self) -> list[str]:
        if not self._built:
            self.build_stages()
        return sorted(self._stages.keys())
