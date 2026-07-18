"""Provider registry with dynamic registration, override management, and cost tracking."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.providers.secrets import KeyVault

from backend.api.errors import ProviderConfigurationError
from backend.config import get_settings
from backend.providers.base import CostEvent, LLMProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Mutable provider registry with override tracking and health checking.

    Inspired by Paperclip's mutable adapter registry with override pause/resume.
    Built-in providers are registered at init. External providers can be
    added, removed, or overridden at runtime without restart.
    """

    def __init__(self) -> None:
        self._providers: dict[str, type[LLMProvider]] = {}
        self._overrides: dict[str, type[LLMProvider]] = {}
        self._builtin_fallbacks: dict[str, type[LLMProvider]] = {}
        self._paused_overrides: set[str] = set()
        self._cost_tracker: CostTracker | None = None
        self._auto_register_builtins()

    def _auto_register_builtins(self) -> None:
        _BUILTIN_IMPORTS = [
            ("openai", "backend.providers.openai_provider", "OpenAIProvider"),
            ("anthropic", "backend.providers.anthropic_provider", "AnthropicProvider"),
            ("gemini", "backend.providers.gemini_provider", "GeminiProvider"),
            ("ollama", "backend.providers.ollama_provider", "OllamaProvider"),
            ("litellm", "backend.providers.litellm_provider", "LiteLLMProvider"),
            # LM Studio uses OpenAI-compatible /v1/chat/completions endpoint
            ("lmstudio", "backend.providers.openai_provider", "OpenAIProvider"),
        ]
        for name, module_path, cls_name in _BUILTIN_IMPORTS:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                self._providers[name] = getattr(mod, cls_name)
            except ImportError:
                logger.debug("Skipping provider '%s': dependency not installed", name)

    def register(self, name: str, cls: type[LLMProvider]) -> None:
        self._providers[name] = cls
        logger.info("Registered provider: %s", name)

    def unregister(self, name: str) -> bool:
        if name in self._providers:
            del self._providers[name]
            self._overrides.pop(name, None)
            self._builtin_fallbacks.pop(name, None)
            self._paused_overrides.discard(name)
            logger.info("Unregistered provider: %s", name)
            return True
        return False

    def override(self, name: str, cls: type[LLMProvider]) -> None:
        """Override a provider with a custom implementation. Original is kept as fallback."""
        if name in self._providers:
            self._builtin_fallbacks[name] = self._providers[name]
        self._overrides[name] = cls
        self._providers[name] = cls
        logger.info("Overrode provider: %s", name)

    def set_override_paused(self, name: str, paused: bool) -> None:
        """Pause/resume an override, falling back to the builtin."""
        if paused and name in self._overrides and name in self._builtin_fallbacks:
            self._providers[name] = self._builtin_fallbacks[name]
            self._paused_overrides.add(name)
            logger.info("Paused override for provider: %s", name)
        elif not paused and name in self._paused_overrides and name in self._overrides:
            self._providers[name] = self._overrides[name]
            self._paused_overrides.discard(name)
            logger.info("Resumed override for provider: %s", name)

    def get(self, name: str) -> type[LLMProvider] | None:
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    def set_cost_tracker(self, tracker: CostTracker) -> None:
        self._cost_tracker = tracker

    @property
    def cost_tracker(self) -> CostTracker | None:
        return self._cost_tracker

    def create(self, name: str | None = None, settings: Any = None) -> LLMProvider:
        """Create a configured provider instance.

        If name is None, uses settings.default_provider.
        If the provider name is unknown, falls back to LiteLLM when enabled.
        """
        settings = settings or get_settings()
        name = name or settings.default_provider

        self._validate_api_key(name, settings)

        if name not in self._providers:
            if getattr(settings, "litellm_fallback_enabled", False):
                from backend.providers.litellm_provider import LiteLLMProvider

                logger.info("Unknown provider '%s' — routing through LiteLLM", name)
                return LiteLLMProvider(model=name, api_key=settings.openai_api_key)
            raise ValueError(
                f"Unknown provider: {name}. Available: {self.list_providers()}"
            )

        cls = self._providers[name]
        provider = self._construct_provider(cls, name, settings)

        if self._cost_tracker:
            provider.set_cost_callback(self._cost_tracker.record)

        if getattr(settings, "caching_enabled", False):
            provider = _wrap_cached(provider, name, settings)

        if getattr(settings, "resilience_enabled", False):
            provider = _wrap_resilient(provider, name, settings)

        return provider

    def _construct_provider(
        self, cls: type[LLMProvider], name: str, settings: Any
    ) -> LLMProvider:
        """Generic provider constructor. Routes by name to pass the right settings."""
        if name == "openai":
            return cls(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                base_url=settings.openai_base_url,
            )
        elif name == "anthropic":
            return cls(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                base_url=settings.anthropic_base_url,
            )
        elif name == "gemini":
            return cls(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
            )
        elif name == "ollama":
            return cls(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
            )
        elif name == "litellm":
            return cls(
                model=settings.litellm_model,
                api_key=settings.openai_api_key,
            )
        elif name == "lmstudio":
            # LM Studio — OpenAI SDK pointed at local server
            # OpenAI SDK needs /v1 suffix; LM Studio serves at root
            base = settings.lmstudio_base_url.rstrip("/")
            if not base.endswith("/v1"):
                base += "/v1"
            return cls(
                api_key="lm-studio",
                model=settings.lmstudio_model,
                base_url=base,
            )
        else:
            return cls()

    @staticmethod
    def _validate_api_key(provider_name: str, settings: Any) -> None:
        _KEY_MAP = {
            "openai": ("openai_api_key", "EROCK_OPENAI_API_KEY"),
            "anthropic": ("anthropic_api_key", "EROCK_ANTHROPIC_API_KEY"),
            "gemini": ("gemini_api_key", "EROCK_GEMINI_API_KEY"),
            "litellm": ("openai_api_key", "EROCK_OPENAI_API_KEY"),
        }
        if provider_name not in _KEY_MAP:
            return
        attr_name, env_var = _KEY_MAP[provider_name]
        value = getattr(settings, attr_name, None)
        if not value or not value.strip():
            raise ProviderConfigurationError(
                detail=f"{env_var} not set",
                hint=(
                    f"Add it to .env or set the environment variable: "
                    f"export {env_var}=sk-... "
                    f"Or switch to a provider that doesn't require a key: ollama"
                ),
            )


