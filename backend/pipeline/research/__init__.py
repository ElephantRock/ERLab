"""LM Studio model management — preflight checks, model loading, context verification.

Ensures the correct model is loaded with adequate context_length before
pipeline runs. Uses the LM Studio native API (/api/v0, /api/v1) which
provides context_length information not available in the OpenAI compat API.

API Reference:
  GET  /api/v0/models            — list all models with state + context info
  POST /api/v1/models/load       — load model with context_length
  POST /api/v1/models/unload     — unload model instance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


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


class LMStudioManager:
    """Manages LM Studio model lifecycle — list, find, load, unload, preflight.

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
            instances.append(ModelInstance(
                model_id=mid,
                instance_id=mid,
                state=m.get("state", "unknown"),
                loaded_context_length=m.get("loaded_context_length", 0),
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
        """Load a model with the specified context length."""
        url = f"{self._base_url}/api/v1/models/load"
        body = {
            "model": model_id or self._model_id,
            "context_length": context_length or self._required_context,
            "flash_attention": flash_attention,
        }
        if offload_kv_cache_to_gpu:
            body["offload_kv_cache_to_gpu"] = True

        resp = httpx.post(url, json=body, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def unload_model(self, instance_id: str) -> dict[str, Any]:
        """Unload a model instance."""
        url = f"{self._base_url}/api/v1/models/unload"
        resp = httpx.post(url, json={"instance_id": instance_id}, timeout=30.0)
        resp.raise_for_status()
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
    ) -> PreflightResult:
        """Check if model is loaded with adequate context. Optionally fix.

        Args:
            model_id: Override model ID (default: from config).
            required_context: Override min context_length (default: from config).
            auto_fix: If True, load/reload the model with required_context when needed.
            evict_foreign: If True (default), unload OTHER models before loading
                to free VRAM. Prevents multi-model contention on single-GPU.

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
            errors.append(f"Model '{target}' not found in LM Studio")
            if auto_fix:
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
