"""LM Studio model management — preflight, grammar enforcement, hot-swap,
queue prioritization, VRAM guardrails, telemetry, and auto-download.

Ensures the correct model is loaded with adequate context_length before
pipeline runs. Uses the LM Studio native API (/api/v0, /api/v1) which
provides context_length information not available in the OpenAI compat API.

API Reference:
  GET  /api/v0/models            — list all models with state + context info
  POST /api/v1/models/load       — load model with context_length
  POST /api/v1/models/unload     — unload model instance
  POST /api/v1/models/download   — download model from Hugging Face
  POST /v1/chat/completions      — OpenAI-compat with response_format
  POST /api/v1/chat              — native v1 with per-request context_length
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ── Data Classes ──────────────────────────────────────────────────

@dataclass
class ModelInstance:
    """A loaded model instance in LM Studio."""

    model_id: str
    instance_id: str
    state: str  # "loaded", "not_loaded", "loading", etc.
    loaded_context_length: int
    max_context_length: int
    quantization: str = ""
    arch: str = ""

    @property
    def is_loaded(self) -> bool:
        return self.state == "loaded"


@dataclass
class PreflightResult:
    """Result of a preflight check and optional model preparation."""

    ready: bool
    model_id: str
    instance_id: str
    context_length: int
    max_context_length: int
    had_to_reload: bool = False
    had_to_load: bool = False
    evicted_models: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class TelemetrySample:
    """A single request's performance data from LM Studio."""

    model_id: str
    tps: float                    # tokens per second
    ttft_seconds: float           # time to first token
    generation_time_seconds: float
    input_tokens: int
    output_tokens: int
    context_length: int = 0
    schema_enforced: bool = False
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class TelemetryLog:
    """Circular buffer of recent telemetry samples."""

    def __init__(self, max_samples: int = 200):
        self._samples: list[TelemetrySample] = []
        self._max = max_samples

    def record(self, sample: TelemetrySample) -> None:
        self._samples.append(sample)
        if len(self._samples) > self._max:
            self._samples = self._samples[-self._max:]

    def get_recent(self, model_id: str = "", n: int = 20) -> list[TelemetrySample]:
        """Get recent samples, optionally filtered by model."""
        pool = (
            [s for s in self._samples if s.model_id == model_id]
            if model_id else self._samples
        )
        return pool[-n:]

    def get_average_tps(self, model_id: str = "") -> float:
        samples = self.get_recent(model_id, n=50)
        if not samples:
            return 0.0
        return sum(s.tps for s in samples) / len(samples)

    def get_average_ttft(self, model_id: str = "") -> float:
        samples = self.get_recent(model_id, n=50)
        if not samples:
            return 0.0
        return sum(s.ttft_seconds for s in samples) / len(samples)

    @property
    def count(self) -> int:
        return len(self._samples)


@dataclass
class VRAMEstimate:
    """Estimated VRAM needed for a model + context."""

    model_weight_mb: int
    kv_cache_mb: int
    total_mb: int
    confidence: str  # "high" (from cert data) | "low" (heuristic)


class InsufficientVRAMError(Exception):
    """Raised when estimated VRAM exceeds available GPU memory."""


class GrammarNotSupportedError(Exception):
    """Raised when the model/provider doesn't support json_schema grammar."""


@dataclass
class DownloadResult:
    """Result of a model download attempt."""

    success: bool
    model_id: str
    status: str  # "completed" | "already_downloaded" | "failed" | "timeout"
    elapsed_seconds: float = 0.0


@dataclass
class ChatV1Result:
    """Result from LM Studio v1 /api/v1/chat endpoint."""

    output: str
    model_instance_id: str
    tps: float = 0.0
    ttft_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0


class RequestPriority(IntEnum):
    """Priority levels for LM Studio request queue."""

    CRITICAL = 0   # synthesis, gap_analysis — pipeline-blocking
    HIGH = 1       # idea_generation, novelty — stage-blocking
    NORMAL = 2     # embedding, reranking — can wait
    LOW = 3        # mechanical checks, formatting — background


@dataclass(order=True)
class _QueuedRequest:
    """Internal priority queue entry."""

    sort_key: tuple[int, float] = field(compare=True)  # (priority, enqueue_time)
    payload: dict = field(compare=False)
    future: asyncio.Future = field(compare=False)
    priority: int = field(compare=False)
    created_at: float = field(compare=False)


