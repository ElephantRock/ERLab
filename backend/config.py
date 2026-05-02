"""Application configuration via environment variables."""

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    reranker_enabled: bool = False
    reranker_type: str = "llm"  # "llm" or "cross_encoder"
    rrf_k: int = 60  # Reciprocal Rank Fusion constant

    # Query transform (WP-1 completion)
    query_transform_enabled: bool = False

    # LiteLLM model routing (priority 20)
    litellm_fallback_enabled: bool = True
    litellm_model: str = "gpt-4o"

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
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_reset_timeout: float = 60.0
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

    # World Model + Autonomy (WP-8)
    versioning_enabled: bool = True
    activation_enabled: bool = True
    activation_decay_rate: float = 0.5
    activation_spreading_rate: float = 0.1
    activation_noise_std: float = 0.02
    dependency_tracking_enabled: bool = True
    reactive_streams_enabled: bool = True

    # Tree-of-Thought reasoning (P4)
    tree_of_thought_enabled: bool = False
    tree_of_thought_max_depth: int = 3
    tree_of_thought_beam_width: int = 2

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
    stage_retry_base_delay: float = 2.0
    stage_retry_max_delay: float = 120.0
    stage_retry_jitter: float = 0.1
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


@functools.lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
