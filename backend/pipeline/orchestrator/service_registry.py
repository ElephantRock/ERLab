"""Service registry — holds all subsystem instances for the pipeline orchestrator.

Extracted from PipelineOrchestrator._init_* methods to isolate service wiring
from execution logic. Each init method corresponds to a subsystem domain.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """Centralized registry for all pipeline subsystem instances.

    Attributes are set by ``init_*`` methods grouped by domain.
    Access via ``registry.<name>`` — e.g. ``registry.search``, ``registry.novelty``.
    """

    def __init__(self) -> None:
        # Will be populated by init_* methods
        self._effective = None  # EffectiveDomainConfigurations (P0.5B WP1)
        pass

    # ── Core services ────────────────────────────────────────────────

    def init_core_services(
        self,
        settings: "Settings",
        provider: "LLMProvider",
        thinking_provider: "LLMProvider | None",
        cost_tracker,
    ) -> None:
        """Core pipeline services: search, PDF, embedding, store, agents."""
        from backend.pipeline.ingestion.pdf_service import PDFService
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.pipeline.literature.search_service import SearchService

        # Build effective domain configurations (P0.5B WP1)
        from backend.pipeline.config.effective_configurations import (
            build_effective_domain_configurations,
        )
        self._effective = build_effective_domain_configurations(settings)

        self.search = SearchService()
        self.pdf = PDFService(mode=settings.s1_parser_mode, s1_parser_url=settings.s1_parser_url)

        from backend.pipeline.knowledge.embedding_providers import create_embedding_provider

        # Resolve embedding base URL: explicit override > provider-specific default
        if settings.embedding_base_url:
            embedding_base = settings.embedding_base_url.rstrip('/')
            if not embedding_base.endswith('/v1'):
                embedding_base += '/v1'
        elif settings.embedding_provider == "lmstudio":
            embedding_base = settings.lmstudio_base_url.rstrip('/') + '/v1'
        else:
            embedding_base = settings.ollama_base_url

        # Resolve the correct embedding model name.
        # LM Studio reports the model as 'text-embedding-bge-m3-embeddings' but older
        # configs may use 'text-embedding-bge-m3' (without the -embeddings suffix).
        # Query LM Studio for the actual loaded model name to avoid 400 errors.
        emb_model = settings.embedding_model
        if settings.embedding_provider == "lmstudio" and "bge-m3" in emb_model.lower():
            try:
                import httpx as _httpx
                _r = _httpx.get(f"{embedding_base}/models", timeout=5)
                if _r.status_code == 200:
                    _loaded = [m["id"] for m in _r.json().get("data", [])
                               if "bge-m3" in m["id"].lower()]
                    if _loaded and _loaded[0] != emb_model:
                        logger.info(
                            "Embedding model corrected: '%s' → '%s' (from LM Studio)",
                            emb_model, _loaded[0],
                        )
                        emb_model = _loaded[0]
            except Exception:
                pass  # fail-soft — use the configured name

        embedding_provider = create_embedding_provider(
            provider_name=settings.embedding_provider,
            model=emb_model,
            api_key=settings.openai_api_key,
            base_url=embedding_base,
            dimension=settings.embedding_dimension or None,
        )

        # Wrap with fallback if configured
        if getattr(settings, "embedding_fallback_enabled", False):
            from backend.pipeline.knowledge.embedding_providers import (
                FallbackEmbeddingProvider,
                create_embedding_provider,
            )
            fallback = create_embedding_provider(
                provider_name="ollama",
                base_url=settings.ollama_base_url,
            )
            embedding_provider = FallbackEmbeddingProvider(embedding_provider, fallback)

        self.embedding = EmbeddingService(
            embedding_provider,
            batch_size=settings.embedding_batch_size,
        )
        self.store = VectorStore(settings.chroma_persist_dir, self.embedding)
        self.embedding_valid = False  # Will be checked lazily on first run

        from backend.pipeline.knowledge.bm25_index import BM25Index
        from backend.pipeline.knowledge.retriever import TwoStageRetriever

        self.bm25 = BM25Index(settings.bm25_persist_dir)

        query_transformer = None
        if getattr(settings, "query_transform_enabled", False):
            from backend.pipeline.knowledge.query_transform import MultiQueryTransformer
            query_transformer = MultiQueryTransformer(provider)

        # Wire reranker from config
        reranker = None
        if settings.reranker_enabled:
            if getattr(settings, "reranker_type", "llm") == "cross_encoder":
                from backend.pipeline.knowledge.reranker import CrossEncoderReranker
                reranker = CrossEncoderReranker()
            else:
                from backend.pipeline.knowledge.reranker import LLMReranker
                reranker = LLMReranker(provider)

        self.retriever = TwoStageRetriever(
            vector_store=self.store,
            bm25_index=self.bm25,
            embedding_service=self.embedding,
            reranker=reranker,
            query_transformer=query_transformer,
            quality_scorer=None,
            rrf_k=getattr(settings, "rrf_k", 60),
            retrieval_mode=getattr(settings, "retrieval_mode", "hybrid"),
        )

        # Quality scorer for retrieval (Gap 1)
        if getattr(settings, "retrieval_quality_scoring_enabled", False):
            from backend.pipeline.knowledge.retrieval_quality import RetrievalQualityScorer
            self.quality_scorer = RetrievalQualityScorer()
            self.retriever._quality_scorer = self.quality_scorer
        else:
            self.quality_scorer = None

        thinking = thinking_provider or provider

        from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer
        from backend.pipeline.novelty.novelty_checker import NoveltyChecker
        from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer

        self.gap_analyzer = GapAnalyzer(thinking)
        self.novelty = NoveltyChecker(thinking, self.store, self.retriever)
        self.feasibility = FeasibilityScorer(thinking)

        # Citation-aware novelty augmentation (Gap 11)
        self.citation_traverser = None
        self.embedding_novelty_scorer = None
        # Note: _kg is initialized in init_governance; citation traverser
        # requires kg, so we set it up later in init_cross_refs()
        self._citation_novelty_enabled = getattr(settings, "citation_novelty_enabled", False)
        self._embedding_novelty_enabled = getattr(settings, "embedding_novelty_enabled", False)

        # Faithfulness checker for gap analysis (Gap 9)
        self.faithfulness_checker = None
        if getattr(settings, "faithfulness_check_enabled", False):
            from backend.pipeline.knowledge.faithfulness import FaithfulnessChecker
            self.faithfulness_checker = FaithfulnessChecker(thinking)

        # Contradiction scanner (Gap 9)
        self.contradiction_scanner = None
        if getattr(settings, "contradiction_detection_enabled", False):
            from backend.pipeline.knowledge.contradiction import ContradictionScanner
            self.contradiction_scanner = ContradictionScanner(
                kg=None,  # Set later in init_cross_refs()
                provider=provider,
                scan_interval=getattr(settings, "contradiction_scan_interval", 10),
            )

        # Forest-of-Thought and Reasoning Verifier (Gap 7)
        self.forest = None
        self.reasoning_verifier = None
        if getattr(settings, "reasoning_verification_enabled", False):
            from backend.pipeline.generation.verifier import ReasoningVerifier
            self.reasoning_verifier = ReasoningVerifier(thinking)

        # Dynamic agent factory (Gap 2)
        self.dynamic_agent_factory = None
        self.sub_goal_generator = None

        # Ensemble reviewer for proposal synthesis (Gap 6)
        ensemble_reviewer = None
        if getattr(settings, "evaluation_framework_enabled", False):
            from backend.pipeline.evaluation.ensemble_review import EnsembleReviewer
            ensemble_reviewer = EnsembleReviewer(thinking)

        from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
        self.synthesizer = ProposalSynthesizer(provider, ensemble_reviewer=ensemble_reviewer)

        from backend.pipeline.export.export_service import ExportService
        self.export = ExportService()

        # Tool registry and plugin loader
        from backend.pipeline.tools.registry import get_tool_registry
        self.tool_registry = get_tool_registry()

        from backend.pipeline.plugins.loader import PluginLoader
        self.plugin_loader = PluginLoader(
            verification_enabled=getattr(settings, "plugin_verification_enabled", False),
            allowlist_path=getattr(settings, "plugin_allowlist_path", "./data/plugins/allowlist.json"),
        )
        self.plugin_loader.load_all(self.tool_registry)

        # Agent orchestrator
        from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
        self.agent = AgentOrchestrator(
            provider, retriever=self.retriever, tool_registry=self.tool_registry
        )

        # Multi-agent system
        self.message_bus = None
        self.agent_registry = None
        self.dag_executor = None
        self.dag_agents: dict = {}
        if getattr(settings, "multi_agent_enabled", True):
            from backend.pipeline.agents.message_bus import MessageBus
            from backend.pipeline.agents.registry import AgentRegistry
            from backend.pipeline.generation.critic_agent import CriticAgent
            from backend.pipeline.generation.dag_executor import DAGExecutor
            from backend.pipeline.generation.ideator_agent import IdeatorAgent
            from backend.pipeline.generation.refiner_agent import RefinerAgent
            from backend.pipeline.generation.topology import build_default_dag

            self.message_bus = MessageBus()
            self.agent_registry = AgentRegistry(self.message_bus)

            dag = build_default_dag()
            if getattr(settings, "tree_of_thought_enabled", False):
                for n in dag.nodes:
                    if n.type.value == "loop":
                        n.config["use_tree_of_thought"] = True
                        n.config["tot_max_depth"] = getattr(settings, "tree_of_thought_max_depth", 3)
                        n.config["tot_beam_width"] = getattr(settings, "tree_of_thought_beam_width", 2)

            self.dag_executor = DAGExecutor(
                dag=dag,
                registry=self.agent_registry,
                bus=self.message_bus,
                provider=provider,
            )
            self.dag_agents = {
                "ideator": IdeatorAgent(provider, retriever=self.retriever),
                "critic": CriticAgent(provider),
                "refiner": RefinerAgent(provider),
            }

        # Dynamic agent factory (deferred, needs agent_registry)
        if getattr(settings, "dynamic_agents_enabled", False):
            from backend.pipeline.agents.dynamic_factory import DynamicAgentFactory
            self.dynamic_agent_factory = DynamicAgentFactory(
                provider=provider,
                registry=self.agent_registry or __import__(
                    "backend.pipeline.agents.registry",
                    fromlist=["AgentRegistry"],
                ).AgentRegistry(),
                bus=self.message_bus,
                max_agents=getattr(settings, "dynamic_agents_max_per_run", 5),
            )
            if getattr(settings, "sub_goal_generation_enabled", False):
                from backend.pipeline.agents.sub_goals import SubGoalGenerator
                self.sub_goal_generator = SubGoalGenerator(
                    provider=provider,
                    factory=self.dynamic_agent_factory,
                )

    def init_cross_refs(self, settings: "Settings") -> None:
        """Wire cross-references that depend on governance (kg) being initialized."""
        if self._citation_novelty_enabled and hasattr(self, "kg"):
            from backend.pipeline.novelty.citation_traversal import CitationGraphTraverser
            self.citation_traverser = CitationGraphTraverser(self.kg)
            self.novelty._citation_traverser = self.citation_traverser

        if self._embedding_novelty_enabled and hasattr(self, "embedding"):
            from backend.pipeline.novelty.embedding_scorer import EmbeddingNoveltyScorer
            from backend.pipeline.knowledge.graph_embeddings import GraphEmbeddingIndex
            graph_index = GraphEmbeddingIndex(
                persist_dir=settings.chroma_persist_dir,
                embedding_service=self.embedding,
            )
            self.embedding_novelty_scorer = EmbeddingNoveltyScorer(self.embedding, graph_index)
            self.novelty._embedding_scorer = self.embedding_novelty_scorer

        if self.contradiction_scanner and hasattr(self, "kg"):
            self.contradiction_scanner._kg = self.kg

    # ── Memory ───────────────────────────────────────────────────────

    def init_memory(self, settings: "Settings") -> None:
        from backend.pipeline.memory.service import MemoryService

        self.memory = None
        self.shared_kb = None

        if not settings.memory_enabled:
            return

        if settings.memory_tier == "tiered":
            from backend.pipeline.memory.tiers import TieredMemoryService
            self.memory = TieredMemoryService(
                working_capacity=settings.memory_working_capacity,
                archival_path=f"{settings.memory_persist_dir}/archival",
                retriever=self.retriever,
            )
            if settings.memory_shared_enabled:
                from backend.pipeline.memory.sharing import SharedKnowledgeBase
                self.shared_kb = SharedKnowledgeBase(self.memory)
        else:
            self.memory = MemoryService(
                settings.memory_persist_dir,
                retriever=self.retriever,
            )

    # ── Cross-stage context ──────────────────────────────────────────

    def init_cross_stage_context(self, settings: "Settings") -> None:
        self.cross_stage_ctx = None
        self.prompt_builder = None

        if not getattr(settings, "cross_stage_context_enabled", True):
            return
        if not self.memory:
            return

        from backend.pipeline.context.cross_stage import CrossStageContext
        from backend.pipeline.context.prompt_layers import LayeredPromptBuilder

        self.cross_stage_ctx = CrossStageContext(self.memory)
        if getattr(settings, "prompt_layers_enabled", True):
            self.prompt_builder = LayeredPromptBuilder(memory=self.memory)

    # ── Self-improvement ─────────────────────────────────────────────

    def init_self_improve(self, settings: "Settings", provider: "LLMProvider") -> None:
        from backend.pipeline.self_improve.evolution import PipelineEvolver

        self.evolver = None
        self.lesson_extractor = None
        self.evolution_engine = None
        self.ab_test_harness = None
        self.ratchet_loop = None
        self.feedback_history = None
        self.skill_registry = None
        self.skill_proposer = None
        self.skill_generator = None

        if settings.self_improve_enabled:
            from pathlib import Path
            Path(settings.self_improve_persist_dir).mkdir(parents=True, exist_ok=True)

            from backend.pipeline.self_improve.constraints import ConstraintConfig
            from backend.pipeline.self_improve.frontier import ParetoFrontier

            frontier = ParetoFrontier(f"{settings.self_improve_persist_dir}/frontier.json")
            constraint_config = ConstraintConfig(
                max_size=settings.constraint_max_size,
                max_growth_pct=settings.constraint_max_growth_pct,
                allow_empty=settings.constraint_allow_empty,
                min_sections=settings.constraint_min_sections,
            )
            from backend.pipeline.self_improve.lessons import LessonExtractor
            self.lesson_extractor = LessonExtractor(provider)
            self.evolver = PipelineEvolver(
                frontier, constraint_config=constraint_config,
                lesson_mapper=self.lesson_extractor,
            )

            # Gap 3: Verified Self-Improvement
            if getattr(settings, "evolution_engine_enabled", False):
                from backend.pipeline.self_improve.engine import EvolutionEngine
                from backend.pipeline.self_improve.ab_test import ABTestHarness
                from backend.pipeline.self_improve.ratchet import RatchetLoop
                from backend.pipeline.self_improve.feedback_history import FeedbackHistory

                self.evolution_engine = EvolutionEngine(
                    self.evolver, provider,
                    decay_rate=getattr(settings, "evolution_engine_decay_rate", 0.95),
                )
                self.ab_test_harness = ABTestHarness(
                    frontier,
                    min_confidence=getattr(settings, "ab_testing_min_confidence", 0.6),
                )
                self.ratchet_loop = RatchetLoop()
                self.feedback_history = FeedbackHistory(
                    f"{settings.self_improve_persist_dir}/feedback_history.json"
                )

        if settings.skills_enabled:
            from backend.pipeline.skills.proposer_generator import SkillGenerator, SkillProposer
            from backend.pipeline.skills.registry import SkillRegistry
            self.skill_registry = SkillRegistry(settings.skills_persist_dir)
            self.skill_proposer = SkillProposer(provider)
            self.skill_generator = SkillGenerator(provider)

    # ── Autonomy ─────────────────────────────────────────────────────

    def init_autonomy(self, settings: "Settings", cost_tracker) -> None:
        self.budget = None
        self.plan_verifier = None
        if settings.budget_enabled:
            from backend.pipeline.autonomy.budget import PlanVerifier, SimpleBudget
            self.budget = SimpleBudget(
                max_tokens=settings.budget_max_tokens,
                max_cost_usd=settings.budget_max_cost_usd,
                max_seconds=settings.budget_max_seconds,
                cost_tracker=cost_tracker,
            )
            self.plan_verifier = PlanVerifier()

        from backend.pipeline.autonomy.hooks import HookDispatcher
        self.hooks = HookDispatcher()
        self.stage_timings: dict[str, list[float]] = {}

        async def _on_stage_complete(payload: dict):
            stage = payload.get("stage", "unknown")
            elapsed = payload.get("elapsed", 0)
            self.stage_timings.setdefault(stage, []).append(elapsed)

        self.hooks.register("pipeline.stage.complete", _on_stage_complete)

        self.state_machine = None
        self.curiosity = None
        if settings.autonomy_enabled:
            from backend.pipeline.autonomy.curiosity import CuriosityDriver
            from backend.pipeline.autonomy.state_machine import ConsciousnessStateMachine
            self.state_machine = ConsciousnessStateMachine(
                idle_timeout_seconds=settings.autonomy_idle_timeout_seconds,
            )
            self.curiosity = CuriosityDriver(None)  # provider set later

        self.scheduler = None
        if getattr(settings, "autonomy_schedule_enabled", False):
            # Scheduler needs orchestrator reference — set later
            self._scheduler_settings = settings

    # ── Governance ───────────────────────────────────────────────────

    def init_governance(self, settings: "Settings", provider: "LLMProvider") -> None:
        self.governance_validator = None
        self.governance_audit = None
        self.governance_policy = None
        self.approval_manager = None

        if settings.governance_enabled:
            from backend.pipeline.governance.events import GovernanceAuditLog
            from backend.pipeline.governance.validator import OutputValidator
            self.governance_validator = OutputValidator(provider)
            self.governance_audit = GovernanceAuditLog(settings.governance_audit_path)

            from backend.pipeline.governance.policy import GovernancePolicy
            policy_path = getattr(settings, "governance_policy_path", None)
            self.governance_policy = GovernancePolicy(policy_path=policy_path) if policy_path else GovernancePolicy()

            from backend.pipeline.governance.approval import ApprovalManager
            self.approval_manager = ApprovalManager(
                timeout_seconds=getattr(settings, "governance_approval_timeout", 3600)
            )

            from backend.api.routes.governance import set_approval_manager
            set_approval_manager(self.approval_manager)

        from backend.pipeline.knowledge.graph import KnowledgeGraph
        self.kg = KnowledgeGraph(
            persist_path=settings.knowledge_graph_path,
            versioning_enabled=settings.versioning_enabled,
        )
        if settings.reactive_streams_enabled:
            from backend.pipeline.knowledge.streams import StreamRegistry
            self.kg.attach_stream_registry(StreamRegistry())

        from backend.pipeline.knowledge.world_model import WorldModel
        activation_pipeline = None
        if settings.activation_enabled:
            from backend.pipeline.knowledge.activation import (
                ActivationPipeline,
                BaseLevelDecay,
                ContextSpreading,
            )
            adaptors = [
                BaseLevelDecay(settings.activation_decay_rate),
                ContextSpreading(settings.activation_spreading_rate),
            ]
            activation_pipeline = ActivationPipeline(adaptors)
        self.world_model = WorldModel(
            settings.world_model_path, activation_pipeline=activation_pipeline
        )

        dependency_tracker = None
        if settings.dependency_tracking_enabled:
            from backend.pipeline.autonomy.dependency import GoalDependencyTracker
            dependency_tracker = GoalDependencyTracker()
        from backend.pipeline.autonomy.goals import GoalManager
        self.goal_manager = GoalManager(settings.goals_path, dependency_tracker=dependency_tracker)

    # ── Evaluation ───────────────────────────────────────────────────

    def init_evaluation(self, settings: "Settings", provider: "LLMProvider") -> None:
        self.pipeline_evaluator = None
        if not getattr(settings, "evaluation_framework_enabled", False):
            return
        from backend.pipeline.evaluation.cache import EvaluationCache
        from backend.pipeline.evaluation.pipeline_evaluator import PipelineEvaluator
        from backend.pipeline.evaluation.quality_gate import (
            QualityGate,
            QualityGateConfig,
            QualityThreshold,
        )
        from backend.pipeline.evaluation.scorer import ScoreDimension

        gate_config = QualityGateConfig(
            thresholds=[
                QualityThreshold(
                    dimension=ScoreDimension.NOVELTY,
                    min_score=settings.evaluation_novelty_min_score,
                    weight=0.3,
                ),
                QualityThreshold(
                    dimension=ScoreDimension.FEASIBILITY,
                    min_score=settings.evaluation_feasibility_min_score,
                    weight=0.3,
                ),
                QualityThreshold(
                    dimension=ScoreDimension.IMPACT,
                    min_score=settings.evaluation_impact_min_score,
                    weight=0.2,
                ),
                QualityThreshold(
                    dimension=ScoreDimension.SOUNDNESS,
                    min_score=settings.evaluation_soundness_min_score,
                    weight=0.2,
                    required=settings.evaluation_soundness_required,
                ),
            ],
            composite_threshold=settings.evaluation_composite_threshold,
            mode=settings.evaluation_quality_gate_mode,
        )
        self.pipeline_evaluator = PipelineEvaluator(
            provider=provider,
            novelty_checker=self.novelty,
            feasibility_scorer=self.feasibility,
            quality_gate=QualityGate(gate_config),
            use_geval=getattr(settings, "evaluation_geval_enabled", False),
            cache=EvaluationCache(max_size=settings.evaluation_cache_max_size),
        )

    # ── Sandboxing ───────────────────────────────────────────────────

    def init_sandboxing(self, settings: "Settings") -> None:
        self.sandbox_manager = None
        if not getattr(settings, "sandboxing_enabled", False):
            return
        from backend.pipeline.sandboxing.manager import SandboxManager
        from backend.pipeline.sandboxing.protocol import SandboxConfig

        sandbox_config = SandboxConfig(
            timeout_seconds=settings.sandbox_default_timeout,
            max_output_bytes=settings.sandbox_default_max_output_bytes,
            memory_limit_mb=settings.sandbox_default_memory_mb,
            network_enabled=settings.sandbox_network_enabled,
        )
        self.sandbox_manager = SandboxManager(
            backend_name=settings.sandbox_backend,
            default_config=sandbox_config,
            shell_image=settings.sandbox_docker_image_shell,
            python_image=settings.sandbox_docker_image_python,
        )
        logger.info("Sandboxing enabled (backend: %s)", self.sandbox_manager.backend_name)

    # ── Observability ────────────────────────────────────────────────

    def init_observability(self, settings: "Settings", cost_tracker) -> None:
        self.observability = None
        if not getattr(settings, "observability_enabled", False):
            from backend.pipeline.tracing.processor import LoggingProcessor, set_tracer
            set_tracer(LoggingProcessor())
            return
        from backend.pipeline.observability import ObservabilityManager
        from backend.pipeline.observability.manager import set_active_manager

        self.observability = ObservabilityManager(
            trace_logging=getattr(settings, "observability_trace_logging", True),
            trace_memory=getattr(settings, "observability_trace_memory", True),
            max_memory_spans=getattr(settings, "observability_max_memory_spans", 10000),
            otlp_enabled=getattr(settings, "observability_otlp_enabled", False),
            otlp_endpoint=getattr(settings, "observability_otlp_endpoint", "http://localhost:4317"),
            otlp_protocol=getattr(settings, "observability_otlp_protocol", "grpc"),
            metrics_enabled=getattr(settings, "observability_metrics_enabled", True),
            cost_tracker=cost_tracker,
        )
        set_active_manager(self.observability)
        logger.info("Observability enabled")

    # ── Metacognitive ────────────────────────────────────────────────

    def init_metacognitive(self, settings: "Settings") -> None:
        self.metacog = None
        if not getattr(settings, "metacognitive_enabled", False):
            return
        from backend.pipeline.metacognitive import MetacognitiveManager, PlateauDetector

        detector = PlateauDetector(
            window_size=getattr(settings, "metacognitive_plateau_window", 3),
            threshold=getattr(settings, "metacognitive_plateau_threshold", 0.02),
            max_evals=getattr(settings, "metacognitive_max_evals", 5),
        )
        self.metacog = MetacognitiveManager(plateau_detector=detector)
        if hasattr(self, "agent") and self.agent is not None:
            self.agent._metacog = self.metacog
        logger.info("Metacognitive strategy enabled")

    # ── MCP ──────────────────────────────────────────────────────────

    def init_mcp(self, settings: "Settings") -> None:
        self.mcp_manager = None
        if not getattr(settings, "mcp_enabled", False):
            return
        from backend.pipeline.tools.mcp.manager import MCPManager
        from backend.pipeline.tools.mcp.server_registry import MCPServerRegistry

        server_registry = MCPServerRegistry(
            config_path=getattr(settings, "mcp_servers_path", "./mcp_servers.yaml"),
        )
        self.mcp_manager = MCPManager(
            server_registry=server_registry,
            tool_registry=self.tool_registry,
        )
        logger.info("MCP integration configured (%d servers)", server_registry.server_count)

    # ── Context management ───────────────────────────────────────────

    def init_context_management(self, settings: "Settings", provider: "LLMProvider") -> None:
        self.context_window_manager = None
        if not getattr(settings, "context_management_enabled", False):
            return
        from backend.pipeline.compaction.window_manager import ContextWindowManager
        self.context_window_manager = ContextWindowManager(
            provider=provider,
            trigger_fraction=getattr(settings, "context_trigger_fraction", 0.85),
            offload_dir=getattr(settings, "context_offload_dir", "./data/context_offload"),
        )
        logger.info("Context management enabled (trigger=%.0f%%)", self.context_window_manager._trigger_fraction * 100)

    # ── Streaming ────────────────────────────────────────────────────

    def init_streaming(self, settings: "Settings") -> None:
        self.stream_manager = None
        if not getattr(settings, "streaming_enabled", False):
            return
        from backend.pipeline.streaming.manager import StreamManager
        self.stream_manager = StreamManager(
            dedup_window=getattr(settings, "streaming_dedup_window", 1.0),
        )
        logger.info("Streaming enabled (dedup_window=%.1fs)", self.stream_manager._dedup_window)

    # ── Consolidation ────────────────────────────────────────────────

    def init_consolidation(self, settings: "Settings", provider: "LLMProvider") -> None:
        self.consolidator = None
        self.consolidation_scheduler = None
        if not getattr(settings, "consolidation_enabled", False):
            return
        from backend.pipeline.memory.consolidation import LLMConsolidator
        from backend.pipeline.memory.scheduler import ConsolidationScheduler

        self.consolidator = LLMConsolidator(
            provider=provider,
            similarity_threshold=getattr(settings, "consolidation_similarity_threshold", 0.9),
        )
        self.consolidation_scheduler = ConsolidationScheduler(
            memory=self.memory,
            consolidator=self.consolidator,
            interval_hours=getattr(settings, "consolidation_interval_hours", 24),
        )
        logger.info("Memory consolidation enabled (threshold=%.2f, interval=%dh)",
                     self.consolidator._similarity_threshold,
                     self.consolidation_scheduler._interval_hours)

    # ── Adaptation ───────────────────────────────────────────────────

    def init_adaptation(self, settings: "Settings") -> None:
        self.adaptation_manager = None
        if not getattr(settings, "adaptation_enabled", False):
            return
        from backend.pipeline.adaptation.manager import AdaptationManager
        self.adaptation_manager = AdaptationManager(
            evolver=self.evolver,
            lesson_extractor=self.lesson_extractor,
            metacog=getattr(self, "metacog", None),
            feedback_window=getattr(settings, "adaptation_feedback_window", 5),
            min_improvement=getattr(settings, "adaptation_min_improvement", 0.02),
        )
        logger.info("Behavioral adaptation enabled (window=%d, min_improvement=%.3f)",
                     settings.adaptation_feedback_window, settings.adaptation_min_improvement)

    # ── Graph RAG ────────────────────────────────────────────────────

    def init_graph_rag(self, settings: "Settings", provider: "LLMProvider") -> None:
        self.graph_rag_retriever = None
        if not settings.graph_rag_enabled:
            return
        from backend.pipeline.knowledge.community_detection import CommunityDetector
        from backend.pipeline.knowledge.entity_extractor import EntityExtractor
        from backend.pipeline.knowledge.graph_embeddings import GraphEmbeddingIndex
        from backend.pipeline.knowledge.graph_rag_retriever import GraphRAGRetriever
        from backend.pipeline.knowledge.graph_walks import GraphWalker

        graph_index = GraphEmbeddingIndex(
            persist_dir=settings.chroma_persist_dir,
            embedding_service=self.embedding,
        )
        walker = GraphWalker(self.kg)
        community_detector = CommunityDetector(self.kg)
        entity_extractor = EntityExtractor(provider)

        self.graph_rag_retriever = GraphRAGRetriever(
            base_retriever=self.retriever,
            kg=self.kg,
            graph_embedding_index=graph_index,
            graph_walker=walker,
            community_detector=community_detector,
            entity_extractor=entity_extractor,
            graph_weight=getattr(settings, "graph_rag_weight", 0.3),
            walk_max_hops=getattr(settings, "graph_rag_walk_max_hops", 2),
            walk_max_results=getattr(settings, "graph_rag_walk_max_results", 20),
        )
        logger.info("Graph RAG enabled (weight=%.2f, max_hops=%d)",
                     getattr(settings, "graph_rag_weight", 0.3),
                     getattr(settings, "graph_rag_walk_max_hops", 2))

    # ── Tool discovery ───────────────────────────────────────────────

    def init_tool_discovery(self, settings: "Settings") -> None:
        self.tool_matcher = None
        self.tool_scorer = None
        if not settings.tool_discovery_enabled:
            return
        from backend.pipeline.knowledge.bm25_index import BM25Index
        from backend.pipeline.tools.tool_index import ToolEmbeddingIndex
        from backend.pipeline.tools.tool_matcher import ToolMatcher
        from backend.pipeline.tools.tool_scoring import ToolScorer

        tool_index = ToolEmbeddingIndex(
            persist_dir=settings.chroma_persist_dir,
            embedding_service=self.embedding,
        )
        bm25 = BM25Index(persist_dir=getattr(settings, "tool_discovery_bm25_dir", "./data/tool_bm25"))
        self.tool_matcher = ToolMatcher(
            tool_embedding_index=tool_index,
            bm25_index=bm25,
            registry=self.tool_registry,
            rrf_k=getattr(settings, "tool_discovery_rrf_k", 60),
        )
        self.tool_scorer = ToolScorer(
            trust_penalty=getattr(settings, "tool_discovery_trust_penalty", 0.2),
            relevance_weight=getattr(settings, "tool_discovery_relevance_weight", 0.7),
            recency_weight=getattr(settings, "tool_discovery_recency_weight", 0.1),
        )
        logger.info("Tool discovery enabled (rrf_k=%d)", getattr(settings, "tool_discovery_rrf_k", 60))

    # ── Negotiation ──────────────────────────────────────────────────

    def init_negotiation(self, settings: "Settings") -> None:
        self.consensus_engine = None
        if not getattr(settings, "negotiation_enabled", False):
            return
        from backend.pipeline.negotiation.consensus import ConsensusAlgorithm, ConsensusEngine
        algo_name = getattr(settings, "negotiation_consensus_algorithm", "weighted_score")
        try:
            algorithm = ConsensusAlgorithm(algo_name)
        except ValueError:
            algorithm = ConsensusAlgorithm.WEIGHTED_SCORE
        self.consensus_engine = ConsensusEngine(algorithm=algorithm)
        logger.info("Negotiation enabled (algorithm=%s)", algorithm.value)

    # ── Session ──────────────────────────────────────────────────────

    def init_session(self, settings: "Settings") -> None:
        self.session_manager = None
        if not getattr(settings, "session_enabled", False):
            return
        from backend.pipeline.session.manager import SessionManager
        data_dir = getattr(settings, "session_data_dir", "./data/sessions")
        self.session_manager = SessionManager(data_dir=data_dir, hooks=self.hooks)
        logger.info("Session management enabled (data_dir=%s)", data_dir)

    # ── Batch init ───────────────────────────────────────────────────

    def init_all(
        self,
        settings: "Settings",
        provider: "LLMProvider",
        thinking_provider: "LLMProvider | None",
        cost_tracker,
    ) -> None:
        """Run all subsystem initializers in dependency order."""
        self.init_core_services(settings, provider, thinking_provider, cost_tracker)
        self.init_memory(settings)
        self.init_cross_stage_context(settings)
        self.init_self_improve(settings, provider)
        self.init_autonomy(settings, cost_tracker)
        self.init_governance(settings, provider)
        # Wire cross-references that depend on governance (kg)
        self.init_cross_refs(settings)
        self.init_evaluation(settings, provider)
        self.init_sandboxing(settings)
        self.init_observability(settings, cost_tracker)
        self.init_metacognitive(settings)
        self.init_mcp(settings)
        self.init_context_management(settings, provider)
        self.init_streaming(settings)
        self.init_consolidation(settings, provider)
        self.init_adaptation(settings)
        self.init_graph_rag(settings, provider)
        self.init_tool_discovery(settings)
        self.init_negotiation(settings)
        self.init_session(settings)