# Module-level singleton
_registry: ProviderRegistry | None = None


def _get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def get_registry() -> ProviderRegistry:
    """Get the global provider registry."""
    return _get_registry()


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    """Register a custom provider. Backward-compatible entry point."""
    _get_registry().register(name, cls)


def create_provider(name: str | None = None) -> LLMProvider:
    """Create a configured provider. Drop-in replacement for the old factory."""
    return _get_registry().create(name)


def get_thinking_provider(settings: Any = None) -> LLMProvider:
    """Get the provider configured for thinking tasks (classification, extraction).

    If thinking_model is not configured, returns the default provider (HB-01).
    Falls back to generation provider on error (HB-02).
    """
    settings = settings or get_settings()
    model_name = getattr(settings, "thinking_model", "")
    if not model_name:
        return _get_registry().create(settings=settings)
    try:
        return _get_registry().create(name=model_name, settings=settings)
    except Exception as e:
        logger.warning("Thinking model '%s' unavailable, falling back to default: %s", model_name, e)
        return _get_registry().create(settings=settings)


def get_generation_provider(settings: Any = None) -> LLMProvider:
    """Get the provider configured for generation tasks (writing, synthesis).

    If generation_model is not configured, returns the default provider (HB-01).
    """
    settings = settings or get_settings()
    model_name = getattr(settings, "generation_model", "")
    if not model_name:
        return _get_registry().create(settings=settings)
    try:
        return _get_registry().create(name=model_name, settings=settings)
    except Exception as e:
        logger.warning("Generation model '%s' unavailable, falling back to default: %s", model_name, e)
        return _get_registry().create(settings=settings)


