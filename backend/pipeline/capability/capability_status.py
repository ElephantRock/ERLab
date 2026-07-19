"""Capability status derivation (P0.4A1.8).

Derives a human-readable capability status from the binding/check ledger
and the current runtime fingerprint.

Status vocabulary:
  currently_verified   latest passed check, not expired, fingerprint matches
  expired              latest passed check but past expires_at
  latest_check_failed  latest completed check is failed/cancelled/abandoned
  no_check             no completed check for this profile+fingerprint+suite
  runtime_drifted      current fingerprint differs from the latest check's
  check_running        latest check is in running status (not terminal)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import EmbeddingCapabilityCheck
from backend.pipeline.capability.contracts import (
    STATUS_ABANDONED,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_RUNNING,
    TERMINAL_CHECK_STATUSES,
)
from backend.pipeline.capability.capability_identity import (
    compute_runtime_config_fingerprint,
)
from backend.pipeline.capability.capability_drift import is_check_current
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)
from backend.pipeline.vector_contracts import EMBEDDING_PROBE_SUITE_V1


STATUS_CURRENTLY_VERIFIED = "currently_verified"
STATUS_EXPIRED = "expired"
STATUS_LATEST_CHECK_FAILED = "latest_check_failed"
STATUS_NO_CHECK = "no_check"
STATUS_RUNTIME_DRIFTED = "runtime_drifted"
STATUS_CHECK_RUNNING = "check_running"


@dataclass(frozen=True)
class CapabilityStatus:
    """Derived capability status for a profile + runtime fingerprint."""

    derived_status: str
    embedding_profile_id: str
    latest_check_id: str | None
    latest_check_status: str | None
    latest_check_binding_id: str | None
    latest_check_expires_at: datetime | None
    runtime_config_fingerprint: str | None


def derive_capability_status(
    session: Session,
    *,
    embedding_profile_id: str,
    current_runtime_config_fingerprint: str | None = None,
    probe_suite_version: str = EMBEDDING_PROBE_SUITE_V1,
) -> CapabilityStatus:
    """Derive the current capability status.

    If ``current_runtime_config_fingerprint`` is None, runtime_drifted
    is omitted from the possible results (cannot determine drift
    without the live config).
    """
    now = datetime.now(timezone.utc)

    # If fingerprint provided, check for any check under that fingerprint
    if current_runtime_config_fingerprint is not None:
        # Look for latest check of ANY status (terminal or running)
        latest_any = session.execute(
            select(EmbeddingCapabilityCheck)
            .where(
                EmbeddingCapabilityCheck.embedding_profile_id == embedding_profile_id,
                EmbeddingCapabilityCheck.runtime_config_fingerprint == current_runtime_config_fingerprint,
                EmbeddingCapabilityCheck.probe_suite_version == probe_suite_version,
            )
            .order_by(
                EmbeddingCapabilityCheck.created_at.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()

        if latest_any is None:
            return CapabilityStatus(
                derived_status=STATUS_NO_CHECK,
                embedding_profile_id=embedding_profile_id,
                latest_check_id=None,
                latest_check_status=None,
                latest_check_binding_id=None,
                latest_check_expires_at=None,
                runtime_config_fingerprint=current_runtime_config_fingerprint,
            )

        if latest_any.check_status == STATUS_RUNNING:
            return CapabilityStatus(
                derived_status=STATUS_CHECK_RUNNING,
                embedding_profile_id=embedding_profile_id,
                latest_check_id=latest_any.check_id,
                latest_check_status=latest_any.check_status,
                latest_check_binding_id=None,
                latest_check_expires_at=None,
                runtime_config_fingerprint=current_runtime_config_fingerprint,
            )

        if latest_any.check_status == STATUS_PASSED:
            if is_check_current(latest_any, now):
                return CapabilityStatus(
                    derived_status=STATUS_CURRENTLY_VERIFIED,
                    embedding_profile_id=embedding_profile_id,
                    latest_check_id=latest_any.check_id,
                    latest_check_status=latest_any.check_status,
                    latest_check_binding_id=latest_any.binding_id,
                    latest_check_expires_at=latest_any.expires_at,
                    runtime_config_fingerprint=current_runtime_config_fingerprint,
                )
            else:
                return CapabilityStatus(
                    derived_status=STATUS_EXPIRED,
                    embedding_profile_id=embedding_profile_id,
                    latest_check_id=latest_any.check_id,
                    latest_check_status=latest_any.check_status,
                    latest_check_binding_id=latest_any.binding_id,
                    latest_check_expires_at=latest_any.expires_at,
                    runtime_config_fingerprint=current_runtime_config_fingerprint,
                )

        # failed / cancelled / abandoned
        return CapabilityStatus(
            derived_status=STATUS_LATEST_CHECK_FAILED,
            embedding_profile_id=embedding_profile_id,
            latest_check_id=latest_any.check_id,
            latest_check_status=latest_any.check_status,
            latest_check_binding_id=None,
            latest_check_expires_at=None,
            runtime_config_fingerprint=current_runtime_config_fingerprint,
        )

    # No fingerprint provided — just check if any check exists for the profile
    any_check = session.execute(
        select(EmbeddingCapabilityCheck)
        .where(
            EmbeddingCapabilityCheck.embedding_profile_id == embedding_profile_id,
        )
        .order_by(EmbeddingCapabilityCheck.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if any_check is None:
        return CapabilityStatus(
            derived_status=STATUS_NO_CHECK,
            embedding_profile_id=embedding_profile_id,
            latest_check_id=None,
            latest_check_status=None,
            latest_check_binding_id=None,
            latest_check_expires_at=None,
            runtime_config_fingerprint=None,
        )

    return CapabilityStatus(
        derived_status="(fingerprint required for drift assessment)",
        embedding_profile_id=embedding_profile_id,
        latest_check_id=any_check.check_id,
        latest_check_status=any_check.check_status,
        latest_check_binding_id=any_check.binding_id,
        latest_check_expires_at=any_check.expires_at,
        runtime_config_fingerprint=None,
    )
