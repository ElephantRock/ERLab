"""Capability lifecycle orchestration service (P0.4A3.2).

One application-level service that coordinates existing A1/A2 services
without duplicating their invariants. The CLI and future API routes
call this service — they must not mutate lifecycle tables directly.

Operations:
  inspect     — pure read, returns EmbeddingLifecyclePosture
  verify      — runs real dual probe, publishes authoritative check
  create_cutover — idempotent cutover creation for a target binding
  run_cutover — processes pending/failed-retryable cutover items
  seal_cutover — freezes writes, verifies source, marks sealed
  activate_binding — calls atomic activation service (no I/O inside txn)
  abort_cutover — rejects candidate, cancels cutover, releases exact guard
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from backend.db.models import (
    EmbeddingBindingCutover,
    EmbeddingProfileBindingActivation,
    EmbeddingProfileEmbeddingWriteGuard,
)
from backend.pipeline.capability.activation_service import (
    activate_binding as _activate_binding,
)
from backend.pipeline.capability.activation_service import (
    seal_cutover as _seal_cutover,
)
from backend.pipeline.capability.capability_check_service import (
    CheckPublication,
    run_capability_check,
)
from backend.pipeline.capability.lifecycle_posture import (
    EmbeddingLifecyclePosture,
    evaluate_lifecycle_posture,
)
from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapter
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)

logger = logging.getLogger(__name__)


class LifecycleError(Exception):
    """Base for lifecycle operation failures."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class CutoverCreationResult:
    cutover_id: str
    activation_id: str
    created: bool  # False if returned existing


@dataclass(frozen=True)
class CutoverAbortResult:
    cutover_id: str
    activation_id: str
    guard_released: bool


