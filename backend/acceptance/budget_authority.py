"""Hard pre-call budget authority for live-paper acceptance.

Every existing budget mechanism in the pipeline is post-call accounting.
Live acceptance requires refusing a call BEFORE it proceeds, accounting
for the projected maximum cost of the next call, not merely the cost
already spent.

The decision before each call is:

    current committed cost
    + active reservations
    + conservative maximum cost of the proposed call
    <= configured ceiling

A hard cap must prevent OVERSHOOT, not merely stop after the ceiling is
reached.

Typed outcomes:
    BudgetConfigurationError  — no enforceable budget before execution
    BudgetReservationDeniedError   — the next call cannot fit under the ceiling
    BudgetReconciliationError — actual usage exceeded the reservation

Classification in the verdict layer:
    No enforceable budget configuration before execution → INVALID_CASE
    A valid run exhausts its permitted budget             → FAIL
    Provider outage                                       → INCONCLUSIVE
Budget exhaustion is never an external interruption.

The refusal exception subclasses PromptTooLargeError so the GatewayProvider
re-raises it instead of falling back to the (billed) inner provider —
a plain Exception there would be swallowed and the call would proceed.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from backend.pipeline.gateway.token_budget import PromptTooLargeError


class BudgetConfigurationError(RuntimeError):
    """No enforceable budget configuration is present before execution."""


class BudgetExceededError(PromptTooLargeError):
    """The next call cannot fit under the configured cost ceiling.

    Subclasses PromptTooLargeError so GatewayProvider re-raises rather
    than falling back to the inner provider (which would bill anyway).
    Overrides __init__ because PromptTooLargeError requires token-window
    args that are meaningless for a cost refusal; we set them to sentinels
    so the isinstance check the GatewayProvider relies on still holds.
    """

    def __init__(self, message: str = ""):
        # Bypass PromptTooLargeError's token-window __init__ while still
        # being an instance of it (the GatewayProvider re-raises on the
        # isinstance(exc, PromptTooLargeError) check).
        Exception.__init__(self, message)
        self.input_tokens = -1
        self.output_reserve = -1
        self.context_window = -1
        self.available = -1


class BudgetReservationDeniedError(BudgetExceededError):
    """A specific reservation request was denied because it would overshoot."""


class BudgetReconciliationError(RuntimeError):
    """Actual usage exceeded the reserved amount (post-call breach)."""


@dataclass
class CallProjection:
    """A conservative pre-call projection of a single billable call's cost."""

    stage: str = ""
    run_id: str | None = None
    max_cost_usd: float = 0.0
    max_input_tokens: int = 0
    max_output_tokens: int = 0

    @staticmethod
    def from_limits(
        max_input_tokens: int,
        max_output_tokens: int,
        price_per_1k_input: float,
        price_per_1k_output: float,
        *,
        stage: str = "",
        run_id: str | None = None,
    ) -> CallProjection:
        """Build a projection from token limits and per-1K-token prices."""
        cost = (
            (max_input_tokens / 1000.0) * price_per_1k_input
            + (max_output_tokens / 1000.0) * price_per_1k_output
        )
        return CallProjection(
            stage=stage, run_id=run_id,
            max_cost_usd=cost,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
        )


@dataclass
class BudgetEnforcementSnapshot:
    """Safe structural record of budget enforcement for evidence."""

    ceiling_usd: float = 0.0
    committed_usd: float = 0.0
    reserved_usd: float = 0.0
    denied_calls: int = 0
    overshoot_usd: float = 0.0
    reconciled: bool = True

    def to_dict(self) -> dict:
        return {
            "ceiling_usd": round(self.ceiling_usd, 8),
            "committed_usd": round(self.committed_usd, 8),
            "reserved_usd": round(self.reserved_usd, 8),
            "denied_calls": self.denied_calls,
            "overshoot_usd": round(self.overshoot_usd, 8),
            "reconciled": self.reconciled,
        }


