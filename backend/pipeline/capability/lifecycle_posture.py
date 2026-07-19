"""Unified embedding lifecycle posture and readiness evaluator (P0.4A3.1).

One authoritative read model that derives the current posture of an
embedding profile from authoritative ledger state.

Side-effect-free: posture evaluation reads state, computes status,
and returns blockers/actions. It must not run probes, recover leases,
create bindings, create cutovers, freeze writes, or activate bindings.

Readiness phases:
  unconfigured, configuration_invalid,
  verification_required, verification_failed,
  runtime_verified_transient, binding_not_activation_eligible,
  cutover_required, cutover_in_progress, cutover_blocked, cutover_ready,
  source_sealing_required, sealed, activation_ready,
  active, active_check_expired, active_runtime_drifted

Do not collapse runtime health and activation posture into one status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.db.models import (
    EmbeddingBindingCutover,
    EmbeddingBindingCutoverItem,
    EmbeddingCapabilityBinding,
    EmbeddingCapabilityCheck,
    EmbeddingProfileBindingActivation,
    EmbeddingProfileEmbeddingWriteGuard,
    VectorIndexRecord,
)
from backend.pipeline.capability.contracts import (
    STATUS_ABANDONED,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_RUNNING,
    TERMINAL_CHECK_STATUSES,
)
from backend.pipeline.capability.capability_drift import is_check_current
from backend.pipeline.vector_contracts import EMBEDDING_PROBE_SUITE_V1

# ── Readiness phases ─────────────────────────────────────────────────

PHASE_UNCONFIGURED = "unconfigured"
PHASE_CONFIGURATION_INVALID = "configuration_invalid"
PHASE_VERIFICATION_REQUIRED = "verification_required"
PHASE_VERIFICATION_FAILED = "verification_failed"
PHASE_RUNTIME_VERIFIED_TRANSIENT = "runtime_verified_transient"
PHASE_BINDING_NOT_ACTIVATION_ELIGIBLE = "binding_not_activation_eligible"
PHASE_CUTOVER_REQUIRED = "cutover_required"
PHASE_CUTOVER_IN_PROGRESS = "cutover_in_progress"
PHASE_CUTOVER_BLOCKED = "cutover_blocked"
PHASE_CUTOVER_READY = "cutover_ready"
PHASE_SOURCE_SEALING_REQUIRED = "source_sealing_required"
PHASE_SEALED = "sealed"
PHASE_ACTIVATION_READY = "activation_ready"
PHASE_ACTIVE = "active"
PHASE_ACTIVE_CHECK_EXPIRED = "active_check_expired"
PHASE_ACTIVE_RUNTIME_DRIFTED = "active_runtime_drifted"

# ── Blocker codes ────────────────────────────────────────────────────

BLOCKER_CONFIGURATION_INVALID = "configuration_invalid"
BLOCKER_CAPABILITY_CHECK_MISSING = "capability_check_missing"
BLOCKER_CAPABILITY_CHECK_FAILED = "capability_check_failed"
BLOCKER_CAPABILITY_CHECK_EXPIRED = "capability_check_expired"
BLOCKER_RUNTIME_CONFIGURATION_DRIFT = "runtime_configuration_drift"
BLOCKER_BINDING_MISSING = "binding_missing"
BLOCKER_BINDING_ALIAS_ONLY = "binding_alias_only"
BLOCKER_BINDING_NOT_ACTIVATION_ELIGIBLE = "binding_not_activation_eligible"
BLOCKER_CUTOVER_MISSING = "cutover_missing"
BLOCKER_CUTOVER_INCOMPLETE = "cutover_incomplete"
BLOCKER_CANONICAL_CONTENT_UNAVAILABLE = "canonical_content_unavailable"
BLOCKER_REPLACEMENT_COVERAGE_INCOMPLETE = "replacement_coverage_incomplete"
BLOCKER_SOURCE_POPULATION_DRIFTED = "source_population_drifted"
BLOCKER_WRITE_GUARD_NOT_FROZEN = "write_guard_not_frozen"
BLOCKER_ACTIVE_WRITE_OPERATIONS_PRESENT = "active_write_operations_present"
BLOCKER_CUTOVER_NOT_SEALED = "cutover_not_sealed"
BLOCKER_COLLECTION_VERIFICATION_FAILED = "collection_verification_failed"

# ── Activation statuses (mirror capability_bound_retrieval) ──────────

_ACTIVATION_ACTIVE = "active"
_ACTIVATION_CANDIDATE = "candidate"

# Cutover statuses that indicate "open" (not terminal)
_OPEN_CUTOVER_STATUSES = frozenset({
    "pending", "snapshotting", "reindexing", "verifying", "ready", "sealed",
})

# Binding postures that are NOT activation-eligible
_ALIAS_ONLY_POSTURES = frozenset({"configured_only"})


@dataclass(frozen=True)
class EmbeddingLifecyclePosture:
    """Unified read model for an embedding profile's current posture.

    Derived entirely from authoritative ledger state. Never mutated.
    """

    embedding_profile_id: str
    embedding_purpose: str

    # Capability health
    configuration_status: str
    runtime_config_fingerprint: str | None
    capability_health_status: str
    latest_check_id: str | None
    latest_check_status: str | None
    latest_check_expires_at: datetime | None

    # Binding
    binding_id: str | None
    model_resolution_posture: str | None
    persistent_activation_eligible: bool

    # Activation
    active_activation_id: str | None
    active_binding_id: str | None

    # Cutover
    open_cutover_id: str | None
    cutover_status: str | None
    source_item_count: int
    indexed_item_count: int
    failed_item_count: int
    unavailable_content_count: int

    # Guard
    write_guard_status: str

    # Derived readiness
    readiness_phase: str
    blocker_codes: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()


def evaluate_lifecycle_posture(
    session: Session,
    *,
    embedding_profile_id: str,
    embedding_purpose: str = "paper",
) -> EmbeddingLifecyclePosture:
    """Derive the current lifecycle posture from authoritative state.

    Side-effect-free. Reads only.
    """
    now = datetime.now(timezone.utc)

    # ── 1. Latest check ──
    latest_check = session.execute(
        select(EmbeddingCapabilityCheck)
        .where(
            EmbeddingCapabilityCheck.embedding_profile_id == embedding_profile_id,
        )
        .order_by(
            EmbeddingCapabilityCheck.completed_at.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()

    # ── 2. Binding ──
    binding = session.execute(
        select(EmbeddingCapabilityBinding)
        .where(
            EmbeddingCapabilityBinding.embedding_profile_id == embedding_profile_id,
        )
        .limit(1)
    ).scalar_one_or_none()

    # ── 3. Active activation ──
    active_activation = session.execute(
        select(EmbeddingProfileBindingActivation).where(
            EmbeddingProfileBindingActivation.embedding_profile_id == embedding_profile_id,
            EmbeddingProfileBindingActivation.status == _ACTIVATION_ACTIVE,
        )
    ).scalar_one_or_none()

    # ── 4. Open cutover ──
    open_cutover = session.execute(
        select(EmbeddingBindingCutover)
        .where(
            EmbeddingBindingCutover.embedding_profile_id == embedding_profile_id,
            EmbeddingBindingCutover.embedding_purpose == embedding_purpose,
            EmbeddingBindingCutover.status.in_(_OPEN_CUTOVER_STATUSES),
        )
        .order_by(EmbeddingBindingCutover.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    # ── 5. Cutover item counts ──
    source_count = 0
    indexed_count = 0
    failed_count = 0
    unavailable_count = 0

    if open_cutover is not None:
        items = session.execute(
            select(EmbeddingBindingCutoverItem.status)
            .where(EmbeddingBindingCutoverItem.cutover_id == open_cutover.cutover_id)
        ).scalars().all()

        source_count = len(items)
        indexed_count = sum(1 for s in items if s in ("indexed", "already_indexed"))
        failed_count = sum(1 for s in items if s == "failed")
        unavailable_count = sum(1 for s in items if s == "content_unavailable")

    # ── 6. Write guard ──
    guard = session.execute(
        select(EmbeddingProfileEmbeddingWriteGuard).where(
            EmbeddingProfileEmbeddingWriteGuard.embedding_profile_id == embedding_profile_id,
            EmbeddingProfileEmbeddingWriteGuard.embedding_purpose == embedding_purpose,
        )
    ).scalar_one_or_none()

    write_guard_status = guard.state if guard else "open"

    # ── 7. Derive readiness phase ──
    blockers: list[str] = []
    actions: list[str] = []
    phase = PHASE_UNCONFIGURED

    # Health status
    if latest_check is None:
        health_status = "no_check"
        blockers.append(BLOCKER_CAPABILITY_CHECK_MISSING)
    elif latest_check.check_status == STATUS_PASSED:
        if is_check_current(latest_check, now):
            health_status = "currently_verified"
        else:
            health_status = "expired"
            blockers.append(BLOCKER_CAPABILITY_CHECK_EXPIRED)
    elif latest_check.check_status == STATUS_FAILED:
        health_status = "latest_check_failed"
        blockers.append(BLOCKER_CAPABILITY_CHECK_FAILED)
    elif latest_check.check_status in (STATUS_ABANDONED, STATUS_CANCELLED):
        health_status = "latest_check_abandoned"
        blockers.append(BLOCKER_CAPABILITY_CHECK_MISSING)
    else:
        health_status = f"check_{latest_check.check_status}"
        blockers.append(BLOCKER_CAPABILITY_CHECK_MISSING)

    # Activation eligible
    activation_eligible = False
    if binding is not None:
        activation_eligible = (
            binding.model_resolution_posture not in _ALIAS_ONLY_POSTURES
        )

    # Determine phase
    if active_activation is not None:
        # Active posture
        if health_status == "expired":
            phase = PHASE_ACTIVE_CHECK_EXPIRED
            actions.append("Run 'erock capability verify' to refresh the check")
        elif health_status == "currently_verified":
            phase = PHASE_ACTIVE
        else:
            phase = PHASE_ACTIVE_CHECK_EXPIRED
            actions.append("Run 'erock capability verify' to restore authorization")
    elif latest_check is not None and health_status == "currently_verified":
        if binding is None:
            phase = PHASE_RUNTIME_VERIFIED_TRANSIENT
            actions.append("Binding will be created on next successful verification")
        elif not activation_eligible:
            phase = PHASE_BINDING_NOT_ACTIVATION_ELIGIBLE
            blockers.append(BLOCKER_BINDING_ALIAS_ONLY)
            actions.append("Use an activation-eligible provider for persistent activation")
        elif open_cutover is None:
            phase = PHASE_CUTOVER_REQUIRED
            actions.append("Run 'erock capability cutover-create' to begin transition")
        elif open_cutover.status in ("pending", "snapshotting", "reindexing", "verifying"):
            phase = PHASE_CUTOVER_IN_PROGRESS
            if failed_count > 0:
                blockers.append(BLOCKER_CUTOVER_INCOMPLETE)
            if unavailable_count > 0:
                blockers.append(BLOCKER_CANONICAL_CONTENT_UNAVAILABLE)
            if indexed_count < source_count:
                blockers.append(BLOCKER_REPLACEMENT_COVERAGE_INCOMPLETE)
            actions.append("Run 'erock capability cutover-run' to continue regeneration")
        elif open_cutover.status == "ready":
            phase = PHASE_SOURCE_SEALING_REQUIRED
            actions.append("Run 'erock capability cutover-seal' to freeze and verify")
        elif open_cutover.status == "sealed":
            phase = PHASE_ACTIVATION_READY
            actions.append("Run 'erock capability activate-binding' to activate")
        else:
            phase = PHASE_CUTOVER_IN_PROGRESS
    elif latest_check is not None and health_status == "latest_check_failed":
        phase = PHASE_VERIFICATION_FAILED
        actions.append("Inspect configuration and retry 'erock capability verify'")
    elif latest_check is not None:
        phase = PHASE_VERIFICATION_REQUIRED
        actions.append("Run 'erock capability verify'")
    else:
        phase = PHASE_VERIFICATION_REQUIRED
        actions.append("Run 'erock capability verify' to perform the first check")

    return EmbeddingLifecyclePosture(
        embedding_profile_id=embedding_profile_id,
        embedding_purpose=embedding_purpose,
        configuration_status="configured" if binding is not None else "unconfigured",
        runtime_config_fingerprint=latest_check.runtime_config_fingerprint if latest_check else None,
        capability_health_status=health_status,
        latest_check_id=latest_check.check_id if latest_check else None,
        latest_check_status=latest_check.check_status if latest_check else None,
        latest_check_expires_at=latest_check.expires_at if latest_check else None,
        binding_id=binding.binding_id if binding else None,
        model_resolution_posture=binding.model_resolution_posture if binding else None,
        persistent_activation_eligible=activation_eligible,
        active_activation_id=active_activation.activation_id if active_activation else None,
        active_binding_id=active_activation.capability_binding_id if active_activation else None,
        open_cutover_id=open_cutover.cutover_id if open_cutover else None,
        cutover_status=open_cutover.status if open_cutover else None,
        source_item_count=source_count,
        indexed_item_count=indexed_count,
        failed_item_count=failed_count,
        unavailable_content_count=unavailable_count,
        write_guard_status=write_guard_status,
        readiness_phase=phase,
        blocker_codes=tuple(blockers),
        next_actions=tuple(actions),
    )
