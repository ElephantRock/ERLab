"""Model capability registry — knows what every model can do.

Combines three data sources:
1. Static YAML config (capabilities.yaml)
2. Live LM Studio probing (actual context windows, loaded status)
3. Empirical reliability data (from past runs, not yet implemented)

Usage:
    registry = ModelCapabilityRegistry()
    await registry.refresh()  # probe LM Studio
    caps = registry.get("qwen/qwen3-4b-2507")
    print(caps.context_window)  # 8192 (live from LM Studio, not hardcoded)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelCapabilities:
    """What a model can do and how well it does it."""

    model_id: str
    provider: str                 # "lmstudio", "anthropic", "openai", etc.
    context_window: int           # total context capacity (live, not hardcoded)
    safe_input_tokens: int = 0     # context_window * 0.70 (leave room for output), auto-computed
    supports_system_prompt: bool = True
    supports_json_schema: bool = False
    supports_tools: bool = False
    roles: set[str] = field(default_factory=set)  # {"draft", "reason", "synthesize", "critique"}
    reliability: dict[str, float] = field(default_factory=dict)  # {"schema_following": 0.6}
    latency_class: str = "local_fast"  # "local_fast", "local_medium", "cloud_medium", "cloud_slow"
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    loaded: bool = True           # is this model currently loaded?
    source: str = "static"        # "static" | "probe" | "empirical"

    def __post_init__(self):
        if not self.safe_input_tokens:
            self.safe_input_tokens = int(self.context_window * 0.70)

    def can_handle(self, input_tokens: int, output_tokens: int = 2048) -> bool:
        """Check if this model can handle a request of given size."""
        return (input_tokens + output_tokens) <= self.context_window * 0.85

    @property
    def max_output_for_input(self, input_tokens: int) -> int:
        """Max output tokens available given input size."""
        budget = int(self.context_window * 0.85)
        return max(0, budget - input_tokens)


# Default capabilities for common models (used before probing)
_STATIC_DEFAULTS: dict[str, dict[str, Any]] = {
    "qwen/qwen3-4b-2507": {
        "provider": "lmstudio",
        "context_window": 4096,  # overridden by probe
        "roles": {"draft", "reason"},
        "supports_json_schema": False,
        "supports_tools": True,
        "reliability": {
            "schema_following": 0.4,
            "citation_grounding": 0.2,
            "long_synthesis": 0.3,
            "scoring": 0.3,
        },
        "latency_class": "local_fast",
    },
    "qwen2.5-14b-instruct": {
        "provider": "lmstudio",
        "context_window": 32768,
        "roles": {"reason", "synthesize", "critique"},
        "supports_json_schema": True,
        "supports_tools": True,
        "reliability": {
            "schema_following": 0.6,
            "citation_grounding": 0.4,
            "long_synthesis": 0.5,
            "scoring": 0.5,
        },
        "latency_class": "local_medium",
    },
    "qwen/qwen3.6-27b": {
        "provider": "lmstudio",
        "context_window": 32768,
        "roles": {"synthesize", "critique"},
        "supports_json_schema": True,
        "supports_tools": True,
        "reliability": {
            "schema_following": 0.7,
            "citation_grounding": 0.5,
            "long_synthesis": 0.6,
            "scoring": 0.6,
        },
        "latency_class": "local_medium",
    },
    "thudm_glm-4-32b-0414": {
        "provider": "lmstudio",
        "context_window": 32768,
        "roles": {"synthesize", "critique", "reason"},
        "supports_json_schema": True,
        "supports_tools": True,
        "reliability": {
            "schema_following": 0.7,
            "citation_grounding": 0.5,
            "long_synthesis": 0.6,
        },
        "latency_class": "local_medium",
    },
    "glm-5.1": {
        "provider": "anthropic",
        "context_window": 8192,
        "roles": {"reason", "synthesize", "critique"},
        "supports_json_schema": True,
        "supports_tools": True,
        "reliability": {
            "schema_following": 0.85,
            "citation_grounding": 0.7,
            "long_synthesis": 0.8,
            "scoring": 0.8,
        },
        "latency_class": "cloud_medium",
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
    },
}

# Conservative fallback for unknown models
_UNKNOWN_MODEL = ModelCapabilities(
    model_id="unknown",
    provider="unknown",
    context_window=4096,
    safe_input_tokens=2867,
    roles={"draft"},
    supports_system_prompt=True,
    supports_json_schema=False,
    supports_tools=False,
    reliability={"schema_following": 0.2, "citation_grounding": 0.1, "long_synthesis": 0.1},
    latency_class="local_fast",
    loaded=True,
    source="fallback",
)


class ModelCapabilityRegistry:
    """Registry of model capabilities.

    Populated from static defaults, then updated by live probing.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, ModelCapabilities] = {}
        self._load_static_defaults()

    def _load_static_defaults(self) -> None:
        """Load static capability defaults."""
        for model_id, data in _STATIC_DEFAULTS.items():
            self._capabilities[model_id] = ModelCapabilities(
                model_id=model_id,
                source="static",
                **data,
            )

    async def refresh(self, lmstudio_url: str | None = None) -> None:
        """Refresh capabilities by probing live providers.

        Args:
            lmstudio_url: LM Studio base URL (e.g., "http://100.64.0.1:1234").
                         If None, skips LM Studio probing.
        """
        if lmstudio_url:
            await self._probe_lmstudio(lmstudio_url)

    async def _probe_lmstudio(self, base_url: str) -> None:
        """Probe LM Studio for live model capabilities."""
        try:
            import httpx

            r = await httpx.AsyncClient(timeout=10.0).get(
                f"{base_url}/api/v1/models"
            )
            if r.status_code != 200:
                logger.warning("LM Studio probe failed: status %d", r.status_code)
                return

            data = r.json()
            for model_info in data.get("models", []):
                model_key = model_info.get("key", "")
                model_type = model_info.get("type", "")

                # Only process LLM models (not embedding/reranker)
                if model_type != "llm":
                    continue

                # Get live context window from loaded instances
                instances = model_info.get("loaded_instances", [])
                if instances:
                    inst = instances[0]
                    live_context = inst.get("config", {}).get("context_length", 4096)
                    loaded = True
                else:
                    # Model exists but not loaded — use max_context_length
                    live_context = model_info.get("max_context_length", 4096)
                    loaded = False

                # Update or create capability entry
                if model_key in self._capabilities:
                    # Update existing with live data
                    caps = self._capabilities[model_key]
                    caps.context_window = live_context
                    caps.safe_input_tokens = int(live_context * 0.70)
                    caps.loaded = loaded
                    caps.source = "probe"
                    logger.info(
                        "Probed %s: ctx=%d, loaded=%s",
                        model_key, live_context, loaded,
                    )
                else:
                    # New model discovered by probe
                    self._capabilities[model_key] = ModelCapabilities(
                        model_id=model_key,
                        provider="lmstudio",
                        context_window=live_context,
                        safe_input_tokens=int(live_context * 0.70),
                        loaded=loaded,
                        source="probe",
                        latency_class="local_fast",
                    )
                    logger.info(
                        "Discovered %s: ctx=%d, loaded=%s",
                        model_key, live_context, loaded,
                    )

        except Exception as e:
            logger.warning("LM Studio probe failed: %s", str(e)[:100])

    def get(self, model_id: str) -> ModelCapabilities:
        """Get capabilities for a model.

        Tries exact match, then prefix/family match, then unknown fallback.
        """
        # Exact match
        if model_id in self._capabilities:
            return self._capabilities[model_id]

        # Prefix match (e.g., "qwen/qwen3-4b-2507:2" → "qwen/qwen3-4b-2507")
        for key, caps in self._capabilities.items():
            if model_id.startswith(key) or key.startswith(model_id.split(":")[0]):
                return caps

        # Family match
        model_lower = model_id.lower()
        family_map = {
            "qwen": "qwen", "glm": "glm", "gpt": "gpt",
            "claude": "claude", "llama": "llama", "mistral": "mistral",
        }
        for family_prefix, family_name in family_map.items():
            if family_prefix in model_lower:
                for caps in self._capabilities.values():
                    if family_name in caps.model_id.lower():
                        return caps

        logger.debug("Unknown model '%s', using conservative defaults", model_id)
        return _UNKNOWN_MODEL

    def get_for_role(self, role: str, min_context: int = 0) -> list[ModelCapabilities]:
        """Get all models suitable for a given role, sorted by context size."""
        candidates = [
            caps for caps in self._capabilities.values()
            if role in caps.roles
            and caps.loaded
            and caps.context_window >= min_context
        ]
        return sorted(candidates, key=lambda c: c.context_window, reverse=True)

    def get_largest_context(self, loaded_only: bool = True) -> ModelCapabilities | None:
        """Get the model with the largest context window."""
        candidates = [
            caps for caps in self._capabilities.values()
            if (not loaded_only or caps.loaded)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.context_window)

    def list_models(self) -> list[dict]:
        """List all known models with their capabilities."""
        return [
            {
                "model_id": caps.model_id,
                "provider": caps.provider,
                "context_window": caps.context_window,
                "safe_input_tokens": caps.safe_input_tokens,
                "roles": sorted(caps.roles),
                "loaded": caps.loaded,
                "source": caps.source,
                "latency_class": caps.latency_class,
            }
            for caps in sorted(self._capabilities.values(), key=lambda c: c.model_id)
        ]
