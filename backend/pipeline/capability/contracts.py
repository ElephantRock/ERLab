"""Capability check lifecycle vocabulary (P0.4A1.3).

Status transitions for ``embedding_capability_checks``.

Lifecycle::

    pending → running → passed | failed | cancelled
                     ↓ (lease expiry)
                  abandoned

``passed``, ``failed``, ``cancelled``, and ``abandoned`` are all immutable
terminals. There is NO ``passed → expired`` transition. Expiry is derived
at read time::

    operational_status = "expired"
    when check_status == "passed" AND now > expires_at

The stored fact that a probe passed is never rewritten to "expired".
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Status vocabulary ─────────────────────────────────────────────────

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_ABANDONED = "abandoned"

TERMINAL_CHECK_STATUSES = frozenset({
    STATUS_PASSED,
    STATUS_FAILED,
    STATUS_CANCELLED,
    STATUS_ABANDONED,
})

ACTIVE_CHECK_STATUSES = frozenset({
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_PASSED,  # passed is terminal but "active" for authorization
})

# ── Transition map ────────────────────────────────────────────────────

VALID_CHECK_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_PENDING: frozenset({STATUS_RUNNING, STATUS_CANCELLED}),
    STATUS_RUNNING: frozenset({
        STATUS_PASSED,
        STATUS_FAILED,
        STATUS_CANCELLED,
        STATUS_ABANDONED,
    }),
    # All terminals are immutable — no outgoing transitions
    STATUS_PASSED: frozenset(),
    STATUS_FAILED: frozenset(),
    STATUS_CANCELLED: frozenset(),
    STATUS_ABANDONED: frozenset(),
}


def is_valid_transition(current: str, target: str) -> bool:
    """Check whether ``current → target`` is a permitted transition."""
    return target in VALID_CHECK_TRANSITIONS.get(current, frozenset())


def is_terminal(status: str) -> bool:
    """Check whether ``status`` is an immutable terminal."""
    return status in TERMINAL_CHECK_STATUSES


# ── Probe kinds ───────────────────────────────────────────────────────

PROBE_KIND_DOCUMENT = "document_probe"
PROBE_KIND_QUERY = "query_probe"
PROBE_KIND_DUAL = "dual_probe"

# ── Outcome dataclasses ───────────────────────────────────────────────


@dataclass(frozen=True)
class PassedCheckObservations:
    """Observed evidence from a successful dual probe.

    All observation fields are populated — the probe proved the runtime
    matches the declared contract.
    """

    observed_document_dimension: int
    observed_query_dimension: int
    observed_document_norm_min: float
    observed_document_norm_max: float
    observed_query_norm: float
    observed_document_reported_model: str | None
    observed_query_reported_model: str | None
    observed_document_provider_revision: str | None
    observed_query_provider_revision: str | None
    observed_document_evidence_source: str
    observed_query_evidence_source: str


@dataclass(frozen=True)
class FailedCheckEvidence:
    """Sanitized evidence from a failed probe."""

    failure_category: str
    failure_code: str
    sanitized_error_detail: str


# ── Exceptions ────────────────────────────────────────────────────────


class CheckAlreadyClaimed(Exception):
    """The check was already claimed by another worker."""


class CheckAlreadyTerminal(Exception):
    """The check is already in a terminal status and cannot be transitioned."""


class InvalidCheckTransition(Exception):
    """The requested transition is not permitted by the lifecycle map."""

    def __init__(self, check_id: str, current: str, target: str):
        self.check_id = check_id
        self.current = current
        self.target = target
        super().__init__(
            f"invalid check transition for {check_id[:16]}...: "
            f"{current} → {target}"
        )
