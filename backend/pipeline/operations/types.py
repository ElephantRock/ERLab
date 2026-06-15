"""Core type contracts for the operation executor.

These types are the single source of truth for:
- What a model-backed call returned (ModelReceipt)
- What the system state was when it ran (ResourceEpoch)
- What a stage produced after execution (StageExecutionResult)
- What failures look like (typed errors)

No component should invent its own versions of these contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StageStatus(str, Enum):
    """Lifecycle states for a single stage execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class FailureClass(str, Enum):
    """Typed failure categories for stage execution.

    Each maps to a distinct recovery strategy. New failure types
    must be added here — bare ``except Exception`` is forbidden
    in operation executor code.
    """

    MODEL_NOT_AVAILABLE = "model_not_available"
    WRONG_MODEL_SERVED = "wrong_model_served"
    MISSING_RECEIPT = "missing_receipt"
    LM_STUDIO_UNREACHABLE = "lm_studio_unreachable"
    PERSISTENCE_ERROR = "persistence_error"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SCHEMA_VALIDATION = "schema_validation"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelReceipt:
    """Verifiable proof that a specific model served a specific call.

    Every model-backed response must carry one. Missing receipt
    raises MissingModelReceiptError. Mismatched served model
    raises WrongModelServedError.
    """

    requested_model: str
    served_model: str
    provider: str
    endpoint: str
    timestamp: str
    context_length: int | None = None


@dataclass(frozen=True)
class ResourceEpoch:
    """Snapshot of LM Studio state at the moment an operation ran.

    Captures the full loaded-model picture — not just the target
    model — so reconciliation logic can detect stale cached state
    or foreign models loaded by external processes.
    """

    operation_id: str
    model_id: str
    loaded_at: str
    observed_loaded_models: list[str]
    vram_usage_mb: float | None = None


@dataclass
class StageExecutionResult:
    """Typed outcome of a single stage execution.

    A stage that returns ``bool`` is compatibility-mode only and
    cannot produce real receipts. Fully conformant stages produce
    results with at least one ``ModelReceipt`` per model-backed call.
    """

    status: StageStatus
    failure_class: str | None = None
    model_receipts: list[ModelReceipt] = field(default_factory=list)
    resource_epoch: ResourceEpoch | None = None
    retryable: bool = False
    collector_record_ids: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def is_compatibility_mode(self) -> bool:
        """True if this result was produced by a non-conformant (bool) stage.

        Compatibility-mode results have no model receipts. They must
        not be treated as fully conformant.
        """
        return self.status == StageStatus.COMPLETED and not self.model_receipts

    @property
    def succeeded(self) -> bool:
        return self.status == StageStatus.COMPLETED


# ── Typed Errors ──────────────────────────────────────────────


class OperationError(Exception):
    """Base class for all operation executor errors."""

    failure_class: FailureClass = FailureClass.UNKNOWN


class MissingModelReceiptError(OperationError):
    """Raised when a model-backed call returns no verifiable receipt.

    This means the response cannot be trusted — the conformance
    layer has no proof of which model actually served the call.
    """

    failure_class = FailureClass.MISSING_RECEIPT


class WrongModelServedError(OperationError):
    """Raised when the served model does not match the requested model.

    The caller asked for model A, but the receipt shows model B was
    served. This is a correctness violation, not a performance issue.
    """

    failure_class = FailureClass.WRONG_MODEL_SERVED

    def __init__(self, requested: str, served: str) -> None:
        self.requested_model = requested
        self.served_model = served
        super().__init__(
            f"Wrong model served: requested '{requested}', got '{served}'"
        )


class ModelNotAvailableError(OperationError):
    """Raised when the required model cannot be loaded or found."""

    failure_class = FailureClass.MODEL_NOT_AVAILABLE


class LMStudioUnreachableError(OperationError):
    """Raised when LM Studio server is not reachable."""

    failure_class = FailureClass.LM_STUDIO_UNREACHABLE
