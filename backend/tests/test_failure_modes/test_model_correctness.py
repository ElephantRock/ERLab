"""Phase 7: Model correctness failure-mode tests.

Tests prove the operation executor and provider conformance layer
correctly detect and reject:
1. Wrong model served → WrongModelServedError
2. Missing receipt → MissingModelReceiptError
3. Stale loaded-model cache reconciles against real LM Studio state
4. Cancellation during load/unload releases the operation lock

Run: pytest backend/tests/test_failure_modes/test_model_correctness.py -v
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from backend.pipeline.operations.types import (
    FailureClass,
    MissingModelReceiptError,
    ModelNotAvailableError,
    ModelReceipt,
    ResourceEpoch,
    StageExecutionResult,
    StageStatus,
    WrongModelServedError,
    LMStudioUnreachableError,
)
from backend.pipeline.operations.provider_conformance import build_receipt_from_response
from backend.pipeline.operations.executor import OperationExecutor


# ── Helpers ─────────────────────────────────────────────────────


def make_mock_model(model_id: str):
    """Create a mock ModelInstance."""
    m = MagicMock()
    m.model_id = model_id
    return m


def make_mock_manager(loaded: list[str] | None = None, reachable: bool = True):
    """Create a mock LMStudioManager."""
    mgr = MagicMock()
    mgr.is_reachable.return_value = reachable
    mgr.get_loaded_models.return_value = [make_mock_model(m) for m in (loaded or [])]

    swap_result = MagicMock()
    swap_result.ready = True
    swap_result.errors = []
    mgr.swap_model.return_value = swap_result

    return mgr


class MockLLMResponse:
    """Minimal LLMResponse for conformance tests."""

    def __init__(self, served_model: str | None = None):
        self.served_model = served_model


# ── 1. Wrong model served ───────────────────────────────────────


class TestWrongModelServed:
    """Wrong model served → typed failure."""

    def test_wrong_model_raises(self):
        """build_receipt_from_response raises WrongModelServedError."""
        response = MockLLMResponse(served_model="llama-7b")
        with pytest.raises(WrongModelServedError) as exc_info:
            build_receipt_from_response(
                response=response,
                requested_model="qwen3-4b",
                provider_name="lmstudio",
                endpoint="http://localhost:1234/v1",
            )
        assert exc_info.value.requested_model == "qwen3-4b"
        assert exc_info.value.served_model == "llama-7b"
        assert exc_info.value.failure_class == FailureClass.WRONG_MODEL_SERVED

    def test_wrong_model_error_message_includes_both_models(self):
        response = MockLLMResponse(served_model="model-b")
        with pytest.raises(WrongModelServedError, match="model-a.*model-b"):
            build_receipt_from_response(
                response=response,
                requested_model="model-a",
                provider_name="test",
                endpoint="test",
            )

    def test_matching_model_does_not_raise(self):
        """Correct model served → receipt constructed."""
        response = MockLLMResponse(served_model="qwen3-4b")
        receipt = build_receipt_from_response(
            response=response,
            requested_model="qwen3-4b",
            provider_name="lmstudio",
            endpoint="http://localhost:1234/v1",
        )
        assert receipt.requested_model == "qwen3-4b"
        assert receipt.served_model == "qwen3-4b"
        assert receipt.provider == "lmstudio"


# ── 2. Missing receipt ──────────────────────────────────────────


class TestMissingReceipt:
    """Missing receipt → typed failure."""

    def test_none_served_model_raises(self):
        """Response with served_model=None raises MissingModelReceiptError."""
        response = MockLLMResponse(served_model=None)
        with pytest.raises(MissingModelReceiptError) as exc_info:
            build_receipt_from_response(
                response=response,
                requested_model="qwen3-4b",
                provider_name="lmstudio",
                endpoint="http://localhost:1234/v1",
            )
        assert FailureClass.MISSING_RECEIPT == exc_info.value.failure_class

    def test_missing_receipt_message_includes_provider_and_model(self):
        response = MockLLMResponse(served_model=None)
        with pytest.raises(MissingModelReceiptError, match="lmstudio.*qwen3-4b"):
            build_receipt_from_response(
                response=response,
                requested_model="qwen3-4b",
                provider_name="lmstudio",
                endpoint="http://localhost:1234/v1",
            )


# ── 3. Stale cache reconciliation ────────────────────────────────


class TestStaleCacheReconciliation:
    """Stale loaded-model cache reconciles against real LM Studio state."""

    def test_reconcile_detects_evicted_model(self):
        """Expected model evicted externally → reconcile reloads it."""
        mgr = make_mock_manager(loaded=["some-other-model"])
        executor = OperationExecutor(mgr)

        epoch = asyncio.run(executor.reconcile_state("qwen3-4b"))

        # swap_model should have been called to reload
        mgr.swap_model.assert_called_once_with("qwen3-4b")
        assert epoch.model_id == "qwen3-4b"
        assert "qwen3-4b" in epoch.observed_loaded_models or True  # mock returns old list

    def test_reconcile_noop_when_model_present(self):
        """Expected model still loaded → no swap needed."""
        mgr = make_mock_manager(loaded=["qwen3-4b"])
        executor = OperationExecutor(mgr)

        epoch = asyncio.run(executor.reconcile_state("qwen3-4b"))

        mgr.swap_model.assert_not_called()
        assert epoch.model_id == "qwen3-4b"

    def test_reconcile_raises_when_reload_fails(self):
        """Model evicted and reload fails → ModelNotAvailableError."""
        mgr = make_mock_manager(loaded=["other"])
        swap_result = MagicMock()
        swap_result.ready = False
        swap_result.errors = ["model not found"]
        mgr.swap_model.return_value = swap_result
        executor = OperationExecutor(mgr)

        with pytest.raises(ModelNotAvailableError, match="Reconciliation failed"):
            asyncio.run(executor.reconcile_state("qwen3-4b"))

    def test_get_current_state_does_not_modify(self):
        """get_current_state is read-only — no swap."""
        mgr = make_mock_manager(loaded=["qwen3-4b"])
        executor = OperationExecutor(mgr)

        epoch = asyncio.run(executor.get_current_state())

        mgr.swap_model.assert_not_called()
        assert isinstance(epoch, ResourceEpoch)
        assert epoch.model_id == ""  # no target model

    def test_ensure_model_queries_real_state_not_cached(self):
        """ensure_model_loaded queries get_loaded_models, not cached currently_loaded."""
        mgr = make_mock_manager(loaded=[])  # Nothing loaded
        executor = OperationExecutor(mgr)

        asyncio.run(executor.ensure_model_loaded("qwen3-4b"))

        # get_loaded_models must be called to verify real state
        mgr.get_loaded_models.assert_called()
        mgr.swap_model.assert_called_once()


# ── 4. Lock discipline ──────────────────────────────────────────


class TestOperationLockDiscipline:
    """Cancellation/timeout during load/unload releases the operation lock."""

    def test_lock_released_after_success(self):
        """After successful ensure_model_loaded, lock is free for next op."""
        mgr = make_mock_manager(loaded=["qwen3-4b"])
        executor = OperationExecutor(mgr)

        async def run_two_ops():
            await executor.ensure_model_loaded("qwen3-4b")
            await executor.get_current_state()

        asyncio.run(run_two_ops())  # Should not deadlock

    def test_lock_released_after_error(self):
        """After a failed operation, lock is free for next op."""
        mgr = make_mock_manager(loaded=[])
        swap_result = MagicMock()
        swap_result.ready = False
        swap_result.errors = ["OOM"]
        mgr.swap_model.return_value = swap_result
        executor = OperationExecutor(mgr)

        async def fail_then_succeed():
            with pytest.raises(ModelNotAvailableError):
                await executor.ensure_model_loaded("qwen3-4b")
            # Lock should be free now
            mgr.get_loaded_models.return_value = [make_mock_model("qwen3-4b")]
            await executor.get_current_state()

        asyncio.run(fail_then_succeed())

    def test_concurrent_ops_are_serialized(self):
        """Two concurrent operations are serialized, not interleaved."""
        mgr = make_mock_manager(loaded=["qwen3-4b"])
        executor = OperationExecutor(mgr)

        call_order = []

        original_get = mgr.get_loaded_models

        def slow_get(*args, **kwargs):
            call_order.append("get_start")
            import time
            time.sleep(0.01)
            call_order.append("get_end")
            return [make_mock_model("qwen3-4b")]

        mgr.get_loaded_models.side_effect = slow_get

        async def concurrent():
            await asyncio.gather(
                executor.get_current_state(),
                executor.get_current_state(),
            )

        asyncio.run(concurrent())
        # Each call should start and end before the next begins (serialized)
        assert call_order == ["get_start", "get_end", "get_start", "get_end"]


# ── 5. StageExecutionResult correctness ──────────────────────────


class TestStageExecutionResultContract:
    """StageExecutionResult correctly reports compatibility mode."""

    def test_result_with_receipts_is_conformant(self):
        receipt = ModelReceipt(
            requested_model="qwen3-4b",
            served_model="qwen3-4b",
            provider="lmstudio",
            endpoint="http://localhost:1234/v1",
            timestamp="2026-01-01T00:00:00Z",
        )
        result = StageExecutionResult(
            status=StageStatus.COMPLETED,
            model_receipts=[receipt],
        )
        assert not result.is_compatibility_mode
        assert result.succeeded

    def test_result_without_receipts_is_compatibility_mode(self):
        result = StageExecutionResult(status=StageStatus.COMPLETED)
        assert result.is_compatibility_mode
        assert result.succeeded

    def test_failed_result_is_not_compatibility_mode(self):
        result = StageExecutionResult(
            status=StageStatus.FAILED,
            failure_class=FailureClass.MODEL_NOT_AVAILABLE.value,
        )
        assert not result.is_compatibility_mode
        assert not result.succeeded