def _validate_api_key(provider_name: str, settings: Any) -> None:
    """Backward-compatible module-level alias."""
    ProviderRegistry._validate_api_key(provider_name, settings)


# ---- Resilience Wiring ----

_vault: KeyVault | None = None


def _get_vault(settings: Any) -> KeyVault | None:
    global _vault
    if _vault is not None:
        return _vault
    if not getattr(settings, "secrets_master_password", None):
        return None
    from backend.providers.secrets import KeyVault

    _vault = KeyVault(
        master_password=settings.secrets_master_password,
        persist_path=f"{settings.secrets_persist_dir}/vault.json",
    )
    try:
        _vault.load()
    except Exception:
        logger.warning("Failed to load key vault — starting fresh")
    return _vault


def _wrap_cached(
    provider: LLMProvider, name: str, settings: Any
) -> LLMProvider:
    from backend.providers.cache import CachedProvider, InMemoryCache, SemanticCache

    cache_type = getattr(settings, "caching_type", "memory")
    max_size = getattr(settings, "caching_max_size", 1000)
    ttl_seconds = getattr(settings, "caching_ttl_seconds", 3600)

    if cache_type == "semantic":
        from backend.pipeline.knowledge.embedding_providers import create_embedding_provider
        from backend.pipeline.knowledge.embedding_service import EmbeddingService

        emb_provider = create_embedding_provider(
            provider_name=getattr(settings, "embedding_provider", "openai"),
            model=getattr(settings, "embedding_model", "text-embedding-3-small"),
            api_key=getattr(settings, "openai_api_key", ""),
            base_url=settings.ollama_base_url,
            dimension=getattr(settings, "embedding_dimension", 1536) or None,
        )
        emb_service = EmbeddingService(
            emb_provider,
            batch_size=getattr(settings, "embedding_batch_size", 100),
        )
        semantic_cache = SemanticCache(
            embedding_service=emb_service,
            persist_dir=getattr(settings, "caching_persist_dir", "./data/chroma"),
            similarity_threshold=getattr(settings, "caching_similarity_threshold", 0.95),
            ttl_seconds=ttl_seconds,
            max_size=max_size,
        )
        memory_cache = InMemoryCache(max_size=max_size, ttl_seconds=ttl_seconds)
        return CachedProvider(
            wrapped=provider,
            cache=memory_cache,
            cache_type="semantic",
            semantic_cache=semantic_cache,
        )

    memory_cache = InMemoryCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return CachedProvider(wrapped=provider, cache=memory_cache, cache_type="memory")


def _wrap_resilient(
    provider: LLMProvider, name: str, settings: Any
) -> LLMProvider:
    from backend.providers.resilience import CircuitBreaker, ResilientProvider, RetryConfig
    from backend.providers.resilience.circuit_breaker import _breakers

    breaker = _breakers.setdefault(
        name,
        CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            reset_timeout=settings.circuit_breaker_reset_timeout,
            cooldown_percent=getattr(settings, "circuit_breaker_cooldown_percent", 0.1),
        ),
    )
    retry_config = RetryConfig(
        max_retries=settings.retry_max_retries,
        base_delay=settings.retry_base_delay,
        max_delay=settings.retry_max_delay,
        cooldown_delay=settings.retry_cooldown_delay,
    )
    vault = _get_vault(settings)
    return ResilientProvider(provider, breaker, retry_config, vault)


# ---- Cost Tracking ----

