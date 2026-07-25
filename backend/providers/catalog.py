"""Model catalog — runtime model discovery and inventory.

Probes inference server endpoints (LM Studio, Ollama, vLLM, cloud APIs)
and builds a live catalog of available models with their capabilities.
No static configuration — everything is discovered at startup.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from backend.providers.hardware import GPUInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class MeasuredCapabilities:
    """Empirically measured capabilities — populated by real LLM calls.

    Every real call updates these numbers. No static profiles,
    no certification suites — just production telemetry.
    """

    json_reliability: float = 0.0  # 0-1: fraction returning valid JSON
    instruction_following: float = 0.0  # 0-1: follows system prompt constraints
    avg_latency_ms: float = 0.0  # average response time
    avg_output_tokens: int = 0  # average tokens per generation
    total_calls: int = 0  # lifetime call count
    failed_calls: int = 0  # lifetime failures
    last_measured: datetime | None = None

    # Per-stage performance (stage_name → score)
    stage_scores: dict[str, float] = field(default_factory=dict)

    @property
    def reliability(self) -> float:
        """Overall reliability (0-1)."""
        if self.total_calls == 0:
            return 0.0
        return 1.0 - (self.failed_calls / self.total_calls)


@dataclass
class ModelInfo:
    """Everything known about a model, discovered at runtime."""

    # Identity
    model_id: str  # e.g. "qwen/qwen3-4b-2507"
    provider_type: str  # "openai_compatible" | "anthropic" | "gemini"
    endpoint_url: str  # base URL of the inference server

    # From /v1/models or /api/v1/models (LM Studio) or /api/tags (Ollama)
    parameter_count: str = "?"  # "4B", "12B", "27B", "35B-A3B"
    context_length: int = 4096  # max context in tokens
    quantization: str = "unknown"  # "Q4_K_M", "BF16", "FP16"
    size_bytes: int = 0  # model file size on disk

    # Capabilities
    supports_json_mode: bool = False  # response_format: json_object
    supports_tools: bool = False  # tool_choice: auto
    supports_vision: bool = False  # image inputs
    supports_thinking: bool = False  # reasoning / thinking tokens

    # Runtime state
    is_loaded: bool = False  # currently in VRAM?
    vram_required_bytes: int = 0  # estimated from size_bytes
    health_status: str = "unknown"  # "healthy" | "degraded" | "unreachable"

    # Optional: API key for this endpoint
    api_key: str | None = None

    # Optional: display name from the server
    display_name: str | None = None

    # Measured capabilities (populated by Profiler, updated by real calls)
    measured: MeasuredCapabilities | None = None

    @property
    def context_label(self) -> str:
        """Human-readable context length, e.g. '32K'."""
        if self.context_length >= 1024:
            return f"{self.context_length // 1024}K"
        return str(self.context_length)

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024**3) if self.size_bytes else 0.0

    def fitness_score(self, min_context: int = 0) -> float:
        """Rough fitness score for ranking. Higher = better."""
        score = 0.0

        # Context length: bonus for meeting requirements, extra for headroom
        if self.context_length >= min_context:
            score += 10.0
            # Bonus for headroom (2x required)
            if min_context > 0:
                ratio = self.context_length / min_context
                score += min(ratio, 4.0) * 2.0  # cap at 8 points

        # Capabilities
        if self.supports_json_mode:
            score += 3.0
        if self.supports_tools:
            score += 2.0
        if self.supports_thinking:
            score += 2.0

        # Measured reliability (weight heavily)
        if self.measured and self.measured.total_calls > 0:
            score += self.measured.reliability * 10.0
            score += self.measured.json_reliability * 5.0

        # Prefer loaded models (no loading delay)
        if self.is_loaded:
            score += 5.0

        # Health
        if self.health_status == "healthy":
            score += 3.0

        # Penalize unreachable
        if self.health_status == "unreachable":
            score -= 100.0

        return score


@dataclass
class EndpointConfig:
    """Configuration for an inference server endpoint."""

    url: str  # base URL, e.g. "http://localhost:1234"
    api_key: str | None = None
    server_type: str = "auto"  # "auto" | "lmstudio" | "ollama" | "vllm" | "anthropic" | "gemini"
    provider_type: str = "openai_compatible"
    model_override: str | None = None  # for cloud APIs that only serve one model
    display_name: str | None = None  # human-readable name


# ---------------------------------------------------------------------------
# Server type detection
# ---------------------------------------------------------------------------


async def detect_server_type(base_url: str) -> str:
    """Auto-detect inference server type from its API shape.

    Probes characteristic endpoints in order of specificity:
    1. LM Studio: /api/v1/models with rich metadata
    2. Ollama: /api/tags
    3. vLLM: /v1/models + /health
    4. Generic OpenAI-compatible: /v1/models only
    """
    # Normalize URL
    url = base_url.rstrip("/")

    async with httpx.AsyncClient(timeout=5.0) as client:
        # 1. LM Studio: /api/v1/models returns rich metadata
        try:
            r = await client.get(f"{url}/api/v1/models")
            if r.status_code == 200:
                data = r.json()
                items = data.get("models", data.get("data", []))
                if isinstance(items, list) and items:
                    first = items[0]
                    if (
                        first.get("type") == "llm"
                        or "max_context_length" in first
                        or "loaded_instances" in first
                        or "params_string" in first
                    ):
                        return "lmstudio"
                    if any(m.get("type") == "llm" for m in items):
                        return "lmstudio"
        except Exception:
            pass

        # 2. Ollama: /api/tags
        try:
            r = await client.get(f"{url}/api/tags")
            if r.status_code == 200:
                return "ollama"
        except Exception:
            pass

        # 3. vLLM: /health returns 200
        try:
            r = await client.get(f"{url}/health")
            if r.status_code == 200:
                return "vllm"
        except Exception:
            pass

        # 4. Generic OpenAI-compatible: /v1/models
        try:
            r = await client.get(f"{url}/v1/models")
            if r.status_code == 200:
                return "openai"
        except Exception:
            pass

    return "unknown"


# ---------------------------------------------------------------------------
# Endpoint probers
# ---------------------------------------------------------------------------


async def probe_lmstudio(base_url: str, api_key: str | None = None) -> list[ModelInfo]:
    """Probe LM Studio's /api/v1/models endpoint.

    LM Studio returns rich metadata per model including capabilities,
    loaded state, context length, and parameter count.
    """
    url = base_url.rstrip("/")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        # Try /api/v1/models first (LM Studio specific)
        r = await client.get(f"{url}/api/v1/models")
        if r.status_code != 200:
            # Fallback to /v1/models
            r = await client.get(f"{url}/v1/models")
        if r.status_code != 200:
            logger.warning("LM Studio at %s returned %d", url, r.status_code)
            return []

        data = r.json()
        models_raw = data.get("models", data.get("data", []))

        # Filter to LLM models only
        if models_raw and isinstance(models_raw, list):
            first = models_raw[0]
            # If items have 'type' field, filter to 'llm' only
            if "type" in first:
                models_raw = [m for m in models_raw if m.get("type") == "llm"]

    models: list[ModelInfo] = []
    for m in models_raw:
        # All items are already filtered to type='llm'

        caps = m.get("capabilities") or {}
        # LM Studio loaded_instances indicates if model is in VRAM
        loaded_instances = m.get("loaded_instances", [])
        is_loaded = bool(loaded_instances) or m.get("is_loaded", False)

        # Extract parameter count from various fields
        metadata = m.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        param_str = (
            m.get("params_string")
            or m.get("parameter_size")
            or metadata.get("size_label", "?")
        )

        # Context length
        ctx_len = m.get("max_context_length", m.get("context_length", 4096))

        # Size
        size = m.get("size_bytes", m.get("size", 0))

        # Quantization
        quant = m.get("quantization", {})
        if isinstance(quant, dict):
            quant_name = quant.get("name", "unknown")
        else:
            quant_name = str(quant)

        # Architecture / reasoning support
        arch = m.get("architecture") or {}
        # architecture can be a string (e.g. "gemma4"), None, or a dict
        if isinstance(arch, str) or arch is None:
            supports_thinking = False  # can't tell from string arch
        else:
            supports_thinking = bool(arch.get("reasoning"))

        # Check capabilities.reasoning (LM Studio returns dict with allowed_options)
        reasoning_caps = caps.get("reasoning")
        if isinstance(reasoning_caps, dict):
            supports_thinking = True  # has reasoning options
        elif isinstance(reasoning_caps, bool) and reasoning_caps:
            supports_thinking = True

        model = ModelInfo(
            model_id=m.get("id", m.get("key", m.get("name", "unknown"))),
            provider_type="openai_compatible",
            endpoint_url=f"{url}/v1",
            parameter_count=param_str,
            context_length=int(ctx_len),
            quantization=quant_name,
            size_bytes=int(size),
            supports_json_mode=True,  # LM Studio supports json_object
            supports_tools=bool(caps.get("trained_for_tool_use", False)),
            supports_vision=bool(caps.get("vision", False)),
            supports_thinking=supports_thinking,
            is_loaded=is_loaded,
            vram_required_bytes=int(size),
            health_status="healthy",
            api_key=api_key,
            display_name=m.get("display_name", m.get("name", m.get("id", None))),
        )
        models.append(model)

    return models


async def probe_ollama(base_url: str) -> list[ModelInfo]:
    """Probe Ollama's /api/tags endpoint."""
    url = base_url.rstrip("/")

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{url}/api/tags")
        if r.status_code != 200:
            logger.warning("Ollama at %s returned %d", url, r.status_code)
            return []

        data = r.json()

    models: list[ModelInfo] = []
    for m in data.get("models", []):
        details = m.get("details", {})
        param_str = details.get("parameter_size", "?")

        # Parse context length from model info
        # Ollama defaults vary by model; try to get from /api/show
        ctx_len = 8192  # conservative default

        families = details.get("families", [])
        if isinstance(families, list):
            supports_vision = "clip" in families
        else:
            supports_vision = False

        model = ModelInfo(
            model_id=m.get("name", "unknown"),
            provider_type="openai_compatible",
            endpoint_url=f"{url}/v1",  # Ollama supports OpenAI-compatible API
            parameter_count=param_str,
            context_length=ctx_len,
            quantization=details.get("quantization_level", "unknown"),
            size_bytes=m.get("size", 0),
            supports_json_mode=True,
            supports_tools=True,
            supports_vision=supports_vision,
            supports_thinking=False,
            is_loaded=True,  # Ollama loads on demand
            vram_required_bytes=m.get("size", 0),
            health_status="healthy",
            display_name=m.get("name", None),
        )
        models.append(model)

    return models


