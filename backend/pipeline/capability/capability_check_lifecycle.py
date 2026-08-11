"""Capability check claim and lease lifecycle (P0.4A1.3).

Implements the check-first lifecycle using the same atomic-claim pattern
as P0.2's ``execution_recorder.py``:

  create_pending_check
      Insert a pending check with binding_id = NULL.

  claim_check
      Conditional UPDATE WHERE status = 'pending' → 'running'.
      Sets claimed_at and lease_expires_at. Raises CheckAlreadyClaimed
      when rowcount != 1.

  recover_stale_running_checks
      UPDATE WHERE status = 'running' AND lease_expires_at < now
      → 'abandoned'. Returns count abandoned.

  complete_check_passed
      Transition running → passed. Sets binding_id, observations,
      expires_at, probed_at, completed_at.

  complete_check_failed
      Transition running → failed. binding_id stays NULL. Sets failure
      evidence and completed_at.

  operator_cancel_check
      Transition pending/running → cancelled. ONLY for explicit operator
      action BEFORE or OUTSIDE an active probe request. Task-level
      CancelledError during a provider request leaves the row 'running'
      for lease recovery.

Each transition is its own short transaction. Terminal rows are immutable
— duplicate lifecycle calls on a terminal are no-ops.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import EmbeddingCapabilityCheck
from backend.pipeline.capability.capability_identity import compute_check_id
from backend.pipeline.capability.contracts import (
    STATUS_ABANDONED,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_RUNNING,
    CheckAlreadyClaimed,
    CheckAlreadyTerminal,
    FailedCheckEvidence,
    InvalidCheckTransition,
    PassedCheckObservations,
    is_terminal,
    is_valid_transition,
)
from backend.pipeline.vector_contracts import (
    CAPABILITY_CHECK_SCHEMA_V1,
    EMBEDDING_PROBE_SUITE_V1,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


# ── Create ────────────────────────────────────────────────────────────


def create_pending_check(
    session: Session,
    *,
    embedding_profile_id: str,
    runtime_config_fingerprint: str,
    probe_suite_version: str = EMBEDDING_PROBE_SUITE_V1,
    probe_kind: str = "dual_probe",
) -> str:
    """Insert a pending check with binding_id = NULL.

    Returns the ``check_id``.
    """
    check_id = compute_check_id()
    check = EmbeddingCapabilityCheck(
        check_id=check_id,
        embedding_profile_id=embedding_profile_id,
        binding_id=None,
        runtime_config_fingerprint=runtime_config_fingerprint,
        probe_suite_version=probe_suite_version,
        check_status=STATUS_PENDING,
        probe_kind=probe_kind,
        attempt_count=0,
        provider_request_count=0,
        check_schema_version=CAPABILITY_CHECK_SCHEMA_V1,
    )
    session.add(check)
    session.flush()
    logger.debug(
        "pending check created: %s... (profile=%s...)",
        check_id[:16],
        embedding_profile_id[:16],
    )
    return check_id


# ── Claim ────────────────────────────────────────────────────────────


def claim_check(
    session_factory: sessionmaker,
    check_id: str,
    *,
    lease_ttl_seconds: int = 120,
) -> None:
    """Atomically claim a pending check.

    Conditional UPDATE::

        UPDATE embedding_capability_checks
        SET check_status = 'running',
            claimed_at = now,
            lease_expires_at = now + ttl,
            attempt_count = attempt_count + 1
        WHERE check_id = :id AND check_status = 'pending'

    Raises ``CheckAlreadyClaimed`` when rowcount != 1.
    """
    now = _now()
    lease_expiry = now + timedelta(seconds=lease_ttl_seconds)

    with session_factory() as session:
        result = session.execute(
            update(EmbeddingCapabilityCheck)
            .where(
                EmbeddingCapabilityCheck.check_id == check_id,
                EmbeddingCapabilityCheck.check_status == STATUS_PENDING,
            )
            .values(
                check_status=STATUS_RUNNING,
                claimed_at=now,
                lease_expires_at=lease_expiry,
                attempt_count=EmbeddingCapabilityCheck.attempt_count + 1,
            )
        )
        session.commit()

        if result.rowcount != 1:
            # Re-read current status for the error
            current = session.execute(
                select(EmbeddingCapabilityCheck.check_status).where(
                    EmbeddingCapabilityCheck.check_id == check_id
                )
            ).scalar_one_or_none()

            if current is None:
                raise CheckAlreadyClaimed(f"check {check_id[:16]}... not found")
            raise CheckAlreadyClaimed(
                f"check {check_id[:16]}... already in status {current!r}"
            )

    logger.debug("check claimed: %s...", check_id[:16])


# ── Recover stale ────────────────────────────────────────────────────


def recover_stale_running_checks(
    session_factory: sessionmaker,
    now: datetime | None = None,
) -> int:
    """Abandon checks whose lease has expired.

    UPDATE WHERE status = 'running' AND lease_expires_at < now
    → 'abandoned'.

    Returns the count of checks abandoned.
    """
    if now is None:
        now = _now()

    with session_factory() as session:
        result = session.execute(
            update(EmbeddingCapabilityCheck)
            .where(
                EmbeddingCapabilityCheck.check_status == STATUS_RUNNING,
                EmbeddingCapabilityCheck.lease_expires_at < now,
            )
            .values(
                check_status=STATUS_ABANDONED,
                completed_at=now,
            )
        )
        session.commit()
        count = result.rowcount or 0

    if count > 0:
        logger.info("recovered %d stale running checks (→ abandoned)", count)
    return count


# ── Complete ─────────────────────────────────────────────────────────


def _get_current_status(session: Session, check_id: str) -> str | None:
    return session.execute(
        select(EmbeddingCapabilityCheck.check_status).where(
            EmbeddingCapabilityCheck.check_id == check_id
        )
    ).scalar_one_or_none()


def complete_check_passed(
    session_factory: sessionmaker,
    check_id: str,
    *,
    binding_id: str,
    observations: PassedCheckObservations,
    expires_at: datetime,
    provider_request_count: int = 1,
) -> None:
    """Transition running → passed.

    Sets binding_id, all observation fields, expires_at, probed_at,
    completed_at. Raises ``InvalidCheckTransition`` if the check is not
    in 'running' status. Raises ``CheckAlreadyTerminal`` if the check is
    already terminal (idempotent no-op for a passed check).
    """
    now = _now()

    with session_factory() as session:
        current = _get_current_status(session, check_id)
        if current is None:
            raise ValueError(f"check {check_id[:16]}... not found")

        if current == STATUS_PASSED:
            raise CheckAlreadyTerminal(
                f"check {check_id[:16]}... already passed"
            )

        if not is_valid_transition(current, STATUS_PASSED):
            raise InvalidCheckTransition(check_id, current, STATUS_PASSED)

        result = session.execute(
            update(EmbeddingCapabilityCheck)
            .where(
                EmbeddingCapabilityCheck.check_id == check_id,
                EmbeddingCapabilityCheck.check_status == STATUS_RUNNING,
            )
            .values(
                check_status=STATUS_PASSED,
                binding_id=binding_id,
                probed_at=now,
                completed_at=now,
                expires_at=expires_at,
                provider_request_count=provider_request_count,
                observed_document_dimension=observations.observed_document_dimension,
                observed_query_dimension=observations.observed_query_dimension,
                observed_document_norm_min=observations.observed_document_norm_min,
                observed_document_norm_max=observations.observed_document_norm_max,
                observed_query_norm=observations.observed_query_norm,
                observed_document_reported_model=observations.observed_document_reported_model,
                observed_query_reported_model=observations.observed_query_reported_model,
                observed_document_provider_revision=observations.observed_document_provider_revision,
                observed_query_provider_revision=observations.observed_query_provider_revision,
                observed_document_evidence_source=observations.observed_document_evidence_source,
                observed_query_evidence_source=observations.observed_query_evidence_source,
            )
        )
        session.commit()

        if result.rowcount != 1:
            raise InvalidCheckTransition(check_id, current, STATUS_PASSED)

    logger.info(
        "check passed: %s... (binding=%s..., expires_at=%s)",
        check_id[:16],
        binding_id[:16],
        expires_at.isoformat(),
    )


def complete_check_failed(
    session_factory: sessionmaker,
    check_id: str,
    *,
    failure: FailedCheckEvidence,
    provider_request_count: int = 1,
) -> None:
    """Transition running → failed.

    binding_id stays NULL. Sets failure evidence and completed_at.
    """
    now = _now()

    with session_factory() as session:
        current = _get_current_status(session, check_id)
        if current is None:
            raise ValueError(f"check {check_id[:16]}... not found")

        if current == STATUS_FAILED:
            raise CheckAlreadyTerminal(
                f"check {check_id[:16]}... already failed"
            )

        if not is_valid_transition(current, STATUS_FAILED):
            raise InvalidCheckTransition(check_id, current, STATUS_FAILED)

        result = session.execute(
            update(EmbeddingCapabilityCheck)
            .where(
                EmbeddingCapabilityCheck.check_id == check_id,
                EmbeddingCapabilityCheck.check_status == STATUS_RUNNING,
            )
            .values(
                check_status=STATUS_FAILED,
                probed_at=now,
                completed_at=now,
                provider_request_count=provider_request_count,
                failure_category=failure.failure_category,
                failure_code=failure.failure_code,
                sanitized_error_detail=failure.sanitized_error_detail,
            )
        )
        session.commit()

        if result.rowcount != 1:
            raise InvalidCheckTransition(check_id, current, STATUS_FAILED)

    logger.info(
        "check failed: %s... (code=%s)",
        check_id[:16],
        failure.failure_code,
    )


# ── Cancel ───────────────────────────────────────────────────────────


def operator_cancel_check(
    session_factory: sessionmaker,
    check_id: str,
) -> None:
    """Transition pending/running → cancelled.

    ONLY for explicit operator cancellation BEFORE or OUTSIDE an active
    probe request. Task-level ``CancelledError`` during a provider
    request should NOT call this — it leaves the row 'running' for lease
    recovery via ``recover_stale_running_checks``.

    Sets completed_at. binding_id stays NULL.
    """
    now = _now()

    with session_factory() as session:
        current = _get_current_status(session, check_id)
        if current is None:
            raise ValueError(f"check {check_id[:16]}... not found")

        if is_terminal(current):
            raise CheckAlreadyTerminal(
                f"check {check_id[:16]}... already terminal ({current})"
            )

        if not is_valid_transition(current, STATUS_CANCELLED):
            raise InvalidCheckTransition(check_id, current, STATUS_CANCELLED)

        result = session.execute(
            update(EmbeddingCapabilityCheck)
            .where(
                EmbeddingCapabilityCheck.check_id == check_id,
                EmbeddingCapabilityCheck.check_status.in_([
                    STATUS_PENDING, STATUS_RUNNING
                ]),
            )
            .values(
                check_status=STATUS_CANCELLED,
                completed_at=now,
            )
        )
        session.commit()

        if result.rowcount != 1:
            raise InvalidCheckTransition(check_id, current, STATUS_CANCELLED)

    logger.info("check cancelled: %s...", check_id[:16])
