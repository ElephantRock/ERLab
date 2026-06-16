"""Application configuration via environment variables."""

import functools
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ProductionConfigError(Exception):
    """Raised when production configuration has insecure defaults."""


class ProductionConfigWarning(Exception):
    """Warning for production configuration that is risky but not fatal."""



class Settings(BaseSettings):
    """Central configuration. All fields can be overridden with EROCK_ prefixed env vars."""

    model_config = SettingsConfigDict(
        env_prefix="EROCK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Elephant Rock Research"
    debug: bool = False
    env: str = "development"  # EROCK_ENV — "development" or "production"

    # LLM Providers
    default_provider: str = "openai"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    gemini_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Model overrides (optional)
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-20250514"
    gemini_model: str = "gemini-2.0-flash"
    ollama_model: str = "llama3"

    # Academic APIs
    semantic_scholar_api_key: str | None = None
    openalex_email: str | None = None
    crossref_api_url: str = "https://api.crossref.org"
    openalex_api_url: str = "https://api.openalex.org"
    semantic_scholar_api_url: str = "https://api.semanticscholar.org/graph/v1"
    pubmed_api_key: str | None = None
    pubmed_enabled: bool = True
    crossref_enabled: bool = True

    # Knowledge Base
    chroma_persist_dir: str = "./data/chroma"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    embedding_batch_size: int = 100
    embedding_fallback_enabled: bool = False
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Retrieval (WP-1: hybrid BM25 + semantic search)
    retrieval_mode: str = "hybrid"  # "substring", "semantic", "hybrid"
    bm25_persist_dir: str = "./data/bm25"
    reranker_enabled: bool = True
    reranker_type: str = "cross_encoder"  # "llm" or "cross_encoder"
    rrf_k: int = 60  # Reciprocal Rank Fusion constant

    # Query transform (WP-1 completion)
    query_transform_enabled: bool = False

    # LiteLLM model routing (priority 20)
    litellm_fallback_enabled: bool = True
    litellm_model: str = "gpt-4o"

    # Model Split (BATCH-78)
    thinking_model: str = ""  # empty = same as default provider
    generation_model: str = ""  # empty = same as default provider
    thinking_model_max_tokens: int = 2048
    generation_model_max_tokens: int = 8192
    search_depth: int = 1  # 1=single pass, 2=recursive with follow-up queries

    # LM Studio (local hybrid model)
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_model: str = "qwen/qwen3-4b-2507"
    lmstudio_enabled: bool = False  # Set True to use for thinking tasks
    lmstudio_max_tokens: int = 2048
    lmstudio_context_length: int = 32768  # Preflight target context for model reload
    lmstudio_temperature: float = 0.1
    lmstudio_auto_download: bool = False  # Auto-download missing models from Hugging Face
    lmstudio_download_timeout: int = 600  # Max seconds to wait for model download

    # vLLM / OpenAI-compatible local server
    vllm_base_url: str = ""  # e.g. "http://localhost:8000"

    # GPU Hardware
    gpu_vram_mb: int = 12288  # GPU VRAM in MB. Used for pre-load safety checks (default: RTX 3080 Ti)
    gpu_auto_detect: bool = True  # Auto-detect GPU VRAM; overrides gpu_vram_mb if True
    gpu_override_vram_mb: int = 0  # If >0, force this VRAM value (for remote inference servers)

    # Pipeline Defaults
    generation_rounds: int = 2
    ideas_per_round: int = 3
    novelty_top_k: int = 20

    # API Authentication
    api_key: str | None = None  # EROCK_API_KEY env var; empty = auth disabled

    # JWT Authentication (BATCH-28)
    auth_enabled: bool = False  # When False, no JWT auth required (dev mode)
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours

    # API Middleware
    cors_origins: list[str] = ["*"]  # EROCK_CORS_ORIGINS (JSON list)
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60

    # Database
    database_url: str = "sqlite:///./data/elephant_rock.db"

    # S1-Parser
    s1_parser_mode: str = "import"  # "import" or "http"
    s1_parser_url: str = "http://localhost:8000"

    # Memory (Phase 2)
    memory_enabled: bool = True
    memory_persist_dir: str = "./data/memory"
    memory_decay_rate: float = 0.99
    memory_min_confidence: float = 0.1
    memory_tier: str = "tiered"  # "flat" (legacy) or "tiered"
    memory_working_capacity: int = 100
    memory_shared_enabled: bool = True

    # Self-Improvement (Phase 2)
    self_improve_enabled: bool = True
    self_improve_persist_dir: str = "./data/self_improve"

    # Autonomy (Phase 3)
    autonomy_enabled: bool = False
    autonomy_idle_timeout_seconds: int = 3600
    autonomy_max_autonomous_runs: int = 10

    # Budget (Phase 3)
    budget_enabled: bool = True
    budget_max_tokens: int = 500000
    budget_max_cost_usd: float = 10.0
    budget_max_seconds: float = 600
    cost_persist_dir: str = "./data/costs"

    # Provider Resilience (WP-01)
    resilience_enabled: bool = True
    circuit_breaker_failure_threshold: int = 15
    circuit_breaker_reset_timeout: float = 30.0
    retry_max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_cooldown_delay: float = 30.0
    secrets_master_password: str | None = None
    secrets_persist_dir: str = "./data/secrets"

    # Evaluation Framework (WP-02)
    evaluation_framework_enabled: bool = True
    evaluation_geval_enabled: bool = True
    evaluation_cache_max_size: int = 500
    evaluation_quality_gate_mode: str = "any"
    evaluation_composite_threshold: float = 0.4
    evaluation_novelty_min_score: float = 0.3
    evaluation_feasibility_min_score: float = 0.4
    evaluation_impact_min_score: float = 0.3
    evaluation_soundness_min_score: float = 0.5
    evaluation_soundness_required: bool = True

    # Sandboxing (WP-03)
    sandboxing_enabled: bool = False
    sandbox_backend: str = "auto"
    sandbox_default_timeout: float = 30.0
    sandbox_default_max_output_bytes: int = 100_000
    sandbox_default_memory_mb: int = 256
    sandbox_network_enabled: bool = False
    sandbox_docker_image_shell: str = "alpine:3.19"
    sandbox_docker_image_python: str = "python:3.11-slim"

    # Observability (WP-04)
    observability_enabled: bool = True
    observability_trace_memory: bool = True
    observability_trace_logging: bool = True
    observability_max_memory_spans: int = 10000
    observability_otlp_enabled: bool = False
    observability_otlp_endpoint: str = "http://localhost:4317"
    observability_otlp_protocol: str = "grpc"
    observability_metrics_enabled: bool = True

    # Semantic Caching (WP-05)
    caching_enabled: bool = True
    caching_type: str = "memory"
    caching_max_size: int = 1000
    caching_similarity_threshold: float = 0.95
    caching_ttl_seconds: int = 3600
    caching_persist_dir: str = "./data/chroma"

    # Cost Routing (WP-06)
    cost_routing_enabled: bool = True
    cost_routing_strategy: str = "cheapest"
    cost_routing_per_provider_limits: dict[str, float] = {}
    cost_routing_latency_window: int = 100

    # Metacognitive Strategy (WP-07)
    metacognitive_enabled: bool = False
    metacognitive_plateau_window: int = 3
    metacognitive_plateau_threshold: float = 0.02
    metacognitive_max_evals: int = 5

    # Model routing (P3)
    model_routing_enabled: bool = True
    model_routing: dict[str, dict] = {}
    model_fallback_chain: list[str] = []

    # Litellm native resilience
    litellm_num_retries: int = 3
    litellm_allowed_fails: int = 5
    litellm_cooldown_time: int = 60

    # Circuit breaker percentage-based cooldown
    circuit_breaker_cooldown_percent: float = 0.1

    # Plugin verification (P3)
    plugin_verification_enabled: bool = False
    plugin_allowlist_path: str = "./data/plugins/allowlist.json"

    # Knowledge Graph (Phase 4)
    knowledge_graph_path: str = "./data/knowledge_graph.json"

    # World Model (Phase 5)
    world_model_path: str = "./data/world_model.json"

    # Governance (Phase 5)
    governance_enabled: bool = True
    governance_audit_path: str = "./data/governance_audit.jsonl"
    governance_policy_path: str | None = None
    governance_approval_timeout: float = 3600  # seconds to wait for human approval

    # Goals (Phase 5)
    goals_path: str = "./data/goals.json"

    # Skills (WP-4)
    skills_enabled: bool = True
    skills_persist_dir: str = "./data/skills"

    # Multi-Agent (WP-3)
    multi_agent_enabled: bool = True  # Uses TopologyDAG by default

    # Context Compaction
    compaction_enabled: bool = True
    compaction_smart_truncation: bool = True
    compaction_summarization: bool = True
    compaction_budget_management: bool = True
    compaction_fallback_model: str = "gpt-4o"
    compaction_stage_budgets: str = (
        '{"gap_analysis":{"base":6000,"min_budget":3000,"max_budget":10000},'
        '"idea_generation":{"base":8000,"min_budget":4000,"max_budget":15000},'
        '"novelty_checking":{"base":4000,"min_budget":2000,"max_budget":8000},'
        '"feasibility_scoring":{"base":2000,"min_budget":1000,"max_budget":4000},'
        '"proposal_synthesis":{"base":10000,"min_budget":5000,"max_budget":20000}}'
    )
    compaction_paper_limits: str = (
        '{"gap_analysis":30,"idea_generation":20,'
        '"novelty_checking":10,"feasibility_scoring":0,'
        '"proposal_synthesis":15}'
    )
    compaction_abstract_chars_tight: int = 80
    compaction_abstract_chars_loose: int = 150

    # Constraint Config
    constraint_max_size: int = 5000
    constraint_max_growth_pct: float = 0.3
    constraint_min_sections: int = 3
    constraint_allow_empty: bool = False

    # World Model + Autonomy (WP-8)
    versioning_enabled: bool = True
    activation_enabled: bool = True
    activation_decay_rate: float = 0.5
    activation_spreading_rate: float = 0.1
    activation_noise_std: float = 0.02
    dependency_tracking_enabled: bool = True
    reactive_streams_enabled: bool = True

    # Tree-of-Thought reasoning (P4)
    tree_of_thought_enabled: bool = True  # BATCH-66: enabled by default
    tree_of_thought_max_depth: int = 3
    tree_of_thought_beam_width: int = 2

    # Research sub-agent (BATCH-186): isolated search contexts
    research_subagent_enabled: bool = False  # opt-in for now
    research_subagent_max_iterations: int = 20
    research_subagent_context_budget: int = 100_000  # tokens per sub-agent

    # BATCH-190: Notification gateway
    notification_webhook_url: str | None = None  # e.g. Slack webhook URL

    # Autonomous scheduling (P4)
    autonomy_schedule_enabled: bool = False
    autonomy_schedule_interval_seconds: int = 3600

    # MCP Integration (WP-08)
    mcp_enabled: bool = False
    mcp_servers_path: str = "./mcp_servers.yaml"
    mcp_default_timeout: float = 30.0

    # Context Management Enhancement (WP-09)
    context_management_enabled: bool = False
    context_trigger_fraction: float = 0.85
    context_offload_dir: str = "./data/context_offload"

    # Streaming Enhancement (WP-11)
    streaming_enabled: bool = False
    streaming_dedup_window: float = 1.0

    # Memory Consolidation Enhancement (WP-12)
    consolidation_enabled: bool = False
    consolidation_similarity_threshold: float = 0.9
    consolidation_interval_hours: int = 24

    # Behavioral Adaptation (WP-10)
    adaptation_enabled: bool = False
    adaptation_feedback_window: int = 5
    adaptation_min_improvement: float = 0.02

    # Graph RAG (WP-13)
    graph_rag_enabled: bool = False
    graph_rag_walk_max_hops: int = 2
    graph_rag_walk_max_results: int = 20
    graph_rag_weight: float = 0.3
    graph_rag_extract_on_ingest: bool = True

    # Dynamic Tool Discovery (WP-14)
    tool_discovery_enabled: bool = False
    tool_discovery_bm25_dir: str = "./data/tool_bm25"
    tool_discovery_rrf_k: int = 60
    tool_discovery_trust_penalty: float = 0.2
    tool_discovery_relevance_weight: float = 0.7
    tool_discovery_recency_weight: float = 0.1

    # Multi-Agent Negotiation (WP-15)
    negotiation_enabled: bool = False
    negotiation_max_rounds: int = 5
    negotiation_consensus_threshold: float = 0.7
    negotiation_consensus_algorithm: str = "weighted_score"
    negotiation_deadlock_threshold: float = 0.02
    negotiation_proposal_timeout: float = 60.0
    negotiation_critique_timeout: float = 30.0
    negotiation_min_agents: int = 2

    # Session Lifecycle (WP-16)
    session_enabled: bool = False
    session_data_dir: str = "./data/sessions"
    session_default_max_runs: int = 10
    session_default_max_cost_usd: float = 50.0
    session_default_max_tokens: int = 5_000_000
    session_default_max_duration_hours: float = 24.0
    session_gc_idle_timeout_hours: float = 48.0
    session_gc_expiry_hours: float = 168.0  # 7 days

    # Cross-stage context (Gap 10)
    cross_stage_context_enabled: bool = True
    cross_stage_context_namespace: str = "cross_stage"
    prompt_layers_enabled: bool = True

    # Stage-level execution (Gap 13)
    stage_max_retries: int = 3
    stage_default_timeout: float = 1800.0  # 30 minutes per stage
    stage_timeouts: dict = {}  # per-stage overrides e.g. {"ingestion": 3600}
    llm_rate_limit_retries: int = 3  # EROCK_LLM_RATE_LIMIT_RETRIES (BATCH-176)
    stage_retry_base_delay: float = 2.0
    stage_retry_max_delay: float = 120.0
    stage_retry_jitter: float = 0.1
    per_proposal_timeout: float = 300.0  # seconds; capped at 300 by HB-01
    heartbeat_enabled: bool = True
    heartbeat_interval_seconds: float = 30.0
    heartbeat_timeout_seconds: float = 300.0

    # Counterfactual reasoning (Gap 14)
    counterfactual_enabled: bool = True
    counterfactual_refutation_tests: bool = True

    # Adaptive retrieval (Gap 1)
    retrieval_quality_scoring_enabled: bool = True
    retrieval_quality_threshold: float = 0.4
    retrieval_adaptive_requery: bool = True
    retrieval_max_requeries: int = 2

    # Verified Self-Improvement (Gap 3)
    evolution_engine_enabled: bool = False
    evolution_engine_decay_rate: float = 0.95
    ab_testing_enabled: bool = False
    ab_testing_min_confidence: float = 0.6

    # Human-Agent Iterative Refinement (Gap 12)
    refinement_loop_enabled: bool = False
    refinement_max_iterations: int = 3
    quality_backloop_enabled: bool = False
    quality_backloop_min_composite: float = 0.4
    quality_backloop_max_retries: int = 2
    input_guardrails_active: bool = False

    # Contradiction Detection (Gap 9)
    contradiction_detection_enabled: bool = False
    contradiction_scan_interval: int = 10
    faithfulness_check_enabled: bool = False

    # Reasoning Verification (Gap 7)
    forest_of_thought_enabled: bool = False
    forest_of_thought_n_trees: int = 3
    reasoning_verification_enabled: bool = False

    # Dynamic Agent Creation (Gap 2)
    dynamic_agents_enabled: bool = False
    dynamic_agents_max_per_run: int = 5
    sub_goal_generation_enabled: bool = False

    # Citation-Aware Novelty (Gap 11)
    citation_novelty_enabled: bool = False
    citation_traversal_max_hops: int = 3
    embedding_novelty_enabled: bool = False

    # Webhook Notifications (BATCH-32)
    webhook_enabled: bool = False
    webhook_url: str | None = None
    webhook_secret: str | None = None

    # Sentry Error Monitoring (BATCH-52)
    sentry_dsn: str = ""
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.1

    # WebSocket (BATCH-50)
    websocket_enabled: bool = True

    # Sandboxed Experiment Execution (BATCH-49)
    experiment_enabled: bool = False
    experiment_default_timeout: float = 30.0
    experiment_max_code_size: int = 10000

    # ── Research Loop Improvements (Phase 1-7) ────────────────────

    # Phase 1: Decision Gate Loop
    decision_gate_enabled: bool = True
    decision_gate_quality_threshold: float = 0.45
    decision_gate_abort_threshold: float = 0.15
    decision_gate_max_retries: int = 1

    # Phase 3: Contract Enforcement
    contract_enforcement_mode: str = "warn"  # "warn" | "enforce"

    # Phase 4: Evidence Provenance
    provenance_check_enabled: bool = True
    provenance_min_coverage: float = 0.4

    # Phase 5: Durable Run Export
    run_artifacts_enabled: bool = True
    run_artifacts_dir: str = "./data/runs"

    # Phase 6: Memory Warm-Start
    warm_start_enabled: bool = True

    # Phase 7: Abandonment Tracking
    abandonment_tracking_enabled: bool = True
    abandonment_tracking_path: str = "./data/abandoned_directions.jsonl"


    # ── Environment-aware security properties ────────────────────

    @property
    def is_production(self) -> bool:
        """True when running in production mode."""
        return self.env == "production"

    @property
    def effective_cors_origins(self) -> list[str]:
        """CORS origins respecting environment.

        Production + wildcard → empty (same-origin only).
        Otherwise, returns configured cors_origins as-is.
        """
        if self.is_production and self.cors_origins == ["*"]:
            return []
        return self.cors_origins

    @property
    def effective_debug(self) -> bool:
        """Debug flag respecting environment.

        Production always returns False regardless of the debug setting.
        """
        if self.is_production:
            return False
        return self.debug


    # ── Production validation ────────────────────────────────────

    def validate_production(self) -> None:
        """Validate configuration for production deployments.

        Raises ProductionConfigError if any setting has an insecure default
        that must not run in production. This is called automatically by
        get_settings() when env == "production".

        Calling this method in development mode is a no-op.

        Also logs warnings for risky-but-not-fatal settings.
        """
        if not self.is_production:
            return

        errors: list[str] = []
        warnings: list[str] = []

        # 1. JWT secret must not be the default
        if self.jwt_secret == "dev-secret-change-in-production":
            errors.append(
                "jwt_secret is set to the default value. "
                "Set EROCK_JWT_SECRET to a strong, unique secret."
            )

        # 2. CORS must not be wildcard
        if self.cors_origins == ["*"]:
            errors.append(
                "cors_origins is set to wildcard '*' (or not set). "
                "Set EROCK_CORS_ORIGINS to an explicit list of allowed origins."
            )

        # 3. Auth must be enabled
        if not self.auth_enabled:
            errors.append(
                "auth_enabled is False. "
                "Set EROCK_AUTH_ENABLED=true for production deployments."
            )

        # 4. Sandbox must not silently fall back to subprocess
        if self.sandboxing_enabled and self.sandbox_backend == "auto":
            warnings.append(
                "sandbox_backend is 'auto' in production. "
                "This will silently fall back to subprocess if Docker is unavailable. "
                "Set EROCK_SANDBOX_BACKEND explicitly (e.g. 'docker' or 'subprocess')."
            )
        if self.sandboxing_enabled and self.sandbox_backend == "noop":
            errors.append(
                "sandbox_backend is 'noop' in production. "
                "Noop sandbox provides zero isolation. "
                "Use 'docker' or 'subprocess' explicitly."
            )

        # 5. API key must not be empty when auth is enabled
        if self.auth_enabled and not self.api_key:
            warnings.append(
                "auth_enabled is True but api_key is not set. "
                "JWT-based auth will work, but API key auth will be unavailable."
            )

        for w in warnings:
            logger.warning("Production config warning: %s", w)

        if errors:
            raise ProductionConfigError(
                "Production configuration has insecure defaults:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )


@functools.lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    settings = Settings()
    if settings.is_production:
        settings.validate_production()
    return settings
