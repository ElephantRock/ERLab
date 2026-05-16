"""Pipeline orchestrator — coordinates all research pipeline stages."""

import asyncio
import logging
import time
from datetime import datetime

from backend.config import get_settings
from backend.pipeline.export.export_service import ExportService
from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer
from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
from backend.pipeline.ingestion.pdf_service import PDFService
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.knowledge.vector_store import VectorStore
from backend.pipeline.tracing.spans import SpanKind, create_span
from backend.pipeline.tracing.processor import InMemoryProcessor, LoggingProcessor, set_tracer
from backend.pipeline.execution.run_state import RunCheckpoint, RunState, StageCheckpoint, StageStatus
from backend.pipeline.literature.search_service import SearchService
from backend.pipeline.memory.extraction import extract_from_pipeline_result
from backend.pipeline.memory.service import MemoryService
from backend.pipeline.novelty.novelty_checker import NoveltyChecker
from backend.pipeline.verification.proposal_deepener import ProposalDeepener
from backend.pipeline.persistence import PipelinePersistence
from backend.pipeline.result import PipelineResult, StageReport
from backend.pipeline.monitoring.doom_loop import (
    StageOutputSignature,
    check_pipeline_doom,
    hash_stage_output,
)
from backend.pipeline.self_improve.evolution import PipelineEvolver
from backend.pipeline.self_improve.frontier import ParetoFrontier
from backend.pipeline.self_improve.lessons import LessonExtractor
from backend.pipeline.stages import (
    AdversarialReviewStage,
    CitationAuditStage,
    EvaluationStage,
    ExportStage,
    FeasibilityScoringStage,
    GapAnalysisStage,
    GapReflectionStage,
    IdeaGenerationStage,
    IdeaReflectionStage,
    IngestionStage,
    LiteratureSearchStage,
    MechanicalMetricsStage,
    NoveltyCheckingStage,
    PaperSynthesisStage,
    PipelineStage,
    ProposalDeepeningStage,
    ProposalSynthesisStage,
    StageContext,
    TreeSearchStage,
)
from backend.pipeline.reflection.reflector import ReflectionStage
from backend.pipeline.evaluation.proposal_evaluator import ProposalEvaluator
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
from backend.pipeline.synthesis.reference_validator import ReferenceValidator
from backend.pipeline.verification.reference_verifier import ReferenceVerifier
from backend.providers.base import LLMProvider
from backend.providers.provider_factory import get_registry
from backend.providers.retry import retry_llm_call
from backend.providers.token_counter import TokenCounter
from backend.pipeline.compaction.middleware import CompactionMiddleware

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Coordinates the full research idea generation pipeline."""

    _STAGE_ORDER = [
        "literature_search",
        "ingestion",
        "trimmer",  # BATCH-184: paper reranking + truncation
        "gap_analysis",
        "gap_reflection",
        "idea_generation",
        "idea_reflection",
        "novelty_checking",
        "feasibility_scoring",
        "mechanical_metrics",
        "proposal_synthesis",
        "adversarial_review",
        "evaluation",
        "paper_synthesis",
        "citation_audit",
        "proposal_deepening",
        "export",
    ]

    # Backward-compatible attribute delegation: tests that do
    #   orch._gap_analyzer = MagicMock()
    # should keep working by delegating to self._services.gap_analyzer.
    _SERVICE_ATTR_MAP = {
        "_search": "search",
        "_pdf": "pdf",
        "_embedding": "embedding",
        "_store": "store",
        "_embedding_valid": "embedding_valid",
        "_bm25": "bm25",
        "_retriever": "retriever",
        "_quality_scorer": "quality_scorer",
        "_gap_analyzer": "gap_analyzer",
        "_novelty": "novelty",
        "_feasibility": "feasibility",
        "_citation_traverser": "citation_traverser",
        "_embedding_novelty_scorer": "embedding_novelty_scorer",
        "_faithfulness_checker": "faithfulness_checker",
        "_contradiction_scanner": "contradiction_scanner",
        "_forest": "forest",
        "_reasoning_verifier": "reasoning_verifier",
        "_dynamic_agent_factory": "dynamic_agent_factory",
        "_sub_goal_generator": "sub_goal_generator",
        "_synthesizer": "synthesizer",
        "_export": "export",
        "_tool_registry": "tool_registry",
        "_plugin_loader": "plugin_loader",
        "_agent": "agent",
        "_message_bus": "message_bus",
        "_agent_registry": "agent_registry",
        "_dag_executor": "dag_executor",
        "_dag_agents": "dag_agents",
        "_memory": "memory",
        "_shared_kb": "shared_kb",
        "_cross_stage_ctx": "cross_stage_ctx",
        "_prompt_builder": "prompt_builder",
        "_evolver": "evolver",
        "_lesson_extractor": "lesson_extractor",
        "_evolution_engine": "evolution_engine",
        "_ab_test_harness": "ab_test_harness",
        "_ratchet_loop": "ratchet_loop",
        "_feedback_history": "feedback_history",
        "_skill_registry": "skill_registry",
        "_skill_proposer": "skill_proposer",
        "_skill_generator": "skill_generator",
        "_budget": "budget",
        "_plan_verifier": "plan_verifier",
        "_hooks": "hooks",
        "_stage_timings": "stage_timings",
        "_state_machine": "state_machine",
        "_curiosity": "curiosity",
        "_scheduler": "scheduler",
        "_governance_validator": "governance_validator",
        "_governance_audit": "governance_audit",
        "_governance_policy": "governance_policy",
        "_approval_manager": "approval_manager",
        "_kg": "kg",
        "_world_model": "world_model",
        "_goal_manager": "goal_manager",
        "_pipeline_evaluator": "pipeline_evaluator",
        "_sandbox_manager": "sandbox_manager",
        "_observability": "observability",
        "_metacog": "metacog",
        "_mcp_manager": "mcp_manager",
        "_context_window_manager": "context_window_manager",
        "_stream_manager": "stream_manager",
        "_consolidator": "consolidator",
        "_consolidation_scheduler": "consolidation_scheduler",
        "_adaptation_manager": "adaptation_manager",
        "_graph_rag_retriever": "graph_rag_retriever",
        "_tool_matcher": "tool_matcher",
        "_tool_scorer": "tool_scorer",
        "_consensus_engine": "consensus_engine",
        "_session_manager": "session_manager",
    }

    def __getattr__(self, name: str):
        """Delegate _service_attr reads to self._services.attr.
        Also lazily creates _services for tests that use __new__.
        """
        # Avoid infinite recursion during pickling/deepcopy
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        # Handle _services itself — lazily create
        if name == "_services":
            from backend.pipeline.orchestrator.service_registry import ServiceRegistry
            svc = ServiceRegistry()
            self.__dict__["_services"] = svc
            return svc
        svc_name = self._SERVICE_ATTR_MAP.get(name)
        if svc_name is not None:
            services = self._services  # recurses once, then lazy-creates
            return getattr(services, svc_name)
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    @property
    def services(self):
        """Access the service registry. Lazily created for test compat."""
        return self._services

    def __setattr__(self, name: str, value) -> None:
        svc_name = self._SERVICE_ATTR_MAP.get(name)
        if svc_name is not None:
            # Ensure _services exists (lazy for test __new__ compat)
            if "_services" not in self.__dict__:
                from backend.pipeline.orchestrator.service_registry import ServiceRegistry
                self.__dict__["_services"] = ServiceRegistry()
            setattr(self._services, svc_name, value)
        else:
            super().__setattr__(name, value)

    def __init__(self, provider: LLMProvider | None = None, stage_callback=None, settings: "Settings | None" = None, strategy: str | None = None):
        settings = settings or get_settings()
        self._registry = get_registry()
        # Guard against Settings being passed as provider (positional arg confusion)
        if provider is not None and not hasattr(provider, "structured_output"):
            logger.warning(
                "PipelineOrchestrator received %s as 'provider'; ignoring and creating default",
                type(provider).__name__,
            )
            provider = None
        self._provider = provider or self._registry.create(settings=settings)
        self._cost_tracker = self._registry.cost_tracker
        self._stage_callback = stage_callback
        self._settings = settings
        self._last_stage_retries = 0
        self._doom_history: list[dict] = []
        self._doom_detected = False

        # Hybrid model routing: local for thinking tasks, cloud for generation
        self._model_selector = None
        self._thinking_provider = None
        if getattr(settings, 'lmstudio_enabled', False) or getattr(settings, 'thinking_model', ''):
            try:
                from backend.pipeline.model_selection import ModelSelector
                self._model_selector = ModelSelector(settings)
                self._thinking_provider = self._model_selector.resolve('classify')
                logger.info(
                    "Hybrid model routing enabled: thinking=%s, generation=%s",
                    getattr(self._thinking_provider, 'provider_name', 'local'),
                    self._provider.provider_name if hasattr(self._provider, 'provider_name') else 'cloud',
                )
            except Exception as e:
                logger.warning("Model selector init failed, using single provider: %s", e)

        # Strategy: resolve from pipeline.yaml (BATCH-184: single source of truth)
        self._strategy_name = strategy or "deep_research"
        self._strategy_config = self._load_yaml_strategy(self._strategy_name)
        logger.info("Pipeline strategy: %s (from pipeline.yaml)", self._strategy_name)

        # Task routing (optional per-stage model selection)
        self._task_router = None
        if getattr(settings, "model_routing_enabled", False) or getattr(settings, "cost_routing_enabled", False):
            from backend.providers.task_router import create_router
            self._task_router = create_router(
                registry=self._registry,
                cost_tracker=self._cost_tracker,
                settings=settings,
            )

        # Tracing
        self._trace_processor = InMemoryProcessor()

        # Guardrails
        from backend.pipeline.governance.guardrails import default_input_guardrails
        self._input_guardrails = default_input_guardrails()

        # ── Service Registry ──────────────────────────────────────
        from backend.pipeline.orchestrator.service_registry import ServiceRegistry
        self._services = ServiceRegistry()
        self._services.init_all(settings, self._provider, self._thinking_provider, self._cost_tracker)

        # Wire hooks to agent orchestrator for impasse events
        self._services.agent.set_hooks(self._services.hooks)

        # Wire SharedMemoryBridge connecting MessageBus and SharedKB
        self._shared_memory_bridge = None
        if self._services.shared_kb and self._services.message_bus:
            from backend.pipeline.memory.sharing import SharedMemoryBridge
            self._shared_memory_bridge = SharedMemoryBridge(self._services.shared_kb, self._services.message_bus)

        # Curiosity driver needs provider reference
        if self._services.curiosity:
            self._services.curiosity._provider = self._provider

        # Scheduler needs orchestrator reference
        if getattr(self._services, '_scheduler_settings', None):
            from backend.pipeline.autonomy.scheduler import AutonomousScheduler
            sched_settings = self._services._scheduler_settings
            self._services.scheduler = AutonomousScheduler(
                orchestrator=self,
                interval_seconds=getattr(sched_settings, "autonomy_schedule_interval_seconds", 3600),
            )

        # Integration: Soul + Journal + Context
        self._integration = None  # Initialized per-run with run_id/domain

        # Reference verification
        self._reference_verifier = ReferenceVerifier()

        self._persistence = PipelinePersistence()
        self._token_counter = TokenCounter()
        self._compaction = CompactionMiddleware(
            provider=self._provider,
            token_counter=self._token_counter,
            enabled=getattr(settings, "compaction_enabled", False),
            smart_truncation=getattr(settings, "compaction_smart_truncation", True),
            summarization=getattr(settings, "compaction_summarization", True),
            budget_management=getattr(settings, "compaction_budget_management", True),
            global_token_limit=getattr(settings, "budget_max_tokens", 500000),
        )

        # ── Stage Executor & Result Processor ─────────────────────
        from backend.pipeline.orchestrator.stage_executor import StageExecutor
        self._executor = StageExecutor(
            settings=settings,
            persistence=self._persistence,
            stage_callback=stage_callback,
            cost_tracker=self._cost_tracker,
            token_counter=self._token_counter,
            budget=self._services.budget,
            strategy_name=self._strategy_name,
        )

        from backend.pipeline.orchestrator.result_processor import ResultProcessor
        self._processor = ResultProcessor(
            reference_verifier=self._reference_verifier,
            persistence=self._persistence,
            integration=self._integration,
            provider=self._provider,
            cross_stage_ctx=self._services.cross_stage_ctx,
        )

        self._stages = self._build_stages()

        # Register built-in tools after all services are initialized
        from backend.pipeline.tools.builtin import register_builtin_tools
        register_builtin_tools(
            self._services.tool_registry,
            search_service=self._services.search,
            vector_store=self._services.store,
            memory_service=self._services.memory,
            knowledge_graph=self._services.kg,
        )

    @property
    def strategy_name(self) -> str:
        """Return the name of the active pipeline strategy."""
        return self._strategy_name

    def dry_run(self, domain: str = "test", strategy: str | None = None) -> str:
        """Print execution plan without running (BATCH-184).

        Reads pipeline.yaml for stage list and model assignments.
        Returns the plan as a formatted string.
        """
        from backend.pipeline.dag.config import ConfigLoader

        strat = strategy or self._strategy_name
        config = ConfigLoader().load()
        strategies = config.get("strategies", {})
        if strat not in strategies:
            return f"Unknown strategy '{strat}'. Available: {', '.join(strategies.keys())}"

        stages = strategies[strat].get("stages", [])
        models = config.get("models", {})

        # Stage-to-category mapping (from pipeline.yaml comments)
        CATEGORY_MAP = {
            "literature_search": "thinking", "ingestion": "embedding",
            "trimmer": "system", "gap_analysis": "thinking",
            "gap_reflection": "thinking", "idea_generation": "thinking",
            "idea_reflection": "thinking", "novelty_checking": "embedding",
            "feasibility_scoring": "thinking", "mechanical_metrics": "system",
            "proposal_synthesis": "generation", "adversarial_review": "thinking",
            "evaluation": "thinking", "paper_synthesis": "generation",
            "citation_audit": "thinking", "proposal_deepening": "generation",
            "export": "system",
        }

        lines = [
            f"dry_run: strategy={strat}, domain={domain}",
            f"run_id: (not generated -- dry run)",
            f"stages: {len(stages)}",
            "",
        ]
        for i, name in enumerate(stages, 1):
            category = CATEGORY_MAP.get(name, "system")
            model_cfg = models.get(category, {})
            provider = model_cfg.get("provider", "unknown")
            model = model_cfg.get("model", "unknown")
            lines.append(f"   {i}. {name:<28s} {category} ({provider}/{model})")

        return "\n".join(lines)

    @staticmethod
    def _load_yaml_strategy(strategy_name: str):
        """Load strategy config from pipeline.yaml (BATCH-184).

        Returns a StrategyConfig with stages dict built from YAML.
        Falls back to legacy StrategyRegistry if YAML is unavailable.
        """
        try:
            from backend.pipeline.dag.config import ConfigLoader
            from backend.pipeline.strategies.models import StageConfig, StrategyConfig
            config = ConfigLoader().load()
            strategies = config.get("strategies", {})
            if strategy_name not in strategies:
                raise ValueError(
                    f"Unknown strategy '{strategy_name}'. "
                    f"Available: {', '.join(strategies.keys())}"
                )
            strat_yaml = strategies[strategy_name]
            stages = {}
            for name in strat_yaml.get("stages", []):
                stages[name] = StageConfig(enabled=True)
            return StrategyConfig(
                name=strategy_name,
                description=strat_yaml.get("description", ""),
                stages=stages,
            )
        except Exception as e:
            logger.warning("YAML strategy load failed, falling back to presets: %s", e)
            from backend.pipeline.strategies import StrategyRegistry, register_presets
            registry = StrategyRegistry()
            register_presets(registry)
            return registry.get(strategy_name)

    def _build_synthesis_stage(self, ref_validator) -> PipelineStage:
        """Build the proposal synthesis stage, selecting synthesizer based on strategy."""
        if self._strategy_name == "fast_scan":
            from backend.pipeline.synthesis.fast_synthesizer import FastProposalSynthesizer
            fast_synth = FastProposalSynthesizer(provider=self._provider)
            return ProposalSynthesisStage(
                fast_synth,
                self._services.governance_validator,
                self._services.governance_audit,
                ref_validator=ref_validator,
            )
        # Default: full proposal synthesizer
        return ProposalSynthesisStage(
            self._services.synthesizer,
            self._services.governance_validator,
            self._services.governance_audit,
            ref_validator=ref_validator,
        )

    def _resolve_user_model(self, model_id: str):
        """Resolve a user-selected model ID to a provider instance."""
        from backend.providers.provider_factory import create_provider
        from backend.config import get_settings
        settings = get_settings()

        if model_id == "cloud":
            return create_provider("anthropic", settings=settings)
        elif model_id == "local":
            return create_provider("lmstudio", settings=settings)
        else:
            return create_provider(model_id, settings=settings)

    def _build_adversarial_review_stage(
        self, synthesizer, thinking_provider,
    ) -> AdversarialReviewStage:
        """Build the adversarial review stage with cross-model provider resolution.

        Uses the thinking provider (local LM Studio) for review,
        while the synthesizer uses the generation provider (cloud).
        """
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer

        reviewer = AdversarialReviewer(thinking_provider or self._provider)
        return AdversarialReviewStage(
            reviewer=reviewer,
            synthesizer=synthesizer,
            generation_provider=self._provider,
            thinking_provider=thinking_provider,
        )

    def _build_stages(self) -> list[PipelineStage]:
        ref_validator = ReferenceValidator(store=self._services.store)

        # Build the idea generation stage based on tree_of_thought_enabled flag (HB-01)
        idea_stage: PipelineStage
        if getattr(self._settings, "tree_of_thought_enabled", False):
            from backend.pipeline.generation.tree_search import TreeSearchConfig, TreeSearchEngine

            tree_config = TreeSearchConfig(
                beam_width=getattr(self._settings, "tree_of_thought_beam_width", 2),
                max_depth=getattr(self._settings, "tree_of_thought_max_depth", 3),
            )
            # Use the existing ideator agent (implements the Ideator protocol)
            tree_engine = TreeSearchEngine(
                ideator=self._services.agent,  # IdeatorAgent implements the Ideator protocol
                config=tree_config,
            )
            idea_stage = TreeSearchStage(
                engine=tree_engine,
                hooks=self._services.hooks,
                provider=self._provider,
                kg=self._services.kg,
            )
            logger.info(
                "TreeSearchStage enabled (beam_width=%d, max_depth=%d)",
                tree_config.beam_width, tree_config.max_depth,
            )
        else:
            idea_stage = IdeaGenerationStage(
                self._services.agent,
                self._services.hooks,
                dag_executor=self._services.dag_executor,
                dag_agents=self._services.dag_agents,
                provider=self._provider,
                kg=self._services.kg,
                forest=self._services.forest,
                reasoning_verifier=self._services.reasoning_verifier,
            )

        # Adversarial review stage — uses thinking provider (local) to review
        # proposals generated by the generation provider (cloud)
        from backend.providers.provider_factory import get_thinking_provider
        thinking_provider = self._thinking_provider
        if thinking_provider is None:
            try:
                thinking_provider = get_thinking_provider(self._settings)
            except Exception as e:
                logger.warning("Could not resolve thinking provider for adversarial review: %s", e)

        adversarial_stage = self._build_adversarial_review_stage(
            synthesizer=self._services.synthesizer,
            thinking_provider=thinking_provider,
        )

        # BATCH-172: resolve thinking_provider with fallback
        tp = self._thinking_provider or self._provider

        # BATCH-184: Trimmer config from YAML
        try:
            from backend.pipeline.dag.runner import DAGRunner
            dag_cfg = DAGRunner().load_config()
            budgets = dag_cfg.get("budgets", {})
            trim_top_k = budgets.get("trim_top_k", 20)
            trim_max_chars = budgets.get("max_abstract_chars", 800)
        except Exception:
            trim_top_k, trim_max_chars = 20, 800

        from backend.pipeline.dag.trimmer import TrimmerStage

        return [
            LiteratureSearchStage(self._services.search, self._services.hooks),
            IngestionStage(self._services.store, self._services.bm25, self._services.embedding, kg=self._services.kg, provider=self._provider),
            TrimmerStage(top_k=trim_top_k, max_abstract_chars=trim_max_chars),  # BATCH-184
            GapAnalysisStage(self._services.gap_analyzer, self._services.goal_manager, self._services.hooks, self._services.memory, kg=self._services.kg, faithfulness_checker=self._services.faithfulness_checker),
            GapReflectionStage(provider=tp, reflector=ReflectionStage(provider=tp), threshold=0.6),
            idea_stage,
            IdeaReflectionStage(provider=tp, reflector=ReflectionStage(provider=tp), threshold=0.6),
            NoveltyCheckingStage(self._services.novelty, self._services.hooks),
            FeasibilityScoringStage(self._services.feasibility),
            MechanicalMetricsStage(),
            self._build_synthesis_stage(ref_validator),
            adversarial_stage,
            EvaluationStage(provider=tp, evaluator=ProposalEvaluator(provider=tp)),
            PaperSynthesisStage(provider=self._provider),
            CitationAuditStage(provider=thinking_provider),
            ProposalDeepeningStage(deepener=ProposalDeepener(provider=self._provider)),
            ExportStage(self._services.export),
        ]

    # ── Main Pipeline ────────────────────────────────────────────────

    async def run(
        self,
        domain: str = "AI/NLP",
        search_queries: list[str] | None = None,
        max_gaps: int = 5,
        generation_rounds: int | None = None,
        ideas_per_round: int | None = None,
        export_format: str | None = "markdown",
        run_id: str | None = None,
        session_id: str | None = None,
        skip_stages: set[str] | None = None,
    ) -> PipelineResult:
        """Execute the full pipeline from literature search to export.

        Stage gating is controlled by the active strategy preset from
        pipeline.yaml — the single source of truth. No run_* booleans.

        Args:
            skip_stages: Set of stage names to skip (used by --resume to avoid
                re-running already-completed stages).
        """
        result = PipelineResult()
        rounds = generation_rounds or self._settings.generation_rounds
        ideas_per = ideas_per_round or self._settings.ideas_per_round

        run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        result.run_id = run_id
        self._current_run_id = run_id  # BATCH-184: for StageLogger
        self._stage_logger = None  # Reset logger for new run

        # BATCH-185: Reset doom loop detection for this run
        self._doom_history = []
        self._doom_detected = False

        # BATCH-191: Initialize Consolidated Context Window
        from backend.pipeline.monitoring.ccw import ConsolidatedContextWindow
        self._ccw = ConsolidatedContextWindow()

        # BATCH-190: Initialize notification gateway
        try:
            from backend.pipeline.notifications.gateway import create_notifier
            webhook_url = getattr(settings, 'notification_webhook_url', None)
            self._notifier = create_notifier(webhook_url)
        except Exception:
            self._notifier = None

        # BATCH-190: Send run_started notification
        if self._notifier:
            try:
                from backend.pipeline.notifications.gateway import Notification, PipelineEvent
                await self._notifier.send(Notification(
                    event=PipelineEvent.RUN_STARTED,
                    run_id=run_id, strategy=strategy, domain=domain,
                    message=f"Pipeline started: {strategy} on '{domain}'",
                ))
            except Exception:
                pass

        # Phase 7: Initialize integration service (Soul + Journal + Context)
        try:
            from backend.pipeline.integration_service import PipelineIntegrationService
            self._integration = PipelineIntegrationService(
                run_id=run_id, domain=domain,
                token_budget=getattr(self._settings, 'thinking_model_max_tokens', 8192),
            )
            self._integration.journal_note("pipeline", f"Pipeline started for domain: {domain}")
        except Exception as e:
            logger.warning("Integration service init failed (non-fatal): %s", e)
            self._integration = None

        # G1: Lazy validation — check embedding provider on first run
        if not self._services.embedding_valid:
            self._services.embedding_valid = await self._services.embedding.validate_startup()
            if not self._services.embedding_valid:
                logger.warning(
                    "Embedding provider returns zero vectors — novelty checking will "
                    "produce low-confidence results. Stage will run but mark profiles "
                    "as UNVERIFIABLE."
                )

        # G5: Run watchdog before starting — clean up stale runs from prior crashes
        try:
            from backend.pipeline.execution.watchdog import PipelineWatchdog
            from datetime import timedelta as _td
            watchdog = PipelineWatchdog(self._persistence, timeout=_td(minutes=30))
            stale_count = watchdog.check_sync()
            if stale_count > 0:
                logger.info("Watchdog: marked %d stale runs as failed before starting new run", stale_count)
        except Exception as e:
            logger.debug("Watchdog check failed (non-fatal): %s", e)

        # Session: register run and check budget
        if session_id and self._services.session_manager:
            budget_check = self._services.session_manager.check_budget(session_id)
            if budget_check["over_budget"]:
                logger.warning("Session %s is over budget — aborting run", session_id)
                return result
            self._services.session_manager.register_run(session_id, run_id)

        # Self-improvement: propose evolved parameters
        params = {
            "generation_rounds": rounds,
            "ideas_per_round": ideas_per,
            "max_gaps": max_gaps,
        }
        if self._services.evolver:
            evolved = self._services.evolver.propose()
            if generation_rounds is None and "generation_rounds" in evolved:
                rounds = int(evolved["generation_rounds"])
            if ideas_per_round is None and "ideas_per_round" in evolved:
                ideas_per = int(evolved["ideas_per_round"])

            # Wire evolved temperatures into agent orchestrator
            temps = {}
            for key in ("ideator_temperature", "critic_temperature", "refiner_temperature"):
                if key in evolved:
                    temps[key] = float(evolved[key])
            if temps:
                self._services.agent.set_temperature_overrides(temps)

            # Wire novelty_top_k
            if "novelty_top_k" in evolved and hasattr(self, "_novelty"):
                self._services.novelty._top_k = int(evolved["novelty_top_k"])

            params.update(evolved)  # type: ignore[arg-type]
        result.params_used = params

        # Create DB run record
        db_run_id = self._persistence.create_run_record(domain, params, session_id=session_id)

        # Budget: validate plan and start tracking
        if self._services.budget and self._services.plan_verifier:
            ok, msg = self._services.plan_verifier.validate(params, self._services.budget)
            if not ok:
                logger.warning("Budget validation failed: %s. Aborting.", msg)
                return result
            self._services.budget.start()

        # MCP: connect servers and discover tools
        if self._services.mcp_manager and not self._services.mcp_manager._started:
            try:
                tool_count = await self._services.mcp_manager.start()
                logger.info("MCP manager started: %d tools registered", tool_count)
            except Exception as e:
                logger.warning("MCP startup failed (continuing without MCP tools): %s", e)

        # Hook: pipeline.start
        await self._services.hooks.dispatch_sync_safe(
            "pipeline.start",
            {
                "run_id": run_id,
                "domain": domain,
                "params": params,
            },
        )

        # Build context
        ctx = StageContext(
            result=result,
            domain=domain,
            run_id=run_id,
            db_run_id=db_run_id,
            params=params,
            search_queries=search_queries,
            max_gaps=max_gaps,
            rounds=rounds,
            ideas_per=ideas_per,
            export_format=export_format,
        )

        # Create run checkpoint for durable execution
        checkpoint = RunCheckpoint.create_new(
            run_id=run_id,
            stage_names=[s.name for s in self._stages],
        )
        checkpoint.mark_stage_running(self._stages[0].name)
        self._persistence.save_checkpoint(checkpoint)

        # Execute stages (BATCH-173: track all stages in stage_report)
        for stage in self._stages:
            # Strategy: skip stages disabled in the current strategy config
            strategy_stage = self._strategy_config.stages.get(stage.name)
            if strategy_stage is not None and not strategy_stage.enabled:
                logger.info("Strategy '%s' skips stage: %s", self._strategy_name, stage.name)
                result.stage_report.append(StageReport(
                    name=stage.name,
                    status="skipped_by_strategy",
                    skip_reason=f"Strategy {self._strategy_name}",
                ))
                continue

            # BATCH-185: Skip optional stages when doom loop detected
            if self._doom_detected and stage.name not in ("export",):
                result.stage_report.append(StageReport(
                    name=stage.name,
                    status="skipped_by_doom",
                    skip_reason="Doom loop detected — skipping optional stage",
                ))
                continue

            # Resume support: skip stages already completed in a prior run
            if skip_stages and stage.name in skip_stages:
                logger.info("Skipping completed stage (resume): %s", stage.name)
                continue

            logger.info("=== %s ===", stage.name.replace("_", " ").title())

            # Advance stage tracking in DB before execution
            if db_run_id:
                self._persistence.advance_stage(db_run_id, stage.name)

            # Per-stage model routing
            if self._task_router:
                ctx.provider_override = self._task_router.get_provider(stage.name, run_id)

            # User-configured per-stage model override (UI model selector)
            from backend.api.routes.model_config import get_stage_model
            user_model = get_stage_model(stage.name)
            if user_model and user_model != "auto":
                try:
                    ctx.provider_override = self._resolve_user_model(user_model)
                except Exception as e:
                    logger.warning("User model '%s' for stage '%s' failed, using default: %s", user_model, stage.name, e)

            # Policy gate: evaluate governance policy before each stage
            if self._services.governance_policy:
                from backend.pipeline.governance.policy import PolicyAction

                decision = self._services.governance_policy.evaluate(
                    scope=stage.name,
                    capability="execute",
                )
                if decision.action == PolicyAction.DENY:
                    logger.warning(
                        "Governance policy DENIED stage '%s': %s",
                        stage.name,
                        decision.reason,
                    )
                    if self._services.governance_audit:
                        from backend.pipeline.governance.events import GovernanceEvent

                        self._services.governance_audit.record(GovernanceEvent(
                            event_type="policy.deny",
                            stage=stage.name,
                            content_hash="",
                            checks_summary=f"Rule: {decision.rule_name}, Reason: {decision.reason}",
                        ))
                    continue
                if decision.action == PolicyAction.GATE:
                    logger.info(
                        "Governance policy GATE on stage '%s': %s — awaiting approval",
                        stage.name,
                        decision.reason,
                    )
                    if self._services.governance_audit:
                        from backend.pipeline.governance.events import GovernanceEvent

                        self._services.governance_audit.record(GovernanceEvent(
                            event_type="policy.gate",
                            stage=stage.name,
                            content_hash="",
                            checks_summary=f"Rule: {decision.rule_name}, Awaiting approval",
                        ))

                    if hasattr(self, "_approval_manager"):
                        approval = await self._services.approval_manager.request_approval(
                            stage=stage.name,
                            reason=decision.reason,
                            rule_name=decision.rule_name,
                        )
                        if approval.status.value != "approved":
                            logger.warning(
                                "Stage '%s' %s: %s",
                                stage.name,
                                approval.status.value,
                                approval.amendment or decision.reason,
                            )
                            continue

            t0 = time.time()
            # Cross-stage context: load prior outputs
            if self._services.cross_stage_ctx:
                prior = await self._services.cross_stage_ctx.load_prior_context(run_id, stage.name)
                if prior:
                    ctx.params["prior_context"] = prior
            with create_span(SpanKind.STAGE, stage.name, run_id=run_id) as span:
                prepared_ctx = await self._compaction.prepare_context(ctx, stage.name)
                # Heartbeat monitoring
                heartbeat = None
                if getattr(self._settings, "heartbeat_enabled", True):
                    from backend.pipeline.execution.heartbeat import StageHeartbeat
                    heartbeat = StageHeartbeat(
                        checkpoint, self._persistence,
                        interval_seconds=getattr(self._settings, "heartbeat_interval_seconds", 30.0),
                    )
                    await heartbeat.start(stage.name)
                try:
                    should_continue = await self._execute_stage_with_retry(
                        stage, prepared_ctx, checkpoint
                    )
                    elapsed = time.time() - t0
                    result.stage_report.append(StageReport(
                        name=stage.name,
                        status="executed",
                        elapsed_s=round(elapsed, 3),
                        retries_used=getattr(self, '_last_stage_retries', 0),
                    ))
                except Exception as e:
                    elapsed = time.time() - t0
                    import traceback as _tb
                    logger.error(
                        "Stage '%s' failed (continuing pipeline): %s\n%s",
                        stage.name, e, _tb.format_exc(),
                    )
                    result.stage_report.append(StageReport(
                        name=stage.name,
                        status="skipped_by_error",
                        elapsed_s=round(elapsed, 3),
                        error=str(e)[:500],
                        retries_used=0,
                    ))
                    if heartbeat:
                        await heartbeat.stop()
                    # Record partial stage info
                    self._record_stage(stage.name, t0)
                    continue
                finally:
                    if heartbeat:
                        await heartbeat.stop()
            elapsed = time.time() - t0
            self._record_stage(stage.name, t0)

            # Phase D: Verify stage output contract
            try:
                from backend.pipeline.monitoring.contracts import STAGE_CONTRACTS, verify_contract
                contract = STAGE_CONTRACTS.get(stage.name)
                if contract:
                    violation = verify_contract(stage.name, result, contract)
                    if violation:
                        if violation.is_error:
                            logger.error(
                                "CONTRACT VIOLATION: %s — %s",
                                stage.name, "; ".join(violation.violations),
                            )
                        else:
                            logger.warning(
                                "CONTRACT WARNING: %s — %s",
                                stage.name, "; ".join(violation.violations),
                            )
            except Exception as e:
                logger.debug("Contract verification failed (non-fatal): %s", e)

            self._compaction.record_usage(stage.name)
            if self._services.metacog:
                self._services.metacog.record_stage(stage.name, {"elapsed_seconds": elapsed})
            await self._services.hooks.dispatch_sync_safe(
                "pipeline.stage.complete",
                {"stage": stage.name, "elapsed": elapsed, "run_id": run_id},
            )

            # BATCH-185: Doom loop detection
            if not self._doom_detected:
                try:
                    from backend.pipeline.monitoring.doom_loop import (
                        extract_stage_fingerprint,
                        hash_stage_output,
                        check_pipeline_doom,
                    )
                    fingerprint = extract_stage_fingerprint(
                        stage.name,
                        gaps=result.gaps if hasattr(result, 'gaps') else None,
                        ideas=result.ideas if hasattr(result, 'ideas') else None,
                        proposals=result.proposals if hasattr(result, 'proposals') else None,
                    )
                    if fingerprint:
                        self._doom_history.append({
                            "stage_name": stage.name,
                            "output_hash": hash_stage_output(fingerprint),
                        })
                        doom_msg = check_pipeline_doom(self._doom_history)
                        if doom_msg:
                            logger.warning("Doom loop detected: %s", doom_msg)
                            self._doom_detected = True
                except Exception as e:
                    logger.debug("Doom loop check failed for %s: %s", stage.name, e)

            # BATCH-191: CCW compression after key stages
            if self._ccw:
                try:
                    if stage.name == "literature_search" or stage.name == "ingestion":
                        if ctx.all_papers:
                            self._ccw.add_papers(ctx.all_papers)
                            logger.info("CCW: compressed %d papers (%d tokens)",
                                         len(self._ccw.papers), self._ccw.estimate_tokens())
                    elif stage.name == "gap_analysis":
                        if result.gaps:
                            self._ccw.add_gaps(result.gaps)
                            logger.info("CCW: compressed %d gaps", len(self._ccw.gaps))
                    elif stage.name == "idea_generation":
                        if result.ideas:
                            self._ccw.add_ideas(result.ideas)
                            logger.info("CCW: compressed %d ideas", len(self._ccw.ideas))
                except Exception as e:
                    logger.debug("CCW compression failed for %s: %s", stage.name, e)

            # BATCH-190: Stage completion notification
            if self._notifier:
                try:
                    from backend.pipeline.notifications.gateway import Notification, PipelineEvent
                    await self._notifier.send(Notification(
                        event=PipelineEvent.STAGE_COMPLETED,
                        run_id=run_id, strategy=strategy, domain=domain,
                        message=f"Stage {stage.name} completed ({elapsed:.1f}s)",
                        data={"stage": stage.name, "elapsed": elapsed},
                    ))
                except Exception:
                    pass

            # Persistence checkpoints
            if stage.name == "literature_search":
                self._persistence.persist_papers(ctx.all_papers, db_run_id)
                self._collect_warnings(result)

                # Rerank papers using cross-encoder for better relevance ordering
                try:
                    from backend.pipeline.knowledge.reranker import create_reranker
                    reranker = create_reranker("auto")
                    if ctx.all_papers and ctx.domain:
                        docs = [
                            {"id": str(p.id), "text": f"{p.title} {p.abstract or ''}"}
                            for p in ctx.all_papers
                            if p.abstract
                        ]
                        if docs:
                            ranked = await reranker.rerank(ctx.domain, docs, top_k=min(20, len(docs)))
                            # Reorder all_papers based on reranked order
                            ranked_ids = {r.id: r.score for r in ranked}
                            scored_papers = []
                            for p in ctx.all_papers:
                                score = ranked_ids.get(str(p.id), 0.0)
                                scored_papers.append((score, p))
                            scored_papers.sort(key=lambda x: x[0], reverse=True)
                            ctx.all_papers = [p for _, p in scored_papers]
                            logger.info(
                                "Reranked %d papers, top score=%.3f",
                                len(ranked),
                                ranked[0].score if ranked else 0.0,
                            )
                except Exception as e:
                    logger.debug("Reranking skipped: %s", str(e)[:100])

                # BATCH-RAG-02: Compute retrieval metrics after literature search
                try:
                    from backend.pipeline.evaluation.retrieval_metrics import (
                        compute_retrieval_metrics,
                        RetrievedDocument,
                    )
                    queries = ctx.search_queries or [ctx.domain]
                    if ctx.all_papers and queries:
                        docs_per_query = []
                        for q in queries:
                            docs = [
                                RetrievedDocument(
                                    doc_id=str(p.id),
                                    rank=i + 1,
                                    score=p.relevance_score or 0.0,
                                    is_relevant=False,  # No ground truth in live runs
                                )
                                for i, p in enumerate(ctx.all_papers[:20])
                            ]
                            docs_per_query.append((q, docs))
                        metrics_report = compute_retrieval_metrics(docs_per_query)
                        metrics_report.domain = ctx.domain
                        metrics_report.strategy = ctx.params.get("strategy", "unknown")
                        # Store in result metadata for later retrieval
                        if not hasattr(result, '_retrieval_metrics'):
                            result._retrieval_metrics = metrics_report
                        logger.info(
                            "Retrieval metrics: %d queries, %d docs, hit_rate=%.2f",
                            metrics_report.total_queries,
                            metrics_report.total_documents_retrieved,
                            metrics_report.hit_rate,
                        )
                except Exception as e:
                    logger.debug("Retrieval metrics computation skipped: %s", str(e)[:100])
                if not should_continue:
                    self._persistence.mark_run_failed(db_run_id, "No papers found")
                    self._collect_warnings(result)
                    await self._services.hooks.dispatch_sync_safe(
                        "pipeline.complete",
                        {
                            "run_id": run_id,
                            "status": "no_papers",
                        },
                    )
                    return result

            if stage.name == "gap_analysis":
                self._persistence.persist_gaps(result, db_run_id)
                self._collect_warnings(result)

            if stage.name == "idea_generation":
                # Intermediate save: persist ideas immediately so they survive a crash
                # before proposal synthesis (AC-02-01).
                self._persistence.persist_ideas(result, db_run_id)
                self._collect_warnings(result)

                # Persist tree visualization data (BATCH-63/TASK-02)
                if getattr(result, 'tree_data', None):
                    self._persistence.persist_tree_data(result.tree_data, db_run_id)
                    self._collect_warnings(result)

            if stage.name == "feasibility_scoring":
                self._persistence.persist_ideas(result, db_run_id)
                self._collect_warnings(result)

                # Unified evaluation (WP-02)
                if self._services.pipeline_evaluator:
                    eval_reports = await self._services.pipeline_evaluator.evaluate_all(
                        ideas=result.ideas,
                        novelty_reports=result.novelty_reports,
                        feasibility_reports=result.feasibility_reports,
                    )
                    result.evaluation_reports = eval_reports
                    for idx, er in eval_reports.items():
                        if er.quality_gate_result and not er.quality_gate_result.passed:
                            logger.warning(
                                "Idea '%s' failed quality gate: %s (%s)",
                                er.idea_title[:50],
                                er.quality_gate_result.failures,
                                er.quality_gate_result.recommendation,
                            )
                    if self._services.metacog:
                        for er in eval_reports.values():
                            self._services.metacog.record_evaluation(er)
                        plateau = self._services.metacog.check_plateau("overall_score")
                        if plateau.is_plateau:
                            logger.warning("Metacognitive plateau: %s", plateau.reason)

                # Quality backloop (Gap 12): loop back if ideas are weak
                if getattr(self._settings, "quality_backloop_enabled", False) and result.ideas:
                    avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
                    min_composite = getattr(self._settings, "quality_backloop_min_composite", 0.4)
                    if avg_score < min_composite:
                        logger.info(
                            "Quality backloop: avg score %.3f < %.3f, regenerating ideas",
                            avg_score, min_composite,
                        )
                        # Mark low-scoring ideas for replacement
                        result.ideas = [i for i in result.ideas if i.score >= min_composite]

            if stage.name == "proposal_synthesis":
                self._persistence.persist_proposals(result, db_run_id)
                self._collect_warnings(result)
                # Phase 8: Run reference verification after synthesis (HB-02)
                self._verify_references(result, ctx)

                # BATCH-RAG-03: Faithfulness scoring via LLM-as-judge
                try:
                    from backend.pipeline.evaluation.faithfulness_scorer import FaithfulnessScorer
                    scorer = FaithfulnessScorer(provider=None)  # Heuristic mode for now
                    source_abstracts = [
                        p.abstract for p in ctx.all_papers[:30]
                        if hasattr(p, 'abstract') and p.abstract
                    ]
                    for prop in result.proposals:
                        report = asyncio.get_event_loop().run_until_complete(
                            scorer.score_proposal(
                                proposal_text=prop.methodology if hasattr(prop, 'methodology') else str(prop),
                                proposal_title=prop.title if hasattr(prop, 'title') else "",
                                proposal_id=str(prop.id) if hasattr(prop, 'id') else "",
                                source_texts=source_abstracts,
                            )
                        )
                        prop._faithfulness_report = report
                    logger.info("Faithfulness scoring complete for %d proposals", len(result.proposals))
                except Exception as e:
                    logger.debug("Faithfulness scoring skipped: %s", str(e)[:100])

            # Cross-stage context: persist stage outputs
            if self._services.cross_stage_ctx:
                await self._persist_stage_context(run_id, stage.name, ctx, result)

            # Save checkpoint after each stage for durable execution
            checkpoint.mark_stage_completed(stage.name)
            next_idx = self._STAGE_ORDER.index(stage.name) + 1 if stage.name in self._STAGE_ORDER else -1
            if next_idx < len(self._stages):
                checkpoint.mark_stage_running(self._stages[next_idx].name)
            self._persistence.save_checkpoint(checkpoint)

            # Phase 7: Journal stage completion
            if self._integration:
                self._integration.journal_note(
                    stage.name,
                    f"Stage completed",
                    {"elapsed_s": f"{elapsed:.1f}"} if 'elapsed' in dir() else {},
                )

            # BATCH-185: Doom loop detection — check after each stage
            fingerprint = self._extract_stage_fingerprint(stage.name, result)
            if fingerprint:  # Only check monitored stages
                output_hash = hash_stage_output(fingerprint)
                self._doom_history.append({
                    "stage_name": stage.name,
                    "output_hash": output_hash,
                })
                doom_msg = check_pipeline_doom(self._doom_history)
                if doom_msg:
                    logger.warning("BATCH-185 doom detection: %s", doom_msg)
                    self._doom_detected = True

            # BATCH-185: Skip remaining optional stages if doom detected (except export)
            if self._doom_detected and not isinstance(stage, ExportStage):
                logger.info(
                    "Doom detected — skipping remaining optional stages (export will still run)"
                )
                # Report remaining stages as skipped
                reported_names = {r.name for r in result.stage_report}
                for remaining_stage in self._stages:
                    if (
                        remaining_stage.name not in reported_names
                        and not isinstance(remaining_stage, ExportStage)
                    ):
                        result.stage_report.append(StageReport(
                            name=remaining_stage.name,
                            status="skipped_by_doom",
                            skip_reason="Doom loop detected",
                        ))
                # Continue loop — export stage will still execute
                continue

            if not should_continue or self._should_stop():
                # Fill not_reached for remaining stages
                reported_names = {r.name for r in result.stage_report}
                for stage_name in self._STAGE_ORDER:
                    if stage_name not in reported_names:
                        result.stage_report.append(StageReport(
                            name=stage_name,
                            status="not_reached",
                        ))
                # Persist stage report to DB
                self._persist_stage_report(result, db_run_id)
                return result

        # Fill not_reached for stages not in the loop (e.g. strategy excluded)
        reported_names = {r.name for r in result.stage_report}
        for stage_name in self._STAGE_ORDER:
            if stage_name not in reported_names:
                result.stage_report.append(StageReport(
                    name=stage_name,
                    status="not_reached",
                ))
        # Persist stage report to DB
        self._persist_stage_report(result, db_run_id)

        # Phase 8: Pipeline quality evaluation
        self._evaluate_pipeline(result, ctx)

        # Post-pipeline: Self-improvement evaluation
        if self._services.evolver and result.ideas:
            avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
            avg_novelty = (
                sum(r.overall_score for r in result.novelty_reports.values())
                / len(result.novelty_reports)
                if result.novelty_reports
                else 0.0
            )

            # Compute FitnessScore from run outcomes
            from backend.pipeline.self_improve.fitness import FitnessScore

            total_text = sum(len(i.proposed_method) for i in result.ideas)
            length_penalty = FitnessScore.length_penalty_ramp(total_text, 50000)
            fitness = FitnessScore(
                correctness=avg_score,
                procedure_following=min(1.0, len(result.ideas) / max(1, ideas_per * rounds)),
                conciseness=1.0 - length_penalty,
                length_penalty=length_penalty,
            )

            self._services.evolver.evaluate(
                params=params,
                run_id=run_id,
                avg_idea_score=avg_score,
                avg_novelty_score=avg_novelty,
                good_ideas=sum(1 for i in result.ideas if i.score >= 0.6),
                fitness=fitness,
            )

        # Post-pipeline: Lesson extraction → store as memories
        if self._services.lesson_extractor and result.ideas:
            avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
            if avg_score < 0.7:
                lessons = await self._services.lesson_extractor.extract(result, params)
                if lessons:
                    logger.info("Extracted %d lessons from run", len(lessons))
                    # Store lessons as memories
                    if self._services.memory:
                        from backend.pipeline.knowledge.truth import TruthValue
                        from backend.pipeline.memory.models import MemoryEntry, MemoryType

                        for lesson in lessons:
                            try:
                                entry = MemoryEntry(
                                    id="",
                                    content=str(lesson),
                                    memory_type=MemoryType.EPISODIC,
                                    namespace="pipeline_experience",
                                    truth=TruthValue.from_observation(frequency=0.7),
                                    tags=["lesson", "self_improve"],
                                    created_at=datetime.now(),
                                )
                                await self._services.memory.store(entry)
                            except Exception as e:
                                logger.warning("Failed to store lesson as memory: %s", e)
                        logger.info("Stored %d lessons as memories", len(lessons))

                    # Feed lessons back into evolver for parameter adjustment
                    if self._services.evolver and lessons:
                        adjusted = self._services.evolver.apply_lessons(
                            [str(l) for l in lessons], params
                        )
                        logger.info(
                            "Lessons fed back to evolver. %d params adjusted",
                            sum(1 for k in adjusted if adjusted[k] != params.get(k)),
                        )

                    # Activate skill proposer/generator with lessons
                    if self._services.skill_proposer and self._services.skill_generator and self._services.skill_registry:
                        skills = self._services.skill_registry.discover(domain=domain)
                        for skill in skills:
                            try:
                                diagnosis, suggestion = await self._services.skill_proposer.diagnose(
                                    skill, trace=str(lessons)
                                )
                                improved = await self._services.skill_generator.generate(
                                    skill, diagnosis, suggestion
                                )
                                self._services.skill_registry.add_version(skill.id, improved, score=avg_score)
                            except Exception as e:
                                logger.warning("Skill evolution failed for %s: %s", skill.id, e)

        # Post-pipeline: World model update + change detection
        if self._services.world_model and result.ideas:
            await self._services.world_model.update_from_run(result, self._provider)
            logger.info("World model updated")

            # Check for significant changes and re-evaluate goals
            if self._services.kg and getattr(self._settings, "versioning_enabled", True):
                from backend.pipeline.knowledge.change_detector import WorldModelChangeDetector
                detector = WorldModelChangeDetector(self._services.kg, contradiction_scanner=self._services.contradiction_scanner)
                summary = await detector.check_and_notify(
                    goal_manager=getattr(self, "_goal_manager", None),
                )
                if summary and summary.severity.value != "low":
                    logger.info(
                        "Change detection: %s severity, %d changes",
                        summary.severity.value, summary.total_changes,
                    )

        # Post-pipeline: Fire-and-forget memory extraction
        if self._services.memory:
            asyncio.create_task(self._background_memory_extraction(result, run_id))

        # Hook: pipeline.complete
        await self._services.hooks.dispatch_sync_safe(
            "pipeline.complete",
            {
                "run_id": run_id,
                "ideas_count": len(result.ideas),
                "gaps_count": len(result.gaps),
                "proposals_count": len(result.proposals),
            },
        )

        logger.info("=== Pipeline Complete ===")
        self._persistence.mark_run_completed(db_run_id)

        # BATCH-190: Run completed notification
        if self._notifier:
            try:
                from backend.pipeline.notifications.gateway import Notification, PipelineEvent
                n_gaps = len(result.gaps) if result.gaps else 0
                n_ideas = len(result.ideas) if result.ideas else 0
                n_proposals = len(result.proposals) if result.proposals else 0
                await self._notifier.send(Notification(
                    event=PipelineEvent.RUN_COMPLETED,
                    run_id=run_id, strategy=strategy, domain=domain,
                    message=f"Pipeline completed: {n_gaps} gaps, {n_ideas} ideas, {n_proposals} proposals",
                    data={"gaps": n_gaps, "ideas": n_ideas, "proposals": n_proposals},
                ))
            except Exception:
                pass

        # Persist cost events
        if self._cost_tracker and self._cost_tracker._events:
            cost_dir = getattr(self._settings, "cost_persist_dir", "./data/costs")
            self._cost_tracker.persist(f"{cost_dir}/{run_id}.jsonl")

        # Session: complete run record
        if session_id and self._services.session_manager:
            tokens = self._cost_tracker.total_tokens if self._cost_tracker else 0
            cost = self._cost_tracker.total_cost if self._cost_tracker else 0.0
            self._services.session_manager.complete_run(session_id, run_id, tokens_used=tokens, cost_usd=cost)

        # Phase 7: Write journal at pipeline end
        if self._integration:
            self._integration.journal_note(
                "pipeline", "Pipeline completed",
                {"ideas": len(result.ideas), "gaps": len(result.gaps)},
            )
            notes_path, readme_path = self._integration.journal_write()
            if notes_path:
                logger.info("Research journal written to %s", notes_path)

        return result

    # ── Durable Execution: Resume ────────────────────────────────────

    async def resume(
        self,
        run_id: str,
        domain: str = "AI/NLP",
        search_queries: list[str] | None = None,
        max_gaps: int = 5,
        export_format: str | None = "markdown",
        max_stage_retries: int = 2,
    ) -> PipelineResult | None:
        """Resume a previously failed/interrupted pipeline run from checkpoint.

        Loads the checkpoint, skips completed stages, and continues from the
        next unfinished stage. Returns None if no checkpoint found.
        """
        checkpoint = self._persistence.load_checkpoint(run_id)
        if not checkpoint:
            logger.warning("No checkpoint found for run %s", run_id)
            return None

        completed_names = {s.stage_name for s in checkpoint.stages if s.status == StageStatus.COMPLETED}
        logger.info(
            "Resuming run %s: %d/%d stages already completed",
            run_id,
            len(completed_names),
            len(checkpoint.stages),
        )

        result = PipelineResult()
        result.run_id = run_id
        params = {}
        db_run_id = None

        # State reconstruction: load prior outputs from database
        db_run = self._persistence.get_run_by_uuid(run_id)
        if db_run:
            db_run_id = db_run.id
            try:
                loaded_gaps = self._persistence.load_gaps(db_run_id)
                if loaded_gaps:
                    result.gaps = loaded_gaps
                    logger.info("Reconstructed %d gaps from database", len(loaded_gaps))
            except Exception as exc:
                logger.warning("Failed to reconstruct gaps: %s", exc)
            try:
                loaded_ideas = self._persistence.load_ideas(db_run_id)
                if loaded_ideas:
                    result.ideas = loaded_ideas
                    logger.info("Reconstructed %d ideas from database", len(loaded_ideas))
            except Exception as exc:
                logger.warning("Failed to reconstruct ideas: %s", exc)

        # Cross-stage context: load additional persisted outputs
        if self._services.cross_stage_ctx:
            try:
                prior = await self._services.cross_stage_ctx.load_prior_context(run_id, "export")
                if prior:
                    ctx_params = {"reconstructed_context": prior}
                    params.update(ctx_params)
                    logger.info("Loaded cross-stage context with %d stages", len(prior))
            except Exception as exc:
                logger.warning("Failed to load cross-stage context: %s", exc)

        ctx = StageContext(
            result=result,
            domain=domain,
            run_id=run_id,
            db_run_id=db_run_id,
            params=params,
            search_queries=search_queries,
            max_gaps=max_gaps,
            rounds=self._settings.generation_rounds,
            ideas_per=self._settings.ideas_per_round,
            export_format=export_format,
        )

        for stage in self._stages:
            if stage.name in completed_names:
                logger.info("Skipping completed stage: %s", stage.name)
                continue

            logger.info("=== [RESUME] %s ===", stage.name.replace("_", " ").title())

            # Retry logic with exponential backoff
            for attempt in range(max_stage_retries + 1):
                try:
                    t0 = time.time()
                    checkpoint.mark_stage_running(stage.name)
                    self._persistence.save_checkpoint(checkpoint)

                    with create_span(SpanKind.STAGE, f"{stage.name} (resume)", run_id=run_id):
                        prepared_ctx = await self._compaction.prepare_context(ctx, stage.name)
                        should_continue = await stage.execute(prepared_ctx)

                    elapsed = time.time() - t0
                    self._record_stage(stage.name, t0)
                    await self._services.hooks.dispatch_sync_safe(
                        "pipeline.stage.complete",
                        {"stage": stage.name, "elapsed": elapsed, "run_id": run_id},
                    )

                    checkpoint.mark_stage_completed(stage.name)
                    self._persistence.save_checkpoint(checkpoint)
                    break  # Success, exit retry loop
                except Exception as e:
                    logger.error(
                        "Stage %s failed (attempt %d/%d): %s",
                        stage.name, attempt + 1, max_stage_retries + 1, e,
                    )
                    if attempt == max_stage_retries:
                        checkpoint.mark_stage_failed(stage.name, str(e))
                        self._persistence.save_checkpoint(checkpoint)
                        logger.error("Stage %s exhausted retries. Checkpoint saved.", stage.name)
                        return result
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)

            # Persistence (same as normal run)
            if stage.name == "literature_search":
                self._persistence.persist_papers(ctx.all_papers, db_run_id)
            elif stage.name == "gap_analysis":
                self._persistence.persist_gaps(result, db_run_id)
            elif stage.name == "feasibility_scoring":
                self._persistence.persist_ideas(result, db_run_id)
            elif stage.name == "proposal_synthesis":
                self._persistence.persist_proposals(result, db_run_id)

            self._collect_warnings(result)
            if not should_continue:
                return result

        logger.info("=== Resumed Pipeline Complete ===")
        self._persistence.mark_run_completed(db_run_id)
        return result

    # ── Autonomous Cycle ─────────────────────────────────────────────

    async def _transition_and_dispatch(self, trigger: str) -> None:
        """Transition state machine and dispatch hook event."""
        if not self._services.state_machine:
            return
        old = self._services.state_machine.current_state
        self._services.state_machine.transition(trigger)
        await self._services.hooks.dispatch_sync_safe(
            "state.transition",
            {"from": old.value, "to": self._services.state_machine.current_state.value, "trigger": trigger},
        )

    async def autonomous_cycle(
        self,
        domain: str = "AI/NLP",
        max_autonomous_runs: int | None = None,
    ) -> list[PipelineResult]:
        """Run autonomous research cycles using the consciousness state machine."""
        if not self._services.state_machine:
            logger.warning("Autonomy not enabled. Set EROCK_AUTONOMY_ENABLED=true.")
            return []

        max_runs = max_autonomous_runs or self._settings.autonomy_max_autonomous_runs
        results: list[PipelineResult] = []

        for run_idx in range(max_runs):
            state = self._services.state_machine.current_state
            logger.info("Autonomous cycle %d/%d — state: %s", run_idx + 1, max_runs, state.value)

            if state.value == "idle":
                if self._services.state_machine.should_explore():
                    await self._transition_and_dispatch("idle_timeout")
                    continue
                else:
                    logger.info("Idle — waiting for trigger. Ending autonomous cycle.")
                    break

            if state.value == "exploring":
                search_queries = None
                if self._services.curiosity:
                    suggestion = await self._services.curiosity.suggest_exploration_topic()
                    if suggestion:
                        search_queries = suggestion.get("search_queries")
                        self._services.curiosity.record_explored_topic(suggestion.get("topic", domain))
                        logger.info("Curiosity suggests: %s", suggestion.get("topic"))

                        # Persist curiosity suggestion to memory
                        if self._services.memory:
                            from backend.pipeline.knowledge.truth import TruthValue
                            from backend.pipeline.memory.models import MemoryEntry, MemoryType

                            try:
                                entry = MemoryEntry(
                                    id="",
                                    content=f"Curiosity exploration: {suggestion.get('topic', domain)}",
                                    memory_type=MemoryType.EPISODIC,
                                    namespace="curiosity_exploration",
                                    truth=TruthValue.from_observation(frequency=0.7),
                                    tags=["curiosity", "autonomous"],
                                    created_at=datetime.now(),
                                )
                                await self._services.memory.store(entry)
                            except Exception as e:
                                logger.warning("Failed to persist curiosity topic: %s", e)

                result = await self.run(
                    domain=domain,
                    search_queries=search_queries,
                )
                results.append(result)

                if result.gaps:
                    await self._transition_and_dispatch("new_high_confidence_gap")
                else:
                    await self._transition_and_dispatch("no_gaps_found")
                continue

            if state.value == "focused":
                result = await self.run(domain=domain)
                results.append(result)
                await self._transition_and_dispatch("generation_complete")
                continue

            if state.value == "contemplating":
                await self._transition_and_dispatch("analysis_complete")
                continue

            if state.value == "dreaming":
                if self._services.memory:
                    await self._services.memory.consolidate()  # type: ignore[union-attr]
                    await self._services.memory.apply_decay(self._settings.memory_decay_rate)  # type: ignore[union-attr]
                    logger.info("Dreaming: memory consolidated and decayed")

                await self._transition_and_dispatch("consolidation_complete")
                continue

        logger.info("Autonomous cycle complete. %d runs executed.", len(results))
        return results

    # ── Helpers ──────────────────────────────────────────────────────

    async def _execute_stage_with_retry(
        self, stage: PipelineStage, ctx: StageContext, checkpoint: RunCheckpoint
    ) -> bool:
        """Delegate to StageExecutor."""
        return await self._executor.execute_with_retry(stage, ctx, checkpoint)

    def _record_stage(self, stage_name: str, start_time: float) -> None:
        """Delegate to StageExecutor."""
        self._executor.record_stage(stage_name, start_time, self._STAGE_ORDER)

    def _verify_references(self, result: PipelineResult, ctx: StageContext) -> None:
        """Delegate to ResultProcessor."""
        self._processor.verify_references(result, ctx)

    @staticmethod
    def _extract_stage_fingerprint(stage_name: str, result: PipelineResult) -> str:
        """Delegate to ResultProcessor."""
        return ResultProcessor.extract_stage_fingerprint(stage_name, result)

    def _evaluate_pipeline(self, result: PipelineResult, ctx: StageContext) -> None:
        """Delegate to ResultProcessor."""
        self._processor.evaluate_pipeline(result, ctx)

    def _should_stop(self) -> bool:
        """Delegate to ResultProcessor."""
        return self._processor.should_stop(
            self._services.budget, self._cost_tracker, self._settings)

    async def _persist_stage_context(
        self, run_id: str, stage_name: str, ctx: StageContext, result: PipelineResult
    ) -> None:
        """Delegate to ResultProcessor."""
        await self._processor.persist_stage_context(run_id, stage_name, ctx, result)

    def _collect_warnings(self, result: PipelineResult) -> None:
        """Delegate to ResultProcessor."""
        self._processor.collect_warnings(result)

    def _persist_stage_report(self, result: PipelineResult, db_run_id: int | None) -> None:
        """Delegate to ResultProcessor."""
        self._processor.persist_stage_report(result, db_run_id)

    async def _background_memory_extraction(self, result: PipelineResult, run_id: str) -> None:
        """Delegate to ResultProcessor."""
        await self._processor.background_memory_extraction(
            result, run_id, self._provider, self._services.memory)

    async def start_scheduler(self) -> dict | None:
        """Start the autonomous scheduler."""
        if not self._services.scheduler:
            return None
        await self._services.scheduler.start()
        return self._services.scheduler.status()

    async def stop_scheduler(self) -> dict | None:
        """Stop the autonomous scheduler."""
        if not self._services.scheduler:
            return None
        await self._services.scheduler.stop()
        return self._services.scheduler.status()

    def scheduler_status(self) -> dict | None:
        """Get scheduler status."""
        if not self._services.scheduler:
            return None
        return self._services.scheduler.status()
