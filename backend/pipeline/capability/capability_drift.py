"""Runtime drift detection and authority queries (P0.4A1.7).

  current_fingerprint_matches(effective_config, stored_fingerprint) -> bool
      Recompute fingerprint from live config, compare to check's stored value.

  get_latest_completed_check(session, profile_id, fingerprint, suite) -> Check | None
      Authority query: latest TERMINAL check for (profile, fingerprint, suite).
      NOT 'latest passed' — a newer failure overrides an older pass.

  is_check_current(check, now) -> bool
      check.check_status == 'passed' AND now < check.expires_at

The authority rule (fail-closed):

  latest completed check for (profile_id, runtime_config_fingerprint, probe_suite_version):
    passed AND not expired AND dual_probe AND binding_id NOT NULL -> authorize
    failed / cancelled / abandoned -> deny (newer failure overrides older pass)
    no completed check -> deny
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.db.models import EmbeddingCapabilityCheck
from backend.pipeline.capability.capability_identity import (
    compute_runtime_config_fingerprint,
)
from backend.pipeline.capability.contracts import (
    STATUS_PASSED,
    TERMINAL_CHECK_STATUSES,
)
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)


def current_fingerprint_matches(
    effective_config: EffectiveEmbeddingConfiguration,
    stored_fingerprint: str,
) -> bool:
    """Recompute fingerprint from live config and compare to stored value."""
    current = compute_runtime_config_fingerprint(effective_config)
    return current == stored_fingerprint


def get_latest_completed_check(
    session: Session,
    embedding_profile_id: str,
    runtime_config_fingerprint: str,
    probe_suite_version: str,
) -> EmbeddingCapabilityCheck | None:
    """Latest terminal check for the given profile + fingerprint + suite.

    NOT 'latest passed' — a newer failure/cancellation/abandonment
    overrides an older pass. This is the authority query: the latest
    completed check determines authorization.
    """
    return session.execute(
        select(EmbeddingCapabilityCheck)
        .where(
            EmbeddingCapabilityCheck.embedding_profile_id == embedding_profile_id,
            EmbeddingCapabilityCheck.runtime_config_fingerprint == runtime_config_fingerprint,
            EmbeddingCapabilityCheck.probe_suite_version == probe_suite_version,
            EmbeddingCapabilityCheck.check_status.in_(TERMINAL_CHECK_STATUSES),
        )
        .order_by(
            EmbeddingCapabilityCheck.completed_at.desc(),
            # Secondary tiebreaker: the auto-generated rowid reflects
            # insertion order, so a check created later sorts later even
            # when completed_at timestamps tie at microsecond precision.
            text("rowid DESC"),
        )
        .limit(1)
    ).scalar_one_or_none()


def is_check_current(
    check: EmbeddingCapabilityCheck,
    now: datetime | None = None,
) -> bool:
    """Check is current: passed AND not expired.

    Expiry is DERIVED at read time — the stored check_status is never
    mutated to 'expired'.
    """
    if now is None:
        now = datetime.now(UTC)
    if check.check_status != STATUS_PASSED:
        return False
    if check.expires_at is None:
        return False
    # Handle timezone-naive datetimes from SQLite
    expires = check.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return now < expires