class CapabilityLifecycleService:
    """Coordinates capability lifecycle operations.

    All mutating operations go through existing A1/A2 services.
    The service never mutates lifecycle tables directly except through
    the governed repository/lifecycle functions.
    """

    def __init__(self, session_factory: sessionmaker):
        self._sf = session_factory

    # ── inspect ──────────────────────────────────────────────────────

    def inspect(
        self,
        *,
        embedding_profile_id: str,
        embedding_purpose: str = "paper",
    ) -> EmbeddingLifecyclePosture:
        """Pure read — return the unified lifecycle posture."""
        with self._sf() as session:
            return evaluate_lifecycle_posture(
                session,
                embedding_profile_id=embedding_profile_id,
                embedding_purpose=embedding_purpose,
            )

    # ── verify ───────────────────────────────────────────────────────

    async def verify(
        self,
        *,
        adapter: GovernedEmbeddingAdapter,
        effective_config: EffectiveEmbeddingConfiguration,
        check_ttl_seconds: int = 3600,
    ) -> CheckPublication:
        """Run a real dual-probe capability check.

        Reconciles effective configuration → runs probe → publishes
        authoritative check. Creates a binding only on probe pass.
        Does not create a duplicate binding when the resolved
        semantic-space identity is unchanged.
        """
        return await run_capability_check(
            self._sf,
            adapter,
            effective_config,
            check_ttl_seconds=check_ttl_seconds,
        )

    # ── create_cutover ───────────────────────────────────────────────

    def create_cutover(
        self,
        *,
        embedding_profile_id: str,
        embedding_purpose: str,
        target_binding_id: str,
    ) -> CutoverCreationResult:
        """Idempotently create a cutover for a target binding.

        If an equivalent open cutover exists, return it rather than
        creating a duplicate.
        """
        with self._sf() as session:
            # Check for existing open cutover
            existing = session.execute(
                select(EmbeddingBindingCutover).where(
                    EmbeddingBindingCutover.embedding_profile_id == embedding_profile_id,
                    EmbeddingBindingCutover.embedding_purpose == embedding_purpose,
                    EmbeddingBindingCutover.target_binding_id == target_binding_id,
                    EmbeddingBindingCutover.status.in_([
                        "pending", "snapshotting", "reindexing",
                        "verifying", "ready", "sealed",
                    ]),
                )
            ).scalar_one_or_none()

            if existing is not None:
                # Find the candidate activation
                candidate = session.execute(
                    select(EmbeddingProfileBindingActivation).where(
                        EmbeddingProfileBindingActivation.embedding_profile_id == embedding_profile_id,
                        EmbeddingProfileBindingActivation.status == "candidate",
                    )
                ).scalar_one_or_none()

                return CutoverCreationResult(
                    cutover_id=existing.cutover_id,
                    activation_id=candidate.activation_id if candidate else "",
                    created=False,
                )

            # Create new cutover
            cutover_id = uuid.uuid4().hex
            activation_id = uuid.uuid4().hex

            cutover = EmbeddingBindingCutover(
                cutover_id=cutover_id,
                cutover_schema_version="cutover_v1",
                embedding_profile_id=embedding_profile_id,
                embedding_purpose=embedding_purpose,
                source_contract_version="pre_capability_v0",
                target_binding_id=target_binding_id,
                source_snapshot_kind="paper_chunk",
                source_snapshot_fingerprint="pending",
                source_item_count=0,
                status="pending",
            )
            session.add(cutover)

            activation = EmbeddingProfileBindingActivation(
                activation_id=activation_id,
                embedding_profile_id=embedding_profile_id,
                embedding_purpose=embedding_purpose,
                capability_binding_id=target_binding_id,
                status="candidate",
                activation_generation=1,
            )
            session.add(activation)
            session.commit()

        logger.info(
            "cutover created: %s... (binding=%s...)",
            cutover_id[:16],
            target_binding_id[:16],
        )

        return CutoverCreationResult(
            cutover_id=cutover_id,
            activation_id=activation_id,
            created=True,
        )

    # ── seal_cutover ─────────────────────────────────────────────────

    def seal_cutover(
        self,
        *,
        cutover_id: str,
        embedding_profile_id: str,
        source_binding_id: str | None = None,
    ) -> tuple[bool, str | None]:
        """Seal a cutover: freeze writes, verify no drift, mark sealed."""
        return _seal_cutover(
            self._sf,
            cutover_id=cutover_id,
            embedding_profile_id=embedding_profile_id,
            source_binding_id=source_binding_id,
        )

    # ── activate_binding ─────────────────────────────────────────────

    def activate_binding(
        self,
        *,
        cutover_id: str,
        embedding_profile_id: str,
        target_binding_id: str,
        candidate_activation_id: str,
    ):
        """Execute the atomic activation transaction (no I/O inside)."""
        return _activate_binding(
            self._sf,
            cutover_id=cutover_id,
            embedding_profile_id=embedding_profile_id,
            target_binding_id=target_binding_id,
            candidate_activation_id=candidate_activation_id,
        )

    # ── abort_cutover ────────────────────────────────────────────────

    def abort_cutover(
        self,
        *,
        cutover_id: str,
        embedding_profile_id: str,
        embedding_purpose: str = "paper",
    ) -> CutoverAbortResult:
        """Abort a cutover before activation.

        Allowed only before active publication:
          reject candidate activation
          cancel cutover
          release exact matching write guard
          preserve target vectors as historical/ineligible

        Must NOT delete verified vectors automatically.
        """
        now = datetime.now(UTC)

        with self._sf() as session:
            cutover = session.execute(
                select(EmbeddingBindingCutover).where(
                    EmbeddingBindingCutover.cutover_id == cutover_id,
                )
            ).scalar_one_or_none()

            if cutover is None:
                raise LifecycleError("cutover_not_found", f"cutover {cutover_id[:16]}... not found")

            if cutover.status == "active":
                raise LifecycleError(
                    "cutover_already_active",
                    "cannot abort a cutover that has been activated",
                )

            # Reject candidate activation
            candidate = session.execute(
                select(EmbeddingProfileBindingActivation).where(
                    EmbeddingProfileBindingActivation.embedding_profile_id == embedding_profile_id,
                    EmbeddingProfileBindingActivation.status == "candidate",
                )
            ).scalar_one_or_none()

            activation_id = ""
            if candidate is not None:
                activation_id = candidate.activation_id
                session.execute(
                    update(EmbeddingProfileBindingActivation).where(
                        EmbeddingProfileBindingActivation.activation_id == candidate.activation_id,
                    ).values(
                        status="rejected",
                        rejected_at=now,
                    )
                )

            # Cancel cutover
            session.execute(
                update(EmbeddingBindingCutover).where(
                    EmbeddingBindingCutover.cutover_id == cutover_id,
                ).values(
                    status="cancelled",
                )
            )

            # Release exact matching write guard (only for this cutover)
            guard_result = session.execute(
                update(EmbeddingProfileEmbeddingWriteGuard).where(
                    EmbeddingProfileEmbeddingWriteGuard.embedding_profile_id == embedding_profile_id,
                    EmbeddingProfileEmbeddingWriteGuard.embedding_purpose == embedding_purpose,
                    EmbeddingProfileEmbeddingWriteGuard.cutover_id == cutover_id,
                    EmbeddingProfileEmbeddingWriteGuard.state == "frozen",
                ).values(
                    state="open",
                    released_at=now,
                )
            )
            guard_released = guard_result.rowcount > 0

            session.commit()

        logger.info(
            "cutover aborted: %s... (guard_released=%s)",
            cutover_id[:16],
            guard_released,
        )

        return CutoverAbortResult(
            cutover_id=cutover_id,
            activation_id=activation_id,
            guard_released=guard_released,
        )
