"""Operation Executor — the single authoritative model lifecycle owner.

This is the ONLY component allowed to load, unload, swap, reconcile,
or verify LM Studio models. Orchestrator and stages must not call
swap_model, load_model, or unload_model directly.

Design principles:
1. One operation at a time — no concurrent model lifecycle operations.
2. Real LM Studio state is queried before action — ``currently_loaded``
   is a hint, not truth. The executor calls ``list_models()`` /
   ``get_loaded_models()`` to verify.
3. Sync LMStudioManager APIs are wrapped with ``asyncio.to_thread()``
   so the executor is fully async-safe.
4. Every operation returns a ResourceEpoch capturing the observed state.
5. Cancellation during load/unload must leave no corrupt state.

Usage::

    executor = OperationExecutor(manager)
    epoch = await executor.ensure_model_loaded("qwen3-4b", context_length=32768)
    # ... stage does LLM call ...
    receipt = build_receipt_from_response(response, ...)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from backend.pipeline.operations.types import (
    LMStudioUnreachableError,
    ModelNotAvailableError,
    ResourceEpoch,
)

logger = logging.getLogger(__name__)


class OperationExecutor:
    """Authoritative boundary for all LM Studio model lifecycle operations.

    Wraps the synchronous ``LMStudioManager`` with ``asyncio.to_thread()``
    so callers get a fully async interface without blocking the event loop.

    The executor holds a lock to guarantee only one lifecycle operation
    runs at a time. This prevents race conditions when multiple stages
    request different models concurrently.
    """

    def __init__(self, manager) -> None:
        """Initialize the executor with an LMStudioManager instance.

        Args:
            manager: LMStudioManager instance. Its methods are synchronous
                     and will be wrapped with asyncio.to_thread().
        """
        self._manager = manager
        self._lock = asyncio.Lock()

    # ── Model Lifecycle ─────────────────────────────────────────

    async def ensure_model_loaded(
        self,
        model_id: str,
        context_length: int = 0,
    ) -> ResourceEpoch:
        """Ensure the requested model is loaded in LM Studio.

        This is the primary entry point for stages that need a specific model.
        It queries real LM Studio state, swaps if needed, and returns a
        ResourceEpoch snapshot.

        Args:
            model_id: The model to ensure is loaded.
            context_length: Required context length (0 = use manager default).

        Returns:
            ResourceEpoch capturing the observed LM Studio state.

        Raises:
            LMStudioUnreachableError: If LM Studio is not reachable.
            ModelNotAvailableError: If the model cannot be loaded.
        """
        async with self._lock:
            # 1. Check real LM Studio state (not cached currently_loaded)
            loaded_models = await self._safe_get_loaded_models()

            # 2. Check if target is already loaded
            target_loaded = any(
                m.model_id == model_id for m in loaded_models
            )

            if not target_loaded:
                logger.info(
                    "Operation Executor: model '%s' not loaded. "
                    "Performing swap (currently loaded: %s).",
                    model_id,
                    [m.model_id for m in loaded_models] or "none",
                )

                # 3. Swap to the target model
                result = await asyncio.to_thread(
                    self._manager.swap_model, model_id, context_length
                )

                if not result.ready:
                    raise ModelNotAvailableError(
                        f"Failed to load model '{model_id}': {result.errors}"
                    )

            # 4. Capture resource epoch from real state
            return await self._capture_epoch(model_id)

    async def get_current_state(self) -> ResourceEpoch:
        """Query real LM Studio state without modifying it.

        Use this for pre-flight checks or reconciliation when a stage
        needs to know what's loaded but doesn't need to change it.
        """
        async with self._lock:
            return await self._capture_epoch("")

    async def reconcile_state(self, expected_model: str) -> ResourceEpoch:
        """Reconcile cached state against real LM Studio state.

        If the expected model is not actually loaded (e.g., an external
        process evicted it), this will reload it.

        Use this when the executor suspects stale cached state —
        for example, after a long-running operation or an error recovery.
        """
        async with self._lock:
            loaded_models = await self._safe_get_loaded_models()
            actually_loaded = {m.model_id for m in loaded_models}

            if expected_model not in actually_loaded:
                logger.warning(
                    "Reconcile: expected '%s' but it's not loaded. "
                    "Real loaded: %s. Reloading.",
                    expected_model,
                    actually_loaded or "none",
                )
                result = await asyncio.to_thread(
                    self._manager.swap_model, expected_model
                )
                if not result.ready:
                    raise ModelNotAvailableError(
                        f"Reconciliation failed: cannot load '{expected_model}': {result.errors}"
                    )

            return await self._capture_epoch(expected_model)

    # ── Internal Helpers ────────────────────────────────────────

    async def _safe_get_loaded_models(self) -> list:
        """Query real loaded models from LM Studio, handling errors.

        Returns:
            List of ModelInstance objects for currently loaded models.

        Raises:
            LMStudioUnreachableError: If LM Studio is not reachable.
        """
        try:
            models = await asyncio.to_thread(self._manager.get_loaded_models)
            return models
        except Exception as exc:
            # Check if it's a connectivity issue
            is_reachable = await asyncio.to_thread(self._manager.is_reachable)
            if not is_reachable:
                raise LMStudioUnreachableError(
                    f"LM Studio is not reachable: {exc}"
                ) from exc
            # Non-connectivity error — log and return empty
            logger.error("Failed to query LM Studio loaded models: %s", exc)
            return []

    async def _capture_epoch(self, model_id: str) -> ResourceEpoch:
        """Capture a ResourceEpoch from the current real LM Studio state."""
        loaded_models = await self._safe_get_loaded_models()
        loaded_ids = [m.model_id for m in loaded_models]

        return ResourceEpoch(
            operation_id=f"op_{uuid.uuid4().hex[:12]}",
            model_id=model_id,
            loaded_at=datetime.now(timezone.utc).isoformat(),
            observed_loaded_models=loaded_ids,
        )