class LMStudioRequestQueue:
    """Priority queue for LM Studio requests. Prevents GPU saturation.

    On a single GPU only one inference runs at a time. Without a queue,
    concurrent callers (embeddings, reranking, LLM calls) all hit LM Studio
    and the first-come-first-served scheduling can block synthesis behind
    background embedding calls. This queue ensures higher-priority requests
    (like synthesis) are processed first when a slot opens.
    """

    def __init__(self, base_url: str, max_concurrent: int = 1):
        self._base_url = base_url
        self._max_concurrent = max_concurrent
        self._queue: asyncio.PriorityQueue[_QueuedRequest] = asyncio.PriorityQueue()
        self._active = 0
        self._lock = asyncio.Lock()
        self._workers_started = False
        self._total_enqueued = 0
        self._total_completed = 0

    def start_workers(self) -> None:
        """Start background worker tasks. Call once after event loop is running."""
        if self._workers_started:
            return
        for _ in range(self._max_concurrent):
            asyncio.ensure_future(self._worker())
        self._workers_started = True

    async def submit(
        self,
        payload: dict,
        priority: RequestPriority = RequestPriority.NORMAL,
        timeout: float = 120.0,
    ) -> dict:
        """Submit a request. Returns response when processed."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future[dict] = loop.create_future()
        entry = _QueuedRequest(
            sort_key=(int(priority), time.monotonic()),
            payload=payload,
            future=future,
            priority=int(priority),
            created_at=time.time(),
        )
        self._queue.put_nowait(entry)
        self._total_enqueued += 1

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            future.cancel(msg="Queue timeout")
            raise

    async def _worker(self) -> None:
        """Background worker: picks highest-priority request and executes."""
        while True:
            entry = await self._queue.get()
            try:
                async with self._lock:
                    self._active += 1

                url = entry.payload.pop("_url", f"{self._base_url}/v1/chat/completions")
                method = entry.payload.pop("_method", "POST")
                timeout = entry.payload.pop("_timeout", 120.0)

                async with httpx.AsyncClient() as client:
                    resp = await client.request(
                        method, url,
                        json=entry.payload,
                        timeout=timeout,
                    )

                if resp.status_code >= 400:
                    entry.future.set_exception(
                        httpx.HTTPStatusError(
                            f"LM Studio returned {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )
                    )
                else:
                    entry.future.set_result(resp.json())

            except Exception as exc:
                if not entry.future.done():
                    entry.future.set_exception(exc)
            finally:
                async with self._lock:
                    self._active -= 1
                self._total_completed += 1
                self._queue.task_done()

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def stats(self) -> dict:
        return {
            "queue_depth": self.queue_depth,
            "active_requests": self._active,
            "total_enqueued": self._total_enqueued,
            "total_completed": self._total_completed,
        }


# ── Stage → Priority Mapping ─────────────────────────────────────

_STAGE_PRIORITY: dict[str, RequestPriority] = {
    "proposal_synthesis": RequestPriority.CRITICAL,
    "gap_analysis": RequestPriority.CRITICAL,
    "idea_generation": RequestPriority.HIGH,
    "novelty_checking": RequestPriority.HIGH,
    "feasibility_scoring": RequestPriority.HIGH,
    "literature_search": RequestPriority.NORMAL,
    "ingestion": RequestPriority.NORMAL,
    "mechanical_metrics": RequestPriority.LOW,
    "export": RequestPriority.LOW,
}


# ── VRAM Estimation ──────────────────────────────────────────────

# Approximation: bytes per parameter per quantization level
_BYTES_PER_PARAM = {
    "Q4_K_M": 0.5625,    # ~4.5 bits
    "Q5_K_M": 0.6875,    # ~5.5 bits
    "Q6_K": 0.8125,      # ~6.5 bits
    "Q8_0": 1.0625,      # ~8.5 bits
    "F16": 2.0,
    "F32": 4.0,
    "unknown": 0.5625,   # assume Q4_K_M (most common for GGUF)
}

# Hidden dimensions for KV cache estimation.
# For GQA models, the KV dimension is num_kv_heads * head_dim, not hidden_dim.
# We use conservative estimates that match actual GGUF behavior.
_KV_CACHE_MB_PER_CTX_TOKEN: dict[str, float] = {
    # Empirical: qwen3-4b uses ~0.14MB per 1K context tokens (GQA with 4 KV heads)
    "qwen3": 0.00014,
    # qwen2.5-14b uses ~0.28MB per 1K context tokens
    "qwen2.5": 0.00028,
    # qwen3.6-27b (MoE): ~0.56MB per 1K context tokens
    "qwen3.6": 0.00056,
    "qwen3.5": 0.00028,
    "glm4": 0.00028,
}
_DEFAULT_KV_MB_PER_TOKEN = 0.00014  # conservative default


def _parse_param_count(param_str: str) -> float:
    """Parse parameter count like '4b', '27b', '0.8b' to billions."""
    s = param_str.lower().strip().rstrip("b").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


# ── Main Manager ──────────────────────────────────────────────────

class LMStudioManager:
    """Manages LM Studio model lifecycle — list, find, load, unload, preflight.

    Features:
    - Preflight checks with auto-fix and foreign model eviction
    - Grammar-enforced structured output (json_schema strict mode)
    - Dynamic hot-swapping between models mid-pipeline
    - Per-request context length via v1 chat endpoint
    - Priority queue for request ordering
    - VRAM estimation and pre-load guardrails
    - Performance telemetry collection
    - Auto-download of missing models

    Usage::

        mgr = LMStudioManager()  # reads config from settings
        result = mgr.preflight_check(auto_fix=True)
        if not result.ready:
            logger.error("LM Studio not ready: %s", result.errors)
    """

    def __init__(
        self,
        base_url: str = "",
        model_id: str = "",
        required_context: int = 0,
    ):
        # Lazy import to avoid circular deps at module level.
        from backend.config import get_settings

        settings = get_settings()

        # Strip /v1 suffix if present — native API lives at root.
        self._base_url = (base_url or settings.lmstudio_base_url).rstrip("/v1").rstrip("/")
        self._model_id = model_id or settings.lmstudio_model
        self._required_context = required_context or getattr(settings, "lmstudio_context_length", 32768)
        self._gpu_vram_mb: int = getattr(settings, "gpu_vram_mb", 12288)
        self._auto_download: bool = getattr(settings, "lmstudio_auto_download", False)
        self._download_timeout: float = float(getattr(settings, "lmstudio_download_timeout", 600))

        # Telemetry
        self._telemetry = TelemetryLog()

        # Request queue (initialized lazily when event loop is available)
        self._queue: LMStudioRequestQueue | None = None

        # Track currently loaded model for hot-swap
        self._currently_loaded: str = ""
        self._current_instance_id: str = ""

    # ── Properties ───────────────────────────────────────────────

    @property
    def telemetry(self) -> TelemetryLog:
        return self._telemetry

    @property
    def currently_loaded(self) -> str:
        """Model ID currently loaded in LM Studio (empty string if unknown)."""
        return self._currently_loaded

    # ── Native API calls ─────────────────────────────────────────

    def list_models(self) -> list[ModelInstance]:
        """List all models from LM Studio native API with context info."""
        url = f"{self._base_url}/api/v0/models"
        try:
            resp = httpx.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("Failed to list models from %s: %s", url, exc)
            return []

        instances = []
        for m in data.get("data", []):
            mid = m.get("id", "")
            state = m.get("state", "unknown")
            # v0 API doesn't always include loaded_context_length; infer from state
            loaded_ctx = m.get("loaded_context_length", 0)
            if state == "loaded" and not loaded_ctx:
                loaded_ctx = m.get("max_context_length", 0)
            instances.append(ModelInstance(
                model_id=mid,
                instance_id=mid,
                state=state,
                loaded_context_length=loaded_ctx,
                max_context_length=m.get("max_context_length", 0),
                quantization=m.get("quantization", ""),
                arch=m.get("arch", ""),
            ))
        return instances

    def find_model(self, model_id: str = "") -> ModelInstance | None:
        """Find a specific model by ID. Prefer loaded instance."""
        target = model_id or self._model_id
        models = self.list_models()

        # Prefer loaded instance.
        for m in models:
            if m.model_id == target and m.is_loaded:
                return m
        # Fallback: any matching model (even not loaded).
        for m in models:
            if m.model_id == target:
                return m
        return None

    def load_model(
        self,
        model_id: str = "",
        context_length: int = 0,
        flash_attention: bool = True,
        offload_kv_cache_to_gpu: bool = True,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Load a model with the specified context length.

        Includes VRAM guardrail check before loading.
        """
        target = model_id or self._model_id
        ctx = context_length or self._required_context

        # VRAM guardrail
        estimate = self.estimate_vram(target, ctx)
        max_vram = self._gpu_vram_mb
        if estimate.total_mb > max_vram * 0.90:
            raise InsufficientVRAMError(
                f"Model '{target}' with ctx={ctx} needs ~{estimate.total_mb}MB "
                f"but GPU has {max_vram}MB (90% limit={int(max_vram * 0.90)}MB). "
                f"Reduce context_length or use a smaller model. "
                f"(weight={estimate.model_weight_mb}MB, kv_cache={estimate.kv_cache_mb}MB, "
                f"confidence={estimate.confidence})"
            )

        url = f"{self._base_url}/api/v1/models/load"
        body = {
            "model": target,
            "context_length": ctx,
            "flash_attention": flash_attention,
        }
        if offload_kv_cache_to_gpu:
            body["offload_kv_cache_to_gpu"] = True

        resp = httpx.post(url, json=body, timeout=timeout)
        resp.raise_for_status()
        result = resp.json()

        # Track loaded model
        self._currently_loaded = target
        self._current_instance_id = result.get("instance_id", target)

        return result

    def unload_model(self, instance_id: str) -> dict[str, Any]:
        """Unload a model instance."""
        url = f"{self._base_url}/api/v1/models/unload"
        resp = httpx.post(url, json={"instance_id": instance_id}, timeout=30.0)
        resp.raise_for_status()

        # Clear tracking if this was the tracked model
        if instance_id == self._current_instance_id:
            self._currently_loaded = ""
            self._current_instance_id = ""

        return resp.json()

    # ── Health checks ────────────────────────────────────────────

    def is_reachable(self, timeout: float = 5.0) -> bool:
        """Check if LM Studio server is reachable."""
        try:
            resp = httpx.get(f"{self._base_url}/v1/models", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def get_loaded_models(self) -> list[ModelInstance]:
        """Get only currently loaded (ready) models."""
        return [m for m in self.list_models() if m.is_loaded]

    # ── Grammar-Enforced Structured Output ──────────────────────

    def complete_with_schema(
        self,
        messages: list[dict],
        schema: dict,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        context_length: int = 0,
        model_id: str = "",
    ) -> dict:
        """Call LM Studio with json_schema grammar enforcement.

        Uses the OpenAI-compat /v1/chat/completions endpoint with
        response_format: {type: "json_schema", json_schema: {strict: True}}.

        Returns parsed dict. Raises GrammarNotSupportedError if the
        model/provider doesn't support json_schema.
        """
        target = model_id or self._model_id
        url = f"{self._base_url}/v1/chat/completions"

        body: dict[str, Any] = {
            "model": target,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": schema,
                    "strict": True,
                },
            },
        }

        t_start = time.monotonic()
        resp = httpx.post(url, json=body, timeout=180.0)
        elapsed = time.monotonic() - t_start

        if resp.status_code == 400:
            error_body = resp.text.lower()
            if "json_schema" in error_body or "response_format" in error_body or "grammar" in error_body:
                raise GrammarNotSupportedError(
                    f"Model '{target}' does not support json_schema grammar: {resp.text[:200]}"
                )
            resp.raise_for_status()

        resp.raise_for_status()
        data = resp.json()

        # Extract content
        text = ""
        usage = data.get("usage", {})
        choices = data.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "") or ""

        if not text:
            raise GrammarNotSupportedError(
                f"Model '{target}' returned empty content with grammar enforcement"
            )

        # Parse JSON
        try:
            result = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GrammarNotSupportedError(
                f"Grammar enforcement produced invalid JSON: {exc}"
            ) from exc

        # Record telemetry from response stats (v0 compat API includes usage)
        stats = data.get("stats", {})
        tps = stats.get("tokens_per_second", 0.0)
        ttft = stats.get("time_to_first_token", 0.0)
        if tps == 0.0 and elapsed > 0 and usage.get("completion_tokens", 0) > 0:
            tps = usage["completion_tokens"] / elapsed

        self._telemetry.record(TelemetrySample(
            model_id=target,
            tps=tps,
            ttft_seconds=ttft,
            generation_time_seconds=elapsed,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            context_length=context_length,
            schema_enforced=True,
        ))

        return result

    # ── V1 Chat (Per-Request Context Length) ─────────────────────

    async def chat_v1(
        self,
        input: str | list[dict],
        model_id: str = "",
        context_length: int = 0,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_output_tokens: int = 4096,
    ) -> ChatV1Result:
        """Call LM Studio v1 /api/v1/chat with per-request context_length.

        The v1 endpoint uses 'input' (not 'messages'), returns typed output
        arrays, and accepts context_length per request without reloading.
        """
        target = model_id or self._model_id
        url = f"{self._base_url}/api/v1/chat"

        body: dict[str, Any] = {
            "model": target,
            "input": input,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        if context_length > 0:
            body["context_length"] = context_length
        if system_prompt:
            body["system_prompt"] = system_prompt

        t_start = time.monotonic()
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, timeout=180.0)
        elapsed = time.monotonic() - t_start

        if resp.status_code >= 400:
            resp.raise_for_status()

        data = resp.json()

        # Extract output text from typed output array
        output_parts = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                output_parts.append(item.get("content", ""))

        output_text = "\n".join(output_parts)
        stats = data.get("stats", {})

        # Record telemetry
        tps = stats.get("tokens_per_second", 0.0)
        ttft = stats.get("time_to_first_token_seconds", 0.0)
        if tps == 0.0 and elapsed > 0 and stats.get("total_output_tokens", 0) > 0:
            tps = stats["total_output_tokens"] / elapsed

        self._telemetry.record(TelemetrySample(
            model_id=target,
            tps=tps,
            ttft_seconds=ttft,
            generation_time_seconds=elapsed,
            input_tokens=stats.get("input_tokens", 0),
            output_tokens=stats.get("total_output_tokens", 0),
            context_length=context_length,
            schema_enforced=False,
        ))

        return ChatV1Result(
            output=output_text,
            model_instance_id=data.get("model_instance_id", target),
            tps=tps,
            ttft_seconds=ttft,
            input_tokens=stats.get("input_tokens", 0),
            output_tokens=stats.get("total_output_tokens", 0),
        )

    # ── Dynamic Hot-Swap ────────────────────────────────────────

    def swap_model(
        self,
        new_model_id: str,
        context_length: int = 0,
    ) -> PreflightResult:
        """Unload current model and load a different one.

        Used when the router selects a different model for the next stage.
        On single-GPU systems only one model can be loaded at a time.

        Args:
            new_model_id: Model to load.
            context_length: Context for the new model (default: required_context).

        Returns:
            PreflightResult with ready=True if swap succeeded.
        """
        ctx = context_length or self._required_context

        # Already loaded?
        if self._currently_loaded == new_model_id:
            instance = self.find_model(new_model_id)
            if instance and instance.is_loaded:
                return PreflightResult(
                    ready=True,
                    model_id=new_model_id,
                    instance_id=self._current_instance_id,
                    context_length=instance.loaded_context_length or ctx,
                    max_context_length=instance.max_context_length,
                )

        # Unload current if loaded
        if self._currently_loaded:
            try:
                logger.info(
                    "Hot-swap: unloading '%s' → loading '%s' (ctx=%d)",
                    self._currently_loaded, new_model_id, ctx,
                )
                self.unload_model(self._current_instance_id)
            except Exception as exc:
                logger.warning("Hot-swap: unload of '%s' failed: %s", self._currently_loaded, exc)

        # Load new model
        try:
            result = self.load_model(new_model_id, context_length=ctx)
            return PreflightResult(
                ready=True,
                model_id=new_model_id,
                instance_id=result.get("instance_id", new_model_id),
                context_length=ctx,
                max_context_length=0,
                had_to_reload=True,
            )
        except Exception as exc:
            return PreflightResult(
                ready=False,
                model_id=new_model_id,
                instance_id="",
                context_length=0,
                max_context_length=0,
                errors=[f"Hot-swap failed: {exc}"],
            )

    # ── Priority Queue ──────────────────────────────────────────

    def init_queue(self, max_concurrent: int = 1) -> LMStudioRequestQueue:
        """Initialize the request priority queue."""
        self._queue = LMStudioRequestQueue(
            base_url=self._base_url,
            max_concurrent=max_concurrent,
        )
        self._queue.start_workers()
        return self._queue

    @property
    def queue(self) -> LMStudioRequestQueue | None:
        return self._queue

    @staticmethod
    def priority_for_stage(stage: str) -> RequestPriority:
        """Get the request priority for a pipeline stage."""
        return _STAGE_PRIORITY.get(stage, RequestPriority.NORMAL)

    # ── VRAM Estimation ─────────────────────────────────────────

    def estimate_vram(
        self,
        model_id: str,
        context_length: int = 0,
    ) -> VRAMEstimate:
        """Estimate VRAM needed for a model + context.

        Uses model certification candidate data when available,
        falls back to heuristics based on model ID parsing.
        No nvidia-smi or pynvml required.
        """
        ctx = context_length or self._required_context

        # Try to load from candidate YAML
        param_count_b = 0.0
        arch = ""
        quantization = "unknown"
        confidence = "low"

        candidate_path = Path(
            f"data/model_certification/candidates/{model_id.replace('/', '-')}.yaml"
        )
        if candidate_path.exists():
            try:
                import yaml
                data = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))
                param_str = data.get("parameter_count", "")
                param_count_b = _parse_param_count(str(param_str))
                arch = data.get("model_family", "")
                quantization = data.get("quantization", "unknown")
                confidence = "high"
            except Exception:
                pass

        # Fallback: parse model ID for param count hints
        if param_count_b == 0:
            mid_lower = model_id.lower()
            for suffix, count in [("27b", 27), ("14b", 14), ("9b", 9), ("4b", 4), ("0.8b", 0.8)]:
                if suffix in mid_lower:
                    param_count_b = count
                    break
            # Try to guess arch from model ID
            if "qwen3.6" in mid_lower:
                arch = "qwen3.6"
            elif "qwen3.5" in mid_lower:
                arch = "qwen3.5"
            elif "qwen3" in mid_lower:
                arch = "qwen3"
            elif "qwen2.5" in mid_lower:
                arch = "qwen2.5"
            elif "glm" in mid_lower:
                arch = "glm4"

        # Model weight estimation
        bytes_per = _BYTES_PER_PARAM.get(quantization, _BYTES_PER_PARAM["unknown"])
        model_weight_mb = int(param_count_b * 1e9 * bytes_per / (1024 * 1024))

        # KV cache estimation using per-architecture rates (accounts for GQA)
        kv_rate = _KV_CACHE_MB_PER_CTX_TOKEN.get(arch, _DEFAULT_KV_MB_PER_TOKEN)
        kv_cache_mb = int(kv_rate * ctx * 1024)  # rate is per 1K tokens

        total_mb = model_weight_mb + kv_cache_mb

        return VRAMEstimate(
            model_weight_mb=model_weight_mb,
            kv_cache_mb=kv_cache_mb,
            total_mb=total_mb,
            confidence=confidence,
        )

    # ── Auto-Download ────────────────────────────────────────────

    async def download_model(
        self,
        model_id: str,
        timeout: float = 0,
    ) -> DownloadResult:
        """Download a model from Hugging Face via LM Studio.

        POST /api/v1/models/download initiates the download.
        Since there's no dedicated status endpoint, we poll by re-posting.

        Args:
            model_id: Hugging Face model identifier.
            timeout: Max seconds to wait (default: from config).

        Returns:
            DownloadResult with success status.
        """
        t_max = timeout or self._download_timeout
        url = f"{self._base_url}/api/v1/models/download"
        body = {"model": model_id}

        t_start = time.monotonic()

        async with httpx.AsyncClient() as client:
            # Initial download request
            resp = await client.post(url, json=body, timeout=30.0)
            data = resp.json()
            status = data.get("status", "")

            if status == "already_downloaded":
                return DownloadResult(
                    success=True,
                    model_id=model_id,
                    status="already_downloaded",
                    elapsed_seconds=time.monotonic() - t_start,
                )

            if status == "failed":
                return DownloadResult(
                    success=False,
                    model_id=model_id,
                    status="failed",
                    elapsed_seconds=time.monotonic() - t_start,
                )

            # Poll until complete or timeout
            poll_interval = 5.0
            while time.monotonic() - t_start < t_max:
                await asyncio.sleep(poll_interval)
                try:
                    resp = await client.post(url, json=body, timeout=30.0)
                    data = resp.json()
                    status = data.get("status", "")

                    if status in ("completed", "already_downloaded"):
                        return DownloadResult(
                            success=True,
                            model_id=model_id,
                            status="completed",
                            elapsed_seconds=time.monotonic() - t_start,
                        )
                    if status == "failed":
                        return DownloadResult(
                            success=False,
                            model_id=model_id,
                            status="failed",
                            elapsed_seconds=time.monotonic() - t_start,
                        )
                    # Still downloading — continue polling
                except Exception as exc:
                    logger.warning("Download poll error for '%s': %s", model_id, exc)

            # Timeout
            return DownloadResult(
                success=False,
                model_id=model_id,
                status="timeout",
                elapsed_seconds=time.monotonic() - t_start,
            )

    # ── Preflight ────────────────────────────────────────────────

    def _evict_foreign_models(self, keep_model_id: str) -> list[str]:
        """Unload models that are NOT the target to free VRAM.

        LM Studio loads models into GPU memory. If multiple models are loaded
        simultaneously, they compete for VRAM and the pipeline model may OOM
        or run with degraded performance. This method unloads everything that
        isn't the target model before the pipeline starts.

        Args:
            keep_model_id: Model ID to keep loaded (the pipeline model).

        Returns:
            List of evicted model IDs.
        """
        loaded = self.get_loaded_models()
        foreign = [m for m in loaded if m.model_id != keep_model_id]

        if not foreign:
            return []

        evicted = []
        for m in foreign:
            try:
                logger.info(
                    "Evicting foreign model '%s' (ctx=%d) to free VRAM for '%s'",
                    m.model_id, m.loaded_context_length, keep_model_id,
                )
                self.unload_model(m.instance_id)
                evicted.append(m.model_id)
            except Exception as exc:
                logger.warning(
                    "Failed to evict '%s': %s — proceeding anyway",
                    m.model_id, exc,
                )

        return evicted

    def preflight_check(
        self,
        model_id: str = "",
        required_context: int = 0,
        auto_fix: bool = False,
        evict_foreign: bool = True,
        auto_download: bool = False,
    ) -> PreflightResult:
        """Check if model is loaded with adequate context. Optionally fix.

        Args:
            model_id: Override model ID (default: from config).
            required_context: Override min context_length (default: from config).
            auto_fix: If True, load/reload the model when needed.
            evict_foreign: If True (default), unload OTHER models before loading.
            auto_download: If True, attempt to download model if not found.

        Returns:
            PreflightResult with ready=True if the model is usable.
        """
        target = model_id or self._model_id
        req_ctx = required_context or self._required_context
        errors: list[str] = []

        # 0. Evict foreign models to free VRAM.
        if evict_foreign:
            evicted = self._evict_foreign_models(target)
        else:
            evicted = []

        # 1. Check if model is loaded.
        instance = self.find_model(target)

        if instance is None:
            # Model not found — try auto-download?
            if auto_download or self._auto_download:
                logger.info("Model '%s' not found — attempting auto-download", target)
                try:
                    # Run async download in sync context
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # We're inside an async context — schedule it
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            dl_result = pool.submit(
                                asyncio.run,
                                self.download_model(target)
                            ).result(timeout=self._download_timeout)
                    else:
                        dl_result = asyncio.run(self.download_model(target))

                    if not dl_result.success:
                        errors.append(f"Auto-download failed: {dl_result.status}")
                    else:
                        logger.info("Auto-download of '%s': %s (%.1fs)",
                                    target, dl_result.status, dl_result.elapsed_seconds)
                        # Re-check after download
                        instance = self.find_model(target)
                except Exception as exc:
                    errors.append(f"Auto-download error: {exc}")

            if instance is None:
                errors.append(f"Model '{target}' not found in LM Studio")
                if auto_fix and not (auto_download or self._auto_download):
                    logger.info("Model '%s' not loaded — loading with context %d", target, req_ctx)
                    try:
                        result = self.load_model(target, context_length=req_ctx)
                        return PreflightResult(
                            ready=True,
                            model_id=target,
                            instance_id=result.get("instance_id", target),
                            context_length=req_ctx,
                            max_context_length=0,
                            had_to_load=True,
                            evicted_models=evicted,
                        )
                    except Exception as exc:
                        errors.append(f"Failed to load model: {exc}")
                        return PreflightResult(
                            ready=False, model_id=target, instance_id="",
                            context_length=0, max_context_length=0, errors=errors,
                        )
                elif not errors:
                    # Had download but still not found
                    errors.append(f"Model '{target}' not found after download attempt")

                return PreflightResult(
                    ready=False, model_id=target, instance_id="",
                    context_length=0, max_context_length=0, errors=errors,
                )

        if not instance.is_loaded:
            errors.append(f"Model '{target}' exists but state is '{instance.state}'")
            if auto_fix:
                try:
                    result = self.load_model(target, context_length=req_ctx)
                    return PreflightResult(
                        ready=True,
                        model_id=target,
                        instance_id=result.get("instance_id", target),
                        context_length=req_ctx,
                        max_context_length=instance.max_context_length,
                        had_to_load=True,
                        evicted_models=evicted,
                    )
                except Exception as exc:
                    errors.append(f"Failed to load: {exc}")
                    return PreflightResult(
                        ready=False, model_id=target, instance_id="",
                        context_length=0, max_context_length=instance.max_context_length,
                        errors=errors,
                    )
            return PreflightResult(
                ready=False, model_id=target, instance_id="",
                context_length=0, max_context_length=instance.max_context_length,
                errors=errors,
            )

        # 2. Check context length.
        current_ctx = instance.loaded_context_length
        max_ctx = instance.max_context_length

        if current_ctx >= req_ctx:
            logger.info(
                "Preflight OK: %s loaded, context %d (required %d)",
                target, current_ctx, req_ctx,
            )
            self._currently_loaded = target
            self._current_instance_id = instance.instance_id
            return PreflightResult(
                ready=True,
                model_id=target,
                instance_id=instance.instance_id,
                context_length=current_ctx,
                max_context_length=max_ctx,
                evicted_models=evicted,
            )

        # Context too small — reload if auto_fix.
        errors.append(
            f"Model '{target}' has context {current_ctx}, needs {req_ctx}"
        )
        if auto_fix:
            logger.info("Reloading '%s': context %d -> %d", target, current_ctx, req_ctx)
            try:
                self.unload_model(instance.instance_id)
                result = self.load_model(target, context_length=req_ctx)
                return PreflightResult(
                    ready=True,
                    model_id=target,
                    instance_id=result.get("instance_id", target),
                    context_length=req_ctx,
                    max_context_length=max_ctx,
                    had_to_reload=True,
                    evicted_models=evicted,
                )
            except Exception as exc:
                errors.append(f"Failed to reload: {exc}")
                return PreflightResult(
                    ready=False, model_id=target, instance_id=instance.instance_id,
                    context_length=current_ctx, max_context_length=max_ctx, errors=errors,
                )

        return PreflightResult(
            ready=False,
            model_id=target,
            instance_id=instance.instance_id,
            context_length=current_ctx,
            max_context_length=max_ctx,
            errors=errors,
        )

    # ── Teardown ────────────────────────────────────────────────

    def teardown(self, model_id: str = "") -> bool:
        """Unload the pipeline model after a run completes to free VRAM.

        This is the counterpart to preflight_check(). After the pipeline
        finishes, the model sits idle consuming GPU memory. Call teardown()
        to release it.

        Args:
            model_id: Override model ID (default: from config).

        Returns:
            True if the model was unloaded (or wasn't loaded).
        """
        target = model_id or self._model_id
        instance = self.find_model(target)

        if instance is None or not instance.is_loaded:
            logger.info("Teardown: '%s' not loaded — nothing to do", target)
            return True

        try:
            logger.info(
                "Teardown: unloading '%s' (ctx=%d) to free VRAM",
                target, instance.loaded_context_length,
            )
            self.unload_model(instance.instance_id)
            return True
        except Exception as exc:
            logger.warning("Teardown: failed to unload '%s': %s", target, exc)
            return False

    # ── Context manager ─────────────────────────────────────────

    def __enter__(self) -> LMStudioManager:
        self.preflight_check(auto_fix=True, evict_foreign=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.teardown()