class CostTracker:
    """Per-provider cost tracking with multi-dimensional aggregation.

    Inspired by Paperclip's cost tracking with 6 aggregation dimensions.
    """

    # Rough per-1K-token costs (USD). Can be overridden per provider/model.
    DEFAULT_COSTS: dict[str, dict[str, float]] = {
        "openai": {"input": 0.0025, "output": 0.01},
        "anthropic": {"input": 0.003, "output": 0.015},
        "gemini": {"input": 0.00125, "output": 0.005},
        "ollama": {"input": 0.0, "output": 0.0},
        "lmstudio": {"input": 0.0, "output": 0.0},
        "litellm": {"input": 0.0025, "output": 0.01},
    }

    def __init__(self) -> None:
        self._events: list[CostEvent] = []
        self._cost_overrides: dict[str, dict[str, float]] = {}

    def set_cost_per_1k(self, provider: str, input_cost: float, output_cost: float) -> None:
        self._cost_overrides[provider] = {"input": input_cost, "output": output_cost}

    def record(self, event: CostEvent) -> None:
        if event.cost_usd == 0.0:
            rates = self._cost_overrides.get(event.provider, self.DEFAULT_COSTS.get(event.provider, {"input": 0.0, "output": 0.0}))
            event.cost_usd = (
                (event.input_tokens / 1000.0) * rates.get("input", 0.0)
                + (event.output_tokens / 1000.0) * rates.get("output", 0.0)
            )
        self._events.append(event)

    def summary(self) -> dict[str, Any]:
        if not self._events:
            return {"total_cost_usd": 0.0, "total_tokens": 0, "event_count": 0}
        return {
            "total_cost_usd": sum(e.cost_usd for e in self._events),
            "total_tokens": sum(e.total_tokens for e in self._events),
            "total_input_tokens": sum(e.input_tokens for e in self._events),
            "total_output_tokens": sum(e.output_tokens for e in self._events),
            "event_count": len(self._events),
        }

    def by_provider(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for e in self._events:
            if e.provider not in result:
                result[e.provider] = {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
            r = result[e.provider]
            r["cost_usd"] += e.cost_usd
            r["input_tokens"] += e.input_tokens
            r["output_tokens"] += e.output_tokens
            r["calls"] += 1
        return result

    def by_stage(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for e in self._events:
            stage = e.stage or "unspecified"
            if stage not in result:
                result[stage] = {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
            r = result[stage]
            r["cost_usd"] += e.cost_usd
            r["input_tokens"] += e.input_tokens
            r["output_tokens"] += e.output_tokens
            r["calls"] += 1
        return result

    def by_model(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for e in self._events:
            key = f"{e.provider}/{e.model}"
            if key not in result:
                result[key] = {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
            r = result[key]
            r["cost_usd"] += e.cost_usd
            r["input_tokens"] += e.input_tokens
            r["output_tokens"] += e.output_tokens
            r["calls"] += 1
        return result

    def reset(self) -> None:
        self._events.clear()

    def events_in_range(self, start: float, end: float) -> list:
        """Return cost events whose timestamp falls within [start, end] epoch seconds."""
        return [
            e for e in self._events
            if start <= e.timestamp.timestamp() <= end
        ]

    def persist(self, path: str) -> None:
        """Write all cost events to a JSONL file."""
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for e in self._events:
                line = json.dumps({
                    "provider": e.provider,
                    "model": e.model,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "cost_usd": e.cost_usd,
                    "stage": e.stage,
                    "run_id": e.run_id,
                    "timestamp": e.timestamp.isoformat(),
                })
                f.write(line + "\n")

    @classmethod
    def load(cls, path: str) -> "CostTracker":
        """Load cost events from a JSONL file."""
        tracker = cls()
        from backend.providers.base import CostEvent
        from datetime import datetime, timezone
        with open(path, encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                event = CostEvent(
                    provider=data["provider"],
                    model=data["model"],
                    input_tokens=data["input_tokens"],
                    output_tokens=data["output_tokens"],
                    cost_usd=data.get("cost_usd", 0.0),
                    stage=data.get("stage", ""),
                    run_id=data.get("run_id"),
                    timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                )
                tracker._events.append(event)
        return tracker
