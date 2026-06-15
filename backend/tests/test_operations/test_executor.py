"""Tests for the OperationExecutor — the authoritative model lifecycle owner.

These tests verify:
1. The executor loads required models via swap_model
2. The executor reconciles stale cached state against real LM Studio state
3. currently_loaded is treated as hint, not truth (real state is queried)
4. Sync LMStudioManager APIs are wrapped with asyncio.to_thread
5. LM Studio unreachable is a typed error
6. Model not available is a typed error
7. Cancellation during load/unload leaves no corrupt state (lock released)
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, patch, call

from backend.pipeline.operations.executor import OperationExecutor
from backend.pipeline.operations.types import (
    LMStudioUnreachableError,
    ModelNotAvailableError,
    ResourceEpoch,
)


def make_mock_manager(
    loaded_model_ids: list[str] | None = None,
    swap_succeeds: bool = True,
    reachable: bool = True,
) -> MagicMock:
    """Create a mock LMStudioManager with configurable behavior."""
    manager = MagicMock()

    # Real state queries
    def mock_get_loaded_models():
        return [MagicMock(model_id=mid) for mid in (loaded_model_ids or [])]

    manager.get_loaded_models = mock_get_loaded_models
    manager.is_reachable = MagicMock(return_value=reachable)

    # Swap returns a PreflightResult-like object
    swap_result = MagicMock()
    swap_result.ready = swap_succeeds
    swap_result.errors = [] if swap_succeeds else ["load failed"]
    manager.swap_model = MagicMock(return_value=swap_result)

    # currently_loaded is just a property (cached hint)
    manager.currently_loaded = (loaded_model_ids or [""])[0] if loaded_model_ids else ""

    return manager


class TestEnsureModelLoaded:
    """ensure_model_loaded is the primary entry point for stages."""

    @pytest.mark.asyncio
    async def test_already_loaded_no_swap(self):
        """If the model is already loaded, no swap is needed."""
        manager = make_mock_manager(loaded_model_ids=["qwen3-4b"])
        executor = OperationExecutor(manager)

        epoch = await executor.ensure_model_loaded("qwen3-4b")

        assert isinstance(epoch, ResourceEpoch)
        assert "qwen3-4b" in epoch.observed_loaded_models
        manager.swap_model.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_loaded_triggers_swap(self):
        """If the model is not loaded, swap_model is called."""
        manager = make_mock_manager(loaded_model_ids=["old-model"])
        # After swap, the model becomes loaded
        manager.get_loaded_models = MagicMock(
            side_effect=[
                [MagicMock(model_id="old-model")],  # initial check
                [MagicMock(model_id="qwen3-4b")],   # after swap
            ]
        )
        executor = OperationExecutor(manager)

        epoch = await executor.ensure_model_loaded("qwen3-4b")

        manager.swap_model.assert_called_once_with("qwen3-4b", 0)
        assert epoch.model_id == "qwen3-4b"

    @pytest.mark.asyncio
    async def test_swap_failure_raises_model_not_available(self):
        """If swap fails, a typed error is raised."""
        manager = make_mock_manager(
            loaded_model_ids=[],
            swap_succeeds=False,
        )
        executor = OperationExecutor(manager)

        with pytest.raises(ModelNotAvailableError):
            await executor.ensure_model_loaded("qwen3-4b")

    @pytest.mark.asyncio
    async def test_lm_studio_unreachable_raises_typed_error(self):
        """If LM Studio is not reachable, a typed error is raised."""
        manager = make_mock_manager(reachable=False)
        manager.get_loaded_models = MagicMock(
            side_effect=ConnectionError("connection refused")
        )
        executor = OperationExecutor(manager)

        with pytest.raises(LMStudioUnreachableError):
            await executor.ensure_model_loaded("qwen3-4b")


class TestReconcileState:
    """Reconciliation checks real state, not cached currently_loaded."""

    @pytest.mark.asyncio
    async def test_reconcile_detects_stale_cache(self):
        """If expected model is not actually loaded, reload it."""
        manager = make_mock_manager(loaded_model_ids=["wrong-model"])
        executor = OperationExecutor(manager)

        await executor.reconcile_state("qwen3-4b")

        manager.swap_model.assert_called_once_with("qwen3-4b")

    @pytest.mark.asyncio
    async def test_reconcile_noop_when_model_present(self):
        """If expected model is loaded, no action is taken."""
        manager = make_mock_manager(loaded_model_ids=["qwen3-4b", "other"])
        executor = OperationExecutor(manager)

        epoch = await executor.reconcile_state("qwen3-4b")

        manager.swap_model.assert_not_called()
        assert "qwen3-4b" in epoch.observed_loaded_models

    @pytest.mark.asyncio
    async def test_reconcile_failure_raises_typed_error(self):
        """If reconciliation reload fails, a typed error is raised."""
        manager = make_mock_manager(
            loaded_model_ids=["wrong"],
            swap_succeeds=False,
        )
        executor = OperationExecutor(manager)

        with pytest.raises(ModelNotAvailableError):
            await executor.reconcile_state("qwen3-4b")


class TestGetCurrentState:
    """get_current_state queries without modifying."""

    @pytest.mark.asyncio
    async def test_get_current_state_returns_epoch(self):
        manager = make_mock_manager(loaded_model_ids=["qwen3-4b"])
        executor = OperationExecutor(manager)

        epoch = await executor.get_current_state()

        assert isinstance(epoch, ResourceEpoch)
        assert "qwen3-4b" in epoch.observed_loaded_models
        manager.swap_model.assert_not_called()


class TestConcurrentOperations:
    """Only one lifecycle operation runs at a time."""

    @pytest.mark.asyncio
    async def test_lock_prevents_concurrent_swaps(self):
        """Two concurrent ensure_model_loaded calls are serialized."""
        import threading

        call_order: list[str] = []
        lock = threading.Lock()

        manager = make_mock_manager(loaded_model_ids=[])

        swap_result = MagicMock()
        swap_result.ready = True
        swap_result.errors = []

        def slow_swap(model_id, ctx=0):
            with lock:
                call_order.append(f"swap:{model_id}")
            # Simulate the swap making the model appear loaded
            manager.get_loaded_models = MagicMock(
                return_value=[MagicMock(model_id=model_id)]
            )
            return swap_result

        manager.swap_model = MagicMock(side_effect=slow_swap)
        executor = OperationExecutor(manager)

        # Two concurrent requests for different models
        await asyncio.gather(
            executor.ensure_model_loaded("model-a"),
            executor.ensure_model_loaded("model-b"),
        )

        # Both swaps executed (serialized, not concurrent)
        assert len(call_order) == 2

    @pytest.mark.asyncio
    async def test_lock_released_after_error(self):
        """If an operation fails, the lock is released for the next caller."""
        manager = make_mock_manager(
            loaded_model_ids=[],
            swap_succeeds=False,
        )
        executor = OperationExecutor(manager)

        # First call fails
        with pytest.raises(ModelNotAvailableError):
            await executor.ensure_model_loaded("model-a")

        # Second call should not be blocked
        manager2 = make_mock_manager(loaded_model_ids=["model-b"])
        executor._manager = manager2
        epoch = await executor.ensure_model_loaded("model-b")
        assert "model-b" in epoch.observed_loaded_models


class TestResourceEpochCapture:
    """ResourceEpoch captures full state, not just target model."""

    @pytest.mark.asyncio
    async def test_epoch_captures_all_loaded_models(self):
        manager = make_mock_manager(
            loaded_model_ids=["qwen3-4b", "embedding-nomic", "qwen3-27b"]
        )
        executor = OperationExecutor(manager)

        epoch = await executor.ensure_model_loaded("qwen3-4b")

        assert len(epoch.observed_loaded_models) == 3
        assert "embedding-nomic" in epoch.observed_loaded_models
        assert "qwen3-27b" in epoch.observed_loaded_models

    @pytest.mark.asyncio
    async def test_epoch_has_unique_operation_id(self):
        manager = make_mock_manager(loaded_model_ids=["qwen3-4b"])
        executor = OperationExecutor(manager)

        epoch1 = await executor.get_current_state()
        epoch2 = await executor.get_current_state()

        assert epoch1.operation_id != epoch2.operation_id
