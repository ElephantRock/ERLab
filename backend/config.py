"""Application configuration via environment variables."""

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
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Pipeline Defaults
    generation_rounds: int = 2
    ideas_per_round: int = 3
    novelty_top_k: int = 20

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

    # Knowledge Graph (Phase 4)
    knowledge_graph_path: str = "./data/knowledge_graph.json"

    # World Model (Phase 5)
    world_model_path: str = "./data/world_model.json"

    # Governance (Phase 5)
    governance_enabled: bool = True
    governance_audit_path: str = "./data/governance_audit.jsonl"

    # Goals (Phase 5)
    goals_path: str = "./data/goals.json"


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
