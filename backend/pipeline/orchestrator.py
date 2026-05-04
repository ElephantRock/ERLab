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
from backend.pipeline.persistence import PipelinePersistence
from backend.pipeline.result import PipelineResult
from backend.pipeline.self_improve.evolution import PipelineEvolver
from backend.pipeline.self_improve.frontier import ParetoFrontier
from backend.pipeline.self_improve.lessons import LessonExtractor
from backend.pipeline.stages import (
    ExportStage,
    FeasibilityScoringStage,
    GapAnalysisStage,
    IdeaGenerationStage,
    IngestionStage,
    LiteratureSearchStage,
    MechanicalMetricsStage,
    NoveltyCheckingStage,
    PipelineStage,
    ProposalSynthesisStage,
    StageContext,
    TreeSearchStage,
)
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
from backend.pipeline.synthesis.reference_validator import ReferenceValidator
from backend.providers.base import LLMProvider
from backend.providers.provider_factory import get_registry
from backend.providers.token_counter import TokenCounter
from backend.pipeline.compaction.middleware import CompactionMiddleware

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Coordinates the full research idea generation pipeline."""

    _STAGE_ORDER = [
        "literature_search",
        "ingestion",
        "gap_analysis",
        "idea_generation",
        "novelty_checking",
        "feasibility_scoring",
        "mechanical_metrics",
        "proposal_synthesis",
        "export",
    ]

    def __init__(self, provider: LLMProvider | None = None, stage_callback=None, settings: "Settings | None" = None):
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

        self._init_core_services(settings)
        self._init_memory(settings)
        self._init_cross_stage_context(settings)
        self._init_self_improve(settings)
        self._init_autonomy(settings)
        self._init_governance(settings)
        self._init_evaluation(settings)
        self._init_sandboxing(settings)
        self._init_observability(settings)
        self._init_metacognitive(settings)
        self._init_mcp(settings)
        self._init_context_management(settings)
        self._init_streaming(settings)
        self._init_consolidation(settings)
        self._init_adaptation(settings)
        self._init_graph_rag(settings)
        self._init_tool_discovery(settings)
        self._init_negotiation(settings)
        self._init_session(settings)

        # Wire hooks to agent orchestrator for impasse events
        self._agent.set_hooks(self._hooks)

        # Wire SharedMemoryBridge connecting MessageBus and SharedKB
        self._shared_memory_bridge = None
        if self._shared_kb and getattr(self, "_message_bus", None):
            from backend.pipeline.memory.sharing import SharedMemoryBridge
            self._shared_memory_bridge = SharedMemoryBridge(self._shared_kb, self._message_bus)

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
        self._stages = self._build_stages()

        # Register built-in tools after all services are initialized
        from backend.pipeline.tools.builtin import register_builtin_tools
        register_builtin_tools(
            self._tool_registry,
            search_service=self._search,
            vector_store=self._store,
            memory_service=self._memory,
            knowledge_graph=self._kg,
        )

    # ── Subsystem Factories ──────────────────────────────────────────

    def _init_core_services(self, settings) -> None:
        """Core pipeline services: search, PDF, embedding, store, agents."""
        self._search = SearchService()
        self._pdf = PDFService(mode=settings.s1_parser_mode, s1_parser_url=settings.s1_parser_url)

        from backend.pipeline.knowledge.embedding_providers import create_embedding_provider

        embedding_provider = create_embedding_provider(
            provider_name=settings.embedding_provider,
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            base_url=settings.ollama_base_url,
            dimension=settings.embedding_dimension or None,
        )

        # Wrap with fallback if configured
        if getattr(settings, "embedding_fallback_enabled", False):
            from backend.pipeline.knowledge.embedding_providers import (
                FallbackEmbeddingProvider,
                OllamaEmbeddingProvider,
            )

            fallback = OllamaEmbeddingProvider(
                base_url=settings.ollama_base_url,
            )
            embedding_provider = FallbackEmbeddingProvider(embedding_provider, fallback)

        self._embedding = EmbeddingService(
            embedding_provider,
            batch_size=settings.embedding_batch_size,
        )
        self._store = VectorStore(settings.chroma_persist_dir, self._embedding)

        from backend.pipeline.knowledge.bm25_index import BM25Index
        from backend.pipeline.knowledge.retriever import TwoStageRetriever

        self._bm25 = BM25Index(settings.bm25_persist_dir)

        query_transformer = None
        if getattr(settings, "query_transform_enabled", False):
            from backend.pipeline.knowledge.query_transform import MultiQueryTransformer

            query_transformer = MultiQueryTransformer(self._provider)

        # Wire reranker from config
        reranker = None
        if getattr(settings, "reranker_enabled", False):
            if getattr(settings, "reranker_type", "llm") == "cross_encoder":
                from backend.pipeline.knowledge.reranker import CrossEncoderReranker

                reranker = CrossEncoderReranker()
            else:
                from backend.pipeline.knowledge.reranker import LLMReranker

                reranker = LLMReranker(self._provider)

        self._retriever = TwoStageRetriever(
            vector_store=self._store,
            bm25_index=self._bm25,
            embedding_service=self._embedding,
            reranker=reranker,
            query_transformer=query_transformer,
            quality_scorer=None,
            rrf_k=getattr(settings, "rrf_k", 60),
            retrieval_mode=getattr(settings, "retrieval_mode", "hybrid"),
        )

        # Quality scorer for retrieval (Gap 1)
        if getattr(settings, "retrieval_quality_scoring_enabled", False):
            from backend.pipeline.knowledge.retrieval_quality import RetrievalQualityScorer
            self._quality_scorer = RetrievalQualityScorer()
            self._retriever._quality_scorer = self._quality_scorer
        else:
            self._quality_scorer = None

        self._gap_analyzer = GapAnalyzer(self._provider)
        self._novelty = NoveltyChecker(self._provider, self._store, self._retriever)
        self._feasibility = FeasibilityScorer(self._provider)

        # Citation-aware novelty augmentation (Gap 11)
        self._citation_traverser = None
        self._embedding_novelty_scorer = None
        if getattr(settings, "citation_novelty_enabled", False):
            from backend.pipeline.novelty.citation_traversal import CitationGraphTraverser
            self._citation_traverser = CitationGraphTraverser(self._kg)
            self._novelty._citation_traverser = self._citation_traverser
        if getattr(settings, "embedding_novelty_enabled", False):
            from backend.pipeline.novelty.embedding_scorer import EmbeddingNoveltyScorer
            from backend.pipeline.knowledge.graph_embeddings import GraphEmbeddingIndex
            graph_index = GraphEmbeddingIndex(
                persist_dir=settings.chroma_persist_dir,
                embedding_service=self._embedding,
            )
            self._embedding_novelty_scorer = EmbeddingNoveltyScorer(self._embedding, graph_index)
            self._novelty._embedding_scorer = self._embedding_novelty_scorer

        # Faithfulness checker for gap analysis (Gap 9)
        self._faithfulness_checker = None
        if getattr(settings, "faithfulness_check_enabled", False):
            from backend.pipeline.knowledge.faithfulness import FaithfulnessChecker
            self._faithfulness_checker = FaithfulnessChecker(self._provider)

        # Contradiction scanner for knowledge graph (Gap 9)
        self._contradiction_scanner = None
        if getattr(settings, "contradiction_detection_enabled", False):
            from backend.pipeline.knowledge.contradiction import ContradictionScanner
            self._contradiction_scanner = ContradictionScanner(
                kg=self._kg, provider=self._provider,
                scan_interval=getattr(settings, "contradiction_scan_interval", 10),
            )

        # Forest-of-Thought and Reasoning Verifier (Gap 7)
        self._forest = None
        self._reasoning_verifier = None
        if getattr(settings, "reasoning_verification_enabled", False):
            from backend.pipeline.generation.verifier import ReasoningVerifier
            self._reasoning_verifier = ReasoningVerifier(self._provider)

        # Dynamic agent factory (Gap 2)
        self._dynamic_agent_factory = None
        self._sub_goal_generator = None
        if getattr(settings, "dynamic_agents_enabled", False):
            from backend.pipeline.agents.dynamic_factory import DynamicAgentFactory
            self._dynamic_agent_factory = DynamicAgentFactory(
                provider=self._provider,
                registry=self._agent_registry or __import__(
                    "backend.pipeline.agents.registry",
                    fromlist=["AgentRegistry"],
                ).AgentRegistry(),
                bus=self._message_bus,
                max_agents=getattr(settings, "dynamic_agents_max_per_run", 5),
            )
            if getattr(settings, "sub_goal_generation_enabled", False):
                from backend.pipeline.agents.sub_goals import SubGoalGenerator
                self._sub_goal_generator = SubGoalGenerator(
                    provider=self._provider,
                    factory=self._dynamic_agent_factory,
                )

        # Ensemble reviewer for proposal synthesis (Gap 6)
        ensemble_reviewer = None
        if getattr(settings, "evaluation_framework_enabled", False):
            from backend.pipeline.evaluation.ensemble_review import EnsembleReviewer
            ensemble_reviewer = EnsembleReviewer(self._provider)

        self._synthesizer = ProposalSynthesizer(self._provider, ensemble_reviewer=ensemble_reviewer)
        self._export = ExportService()

        # Tool registry and plugin loader
        from backend.pipeline.tools.registry import get_tool_registry

        self._tool_registry = get_tool_registry()

        from backend.pipeline.plugins.loader import PluginLoader

        self._plugin_loader = PluginLoader(
            verification_enabled=getattr(settings, "plugin_verification_enabled", False),
            allowlist_path=getattr(settings, "plugin_allowlist_path", "./data/plugins/allowlist.json"),
        )
        self._plugin_loader.load_all(self._tool_registry)

        # Pass tool registry to agent orchestrator
        self._agent = AgentOrchestrator(
            self._provider, retriever=self._retriever, tool_registry=self._tool_registry
        )
        # Hooks will be wired after _init_autonomy

        self._message_bus = None
        self._agent_registry = None
        self._dag_executor = None
        self._dag_agents: dict = {}
        if getattr(settings, "multi_agent_enabled", True):
            from backend.pipeline.agents.message_bus import MessageBus
            from backend.pipeline.agents.registry import AgentRegistry
            from backend.pipeline.generation.critic_agent import CriticAgent
            from backend.pipeline.generation.dag_executor import DAGExecutor
            from backend.pipeline.generation.ideator_agent import IdeatorAgent
            from backend.pipeline.generation.refiner_agent import RefinerAgent
            from backend.pipeline.generation.topology import build_default_dag

            self._message_bus = MessageBus()
            self._agent_registry = AgentRegistry(self._message_bus)

            dag = build_default_dag()
            # Configure tree-of-thought on LOOP nodes if enabled
            if getattr(settings, "tree_of_thought_enabled", False):
                for n in dag.nodes:
                    if n.type.value == "loop":
                        n.config["use_tree_of_thought"] = True
                        n.config["tot_max_depth"] = getattr(settings, "tree_of_thought_max_depth", 3)
                        n.config["tot_beam_width"] = getattr(settings, "tree_of_thought_beam_width", 2)

            self._dag_executor = DAGExecutor(
                dag=dag,
                registry=self._agent_registry,
                bus=self._message_bus,
                provider=self._provider,
            )

            # Create agent instances for DAG execution
            self._dag_agents = {
                "ideator": IdeatorAgent(self._provider, retriever=self._retriever),
                "critic": CriticAgent(self._provider),
                "refiner": RefinerAgent(self._provider),
            }

    def _init_memory(self, settings) -> None:
        self._memory: "MemoryService | TieredMemoryService | None" = None
        self._shared_kb = None

        if not settings.memory_enabled:
            return

        if settings.memory_tier == "tiered":
            from backend.pipeline.memory.tiers import TieredMemoryService

            self._memory = TieredMemoryService(
                working_capacity=settings.memory_working_capacity,
                archival_path=f"{settings.memory_persist_dir}/archival",
                retriever=self._retriever,
            )
            if settings.memory_shared_enabled:
                from backend.pipeline.memory.sharing import SharedKnowledgeBase

                self._shared_kb = SharedKnowledgeBase(self._memory)
        else:
            self._memory = MemoryService(
                settings.memory_persist_dir,
                retriever=self._retriever,
            )

    def _init_cross_stage_context(self, settings) -> None:
        self._cross_stage_ctx = None
        self._prompt_builder = None

        if not getattr(settings, "cross_stage_context_enabled", True):
            return
        if not self._memory:
            return

        from backend.pipeline.context.cross_stage import CrossStageContext
        from backend.pipeline.context.prompt_layers import LayeredPromptBuilder

        self._cross_stage_ctx = CrossStageContext(self._memory)

        if getattr(settings, "prompt_layers_enabled", True):
            self._prompt_builder = LayeredPromptBuilder(memory=self._memory)

    def _init_self_improve(self, settings) -> None:
        self._evolver: PipelineEvolver | None = None
        self._lesson_extractor: LessonExtractor | None = None
        self._evolution_engine = None
        self._ab_test_harness = None
        self._ratchet_loop = None
        self._feedback_history = None
        self._skill_registry = None
        self._skill_proposer = None
        self._skill_generator = None

        if settings.self_improve_enabled:
            from pathlib import Path
            Path(settings.self_improve_persist_dir).mkdir(parents=True, exist_ok=True)

            from backend.pipeline.self_improve.constraints import ConstraintConfig
            from backend.pipeline.self_improve.fitness import FitnessScore

            frontier = ParetoFrontier(f"{settings.self_improve_persist_dir}/frontier.json")
            constraint_config = ConstraintConfig(max_size=5000, max_growth_pct=0.3, allow_empty=False, min_sections=3)
            self._lesson_extractor = LessonExtractor(self._provider)
            self._evolver = PipelineEvolver(
                frontier, constraint_config=constraint_config,
                lesson_mapper=self._lesson_extractor,
            )

            # Gap 3: Verified Self-Improvement
            if getattr(settings, "evolution_engine_enabled", False):
                from backend.pipeline.self_improve.engine import EvolutionEngine
                from backend.pipeline.self_improve.ab_test import ABTestHarness
                from backend.pipeline.self_improve.ratchet import RatchetLoop
                from backend.pipeline.self_improve.feedback_history import FeedbackHistory

                self._evolution_engine = EvolutionEngine(
                    self._evolver, self._provider,
                    decay_rate=getattr(settings, "evolution_engine_decay_rate", 0.95),
                )
                self._ab_test_harness = ABTestHarness(
                    frontier,
                    min_confidence=getattr(settings, "ab_testing_min_confidence", 0.6),
                )
                self._ratchet_loop = RatchetLoop()
                self._feedback_history = FeedbackHistory(
                    f"{settings.self_improve_persist_dir}/feedback_history.json"
                )

        if settings.skills_enabled:
            from backend.pipeline.skills.proposer_generator import SkillGenerator, SkillProposer
            from backend.pipeline.skills.registry import SkillRegistry

            self._skill_registry = SkillRegistry(settings.skills_persist_dir)
            self._skill_proposer = SkillProposer(self._provider)
            self._skill_generator = SkillGenerator(self._provider)

    def _init_autonomy(self, settings) -> None:
        self._budget = None
        self._plan_verifier = None
        if settings.budget_enabled:
            from backend.pipeline.autonomy.budget import PlanVerifier, SimpleBudget

            self._budget = SimpleBudget(
                max_tokens=settings.budget_max_tokens,
                max_cost_usd=settings.budget_max_cost_usd,
                max_seconds=settings.budget_max_seconds,
                cost_tracker=self._cost_tracker,
            )
            self._plan_verifier = PlanVerifier()

        from backend.pipeline.autonomy.hooks import HookDispatcher

        self._hooks = HookDispatcher()
        self._stage_timings: dict[str, list[float]] = {}

        async def _on_stage_complete(payload: dict):
            stage = payload.get("stage", "unknown")
            elapsed = payload.get("elapsed", 0)
            self._stage_timings.setdefault(stage, []).append(elapsed)

        self._hooks.register("pipeline.stage.complete", _on_stage_complete)

        self._state_machine = None
        self._curiosity = None
        if settings.autonomy_enabled:
            from backend.pipeline.autonomy.curiosity import CuriosityDriver
            from backend.pipeline.autonomy.state_machine import ConsciousnessStateMachine

            self._state_machine = ConsciousnessStateMachine(
                idle_timeout_seconds=settings.autonomy_idle_timeout_seconds,
            )
            self._curiosity = CuriosityDriver(self._provider)

        # Autonomous scheduler (optional periodic execution)
        self._scheduler = None
        if getattr(settings, "autonomy_schedule_enabled", False):
            from backend.pipeline.autonomy.scheduler import AutonomousScheduler
            self._scheduler = AutonomousScheduler(
                orchestrator=self,
                interval_seconds=getattr(settings, "autonomy_schedule_interval_seconds", 3600),
            )

    def _init_governance(self, settings) -> None:
        self._governance_validator = None
        self._governance_audit = None
        self._governance_policy = None
        if settings.governance_enabled:
            from backend.pipeline.governance.events import GovernanceAuditLog
            from backend.pipeline.governance.validator import OutputValidator

            self._governance_validator = OutputValidator(self._provider)
            self._governance_audit = GovernanceAuditLog(settings.governance_audit_path)

            from backend.pipeline.governance.policy import GovernancePolicy

            policy_path = getattr(settings, "governance_policy_path", None)
            if policy_path:
                self._governance_policy = GovernancePolicy(policy_path=policy_path)
            else:
                self._governance_policy = GovernancePolicy()

            from backend.pipeline.governance.approval import ApprovalManager

            self._approval_manager = ApprovalManager(
                timeout_seconds=getattr(settings, "governance_approval_timeout", 3600)
            )

            # Expose to API routes
            from backend.api.routes.governance import set_approval_manager

            set_approval_manager(self._approval_manager)

        from backend.pipeline.knowledge.graph import KnowledgeGraph

        self._kg = KnowledgeGraph(
            persist_path=settings.knowledge_graph_path,
            versioning_enabled=settings.versioning_enabled,
        )
        if settings.reactive_streams_enabled:
            from backend.pipeline.knowledge.streams import StreamRegistry

            self._kg.attach_stream_registry(StreamRegistry())

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
        self._world_model = WorldModel(
            settings.world_model_path, activation_pipeline=activation_pipeline
        )

        dependency_tracker = None
        if settings.dependency_tracking_enabled:
            from backend.pipeline.autonomy.dependency import GoalDependencyTracker

            dependency_tracker = GoalDependencyTracker()
        from backend.pipeline.autonomy.goals import GoalManager

        self._goal_manager = GoalManager(settings.goals_path, dependency_tracker=dependency_tracker)

    def _init_evaluation(self, settings) -> None:
        self._pipeline_evaluator = None
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
        self._pipeline_evaluator = PipelineEvaluator(
            provider=self._provider,
            novelty_checker=self._novelty,
            feasibility_scorer=self._feasibility,
            quality_gate=QualityGate(gate_config),
            use_geval=getattr(settings, "evaluation_geval_enabled", False),
            cache=EvaluationCache(max_size=settings.evaluation_cache_max_size),
        )

    def _init_sandboxing(self, settings) -> None:
        self._sandbox_manager = None
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
        self._sandbox_manager = SandboxManager(
            backend_name=settings.sandbox_backend,
            default_config=sandbox_config,
            shell_image=settings.sandbox_docker_image_shell,
            python_image=settings.sandbox_docker_image_python,
        )
        logger.info(
            "Sandboxing enabled (backend: %s)", self._sandbox_manager.backend_name,
        )

    def _init_observability(self, settings) -> None:
        self._observability = None
        if not getattr(settings, "observability_enabled", False):
            from backend.pipeline.tracing.processor import LoggingProcessor, set_tracer
            set_tracer(LoggingProcessor())
            return
        from backend.pipeline.observability import ObservabilityManager
        from backend.pipeline.observability.manager import set_active_manager

        self._observability = ObservabilityManager(
            trace_logging=getattr(settings, "observability_trace_logging", True),
            trace_memory=getattr(settings, "observability_trace_memory", True),
            max_memory_spans=getattr(settings, "observability_max_memory_spans", 10000),
            otlp_enabled=getattr(settings, "observability_otlp_enabled", False),
            otlp_endpoint=getattr(settings, "observability_otlp_endpoint", "http://localhost:4317"),
            otlp_protocol=getattr(settings, "observability_otlp_protocol", "grpc"),
            metrics_enabled=getattr(settings, "observability_metrics_enabled", True),
            cost_tracker=self._cost_tracker,
        )
        set_active_manager(self._observability)
        logger.info("Observability enabled")

    def _init_metacognitive(self, settings) -> None:
        self._metacog = None
        if not getattr(settings, "metacognitive_enabled", False):
            return
        from backend.pipeline.metacognitive import MetacognitiveManager, PlateauDetector

        detector = PlateauDetector(
            window_size=getattr(settings, "metacognitive_plateau_window", 3),
            threshold=getattr(settings, "metacognitive_plateau_threshold", 0.02),
            max_evals=getattr(settings, "metacognitive_max_evals", 5),
        )
        self._metacog = MetacognitiveManager(plateau_detector=detector)
        if hasattr(self, '_agent') and self._agent is not None:
            self._agent._metacog = self._metacog
        logger.info("Metacognitive strategy enabled")

    def _init_mcp(self, settings) -> None:
        self._mcp_manager = None
        if not getattr(settings, "mcp_enabled", False):
            return
        from backend.pipeline.tools.mcp.manager import MCPManager
        from backend.pipeline.tools.mcp.server_registry import MCPServerRegistry

        server_registry = MCPServerRegistry(
            config_path=getattr(settings, "mcp_servers_path", "./mcp_servers.yaml"),
        )
        self._mcp_manager = MCPManager(
            server_registry=server_registry,
            tool_registry=self._tool_registry,
        )
        logger.info("MCP integration configured (%d servers)", server_registry.server_count)

    def _init_context_management(self, settings) -> None:
        self._context_window_manager = None
        if not getattr(settings, "context_management_enabled", False):
            return
        from backend.pipeline.compaction.window_manager import ContextWindowManager

        self._context_window_manager = ContextWindowManager(
            provider=self._provider,
            trigger_fraction=getattr(settings, "context_trigger_fraction", 0.85),
            offload_dir=getattr(settings, "context_offload_dir", "./data/context_offload"),
        )
        logger.info("Context management enabled (trigger=%.0f%%)", self._context_window_manager._trigger_fraction * 100)

    def _init_streaming(self, settings) -> None:
        self._stream_manager = None
        if not getattr(settings, "streaming_enabled", False):
            return
        from backend.pipeline.streaming.manager import StreamManager

        self._stream_manager = StreamManager(
            dedup_window=getattr(settings, "streaming_dedup_window", 1.0),
        )
        logger.info("Streaming enabled (dedup_window=%.1fs)", self._stream_manager._dedup_window)

    def _init_consolidation(self, settings) -> None:
        self._consolidator = None
        self._consolidation_scheduler = None
        if not getattr(settings, "consolidation_enabled", False):
            return
        from backend.pipeline.memory.consolidation import LLMConsolidator
        from backend.pipeline.memory.scheduler import ConsolidationScheduler

        self._consolidator = LLMConsolidator(
            provider=self._provider,
            similarity_threshold=getattr(settings, "consolidation_similarity_threshold", 0.9),
        )
        self._consolidation_scheduler = ConsolidationScheduler(
            memory=self._memory,
            consolidator=self._consolidator,
            interval_hours=getattr(settings, "consolidation_interval_hours", 24),
        )
        logger.info("Memory consolidation enabled (threshold=%.2f, interval=%dh)",
                     self._consolidator._similarity_threshold,
                     self._consolidation_scheduler._interval_hours)

    def _init_adaptation(self, settings) -> None:
        self._adaptation_manager = None
        if not getattr(settings, "adaptation_enabled", False):
            return
        from backend.pipeline.adaptation.manager import AdaptationManager

        self._adaptation_manager = AdaptationManager(
            evolver=self._evolver,
            lesson_extractor=self._lesson_extractor,
            metacog=getattr(self, "_metacog", None),
            feedback_window=getattr(settings, "adaptation_feedback_window", 5),
            min_improvement=getattr(settings, "adaptation_min_improvement", 0.02),
        )
        logger.info("Behavioral adaptation enabled (window=%d, min_improvement=%.3f)",
                     settings.adaptation_feedback_window, settings.adaptation_min_improvement)

    def _init_graph_rag(self, settings) -> None:
        self._graph_rag_retriever = None
        if not getattr(settings, "graph_rag_enabled", False):
            return
        from backend.pipeline.knowledge.community_detection import CommunityDetector
        from backend.pipeline.knowledge.entity_extractor import EntityExtractor
        from backend.pipeline.knowledge.graph_embeddings import GraphEmbeddingIndex
        from backend.pipeline.knowledge.graph_rag_retriever import GraphRAGRetriever
        from backend.pipeline.knowledge.graph_walks import GraphWalker

        graph_index = GraphEmbeddingIndex(
            persist_dir=settings.chroma_persist_dir,
            embedding_service=self._embedding,
        )
        walker = GraphWalker(self._kg)
        community_detector = CommunityDetector(self._kg)
        entity_extractor = EntityExtractor(self._provider)

        self._graph_rag_retriever = GraphRAGRetriever(
            base_retriever=self._retriever,
            kg=self._kg,
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

    def _init_tool_discovery(self, settings) -> None:
        self._tool_matcher = None
        self._tool_scorer = None
        if not getattr(settings, "tool_discovery_enabled", False):
            return
        from backend.pipeline.knowledge.bm25_index import BM25Index
        from backend.pipeline.tools.tool_index import ToolEmbeddingIndex
        from backend.pipeline.tools.tool_matcher import ToolMatcher
        from backend.pipeline.tools.tool_scoring import ToolScorer

        tool_index = ToolEmbeddingIndex(
            persist_dir=settings.chroma_persist_dir,
            embedding_service=self._embedding,
        )
        bm25 = BM25Index(persist_dir=getattr(settings, "tool_discovery_bm25_dir", "./data/tool_bm25"))

        self._tool_matcher = ToolMatcher(
            tool_embedding_index=tool_index,
            bm25_index=bm25,
            registry=self._tool_registry,
            rrf_k=getattr(settings, "tool_discovery_rrf_k", 60),
        )
        self._tool_scorer = ToolScorer(
            trust_penalty=getattr(settings, "tool_discovery_trust_penalty", 0.2),
            relevance_weight=getattr(settings, "tool_discovery_relevance_weight", 0.7),
            recency_weight=getattr(settings, "tool_discovery_recency_weight", 0.1),
        )
        logger.info("Tool discovery enabled (rrf_k=%d)", getattr(settings, "tool_discovery_rrf_k", 60))

    def _init_negotiation(self, settings) -> None:
        self._consensus_engine = None
        if not getattr(settings, "negotiation_enabled", False):
            return
        from backend.pipeline.negotiation.consensus import ConsensusAlgorithm, ConsensusEngine

        algo_name = getattr(settings, "negotiation_consensus_algorithm", "weighted_score")
        try:
            algorithm = ConsensusAlgorithm(algo_name)
        except ValueError:
            algorithm = ConsensusAlgorithm.WEIGHTED_SCORE

        self._consensus_engine = ConsensusEngine(algorithm=algorithm)
        logger.info("Negotiation enabled (algorithm=%s)", algorithm.value)

    def _init_session(self, settings) -> None:
        self._session_manager = None
        if not getattr(settings, "session_enabled", False):
            return
        from backend.pipeline.session.manager import SessionManager

        data_dir = getattr(settings, "session_data_dir", "./data/sessions")
        self._session_manager = SessionManager(data_dir=data_dir, hooks=self._hooks)
        logger.info("Session management enabled (data_dir=%s)", data_dir)

    def _build_stages(self) -> list[PipelineStage]:
        ref_validator = ReferenceValidator(store=self._store)

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
                ideator=self._agent,  # IdeatorAgent implements the Ideator protocol
                config=tree_config,
            )
            idea_stage = TreeSearchStage(
                engine=tree_engine,
                hooks=self._hooks,
                provider=self._provider,
                kg=self._kg,
            )
            logger.info(
                "TreeSearchStage enabled (beam_width=%d, max_depth=%d)",
                tree_config.beam_width, tree_config.max_depth,
            )
        else:
            idea_stage = IdeaGenerationStage(
                self._agent,
                self._hooks,
                dag_executor=self._dag_executor,
                dag_agents=self._dag_agents,
                provider=self._provider,
                kg=self._kg,
                forest=self._forest,
                reasoning_verifier=self._reasoning_verifier,
            )

        return [
            LiteratureSearchStage(self._search, self._hooks),
            IngestionStage(self._store, self._bm25, self._embedding, kg=self._kg),
            GapAnalysisStage(self._gap_analyzer, self._goal_manager, self._hooks, self._memory, kg=self._kg, faithfulness_checker=self._faithfulness_checker),
            idea_stage,
            NoveltyCheckingStage(self._novelty, self._hooks),
            FeasibilityScoringStage(self._feasibility),
            MechanicalMetricsStage(),
            ProposalSynthesisStage(
                self._synthesizer,
                self._governance_validator,
                self._governance_audit,
                ref_validator=ref_validator,
            ),
            ExportStage(self._export),
        ]

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
        run_id: str | None = None,
        session_id: str | None = None,
        skip_stages: set[str] | None = None,
    ) -> PipelineResult:
        """Execute the full pipeline from literature search to export.

        Args:
            skip_stages: Set of stage names to skip (used by --resume to avoid
                re-running already-completed stages).
        """
        result = PipelineResult()
        rounds = generation_rounds or self._settings.generation_rounds
        ideas_per = ideas_per_round or self._settings.ideas_per_round

        run_id = run_id or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        result.run_id = run_id

        # Session: register run and check budget
        if session_id and self._session_manager:
            budget_check = self._session_manager.check_budget(session_id)
            if budget_check["over_budget"]:
                logger.warning("Session %s is over budget — aborting run", session_id)
                return result
            self._session_manager.register_run(session_id, run_id)

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

            # Wire evolved temperatures into agent orchestrator
            temps = {}
            for key in ("ideator_temperature", "critic_temperature", "refiner_temperature"):
                if key in evolved:
                    temps[key] = float(evolved[key])
            if temps:
                self._agent.set_temperature_overrides(temps)

            # Wire novelty_top_k
            if "novelty_top_k" in evolved and hasattr(self, "_novelty"):
                self._novelty._top_k = int(evolved["novelty_top_k"])

            params.update(evolved)  # type: ignore[arg-type]
        result.params_used = params

        # Create DB run record
        db_run_id = self._persistence.create_run_record(domain, params, session_id=session_id)

        # Budget: validate plan and start tracking
        if self._budget and self._plan_verifier:
            ok, msg = self._plan_verifier.validate(params, self._budget)
            if not ok:
                logger.warning("Budget validation failed: %s. Aborting.", msg)
                return result
            self._budget.start()

        # MCP: connect servers and discover tools
        if self._mcp_manager and not self._mcp_manager._started:
            try:
                tool_count = await self._mcp_manager.start()
                logger.info("MCP manager started: %d tools registered", tool_count)
            except Exception as e:
                logger.warning("MCP startup failed (continuing without MCP tools): %s", e)

        # Hook: pipeline.start
        await self._hooks.dispatch_sync_safe(
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

        # Execute stages
        for stage in self._stages:
            # Gate optional stages
            if isinstance(stage, NoveltyCheckingStage) and not run_novelty:
                continue
            if isinstance(stage, FeasibilityScoringStage) and not run_feasibility:
                continue
            if isinstance(stage, ProposalSynthesisStage) and not run_synthesis:
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

            # Policy gate: evaluate governance policy before each stage
            if self._governance_policy:
                from backend.pipeline.governance.policy import PolicyAction

                decision = self._governance_policy.evaluate(
                    scope=stage.name,
                    capability="execute",
                )
                if decision.action == PolicyAction.DENY:
                    logger.warning(
                        "Governance policy DENIED stage '%s': %s",
                        stage.name,
                        decision.reason,
                    )
                    if self._governance_audit:
                        from backend.pipeline.governance.events import GovernanceEvent

                        self._governance_audit.record(GovernanceEvent(
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
                    if self._governance_audit:
                        from backend.pipeline.governance.events import GovernanceEvent

                        self._governance_audit.record(GovernanceEvent(
                            event_type="policy.gate",
                            stage=stage.name,
                            content_hash="",
                            checks_summary=f"Rule: {decision.rule_name}, Awaiting approval",
                        ))

                    if hasattr(self, "_approval_manager"):
                        approval = await self._approval_manager.request_approval(
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
            if self._cross_stage_ctx:
                prior = await self._cross_stage_ctx.load_prior_context(run_id, stage.name)
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
                finally:
                    if heartbeat:
                        await heartbeat.stop()
            elapsed = time.time() - t0
            self._record_stage(stage.name, t0)
            self._compaction.record_usage(stage.name)
            if self._metacog:
                self._metacog.record_stage(stage.name, {"elapsed_seconds": elapsed})
            await self._hooks.dispatch_sync_safe(
                "pipeline.stage.complete",
                {"stage": stage.name, "elapsed": elapsed, "run_id": run_id},
            )

            # Persistence checkpoints
            if stage.name == "literature_search":
                self._persistence.persist_papers(ctx.all_papers, db_run_id)
                self._collect_warnings(result)
                if not should_continue:
                    self._persistence.mark_run_failed(db_run_id, "No papers found")
                    self._collect_warnings(result)
                    await self._hooks.dispatch_sync_safe(
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
                if self._pipeline_evaluator:
                    eval_reports = await self._pipeline_evaluator.evaluate_all(
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
                    if self._metacog:
                        for er in eval_reports.values():
                            self._metacog.record_evaluation(er)
                        plateau = self._metacog.check_plateau("overall_score")
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

            # Cross-stage context: persist stage outputs
            if self._cross_stage_ctx:
                await self._persist_stage_context(run_id, stage.name, ctx, result)

            # Save checkpoint after each stage for durable execution
            checkpoint.mark_stage_completed(stage.name)
            next_idx = self._STAGE_ORDER.index(stage.name) + 1 if stage.name in self._STAGE_ORDER else -1
            if next_idx < len(self._stages):
                checkpoint.mark_stage_running(self._stages[next_idx].name)
            self._persistence.save_checkpoint(checkpoint)

            if not should_continue or self._should_stop():
                return result

        # Post-pipeline: Self-improvement evaluation
        if self._evolver and result.ideas:
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

            self._evolver.evaluate(
                params=params,
                run_id=run_id,
                avg_idea_score=avg_score,
                avg_novelty_score=avg_novelty,
                good_ideas=sum(1 for i in result.ideas if i.score >= 0.6),
                fitness=fitness,
            )

        # Post-pipeline: Lesson extraction → store as memories
        if self._lesson_extractor and result.ideas:
            avg_score = sum(i.score for i in result.ideas) / len(result.ideas)
            if avg_score < 0.7:
                lessons = await self._lesson_extractor.extract(result, params)
                if lessons:
                    logger.info("Extracted %d lessons from run", len(lessons))
                    # Store lessons as memories
                    if self._memory:
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
                                await self._memory.store(entry)
                            except Exception as e:
                                logger.warning("Failed to store lesson as memory: %s", e)
                        logger.info("Stored %d lessons as memories", len(lessons))

                    # Feed lessons back into evolver for parameter adjustment
                    if self._evolver and lessons:
                        adjusted = self._evolver.apply_lessons(
                            [str(l) for l in lessons], params
                        )
                        logger.info(
                            "Lessons fed back to evolver. %d params adjusted",
                            sum(1 for k in adjusted if adjusted[k] != params.get(k)),
                        )

                    # Activate skill proposer/generator with lessons
                    if self._skill_proposer and self._skill_generator and self._skill_registry:
                        skills = self._skill_registry.discover(domain=domain)
                        for skill in skills:
                            try:
                                diagnosis, suggestion = await self._skill_proposer.diagnose(
                                    skill, trace=str(lessons)
                                )
                                improved = await self._skill_generator.generate(
                                    skill, diagnosis, suggestion
                                )
                                self._skill_registry.add_version(skill.id, improved, score=avg_score)
                            except Exception as e:
                                logger.warning("Skill evolution failed for %s: %s", skill.id, e)

        # Post-pipeline: World model update + change detection
        if self._world_model and result.ideas:
            await self._world_model.update_from_run(result, self._provider)
            logger.info("World model updated")

            # Check for significant changes and re-evaluate goals
            if self._kg and getattr(self._settings, "versioning_enabled", True):
                from backend.pipeline.knowledge.change_detector import WorldModelChangeDetector
                detector = WorldModelChangeDetector(self._kg, contradiction_scanner=self._contradiction_scanner)
                summary = await detector.check_and_notify(
                    goal_manager=getattr(self, "_goal_manager", None),
                )
                if summary and summary.severity.value != "low":
                    logger.info(
                        "Change detection: %s severity, %d changes",
                        summary.severity.value, summary.total_changes,
                    )

        # Post-pipeline: Fire-and-forget memory extraction
        if self._memory:
            asyncio.create_task(self._background_memory_extraction(result, run_id))

        # Hook: pipeline.complete
        await self._hooks.dispatch_sync_safe(
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

        # Persist cost events
        if self._cost_tracker and self._cost_tracker._events:
            cost_dir = getattr(self._settings, "cost_persist_dir", "./data/costs")
            self._cost_tracker.persist(f"{cost_dir}/{run_id}.jsonl")

        # Session: complete run record
        if session_id and self._session_manager:
            tokens = self._cost_tracker.total_tokens if self._cost_tracker else 0
            cost = self._cost_tracker.total_cost if self._cost_tracker else 0.0
            self._session_manager.complete_run(session_id, run_id, tokens_used=tokens, cost_usd=cost)

        return result

    # ── Durable Execution: Resume ────────────────────────────────────

    async def resume(
        self,
        run_id: str,
        domain: str = "AI/NLP",
        search_queries: list[str] | None = None,
        max_gaps: int = 5,
        run_novelty: bool = True,
        run_feasibility: bool = True,
        run_synthesis: bool = True,
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
        if self._cross_stage_ctx:
            try:
                prior = await self._cross_stage_ctx.load_prior_context(run_id, "export")
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

            # Gate optional stages
            if isinstance(stage, NoveltyCheckingStage) and not run_novelty:
                continue
            if isinstance(stage, FeasibilityScoringStage) and not run_feasibility:
                continue
            if isinstance(stage, ProposalSynthesisStage) and not run_synthesis:
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
                    await self._hooks.dispatch_sync_safe(
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
        if not self._state_machine:
            return
        old = self._state_machine.current_state
        self._state_machine.transition(trigger)
        await self._hooks.dispatch_sync_safe(
            "state.transition",
            {"from": old.value, "to": self._state_machine.current_state.value, "trigger": trigger},
        )

    async def autonomous_cycle(
        self,
        domain: str = "AI/NLP",
        max_autonomous_runs: int | None = None,
    ) -> list[PipelineResult]:
        """Run autonomous research cycles using the consciousness state machine."""
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
                    await self._transition_and_dispatch("idle_timeout")
                    continue
                else:
                    logger.info("Idle — waiting for trigger. Ending autonomous cycle.")
                    break

            if state.value == "exploring":
                search_queries = None
                if self._curiosity:
                    suggestion = await self._curiosity.suggest_exploration_topic()
                    if suggestion:
                        search_queries = suggestion.get("search_queries")
                        self._curiosity.record_explored_topic(suggestion.get("topic", domain))
                        logger.info("Curiosity suggests: %s", suggestion.get("topic"))

                        # Persist curiosity suggestion to memory
                        if self._memory:
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
                                await self._memory.store(entry)
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
                if self._memory:
                    await self._memory.consolidate()  # type: ignore[union-attr]
                    await self._memory.apply_decay(self._settings.memory_decay_rate)  # type: ignore[union-attr]
                    logger.info("Dreaming: memory consolidated and decayed")

                await self._transition_and_dispatch("consolidation_complete")
                continue

        logger.info("Autonomous cycle complete. %d runs executed.", len(results))
        return results

    # ── Helpers ──────────────────────────────────────────────────────

    async def _execute_stage_with_retry(
        self, stage: PipelineStage, ctx: StageContext, checkpoint: RunCheckpoint
    ) -> bool:
        """Execute a stage with retry, exponential backoff, and checkpointing."""
        import random

        max_retries = getattr(self._settings, "stage_max_retries", 3)
        base_delay = getattr(self._settings, "stage_retry_base_delay", 2.0)
        max_delay = getattr(self._settings, "stage_retry_max_delay", 120.0)
        jitter_frac = getattr(self._settings, "stage_retry_jitter", 0.1)

        for attempt in range(max_retries + 1):
            try:
                result = await stage.execute(ctx)
                return result
            except Exception as exc:
                checkpoint.mark_stage_failed(stage.name, str(exc))
                self._persistence.save_checkpoint(checkpoint)
                if attempt >= max_retries:
                    logger.error(
                        "Stage %s exhausted %d retries: %s", stage.name, max_retries, exc
                    )
                    raise
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * jitter_frac
                delay += random.uniform(-jitter, jitter)
                logger.warning(
                    "Stage %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    stage.name, attempt + 1, max_retries + 1, delay, exc,
                )
                await asyncio.sleep(delay)
        return False  # unreachable but satisfies type checker

    def _record_stage(self, stage_name: str, start_time: float) -> None:
        elapsed = time.time() - start_time
        if self._stage_callback:
            idx = (
                self._STAGE_ORDER.index(stage_name) + 1 if stage_name in self._STAGE_ORDER else "?"
            )
            self._stage_callback(stage_name, idx, len(self._STAGE_ORDER), elapsed)
        if self._budget:
            tokens = self._token_counter.snapshot().total_tokens
            cost_usd = 0.0
            if self._cost_tracker:
                stage_costs = self._cost_tracker.by_stage()
                cost_usd = stage_costs.get(stage_name, {}).get("total_cost_usd", 0.0)
            self._budget.record(stage_name, tokens=tokens, cost_usd=cost_usd, elapsed=elapsed)
        self._token_counter.reset()

    def _should_stop(self) -> bool:
        if not self._budget:
            return False
        from backend.pipeline.autonomy.budget import BudgetPolicy

        policy = self._budget.check_policy()
        if policy == BudgetPolicy.STOP:
            logger.warning("Budget STOP triggered. Halting pipeline.")
            return True
        if policy == BudgetPolicy.REPLAN:
            logger.warning("Budget REPLAN — 80%% budget used. Continuing with caution.")
        # Also check CostTracker for hard limit
        if self._cost_tracker:
            summary = self._cost_tracker.summary()
            if summary["total_cost_usd"] > self._settings.budget_max_cost_usd:
                logger.warning(
                    "Cost tracker STOP: $%.2f exceeds budget $%.2f",
                    summary["total_cost_usd"],
                    self._settings.budget_max_cost_usd,
                )
                return True
        return False

    async def _persist_stage_context(
        self, run_id: str, stage_name: str, ctx: StageContext, result: PipelineResult
    ) -> None:
        """Save stage outputs to cross-stage context for later retrieval."""
        try:
            if stage_name == "literature_search" and ctx.all_papers:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "literature_search", "papers",
                    [{"title": p.title, "abstract": getattr(p, "abstract", "")}
                     for p in ctx.all_papers[:50]],
                )
            elif stage_name == "gap_analysis" and result.gaps:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "gap_analysis", "gaps",
                    [{"title": g.title, "description": g.description,
                      "confidence": g.confidence, "gap_type": g.gap_type}
                     for g in result.gaps],
                )
            elif stage_name == "idea_generation" and result.ideas:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "idea_generation", "ideas",
                    [{"title": i.title, "proposed_method": getattr(i, "proposed_method", ""),
                      "score": i.score, "domain": getattr(i, "domain", "")}
                     for i in result.ideas],
                )
            elif stage_name == "feasibility_scoring" and result.feasibility_reports:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "feasibility_scoring", "scores",
                    {str(k): {"overall": v.overall_score}
                     for k, v in result.feasibility_reports.items()},
                )
            elif stage_name == "proposal_synthesis" and result.proposals:
                await self._cross_stage_ctx.save_stage_output(
                    run_id, "proposal_synthesis", "proposals",
                    {"count": len(result.proposals)},
                )
        except Exception as exc:
            logger.warning("Failed to persist cross-stage context for %s: %s", stage_name, exc)

    def _collect_warnings(self, result: PipelineResult) -> None:
        warnings = self._persistence.get_warnings()
        if warnings:
            result.persistence_warnings.extend(warnings)

    async def _background_memory_extraction(self, result: PipelineResult, run_id: str) -> None:
        try:
            stored = await extract_from_pipeline_result(
                result,
                self._provider,
                self._memory,  # type: ignore[arg-type]
                run_id=run_id,
            )
            logger.info("Background memory extraction: stored %d memories", stored)
        except Exception as e:
            logger.error("Background memory extraction failed: %s", e)

    # ── Scheduler Control ─────────────────────────────────────────────

    async def start_scheduler(self) -> dict | None:
        """Start the autonomous scheduler."""
        if not self._scheduler:
            return None
        await self._scheduler.start()
        return self._scheduler.status()

    async def stop_scheduler(self) -> dict | None:
        """Stop the autonomous scheduler."""
        if not self._scheduler:
            return None
        await self._scheduler.stop()
        return self._scheduler.status()

    def scheduler_status(self) -> dict | None:
        """Get scheduler status."""
        if not self._scheduler:
            return None
        return self._scheduler.status()