async def probe_vllm(base_url: str, api_key: str | None = None) -> list[ModelInfo]:
    """Probe vLLM's /v1/models endpoint."""
    url = base_url.rstrip("/")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        r = await client.get(f"{url}/v1/models")
        if r.status_code != 200:
            logger.warning("vLLM at %s returned %d", url, r.status_code)
            return []

        data = r.json()

    models: list[ModelInfo] = []
    for m in data.get("data", []):
        model = ModelInfo(
            model_id=m.get("id", "unknown"),
            provider_type="openai_compatible",
            endpoint_url=f"{url}/v1",
            parameter_count="?",
            context_length=m.get("max_model_len", 8192),
            quantization=m.get("quantization", "unknown"),
            size_bytes=0,  # vLLM doesn't report file size
            supports_json_mode=True,  # vLLM supports guided decoding
            supports_tools=True,
            supports_vision=False,
            supports_thinking=False,
            is_loaded=True,  # vLLM keeps models loaded
            vram_required_bytes=0,
            health_status="healthy",
            api_key=api_key,
            display_name=m.get("id", None),
        )
        models.append(model)

    return models


async def probe_openai_compatible(
    base_url: str, api_key: str | None = None
) -> list[ModelInfo]:
    """Probe a generic OpenAI-compatible /v1/models endpoint."""
    url = base_url.rstrip("/")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        r = await client.get(f"{url}/v1/models")
        if r.status_code != 200:
            logger.warning("OpenAI-compatible at %s returned %d", url, r.status_code)
            return []

        data = r.json()

    models: list[ModelInfo] = []
    for m in data.get("data", []):
        # Opportunistically read extended metadata if present.
        # Many OpenAI-compatible servers (LM Studio proxy, vLLM, LocalAI)
        # return richer fields than a stock OpenAI endpoint.
        caps = m.get("capabilities") or {}
        if not isinstance(caps, dict):
            caps = {}

        ctx_len = (
            m.get("max_model_len")
            or m.get("max_context_length")
            or m.get("context_length")
            or 8192
        )

        size_bytes = m.get("size_bytes", 0)
        if not size_bytes and m.get("size_gb"):
            try:
                size_bytes = int(float(m["size_gb"]) * 1e9)
            except (ValueError, TypeError):
                pass

        # Normalise quantization: may be string or dict
        quant_raw = m.get("quantization", "unknown")
        if isinstance(quant_raw, dict):
            quant_name = quant_raw.get("name", "unknown")
        else:
            quant_name = str(quant_raw) if quant_raw else "unknown"

        model = ModelInfo(
            model_id=m.get("id", "unknown"),
            provider_type="openai_compatible",
            endpoint_url=f"{url}/v1",
            parameter_count=str(m.get("parameter_count", "?")),
            context_length=int(ctx_len),
            quantization=quant_name,
            size_bytes=int(size_bytes),
            supports_json_mode=bool(caps.get("json_mode", True)),
            supports_tools=bool(
                caps.get("trained_for_tool_use", caps.get("tools", True))
            ),
            supports_vision=bool(caps.get("vision", False)),
            supports_thinking=bool(
                caps.get("reasoning", caps.get("thinking", False))
            ),
            is_loaded=bool(m.get("is_loaded", True)),
            vram_required_bytes=int(size_bytes),
            health_status="healthy",
            api_key=api_key,
            display_name=m.get("display_name", m.get("id", None)),
        )
        models.append(model)

    return models


