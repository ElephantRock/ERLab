"""Check-first publication service (P0.4A1.5).

Orchestrates the full capability check lifecycle:

  1. compute runtime_config_fingerprint(effective_config)
  2. recover_stale_running_checks(now)
  3. create_pending_check (binding_id = NULL)
  4. claim_check (atomic, sets lease)
  5. probe = await probe_embedding_capability(adapter, expected_dimension)
  6. IF probe.passed:
       classify_resolution -> resolve_or_create_binding
       complete_check_passed (binding_id, observations, expires_at)
     ELSE:
       complete_check_failed (binding_id remains NULL)
  7. return CheckPublication

On ANY exception during probe: complete_check_failed with sanitized
detail. The check row always reaches a terminal state.

Frozen rule:
  A failed or incomplete probe may create check evidence, but it may
  never create a resolved capability binding. The binding is resolved
  ONLY after the probe passes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import sessionmaker

from backend.pipeline.capability.capability_check_lifecycle import (
    claim_check,
    complete_check_failed,
    complete_check_passed,
    create_pending_check,
    recover_stale_running_checks,
)
from backend.pipeline.capability.capability_identity import (
    compute_check_expiry,
    compute_runtime_config_fingerprint,
)
from backend.pipeline.capability.capability_probe import (
    CapabilityProbeResult,
    probe_embedding_capability,
)
from backend.pipeline.capability.capability_repository import (
    resolve_or_create_binding,
)
from backend.pipeline.capability.capability_resolution import classify_resolution
from backend.pipeline.capability.contracts import (
    CheckAlreadyClaimed,
    CheckAlreadyTerminal,
    FailedCheckEvidence,
    PassedCheckObservations,
    STATUS_PASSED,
    STATUS_FAILED,
)
from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapter
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckPublication:
    """Public contract returned by ``run_capability_check``.

    On pass: ``binding_id`` is populated, ``status`` is 'passed'.
    On fail: ``binding_id`` is None, ``status`` is 'failed'.
    """

    check_id: str
    binding_id: str | None
    status: str
    expires_at: datetime | None
    failure_code: str | None


async def run_capability_check(
    session_factory: sessionmaker,
    adapter: GovernedEmbeddingAdapter,
    effective_config: EffectiveEmbeddingConfiguration,
    *,
    check_ttl_seconds: int = 3600,
    lease_ttl_seconds: int = 120,
) -> CheckPublication:
    """Run a full capability check lifecycle.

    Check-first sequence: the pending check is created BEFORE the probe.
    The binding is resolved ONLY after the probe passes.

    Returns a ``CheckPublication``. The check always reaches a terminal
    state (passed or failed) — never left in pending/running.
    """
    # 1. Compute fingerprint
    fingerprint = compute_runtime_config_fingerprint(effective_config)

    # 2. Recover stale checks
    recover_stale_running_checks(session_factory)

    # 3. Create pending check (binding_id = NULL)
    with session_factory() as session:
        check_id = create_pending_check(
            session,
            embedding_profile_id=effective_config.embedding_profile_id,
            runtime_config_fingerprint=fingerprint,
        )
        session.commit()

    # 4. Claim (atomic)
    try:
        claim_check(session_factory, check_id, lease_ttl_seconds=lease_ttl_seconds)
    except CheckAlreadyClaimed:
        # Should not happen — we just created it
        logger.error("freshly-created check was already claimed: %s...", check_id[:16])
        raise

    # 5. Probe
    probe_result = await probe_embedding_capability(
        adapter, expected_dimension=effective_config.expected_dimension
    )

    # 6. Publish result
    if probe_result.passed:
        return _publish_passed(
            session_factory,
            check_id,
            probe_result,
            effective_config,
            check_ttl_seconds,
        )
    else:
        return _publish_failed(
            session_factory,
            check_id,
            probe_result,
        )


def _publish_passed(
    session_factory: sessionmaker,
    check_id: str,
    probe: CapabilityProbeResult,
    effective_config: EffectiveEmbeddingConfiguration,
    check_ttl_seconds: int,
) -> CheckPublication:
    """Resolve binding and publish a passed check."""
    now = datetime.now(timezone.utc)
    expires_at = compute_check_expiry(now, check_ttl_seconds)

    # Classify resolution from probe evidence
    decision = classify_resolution(
        effective_config,
        probe.document_evidence,  # type: ignore[arg-type]
        probe.query_evidence,  # type: ignore[arg-type]
        probe.observed_document_dimension,  # type: ignore[arg-type]
        probe.observed_query_dimension,  # type: ignore[arg-type]
    )

    # Resolve or create binding (idempotent)
    with session_factory() as session:
        binding_id = resolve_or_create_binding(session, decision)
        session.commit()

    # Build observations
    observations = PassedCheckObservations(
        observed_document_dimension=probe.observed_document_dimension,  # type: ignore[arg-type]
        observed_query_dimension=probe.observed_query_dimension,  # type: ignore[arg-type]
        observed_document_norm_min=probe.observed_document_norm_min,  # type: ignore[arg-type]
        observed_document_norm_max=probe.observed_document_norm_max,  # type: ignore[arg-type]
        observed_query_norm=probe.observed_query_norm,  # type: ignore[arg-type]
        observed_document_reported_model=probe.document_evidence.reported_model if probe.document_evidence else None,
        observed_query_reported_model=probe.query_evidence.reported_model if probe.query_evidence else None,
        observed_document_provider_revision=probe.document_evidence.provider_revision if probe.document_evidence else None,
        observed_query_provider_revision=probe.query_evidence.provider_revision if probe.query_evidence else None,
        observed_document_evidence_source=probe.document_evidence.evidence_source if probe.document_evidence else "configured_only",
        observed_query_evidence_source=probe.query_evidence.evidence_source if probe.query_evidence else "configured_only",
    )

    complete_check_passed(
        session_factory,
        check_id,
        binding_id=binding_id,
        observations=observations,
        expires_at=expires_at,
    )

    logger.info(
        "capability check published (passed): check=%s... binding=%s... expires_at=%s",
        check_id[:16],
        binding_id[:16],
        expires_at.isoformat(),
    )

    return CheckPublication(
        check_id=check_id,
        binding_id=binding_id,
        status=STATUS_PASSED,
        expires_at=expires_at,
        failure_code=None,
    )


def _publish_failed(
    session_factory: sessionmaker,
    check_id: str,
    probe: CapabilityProbeResult,
) -> CheckPublication:
    """Publish a failed check. binding_id stays NULL."""
    failure = FailedCheckEvidence(
        failure_category=probe.failure_category or "unknown",
        failure_code=probe.failure_code or "unknown_failure",
        sanitized_error_detail=probe.sanitized_error_detail or "",
    )

    complete_check_failed(session_factory, check_id, failure=failure)

    logger.info(
        "capability check published (failed): check=%s... code=%s",
        check_id[:16],
        failure.failure_code,
    )

    return CheckPublication(
        check_id=check_id,
        binding_id=None,
        status=STATUS_FAILED,
        expires_at=None,
        failure_code=failure.failure_code,
    )
