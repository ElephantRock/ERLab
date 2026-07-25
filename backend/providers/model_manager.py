"""Universal model manager — single entry point for all LLM calls.

Replaces the 4-layer routing stack (ProviderFactory, TaskRouter,
LLMGateway, SmartRouter) with one object that:
  1. Discovers available models at startup
  2. Detects GPU hardware
  3. Assigns models to stages based on requirements
  4. Creates and caches provider instances
  5. Routes calls to the right provider
  6. Measures capability from every real call

Usage:
    from backend.providers.model_manager import model_manager

    # At app startup:
    await model_manager.initialize()

    # In any pipeline stage:
    provider = model_manager.get_provider("proposal_synthesis")
    result = await provider.complete(messages)
"""

from __future__ import annotations

import logging
from typing import Any

from backend.providers.base import LLMProvider
from backend.providers.catalog import EndpointConfig, ModelCatalog, ModelInfo
from backend.providers.hardware import GPUInfo, HardwareDetector
from backend.providers.selector import ModelSelector

logger = logging.getLogger(__name__)


class ModelManager:
    """Universal model manager. Single entry point for all LLM calls.

    Thread-safe singleton pattern. Initialize once at app startup,
    then call get_provider(stage) from anywhere.
    """

    def __init__(self) -> None:
        self._catalog = ModelCatalog([])
        self._hardware = HardwareDetector()
        self._selector: ModelSelector | None = None
        self._providers: dict[str, LLMProvider] = {}  # model_id → provider
        self._stage_assignments: dict[str, ModelInfo] = {}
        self._gpu: GPUInfo | None = None
        self._initialized = False
        self._settings: Any = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self, settings: Any = None) -> None:
        """Discover models, detect hardware, assign stages.

        Called once at app startup. Can be called again to re-discover
        (e.g., after adding/removing models).
        """
        from backend.config import get_settings

        self._settings = settings or get_settings()

        # 1. Detect GPU
        self._gpu = self._hardware.detect_gpu()

        # Apply VRAM override if configured (for remote inference servers)
        override_mb = getattr(self._settings, "gpu_override_vram_mb", 0)
        if override_mb > 0:
            self._gpu = GPUInfo(
                name=self._gpu.name if self._gpu else "Custom (override)",
                vram_total_bytes=override_mb * 1024 * 1024,
                vram_available_bytes=override_mb * 1024 * 1024,
                compute_capability=self._gpu.compute_capability if self._gpu else "unknown",
                driver_version=self._gpu.driver_version if self._gpu else "unknown",
            )
            logger.info(
                "GPU VRAM override: %d MB", override_mb,
            )
        elif not getattr(self._settings, "gpu_auto_detect", True) and self._gpu is None:
            # Auto-detect disabled and no GPU found — use configured value
            configured_mb = getattr(self._settings, "gpu_vram_mb", 12288)
            if configured_mb > 0:
                self._gpu = GPUInfo(
                    name="Configured",
                    vram_total_bytes=configured_mb * 1024 * 1024,
                    vram_available_bytes=configured_mb * 1024 * 1024,
                    compute_capability="unknown",
                    driver_version="unknown",
                )
        if self._gpu:
            logger.info(
                "GPU: %s (%.1f GB VRAM)",
                self._gpu.name,
                self._gpu.vram_total_gb,
            )
        else:
            logger.info("No GPU detected — CPU-only mode")

        # 2. Build endpoint configs from settings
        endpoints = self._build_endpoints(self._settings)
        if not endpoints:
            logger.warning("No inference endpoints configured")
            self._initialized = True
            return

        # 3. Discover all models
        self._catalog = ModelCatalog(endpoints)
        discovered = await self._catalog.discover_all()

        if not discovered:
            logger.warning("No models discovered across %d endpoints", len(endpoints))
            self._initialized = True
            return

        # 4. Assign stages
        self._selector = ModelSelector(
            self._catalog, self._gpu,
            preferred_model=getattr(self._settings, "lmstudio_model", None),
        )
        self._stage_assignments = self._selector.assign_all()

        # 5. Log the plan
        self._log_assignments()

        self._initialized = True

    # ------------------------------------------------------------------
    # Public API — the 3 methods everyone uses
    # ------------------------------------------------------------------

    def get_provider(self, stage: str) -> LLMProvider:
        """Get the provider assigned to a pipeline stage.

        This is the ONLY way to get an LLM provider. All call sites
        should use this instead of create_provider() or direct
        provider.complete() calls.

        Runtime precedence:
        1. Per-stage real model override (model_assignments.json)
        2. Auto-assigned stage model (selector fitness scoring)
        3. Default/fallback model

        Args:
            stage: Pipeline stage name, e.g. "proposal_synthesis"

        Returns:
            LLMProvider instance for the assigned model.

        Raises:
            RuntimeError: If ModelManager hasn't been initialized.
        """
        if not self._initialized:
            raise RuntimeError(
                "ModelManager not initialized. Call await model_manager.initialize() first."
            )

        # 1. Check explicit per-stage override first
        from backend.api.model_assignments import get_stage_override
        override_id = get_stage_override(stage)
        if override_id:
            override_model = self._catalog.get_model(override_id)
            if override_model and override_model.health_status != "unreachable":
                logger.info(
                    "Using override model '%s' for stage '%s'",
                    override_model.model_id, stage,
                )
                return self._get_or_create_provider(override_model)
            else:
                logger.warning(
                    "Override model '%s' for stage '%s' not available, "
                    "falling back to auto-assignment",
                    override_id, stage,
                )

        # 2. Auto-assigned model from selector
        model = self._stage_assignments.get(stage)
        if model is None:
            # 3. Fallback: try to get any healthy model
            model = self._get_default_model()
            if model is None:
                raise RuntimeError(
                    f"No model available for stage '{stage}' and no fallback model found"
                )

        return self._get_or_create_provider(model)

    def get_stage_model(self, stage: str) -> ModelInfo | None:
        """Get the ModelInfo for a stage's assigned model."""
        return self._stage_assignments.get(stage)

    def get_assignments(self) -> dict[str, ModelInfo]:
        """Return the full stage → model assignment map."""
        return dict(self._stage_assignments)

    def get_catalog(self) -> ModelCatalog:
        """Return the model catalog (for admin/debug endpoints)."""
        return self._catalog

    def get_gpu_info(self) -> GPUInfo | None:
        """Return detected GPU info."""
        return self._gpu

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Convenience methods — route + measure in one call
    # ------------------------------------------------------------------

    async def complete(
        self,
        stage: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Route a completion to the right model for a stage."""
        provider = self.get_provider(stage)
        result = await provider.complete(messages, temperature, max_tokens)
        self._record_call(stage, success=True)
        return result

    async def complete_with_usage(
        self,
        stage: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Any:
        """Route a completion-with-usage to the right model for a stage."""
        provider = self.get_provider(stage)
        result = await provider.complete_with_usage(messages, temperature, max_tokens)
        self._record_call(stage, success=True)
        return result

    async def structured_output(
        self,
        stage: str,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> dict:
        """Route structured output to the right model for a stage."""
        provider = self.get_provider(stage)
        result = await provider.structured_output(messages, schema, temperature)
        self._record_call(stage, success=True, json_success=True)
        return result

    async def structured_output_with_usage(
        self,
        stage: str,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.3,
    ) -> Any:
        """Route structured output with usage to the right model for a stage."""
        provider = self.get_provider(stage)
        result = await provider.structured_output_with_usage(
            messages, schema, temperature, stage=stage,
        )
        self._record_call(stage, success=True, json_success=True)
        return result

    async def complete_with_tools(
        self,
        stage: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Any:
        """Route a tool-calling completion to the right model for a stage."""
        provider = self.get_provider(stage)
        result = await provider.complete_with_tools(
            messages, tools, temperature, max_tokens, stage=stage
        )
        self._record_call(stage, success=True)
        return result

    # ------------------------------------------------------------------
    # Reload
    # ------------------------------------------------------------------

    async def reload(self) -> None:
        """Re-discover models and re-assign stages."""
        logger.info("Reloading model manager...")
        self._providers.clear()
        self._stage_assignments.clear()
        await self.initialize(self._settings)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_endpoints(self, settings: Any) -> list[EndpointConfig]:
        """Build endpoint configs from settings.

        Only includes endpoints that are configured and have non-placeholder values.
        """
        endpoints: list[EndpointConfig] = []

        # LM Studio (local inference)
        if getattr(settings, "lmstudio_enabled", False):
            base = getattr(settings, "lmstudio_base_url", "http://localhost:1234")
            endpoints.append(
                EndpointConfig(
                    url=base,
                    api_key="lm-studio",
                    server_type="auto",
                    provider_type="openai_compatible",
                    display_name="LM Studio",
                )
            )

        # Ollama (local inference)
        ollama_url = getattr(settings, "ollama_base_url", "")
        if ollama_url and ollama_url != "http://localhost:11434":
            # Explicitly configured non-default URL
            endpoints.append(
                EndpointConfig(
                    url=ollama_url,
                    server_type="ollama",
                    provider_type="openai_compatible",
                    display_name="Ollama",
                )
            )
        elif settings.default_provider == "ollama":
            # Default provider is ollama — include default URL
            endpoints.append(
                EndpointConfig(
                    url="http://localhost:11434",
                    server_type="ollama",
                    provider_type="openai_compatible",
                    display_name="Ollama",
                )
            )

        # vLLM / any OpenAI-compatible server
        vllm_url = getattr(settings, "vllm_base_url", "")
        if vllm_url:
            endpoints.append(
                EndpointConfig(
                    url=vllm_url,
                    server_type="auto",
                    provider_type="openai_compatible",
                    display_name="vLLM",
                )
            )

        # Anthropic-compatible (includes Z.AI proxy)
        anthropic_key = settings.anthropic_api_key
        if anthropic_key and anthropic_key != "YOUR_API_KEY_HERE":
            anthropic_url = getattr(settings, "anthropic_base_url", None)
            anthropic_model = getattr(settings, "anthropic_model", "")
            endpoints.append(
                EndpointConfig(
                    url=anthropic_url or "https://api.anthropic.com",
                    api_key=anthropic_key,
                    server_type="anthropic",
                    provider_type="anthropic",
                    model_override=anthropic_model or None,
                    display_name="Anthropic/Z.AI",
                )
            )

        # OpenAI (or OpenAI-compatible, e.g. z.ai proxy — use the configured
        # base_url rather than a hardcoded api.openai.com default). When the
        # endpoint doesn't support /v1/models discovery (common with proxies),
        # model_override registers the configured model directly.
        openai_key = settings.openai_api_key
        if openai_key and openai_key != "YOUR_API_KEY_HERE":
            openai_url = getattr(settings, "openai_base_url", "") or "https://api.openai.com/v1"
            openai_model = getattr(settings, "openai_model", "") or None
            endpoints.append(
                EndpointConfig(
                    url=openai_url,
                    api_key=openai_key,
                    server_type="openai",
                    provider_type="openai",
                    model_override=openai_model,
                    display_name="OpenAI",
                )
            )

        # Gemini
        gemini_key = settings.gemini_api_key
        if gemini_key and gemini_key != "YOUR_API_KEY_HERE":
            endpoints.append(
                EndpointConfig(
                    url="https://generativelanguage.googleapis.com",
                    api_key=gemini_key,
                    server_type="gemini",
                    provider_type="gemini",
                    display_name="Gemini",
                )
            )

        return endpoints

    def _get_or_create_provider(self, model: ModelInfo) -> LLMProvider:
        """Get a cached provider or create one for this model."""
        if model.model_id in self._providers:
            return self._providers[model.model_id]

        provider = self._create_provider_for_model(model)
        self._providers[model.model_id] = provider
        logger.debug(
            "Created provider for %s (%s) → %s",
            model.model_id,
            model.provider_type,
            model.endpoint_url,
        )
        return provider

    def _create_provider_for_model(self, model: ModelInfo) -> LLMProvider:
        """Create the right provider type for a model.

        All OpenAI-compatible servers (LM Studio, vLLM, Ollama, generic)
        use OpenAIProvider. Cloud APIs use their native providers.
        """
        if model.provider_type == "openai_compatible":
            from backend.providers.openai_provider import OpenAIProvider

            return OpenAIProvider(
                api_key=model.api_key or "unused",
                model=model.model_id,
                base_url=model.endpoint_url,
            )
        elif model.provider_type == "anthropic":
            try:
                from backend.providers.anthropic_provider import AnthropicProvider

                return AnthropicProvider(
                    api_key=model.api_key or "",
                    model=model.model_id,
                    base_url=model.endpoint_url,
                )
            except ImportError:
                # Fall back to OpenAI-compatible if Anthropic provider missing
                from backend.providers.openai_provider import OpenAIProvider

                logger.warning(
                    "AnthropicProvider not available, using OpenAI-compatible for %s",
                    model.model_id,
                )
                return OpenAIProvider(
                    api_key=model.api_key or "unused",
                    model=model.model_id,
                    base_url=model.endpoint_url,
                )
        elif model.provider_type == "gemini":
            try:
                from backend.providers.gemini_provider import GeminiProvider

                return GeminiProvider(
                    api_key=model.api_key or "",
                    model=model.model_id,
                )
            except ImportError:
                logger.warning(
                    "GeminiProvider not available for %s", model.model_id
                )
                from backend.providers.openai_provider import OpenAIProvider

                return OpenAIProvider(
                    api_key=model.api_key or "unused",
                    model=model.model_id,
                    base_url=model.endpoint_url,
                )
        else:
            # Fallback: try OpenAI-compatible (works for most servers)
            from backend.providers.openai_provider import OpenAIProvider

            return OpenAIProvider(
                api_key=model.api_key or "unused",
                model=model.model_id,
                base_url=model.endpoint_url,
            )

    def _get_default_model(self) -> ModelInfo | None:
        """Get the best available model as a default fallback."""
        healthy = self._catalog.get_healthy_models()
        if not healthy:
            return None
        # Prefer loaded models, then largest context
        healthy.sort(
            key=lambda m: (m.is_loaded, m.context_length), reverse=True
        )
        return healthy[0]

    def _record_call(
        self,
        stage: str,
        success: bool = True,
        json_success: bool | None = None,
    ) -> None:
        """Record measurement data from a real LLM call."""
        model = self._stage_assignments.get(stage)
        if model is None:
            return
        self._catalog.update_measured(
            model.model_id,
            total_calls=(
                (model.measured.total_calls if model.measured else 0) + 1
            ),
            failed_calls=(
                (model.measured.failed_calls if model.measured else 0) + (0 if success else 1)
            ),
        )
        if json_success is not None and model.measured:
            # Exponential moving average for JSON reliability
            old = model.measured.json_reliability
            new_val = 1.0 if json_success else 0.0
            model.measured.json_reliability = old * 0.9 + new_val * 0.1

    def _log_assignments(self) -> None:
        """Log the stage → model assignment plan."""
        logger.info("=" * 70)
        logger.info("MODEL ASSIGNMENTS (Universal Model Manager)")
        logger.info("=" * 70)
        if self._gpu:
            logger.info(
                "Hardware: %s (%.1f GB VRAM)",
                self._gpu.name,
                self._gpu.vram_total_gb,
            )
        else:
            logger.info("Hardware: CPU-only mode")

        total_models = len(self._catalog)
        loaded = len(self._catalog.get_loaded_models())
        logger.info("Catalog: %d models discovered (%d loaded)", total_models, loaded)
        logger.info("-" * 70)

        for stage, model in sorted(self._stage_assignments.items()):
            ctx = model.context_label
            loaded_mark = "●" if model.is_loaded else "○"
            logger.info(
                "  %s %-25s → %-40s (%s, %s, %s ctx)",
                loaded_mark,
                stage,
                model.model_id,
                model.parameter_count,
                model.quantization,
                ctx,
            )

        # Check for stages without assignments
        from backend.providers.selector import STAGE_REQUIREMENTS

        unassigned = []
        for stage_name, req in STAGE_REQUIREMENTS.items():
            if req.quality_tier > 0 and stage_name not in self._stage_assignments:
                unassigned.append(stage_name)
        if unassigned:
            logger.warning(
                "Unassigned stages (no suitable model found): %s",
                ", ".join(unassigned),
            )

        logger.info("=" * 70)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_model_manager: ModelManager | None = None


def get_model_manager() -> ModelManager:
    """Get the global ModelManager singleton."""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


def reset_model_manager() -> None:
    """Reset the singleton (for testing)."""
    global _model_manager
    _model_manager = None
