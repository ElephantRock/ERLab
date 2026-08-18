"""Pipeline orchestrator — coordinates all research pipeline stages."""

import logging
import time
from datetime import datetime

from backend.config import get_settings
from backend.pipeline.compaction.middleware import CompactionMiddleware
from backend.pipeline.evaluation.proposal_evaluator import ProposalEvaluator
from backend.pipeline.execution.run_state import RunCheckpoint
from backend.pipeline.persistence import PipelinePersistence
from backend.pipeline.reflection.reflector import ReflectionStage
from backend.pipeline.result import PipelineOutcome, PipelineResult, StageReport
from backend.pipeline.stages import (
    AdversarialReviewStage,
    CitationAuditStage,
    EvaluationStage,
    ExperimentExecutionStage,
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
from backend.pipeline.synthesis.reference_validator import ReferenceValidator
from backend.pipeline.tracing.processor import InMemoryProcessor
from backend.pipeline.verification.proposal_deepener import ProposalDeepener
from backend.pipeline.verification.reference_verifier import ReferenceVerifier
from backend.providers.base import LLMProvider
from backend.providers.provider_factory import CostTracker, get_registry
from backend.providers.token_counter import TokenCounter

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
        "experiment_execution",  # Phase 5: opt-in, no-op unless experiment_spec_id in params
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
        # B-COST-01 (Commit 8): create a CostTracker and register it with the
        # provider registry BEFORE creating the provider, so that the factory
        # wires the cost callback into every provider it constructs. Without
        # this, complete_with_usage fires _report_cost into a None callback
        # and zero cost events are captured across the entire pipeline run.
        if self._registry.cost_tracker is None:
            self._registry.set_cost_tracker(CostTracker())
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

        # ── Universal Model Manager (Phase 2) ────────────────────
        self._model_manager = None
        try:
            from backend.providers.model_manager import get_model_manager
            mm = get_model_manager()
            if mm.is_initialized:
                self._model_manager = mm
                assignments = mm.get_assignments()
                logger.info(
                    "Universal Model Manager wired to orchestrator (%d stages assigned)",
                    len(assignments),
                )
        except Exception as e:
            logger.debug("ModelManager not available, using legacy routing: %s", e)

        # Stage name aliases: orchestrator uses different names than selector
        self._mm_stage_aliases = {
            "proposal_deepening": "deepening",
        }

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

        # ── LLM Gateway (control plane) ───────────────────────────
        from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
        from backend.pipeline.gateway.gateway import LLMGateway
        from backend.pipeline.gateway.gateway_provider import GatewayProvider
        from backend.pipeline.gateway.token_budget import TokenBudgeter

        self._capability_registry = ModelCapabilityRegistry()
        self._token_budgeter = TokenBudgeter(
            default_context=getattr(settings, 'lmstudio_max_tokens', 4096),
        )
        self._gateway = LLMGateway(
            capability_registry=self._capability_registry,
            token_budgeter=self._token_budgeter,
            default_model=self._provider.default_model if hasattr(self._provider, 'default_model') else '',
        )

        # Set the provider function that executes actual LLM calls
        inner_provider = self._provider
        # Capture the non-usage structured path for the rare fallback where a
        # provider has no usage-aware structured method. Aliased so the intent
        # (single provider request, honest about the accounting gap) reads at
        # the call site without reintroducing the old direct-call shape.
        _structured_fallback = inner_provider.structured_output
        async def _gateway_provider_fn(*, messages, temperature, max_tokens, schema=None, tools=None, stage="", run_id=None):
            # The authoritative stage and run_id arrive from LLMGateway.call(),
            # which propagates them from the LLMRequest constructed by
            # GatewayProvider. Fall back to the orchestrator's current run_id
            # only when the gateway did not supply one (backward-compatible
            # internal callers).
            if run_id is None:
                run_id = getattr(self, "_current_run_id", None)
            if schema:
                # Route schema calls through the usage-aware boundary so each
                # structured request produces an authoritative token receipt.
                # Falls back only for providers without the usage-aware path,
                # recording the gap as partial accounting.
                if hasattr(inner_provider, "structured_output_with_usage"):
                    resp = await inner_provider.structured_output_with_usage(
                        messages, schema, temperature, stage=stage, run_id=run_id,
                    )
                    structured = getattr(resp, "structured", None)
                    if structured is not None:
                        return structured
                    # Usage path returned no parseable structure — mark the run
                    # as having an unaccounted provider call rather than issuing
                    # a second plain request to paper over the gap.
                    if self._cost_tracker is not None:
                        self._cost_tracker.mark_accounting_partial(
                            run_id, "structured_output_with_usage returned no structured payload"
                        )
                    return {}
                # Provider lacks a usage-aware structured path: the call is
                # billable but cannot be attributed — record the accounting gap.
                if self._cost_tracker is not None:
                    self._cost_tracker.mark_accounting_partial(
                        run_id, "provider lacks structured_output_with_usage"
                    )
                return await _structured_fallback(messages, schema, temperature)
            if tools:
                resp = await inner_provider.complete_with_tools(messages, tools, temperature, max_tokens)
                return resp.content if hasattr(resp, 'content') else str(resp)
            # B-COST-01: prefer the usage-enabled path so per-call token counts
            # and cost fire through _report_cost (wired to CostTracker). Falls
            # back to complete() for providers that do not implement it.
            if hasattr(inner_provider, "complete_with_usage"):
                resp = await inner_provider.complete_with_usage(
                    messages, temperature, max_tokens, stage=stage, run_id=run_id,
                )
                return resp.content if hasattr(resp, "content") else str(resp)
            return await inner_provider.complete(messages, temperature, max_tokens)

        self._gateway.set_provider_fn(_gateway_provider_fn)

        # ── SmartRouter (dry-run by default) ──────────────────────
        try:
            from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
            from backend.pipeline.routing.dry_run_logger import DryRunLogger
            from backend.pipeline.routing.smart_router import SmartRouter
            from backend.pipeline.routing.stage_contract import get_smart_router_config

            router_config = get_smart_router_config()
            if router_config.get("enabled", False):
                lookup = CertifiedCapabilityLookup()
                smart_router = SmartRouter(
                    lookup, mode=router_config.get("mode", "dry_run"),
                    ranking_weights=router_config.get("ranking_weights"),
                )
                dry_run_logger = DryRunLogger(
                    log_dir="data/model_certification/routing_logs"
                )
                self._gateway.set_smart_router(
                    smart_router,
                    mode=router_config.get("mode", "dry_run"),
                    dry_run_logger=dry_run_logger,
                    enforced_stages=router_config.get("enforced_stages", []),
                )
                logger.info(
                    "SmartRouter enabled: mode=%s, enforced_stages=%s",
                    router_config.get("mode", "dry_run"),
                    router_config.get("enforced_stages", []),
                )
        except Exception as e:
            logger.warning("SmartRouter initialization failed (non-fatal): %s", e)

        # Wrap provider through gateway
        self._provider = GatewayProvider(self._gateway, inner_provider)

        # ── Stage-Aware Provider (Phase 3) ────────────────────────
        # All 88 LLM call sites automatically route to the right model
        # via contextvars — no service-file edits needed.
        if self._model_manager:
            from backend.providers.stage_context import StageAwareProvider
            self._provider = StageAwareProvider(self._provider, model_manager=self._model_manager)
            logger.info("StageAwareProvider active: all LLM calls route via ModelManager")

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
            global_token_limit=settings.budget_max_tokens,
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

        from backend.pipeline.orchestrator.stage_lifecycle import StageLifecycle
        self._lifecycle = StageLifecycle(
            services=self._services,
            settings=settings,
            persistence=self._persistence,
            integration=self._integration,
            processor=self._processor,
            provider=self._provider,
            cost_tracker=self._cost_tracker,
            compaction=self._compaction,
            token_counter=self._token_counter,
            notifier=None,  # Set per-run in run()
            ccw=None,  # Set per-run in run()
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
            "run_id: (not generated -- dry run)",
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
            # Default ALL known stages to disabled, then enable only those listed
            ALL_KNOWN_STAGES = [
                "literature_search", "ingestion", "gap_analysis", "gap_reflection",
                "idea_generation", "idea_reflection", "novelty_checking", "feasibility_scoring",
                "mechanical_metrics", "proposal_synthesis", "adversarial_review", "evaluation",
                "paper_synthesis", "citation_audit", "proposal_deepening", "export", "trimmer",
            ]
            stages = {name: StageConfig(enabled=False) for name in ALL_KNOWN_STAGES}
            for name in strat_yaml.get("stages", []):
                stages[name] = StageConfig(enabled=True)
            return StrategyConfig(
                name=strategy_name,
                description=strat_yaml.get("description", ""),
                stages=stages,
            )
        except (FileNotFoundError, KeyError, ValueError, TypeError) as e:
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
        # Try ModelManager first (knows all discovered models)
        if self._model_manager:
            try:
                catalog = self._model_manager.get_catalog()
                for model in catalog.get_all():
                    if model.model_id == model_id or model.display_name == model_id:
                        return self._model_manager._get_or_create_provider(model)
            except (KeyError, ValueError, RuntimeError):
                pass

        # Legacy fallback
        from backend.config import get_settings
        from backend.providers.provider_factory import create_provider
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

        Uses ModelManager's adversarial_review assignment if available,
        otherwise falls back to the thinking provider for review while
        the synthesizer uses the generation provider.
        """
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer

        # Try ModelManager for a dedicated adversarial review model
        mm_review_provider = None
        if self._model_manager:
            try:
                mm_review_provider = self._model_manager.get_provider("adversarial_review")
                mm_model = self._model_manager.get_stage_model("adversarial_review")
                if mm_model:
                    logger.info(
                        "Adversarial review using ModelManager: '%s' (from %s)",
                        mm_model.model_id, mm_model.endpoint_url,
                    )
            except Exception as e:
                logger.debug("ModelManager adversarial_review failed, using legacy: %s", e)
                mm_review_provider = None

        reviewer = AdversarialReviewer(mm_review_provider or thinking_provider or self._provider)
        return AdversarialReviewStage(
            reviewer=reviewer,
            synthesizer=synthesizer,
            generation_provider=self._provider,
            thinking_provider=mm_review_provider or thinking_provider,
        )

    def _load_adaptive_config(self) -> dict:
        """Load the adaptive_search block from pipeline.yaml.

        Returns empty dict if the block is absent or YAML is unavailable.
        """
        try:
            from backend.pipeline.dag.config import ConfigLoader
            config = ConfigLoader().load()
            search = config.get("search", {})
            return search.get("adaptive_search", {})
        except Exception:
            return {}

    def _build_stages(self) -> list[PipelineStage]:
        ref_validator = ReferenceValidator(store=self._services.store)

        # Build the idea-generation stage. fast_scan must stay lightweight:
        # it intentionally skips tree search but still needs ideas so its
        # feasibility + FastProposalSynthesizer stages are reachable.
        idea_stage: PipelineStage
        if self._strategy_name == "fast_scan":
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
            logger.info("fast_scan: lightweight IdeaGenerationStage (tree search disabled)")
        elif getattr(self._settings, "tree_of_thought_enabled", False):
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
            LiteratureSearchStage(
                self._services.search,
                self._services.hooks,
                gateway=self._gateway,
                persistence=self._persistence,
                adaptive_config=self._load_adaptive_config(),
                strategy_name=self._strategy_name,
            ),
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
            ExperimentExecutionStage(),
            PaperSynthesisStage(provider=self._provider),
            CitationAuditStage(provider=thinking_provider),
            ProposalDeepeningStage(deepener=ProposalDeepener(provider=self._provider)),
            ExportStage(self._services.export),
        ]

    # ── Main Pipeline ────────────────────────────────────────────────

    def _enforce_required_provider_readiness(self):
        """Q2: fail-closed required-provider readiness for THIS run.

        Returns the LMStudioManager on success (or None when not
        required / opted out). Raises ProviderUnavailableError before
        research execution when a required provider cannot establish
        readiness. Called by both run() and resume().
        """
        if not self._settings.enforce_provider_readiness:
            return None
        from backend.pipeline.orchestrator.readiness import (
            ProviderUnavailableError,
            enforce_required_provider_readiness,
            lmstudio_required_for_run,
        )
        if not lmstudio_required_for_run(self._settings):
            return None
        lmstudio_url = getattr(
            self._settings, 'lmstudio_base_url', None,
        )
        if not lmstudio_url:
            # Q2 review P1: LM Studio is REQUIRED but no endpoint URL
            # is configured — readiness can never be established. Fail
            # closed instead of silently proceeding.
            raise ProviderUnavailableError(
                "lmstudio",
                "required by this run but lmstudio_base_url is empty",
            )
        mgr, preflight = enforce_required_provider_readiness(
            self._settings,
        )
        self._lmstudio_mgr = mgr  # for grammar enforcement
        # Operation Executor: authoritative model lifecycle owner
        from backend.pipeline.operations.executor import OperationExecutor
        self._operation_executor = OperationExecutor(mgr)
        logger.info(
            "LM Studio preflight OK: %s ctx=%d%s",
            preflight.model_id, preflight.context_length,
            " (auto-loaded)" if preflight.had_to_load else
            " (reloaded)" if preflight.had_to_reload else "",
        )
        return mgr

    async def run(
        self,
        domain: str = "AI/NLP",
        research_question: str | None = None,
        search_queries: list[str] | None = None,
        max_gaps: int = 5,
        generation_rounds: int | None = None,
        ideas_per_round: int | None = None,
        export_format: str | None = "markdown",
        run_id: str | None = None,
        session_id: str | None = None,
        skip_stages: set[str] | None = None,
        proposal_depth: str | None = None,
        novelty_depth: str | None = None,
        idea_diversity: str | None = None,
        experiment_spec_id: str | None = None,
        autonomous_experiment_enabled: bool = False,
    ) -> PipelineResult:
        """Execute the full pipeline from literature search to export.

        Stage gating is controlled by the active strategy preset from
        pipeline.yaml — the single source of truth. No run_* booleans.

        Args:
            skip_stages: Set of stage names to skip (used by --resume to avoid
                re-running already-completed stages).
            proposal_depth: "concise" | "standard" | "detailed"
            novelty_depth: "light" | "standard" | "thorough"
            idea_diversity: "focused" | "balanced" | "exploratory"
        """
        # Resolve quality parameters into effective values
        from backend.pipeline.quality.quality_params import resolve_all
        quality_settings = resolve_all(proposal_depth, novelty_depth, idea_diversity)
        result = PipelineResult()
        rounds = generation_rounds or self._settings.generation_rounds
        ideas_per = ideas_per_round or self._settings.ideas_per_round

        run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        result.run_id = run_id
        self._current_run_id = run_id  # BATCH-184: for StageLogger
        self._stage_logger = None  # Reset logger for new run

        # BATCH-185: Reset doom loop detection for this run
        # BATCH-191: Initialize Consolidated Context Window
        from backend.pipeline.monitoring.ccw import ConsolidatedContextWindow
        self._ccw = ConsolidatedContextWindow()

        # Gateway: Preflight LM Studio — ensure model loaded with sufficient context
        # Q2 (Case-3 3B–3D specimens): required-provider readiness is a
        # precondition, not a warning — fail closed BEFORE research
        # execution. Shared with resume() via the method.
        _lmstudio_mgr = self._enforce_required_provider_readiness()
        _lmstudio_url = getattr(
            self._settings, 'lmstudio_base_url', None,
        )

        # Gateway: Probe LM Studio for live model capabilities
        if hasattr(self, '_capability_registry') and self._capability_registry:
            if _lmstudio_url:
                try:
                    await self._capability_registry.refresh(_lmstudio_url)
                    # Update budgeter with live context from probed model
                    default_model = self._gateway._default_model
                    if default_model:
                        caps = self._capability_registry.get(default_model)
                        self._token_budgeter._default_context = caps.context_window
                        logger.info(
                            "Gateway ready: model=%s, ctx=%d, loaded=%s",
                            caps.model_id, caps.context_window, caps.loaded,
                        )
                except Exception as e:
                    logger.warning("Gateway probe failed, using static defaults: %s", str(e)[:80])

        # BATCH-190: Initialize notification gateway
        try:
            from backend.pipeline.notifications.gateway import create_notifier
            webhook_url = getattr(self._settings, 'notification_webhook_url', None)
            self._notifier = create_notifier(webhook_url)
        except Exception:
            self._notifier = None

        # BATCH-190: Send run_started notification
        if self._notifier:
            try:
                from backend.pipeline.notifications.gateway import Notification, PipelineEvent
                await self._notifier.send(Notification(
                    event=PipelineEvent.RUN_STARTED,
                    run_id=run_id, strategy=self._strategy_name, domain=domain,
                    message=f"Pipeline started: {self._strategy_name} on '{domain}'",
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

        # Push per-run instances into lifecycle
        self._lifecycle.reset_doom()
        self._lifecycle.set_run_context(
            ccw=self._ccw,
            notifier=self._notifier,
            integration=self._integration,
        )
        # Also update the result processor's integration reference
        self._processor._integration = self._integration
        self._processor._cross_stage_ctx = self._services.cross_stage_ctx

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
            from datetime import timedelta as _td

            from backend.pipeline.execution.watchdog import PipelineWatchdog
            watchdog = PipelineWatchdog(self._persistence, timeout=_td(minutes=30))
            stale_count = watchdog.check_sync(exclude_run_id=run_id)
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
        if experiment_spec_id:
            params["experiment_spec_id"] = experiment_spec_id
        if autonomous_experiment_enabled:
            params["autonomous_experiment_enabled"] = True
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

        # Apply user-specified quality parameters (override evolved defaults)
        # Quality params were already resolved at the top of run()
        # Now apply them to the pipeline components:
        effective_temp = quality_settings["effective_ideator_temperature"]
        effective_top_k = quality_settings["effective_novelty_top_k"]

        # Wire ideator temperature (only if user explicitly set diversity)
        if idea_diversity and self._services.agent:
            self._services.agent.set_temperature_overrides({
                "ideator_temperature": effective_temp,
            })
            logger.info("Idea diversity '%s' → temperature=%.2f", idea_diversity, effective_temp)

        # Wire novelty top_k (only if user explicitly set depth)
        if novelty_depth and hasattr(self, '_services') and self._services.novelty:
            self._services.novelty._top_k = effective_top_k
            logger.info("Novelty depth '%s' → top_k=%d", novelty_depth, effective_top_k)

        # Wire proposal depth into synthesizer effective min_words
        if proposal_depth and hasattr(self, '_services') and self._services.synthesizer:
            from backend.pipeline.quality.quality_params import resolve_min_words
            self._services.synthesizer._effective_min_words = resolve_min_words(proposal_depth)
            logger.info(
                "Proposal depth '%s' → abstract min=%d words, method min=%d words",
                proposal_depth,
                self._services.synthesizer._effective_min_words.get('abstract', 150),
                self._services.synthesizer._effective_min_words.get('proposed_method', 600),
            )

        # Store effective quality settings in params for visibility
        params["quality_settings"] = quality_settings

        result.params_used = params

        # Create DB run record
        db_run_id = self._persistence.create_run_record(domain, params, session_id=session_id, run_id=run_id)
        # Case-4 R1 (adjudicated GENERIC_PRODUCT_DEFECT, 2026-08-18): the
        # initial run record is the run's persistence authority.
        # create_run_record() returns None when its insert fails (the
        # warning is already recorded in persistence warnings). A run that
        # cannot establish its own run record must fail closed BEFORE any
        # research stage executes — it must never warn, discard
        # persistence, run the stages, and finalize as SUCCEEDED.
        if db_run_id is None:
            result.outcome = PipelineOutcome.FAILED_EXECUTION
            result.terminal_stage = "persistence_initialization"
            result.terminal_reason = (
                "required initial run record could not be created"
                " (create_run_record returned None; see persistence"
                " warnings) — failing closed before research execution"
            )
            result.persistence_warnings.extend(
                list(self._persistence.get_warnings())
            )
            logger.error(
                "Run-record creation failed for run %s — aborting before"
                " research execution (persistence authority unavailable)",
                run_id,
            )
            return result

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
            research_question=research_question,
            run_id=run_id,
            db_run_id=db_run_id,
            params=params,
            search_queries=search_queries,
            max_gaps=max_gaps,
            rounds=rounds,
            ideas_per=ideas_per,
            export_format=export_format,
        )

        # Phase 6: Memory warm-start — load lessons from prior runs
        if getattr(self._settings, "warm_start_enabled", True) and self._services.memory:
            try:
                from backend.pipeline.memory.warm_start import WarmStartLoader
                loader = WarmStartLoader(self._services.memory)
                warm_hints = await loader.load_hints(domain)
                if warm_hints.has_hints:
                    ctx.params["warm_start_hints"] = warm_hints.to_dict()
                    logger.info(
                        "Warm-start: %d lessons, %d effective params, %d avoided directions",
                        len(warm_hints.lessons),
                        len(warm_hints.effective_params),
                        len(warm_hints.avoided_directions),
                    )
            except Exception as e:
                logger.warning("Warm-start failed (non-fatal): %s", e)

        # Create run checkpoint for durable execution
        checkpoint = RunCheckpoint.create_new(
            run_id=run_id,
            stage_names=[s.name for s in self._stages],
        )
        checkpoint.mark_stage_running(self._stages[0].name)
        self._persistence.save_checkpoint(checkpoint)

        # Execute stages via RunCoordinator (extracted from inline loop)
        from backend.pipeline.orchestrator.run_coordinator import RunCoordinator
        coordinator = RunCoordinator(self)
        all_completed = await coordinator.execute_stage_loop(
            stages=self._stages,
            ctx=ctx,
            result=result,
            checkpoint=checkpoint,
            run_id=run_id,
            domain=domain,
            db_run_id=db_run_id,
            skip_stages=skip_stages,
        )

        # Fill not_reached for stages not in the loop (e.g. strategy excluded)
        reported_names = {r.name for r in result.stage_report}
        for stage_name in self._STAGE_ORDER:
            if stage_name not in reported_names:
                result.stage_report.append(StageReport(
                    name=stage_name,
                    status="not_reached",
                ))

        # Phase 1: Decision Gate — retry targeted stages if quality is low
        if getattr(self._settings, "decision_gate_enabled", True):
            try:
                from backend.pipeline.orchestrator.decision_gate import DecisionGate
                decision_gate = DecisionGate(
                    quality_threshold=getattr(self._settings, "decision_gate_quality_threshold", 0.45),
                    abort_threshold=getattr(self._settings, "decision_gate_abort_threshold", 0.15),
                    max_retries=getattr(self._settings, "decision_gate_max_retries", 1),
                    provenance_min_coverage=getattr(self._settings, "provenance_min_coverage", 0.4),
                )

                for retry_attempt in range(decision_gate._max_retries + 1):
                    decision = decision_gate.evaluate(result, retry_attempt)

                    if decision.action != "retry":
                        logger.info(
                            "Decision Gate: %s (score=%.2f, reason=%s)",
                            decision.action, decision.quality_score, decision.reason,
                        )
                        break

                    logger.info(
                        "Decision Gate: retry %d/%d — re-running %s (score=%.2f)",
                        retry_attempt + 1, decision_gate._max_retries,
                        decision.target_stages, decision.quality_score,
                    )

                    # Re-execute target stages directly
                    for target_name in decision.target_stages:
                        target_stage = next(
                            (s for s in self._stages if s.name == target_name), None
                        )
                        if target_stage is None:
                            logger.warning("Decision Gate: target stage '%s' not found", target_name)
                            continue

                        logger.info("Decision Gate: re-running stage '%s'", target_name)
                        t0 = time.time()
                        try:
                            # Reset stage-specific state
                            if target_name == "proposal_synthesis":
                                result.proposals = {}
                            elif target_name == "idea_generation":
                                result.ideas = []

                            retry_should_continue = await self._execute_stage_with_retry(
                                target_stage, ctx, checkpoint,
                            )
                            elapsed = time.time() - t0

                            # Post-stage processing for the retried stage
                            await self._lifecycle.post_stage_common(
                                target_stage, result, ctx, elapsed, run_id, domain,
                                strategy=self._strategy_name,
                            )
                            await self._lifecycle.post_stage_specific(
                                target_stage, result, ctx, run_id, db_run_id, domain,
                                strategy=self._strategy_name,
                                should_continue=retry_should_continue,
                            )

                            logger.info(
                                "Decision Gate: stage '%s' re-run completed (%.1fs)",
                                target_name, elapsed,
                            )
                        except Exception as e:
                            logger.error(
                                "Decision Gate: stage '%s' retry failed: %s",
                                target_name, e,
                            )
            except Exception as e:
                logger.warning("Decision Gate failed (non-fatal): %s", e)

        # Persist stage report to DB
        self._processor.persist_stage_report(result, db_run_id)

        # Phase 8: Pipeline quality evaluation
        self._processor.evaluate_pipeline(result, ctx)

        # ── Post-pipeline finalization (delegated) ───────────
        await self._lifecycle.post_pipeline_finalize(
            result, ctx, run_id, domain,
            strategy=self._strategy_name,
            params=params,
            db_run_id=db_run_id,
            session_id=session_id,
            ideas_per=ideas_per,
            rounds=rounds,
        )

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

        Delegates to RunCoordinator.resume_from_checkpoint().
        """
        from backend.pipeline.orchestrator.run_coordinator import RunCoordinator

        # Q2 review P1: resumed runs get the same fail-closed readiness.
        self._enforce_required_provider_readiness()

        coordinator = RunCoordinator(self)
        return await coordinator.resume_from_checkpoint(
            run_id=run_id,
            domain=domain,
            search_queries=search_queries,
            max_gaps=max_gaps,
            export_format=export_format,
            max_stage_retries=max_stage_retries,
        )

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

    def _should_stop(self) -> bool:
        """Delegate to ResultProcessor. Kept because pipeline.py patches this for cancellation."""
        return self._processor.should_stop(
            self._services.budget, self._cost_tracker, self._settings)

    # The following ResultProcessor methods are called directly via self._processor
    # from run() and the coordinator. Delegates removed to reduce indirection:
    # - verify_references(result, ctx)
    # - extract_stage_fingerprint(stage_name, result)
    # - evaluate_pipeline(result, ctx)
    # - persist_stage_context(run_id, stage_name, ctx, result)
    # - collect_warnings(result)
    # - persist_stage_report(result, db_run_id)
    # - background_memory_extraction(result, run_id, ...)

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