def make_cloud_model(
    endpoint: EndpointConfig,
    context_length: int = 200_000,
) -> ModelInfo:
    """Create a ModelInfo for a cloud API (no discovery endpoint)."""
    return ModelInfo(
        model_id=endpoint.model_override or "default",
        provider_type=endpoint.provider_type,
        endpoint_url=endpoint.url,
        parameter_count="cloud",
        context_length=context_length,
        quantization="cloud",
        size_bytes=0,  # cloud — no local VRAM
        supports_json_mode=True,
        supports_tools=True,
        supports_vision=True,
        supports_thinking=True,
        is_loaded=True,  # always available
        vram_required_bytes=0,  # cloud — no local VRAM
        health_status="healthy",
        api_key=endpoint.api_key,
        display_name=endpoint.display_name or endpoint.model_override,
    )


# ---------------------------------------------------------------------------
# ModelCatalog
# ---------------------------------------------------------------------------


class ModelCatalog:
    """Discovers and tracks available models across all endpoints.

    Probes every configured endpoint at startup and builds a live
    inventory. Re-probe anytime with discover_all().
    """

    def __init__(self, endpoints: list[EndpointConfig]) -> None:
        self._models: dict[str, ModelInfo] = {}  # model_id → ModelInfo
        self._endpoints = endpoints

    async def discover_all(self) -> list[ModelInfo]:
        """Probe all endpoints and build/rebuild the model catalog."""
        self._models.clear()

        for endpoint in self._endpoints:
            try:
                models = await self._probe_endpoint(endpoint)
                for m in models:
                    # Skip duplicates (same model_id from different endpoints)
                    if m.model_id in self._models:
                        existing = self._models[m.model_id]
                        # Keep the one that's loaded or has more info
                        if m.is_loaded and not existing.is_loaded:
                            self._models[m.model_id] = m
                        elif m.size_bytes > 0 and existing.size_bytes == 0:
                            self._models[m.model_id] = m
                        logger.debug(
                            "Duplicate model %s from %s (keeping %s endpoint)",
                            m.model_id,
                            m.endpoint_url,
                            self._models[m.model_id].endpoint_url,
                        )
                    else:
                        self._models[m.model_id] = m
            except Exception as exc:
                logger.warning(
                    "Endpoint %s (%s) probe failed: %s",
                    endpoint.url,
                    endpoint.server_type,
                    exc,
                )

        logger.info(
            "Model catalog: %d models discovered across %d endpoints",
            len(self._models),
            len(self._endpoints),
        )
        return list(self._models.values())

    async def _probe_endpoint(self, endpoint: EndpointConfig) -> list[ModelInfo]:
        """Probe a single endpoint. Auto-detects server type if needed."""
        server_type = endpoint.server_type

        if server_type == "auto":
            server_type = await detect_server_type(endpoint.url)
            logger.info("Auto-detected server type '%s' at %s", server_type, endpoint.url)

        if server_type == "lmstudio":
            return await probe_lmstudio(endpoint.url, endpoint.api_key)
        elif server_type == "ollama":
            return await probe_ollama(endpoint.url)
        elif server_type == "vllm":
            return await probe_vllm(endpoint.url, endpoint.api_key)
        elif server_type == "openai":
            models = await probe_openai_compatible(endpoint.url, endpoint.api_key)
            # Phase 3 B-01 fix: cloud proxies (e.g. z.ai) may not support
            # /v1/models discovery. If discovery returned nothing but a
            # model_override is set, register the configured model directly.
            if not models and endpoint.model_override:
                logger.info(
                    "OpenAI discovery empty at %s — registering model_override '%s' as cloud model",
                    endpoint.url, endpoint.model_override,
                )
                return [make_cloud_model(endpoint)]
            return models
        elif server_type in ("anthropic", "gemini"):
            # Cloud APIs — create synthetic ModelInfo from config
            return [make_cloud_model(endpoint)]
        else:
            # Unknown — try generic OpenAI-compatible probe
            logger.info(
                "Unknown server type at %s, trying OpenAI-compatible probe", endpoint.url
            )
            return await probe_openai_compatible(endpoint.url, endpoint.api_key)

    def get(self, model_id: str) -> ModelInfo | None:
        """Get a specific model by ID."""
        return self._models.get(model_id)

    def get_all(self) -> list[ModelInfo]:
        """Return all discovered models."""
        return list(self._models.values())

    def get_loaded_models(self) -> list[ModelInfo]:
        """Return models currently loaded in VRAM."""
        return [m for m in self._models.values() if m.is_loaded]

    def get_healthy_models(self) -> list[ModelInfo]:
        """Return models with healthy status."""
        return [m for m in self._models.values() if m.health_status != "unreachable"]

    def get_models_for_stage(
        self,
        min_context: int = 0,
        requires_json: bool = False,
        requires_tools: bool = False,
        requires_thinking: bool = False,
        gpu: GPUInfo | None = None,
    ) -> list[ModelInfo]:
        """Return models meeting minimum requirements, sorted by fitness.

        Args:
            min_context: Minimum context length in tokens.
            requires_json: Must support JSON mode (or have fallback).
            requires_tools: Must support tool calling.
            requires_thinking: Must support thinking/reasoning.
            gpu: GPU info for VRAM fitting (None = no constraint).

        Returns:
            List of ModelInfo sorted by fitness (best first).
        """
        from backend.providers.hardware import HardwareDetector

        hw = HardwareDetector()
        candidates: list[ModelInfo] = []

        for m in self._models.values():
            if m.health_status == "unreachable":
                continue
            if m.context_length < min_context:
                continue
            if requires_tools and not m.supports_tools:
                continue
            if requires_thinking and not m.supports_thinking:
                continue
            # JSON mode: prefer but don't require (fallback exists)
            # VRAM: check if model fits
            if gpu and m.size_bytes > 0 and not hw.model_fits(m.size_bytes, gpu):
                continue
            candidates.append(m)

        # Sort by fitness score
        candidates.sort(
            key=lambda m: m.fitness_score(min_context), reverse=True
        )
        return candidates

    def mark_unreachable(self, model_id: str) -> None:
        """Mark a model as unreachable (e.g., after repeated failures)."""
        if model_id in self._models:
            self._models[model_id].health_status = "unreachable"

    def update_measured(self, model_id: str, **kwargs: Any) -> None:
        """Update measured capabilities for a model."""
        m = self._models.get(model_id)
        if m is None:
            return
        if m.measured is None:
            m.measured = MeasuredCapabilities()
        for key, value in kwargs.items():
            if hasattr(m.measured, key):
                setattr(m.measured, key, value)
        m.measured.last_measured = datetime.now()

    def get_model(self, model_id: str) -> ModelInfo | None:
        """Get a model by ID, or None if not in catalog."""
        return self._models.get(model_id)

    def __len__(self) -> int:
        return len(self._models)

    def __contains__(self, model_id: str) -> bool:
        return model_id in self._models