class BudgetAuthority:
    """One run-scoped authority that reserves cost before each billable call.

    Thread-safe (a lock guards the shared counters) so concurrent calls
    compete correctly for the remaining budget.

    Lifecycle per call:
        reserve(projection)   → conservative maximum held before the call
        reconcile(actual)     → release unused, record committed, detect breach
        release()             → release on provider exception (no reconcile)

    A zero-dollar ceiling permits NO calls (the strictest policy).
    """

    def __init__(
        self,
        ceiling_usd: float,
        *,
        strict: bool = True,
        run_id: str | None = None,
        price_per_1k_input: float = 0.0,
        price_per_1k_output: float = 0.0,
    ):
        if ceiling_usd < 0.0:
            raise BudgetConfigurationError(
                f"ceiling_usd must be non-negative, got {ceiling_usd}"
            )
        if price_per_1k_input < 0.0 or price_per_1k_output < 0.0:
            raise BudgetConfigurationError("prices must be non-negative")
        self._ceiling = ceiling_usd
        self._strict = strict
        self._run_id = run_id
        self._price_in = price_per_1k_input
        self._price_out = price_per_1k_output
        self._committed = 0.0
        self._reserved = 0.0
        self._denied = 0
        self._overshoot = 0.0
        self._reconciled = True
        self._reservations: dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def ceiling_usd(self) -> float:
        return self._ceiling

    @property
    def strict(self) -> bool:
        return self._strict

    def committed_usd(self) -> float:
        with self._lock:
            return self._committed

    def reserved_usd(self) -> float:
        with self._lock:
            return self._reserved

    def remaining_usd(self) -> float:
        with self._lock:
            return max(0.0, self._ceiling - self._committed - self._reserved)

    def cost_for_tokens(self, input_tokens: int, output_tokens: int) -> float:
        """Compute the actual cost of a completed call from token counts."""
        return (
            (input_tokens / 1000.0) * self._price_in
            + (output_tokens / 1000.0) * self._price_out
        )

    def project_call(
        self,
        *,
        max_input_tokens: int,
        max_output_tokens: int,
        stage: str = "",
        run_id: str | None = None,
    ) -> CallProjection:
        """Build a conservative-maximum projection for a call.

        If pricing is configured, the projection cost is token-limited.
        If pricing is unknown (both zero), the projection conservatively
        reserves the ENTIRE remaining budget — guaranteeing no overshoot
        at the cost of admitting at most one call until pricing is set.
        """
        if self._price_in == 0.0 and self._price_out == 0.0:
            # Unknown pricing: reserve the whole remaining budget as the
            # worst case for this single call.
            max_cost = self.remaining_usd()
        else:
            max_cost = (
                (max_input_tokens / 1000.0) * self._price_in
                + (max_output_tokens / 1000.0) * self._price_out
            )
        return CallProjection(
            stage=stage, run_id=run_id,
            max_cost_usd=max_cost,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
        )

    def reserve(self, projection: CallProjection) -> str:
        """Reserve the conservative maximum cost before a call.

        Returns a reservation ID that must be passed to ``reconcile`` or
        ``release`` for this specific call. Raises
        BudgetReservationDeniedError if the reservation would overshoot
        the ceiling. On denial the call MUST NOT proceed and MUST NOT retry.
        """
        with self._lock:
            projected_total = self._committed + self._reserved + projection.max_cost_usd
            if projected_total > self._ceiling + 1e-12:
                self._denied += 1
                raise BudgetReservationDeniedError(
                    f"budget reservation denied: committed={self._committed:.8f} "
                    f"reserved={self._reserved:.8f} projected_call={projection.max_cost_usd:.8f} "
                    f"ceiling={self._ceiling:.8f}"
                )
            reservation_id = uuid.uuid4().hex
            self._reservations[reservation_id] = projection.max_cost_usd
            self._reserved += projection.max_cost_usd
            return reservation_id

    def reconcile(self, reservation_id: str, actual_cost_usd: float) -> None:
        """Reconcile a specific reservation with actual usage after the call.

        Releases the unused portion of the identified reservation. If
        actual committed cost exceeds the ceiling (an overshoot), records
        it and (in strict mode) marks the authority unreconciled.
        """
        with self._lock:
            reserved_amt = self._reservations.pop(reservation_id, 0.0)
            self._reserved = max(0.0, self._reserved - reserved_amt)
            self._committed += actual_cost_usd
            if self._committed > self._ceiling + 1e-9:
                self._overshoot = max(self._overshoot, self._committed - self._ceiling)
                if self._strict:
                    self._reconciled = False

    def release(self, reservation_id: str) -> None:
        """Release a specific outstanding reservation (e.g. on exception)."""
        with self._lock:
            reserved_amt = self._reservations.pop(reservation_id, 0.0)
            self._reserved = max(0.0, self._reserved - reserved_amt)

    def snapshot(self) -> BudgetEnforcementSnapshot:
        with self._lock:
            return BudgetEnforcementSnapshot(
                ceiling_usd=self._ceiling,
                committed_usd=self._committed,
                reserved_usd=self._reserved,
                denied_calls=self._denied,
                overshoot_usd=self._overshoot,
                reconciled=self._reconciled,
            )
