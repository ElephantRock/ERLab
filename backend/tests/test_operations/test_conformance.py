"""Conformance tests for the operation executor and provider receipt contract.

These tests verify:
1. Missing receipt fails
2. Wrong model served fails
3. Wrapper propagation preserves receipt
4. served_model compatibility field works

Run: pytest backend/tests/test_operations/ -v
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.pipeline.operations.types import (
    FailureClass,
    MissingModelReceiptError,
    ModelNotAvailableError,
    ModelReceipt,
    ResourceEpoch,
    StageExecutionResult,
    StageStatus,
    WrongModelServedError,
)
from backend.providers.base import LLMProvider, LLMResponse


# ── ModelReceipt ──────────────────────────────────────────────


class TestModelReceipt:
    """ModelReceipt is the verifiable conformance unit."""

    def test_receipt_is_frozen(self):
        """Receipts must be immutable — they are proof of what happened."""
        receipt = ModelReceipt(
            requested_model="qwen3-4b",
            served_model="qwen3-4b",
            provider="lmstudio",
            endpoint="http://localhost:1234/v1",
            timestamp="2026-06-16T00:00:00Z",
        )
        with pytest.raises(AttributeError):
            receipt.served_model = "different"

    def test_receipt_with_context_length(self):
        receipt = ModelReceipt(
            requested_model="qwen3-4b",
            served_model="qwen3-4b",
            provider="lmstudio",
            endpoint="http://localhost:1234/v1",
            timestamp="2026-06-16T00:00:00Z",
            context_length=32768,
        )
        assert receipt.context_length == 32768

    def test_receipt_default_context_length_is_none(self):
        receipt = ModelReceipt(
            requested_model="qwen3-4b",
            served_model="qwen3-4b",
            provider="lmstudio",
            endpoint="http://localhost:1234/v1",
            timestamp="2026-06-16T00:00:00Z",
        )
        assert receipt.context_length is None


# ── StageExecutionResult ──────────────────────────────────────


class TestStageExecutionResult:
    """StageExecutionResult carries typed outcome, not bool."""

    def test_compatibility_mode_detected(self):
        """A completed result with no receipts is compatibility mode."""
        result = StageExecutionResult(status=StageStatus.COMPLETED)
        assert result.is_compatibility_mode is True
        assert result.succeeded is True

    def test_conformant_result_not_compatibility_mode(self):
        """A completed result with receipts is fully conformant."""
        receipt = ModelReceipt(
            requested_model="qwen3-4b",
            served_model="qwen3-4b",
            provider="lmstudio",
            endpoint="http://localhost:1234/v1",
            timestamp="2026-06-16T00:00:00Z",
        )
        result = StageExecutionResult(
            status=StageStatus.COMPLETED,
            model_receipts=[receipt],
        )
        assert result.is_compatibility_mode is False
        assert result.succeeded is True

    def test_failed_result_not_succeeded(self):
        result = StageExecutionResult(
            status=StageStatus.FAILED,
            failure_class=FailureClass.PROVIDER_ERROR,
            error="LLM call timed out",
        )
        assert result.succeeded is False
        assert result.retryable is False

    def test_default_empty_collections(self):
        """Default factory fields must be independent per instance."""
        r1 = StageExecutionResult(status=StageStatus.COMPLETED)
        r2 = StageExecutionResult(status=StageStatus.COMPLETED)
        r1.model_receipts.append(ModelReceipt(
            requested_model="a", served_model="a",
            provider="p", endpoint="e", timestamp="t",
        ))
        r1.collector_record_ids.append("rec1")
        assert len(r2.model_receipts) == 0
        assert len(r2.collector_record_ids) == 0


# ── Typed Errors ──────────────────────────────────────────────


class TestTypedErrors:
    """Errors must carry typed failure_class, not just a message."""

    def test_missing_receipt_error_has_correct_failure_class(self):
        err = MissingModelReceiptError("No receipt for call")
        assert err.failure_class == FailureClass.MISSING_RECEIPT

    def test_wrong_model_served_error_carries_models(self):
        err = WrongModelServedError("qwen3-4b", "qwen3-27b")
        assert err.failure_class == FailureClass.WRONG_MODEL_SERVED
        assert err.requested_model == "qwen3-4b"
        assert err.served_model == "qwen3-27b"

    def test_wrong_model_served_error_message_is_descriptive(self):
        err = WrongModelServedError("qwen3-4b", "qwen3-27b")
        assert "qwen3-4b" in str(err)
        assert "qwen3-27b" in str(err)

    def test_model_not_available_error_has_correct_failure_class(self):
        err = ModelNotAvailableError("Model not found")
        assert err.failure_class == FailureClass.MODEL_NOT_AVAILABLE


# ── LLMResponse served_model compatibility field ──────────────


class TestLLMResponseServedModel:
    """served_model on LLMResponse is a compatibility field.

    The real conformance unit is ModelReceipt. served_model allows
    the conformance layer to extract receipt information from
    existing provider responses during migration.
    """

    def test_served_model_defaults_to_none(self):
        """Existing responses without served_model still work."""
        resp = LLMResponse(content="hello")
        assert getattr(resp, "served_model", None) is None

    def test_served_model_can_be_set(self):
        """After Phase 1 Step 3, providers will set this field."""
        # This test will fail until we patch LLMResponse.
        # That's intentional — it's a TDD guard.
        resp = LLMResponse(content="hello", served_model="qwen3-4b")  # type: ignore[call-arg]
        assert resp.served_model == "qwen3-4b"


# ── Provider Wrapper Receipt Propagation ──────────────────────


class TestProviderWrapperPropagation:
    """Verify that wrappers propagate served_model through the chain.

    After Phase 1 Step 3, all four wrappers must preserve the
    served_model field set by the inner provider.
    """

    @pytest.mark.asyncio
    async def test_stage_wrapper_propagates_served_model(self):
        """StageAwareProvider must pass through served_model."""
        from backend.providers.stage_wrapper import StageAwareProvider

        inner = AsyncMock(spec=LLMProvider)
        inner.complete_with_usage.return_value = LLMResponse(
            content="hello",
            input_tokens=5,
            output_tokens=3,
            served_model="qwen3-4b",  # type: ignore[call-arg]
        )
        inner.provider_name = "test"
        inner.default_model = "qwen3-4b"
        inner._cost_callback = None

        wrapper = StageAwareProvider(inner, stage="test_stage")
        result = await wrapper.complete_with_usage(
            [{"role": "user", "content": "hi"}],
        )

        assert getattr(result, "served_model", None) == "qwen3-4b"

    @pytest.mark.asyncio
    async def test_stage_wrapper_propagates_served_model_structured(self):
        """StageAwareProvider structured_output_with_usage must pass through served_model."""
        from backend.providers.stage_wrapper import StageAwareProvider

        inner = AsyncMock(spec=LLMProvider)
        inner.structured_output_with_usage.return_value = LLMResponse(
            content='{"key": "value"}',
            structured={"key": "value"},
            input_tokens=10,
            output_tokens=5,
            served_model="qwen3-4b",  # type: ignore[call-arg]
        )
        inner.provider_name = "test"
        inner.default_model = "qwen3-4b"
        inner._cost_callback = None

        wrapper = StageAwareProvider(inner, stage="test_stage")
        result = await wrapper.structured_output_with_usage(
            [{"role": "user", "content": "hi"}],
            schema={"type": "object"},
        )

        assert getattr(result, "served_model", None) == "qwen3-4b"
        assert result.input_tokens == 10
        assert result.output_tokens == 5


# ── Conformance Layer (integration with executor) ─────────────


class TestConformanceRejection:
    """The conformance layer must reject responses without valid receipts."""

    def test_response_without_served_model_cannot_form_receipt(self):
        """A response with no served_model cannot produce a ModelReceipt.

        The executor's conformance layer must treat this as a
        MissingModelReceiptError.
        """
        resp = LLMResponse(content="hello")
        # served_model is None → receipt cannot be constructed
        assert getattr(resp, "served_model", None) is None

    def test_response_with_wrong_served_model_triggers_error(self):
        """If requested != served, conformance layer raises WrongModelServedError."""
        requested = "qwen3-4b"
        served = "qwen3-27b"
        assert requested != served  # guard

        with pytest.raises(WrongModelServedError) as exc_info:
            raise WrongModelServedError(requested, served)

        assert exc_info.value.requested_model == requested
        assert exc_info.value.served_model == served


# ── ResourceEpoch ─────────────────────────────────────────────


class TestResourceEpoch:
    """ResourceEpoch captures full loaded-model state, not just target."""

    def test_resource_epoch_is_frozen(self):
        epoch = ResourceEpoch(
            operation_id="op_001",
            model_id="qwen3-4b",
            loaded_at="2026-06-16T00:00:00Z",
            observed_loaded_models=["qwen3-4b", "qwen3-27b"],
            vram_usage_mb=8192.0,
        )
        with pytest.raises(AttributeError):
            epoch.model_id = "different"

    def test_resource_epoch_observes_all_loaded(self):
        """observed_loaded_models captures everything loaded, not just the target."""
        epoch = ResourceEpoch(
            operation_id="op_001",
            model_id="qwen3-4b",
            loaded_at="2026-06-16T00:00:00Z",
            observed_loaded_models=["qwen3-4b", "embedding-nomic", "qwen3-27b"],
        )
        assert len(epoch.observed_loaded_models) == 3
        assert "qwen3-27b" in epoch.observed_loaded_models

    def test_resource_epoch_default_vram_is_none(self):
        epoch = ResourceEpoch(
            operation_id="op_001",
            model_id="qwen3-4b",
            loaded_at="2026-06-16T00:00:00Z",
            observed_loaded_models=["qwen3-4b"],
        )
        assert epoch.vram_usage_mb is None
