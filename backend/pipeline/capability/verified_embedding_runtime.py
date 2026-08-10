"""Encapsulated VerifiedEmbeddingRuntime (P0.4A1.6).

A bounded in-process authorization token for embedding operations.
The runtime is NOT a dataclass — it encapsulates its adapter behind
private fields and enforces per-operation validity:

  - check not expired (now < check_expires_at)
  - latest authoritative check is still passed (not overridden by
    a newer failure)
  - runtime fingerprint unchanged
  - binding/profile agreement intact

No public adapter access. Callers MUST go through embed_documents /
embed_query, which validate authority before delegating.

Required zero count after A1.6:
  governed callers accessing raw GovernedEmbeddingAdapter directly = 0

The verified runtime does NOT certify historical vectors. Existing
vector records remain pre_capability_v0 under the P0.3 contract.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import sessionmaker

from backend.pipeline.capability.capability_drift import (
    current_fingerprint_matches,
    get_latest_completed_check,
    is_check_current,
)
from backend.pipeline.capability.capability_errors import (
    CAPABILITY_AUTHORITY_REVOKED_AT_USE,
    CAPABILITY_BINDING_MISMATCH,
    CAPABILITY_CHECK_EXPIRED,
    CAPABILITY_CHECK_FAILED,
    CAPABILITY_CHECK_NOT_FOUND,
    CAPABILITY_RUNTIME_DRIFT,
    CapabilityAuthorizationError,
)
from backend.pipeline.capability.contracts import (
    STATUS_ABANDONED,
    STATUS_CANCELLED,
    STATUS_FAILED,
    STATUS_PASSED,
)
from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapter
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)
from backend.pipeline.vector_contracts import EMBEDDING_PROBE_SUITE_V1

logger = logging.getLogger(__name__)


# ── Authorized embedding receipts (P0.4A2.2) ─────────────────────────


@dataclass(frozen=True)
class AuthorizedEmbeddingBatch:
    """Document embedding batch with immutable authorization evidence.

    Returned by ``embed_documents_authorized``. Persistent production
    callers MUST use receipt-returning methods so the authorization
    evidence is bound to the result.
    """

    embeddings: tuple[tuple[float, ...], ...]
    capability_binding_id: str
    capability_check_id: str
    runtime_config_fingerprint: str
    authorized_at: datetime


@dataclass(frozen=True)
class AuthorizedQueryEmbedding:
    """Query embedding with immutable authorization evidence.

    Returned by ``embed_query_authorized``.
    """

    embedding: tuple[float, ...]
    capability_binding_id: str
    capability_check_id: str
    runtime_config_fingerprint: str
    authorized_at: datetime


class VerifiedEmbeddingRuntime:
    """Encapsulated authorization token for embedding operations.

    Every operation re-validates:
      - check not expired (now < check_expires_at)
      - runtime fingerprint unchanged
      - latest authoritative check still passed
      - binding/profile agreement intact

    No public adapter access — ``hasattr(verified, 'embedding_adapter')``
    is False. Callers MUST go through ``embed_documents`` / ``embed_query``.
    """

    def __init__(
        self,
        *,
        embedding_adapter: GovernedEmbeddingAdapter,
        effective_embedding_config: EffectiveEmbeddingConfiguration,
        capability_binding_id: str,
        capability_check_id: str,
        check_expires_at: datetime,
        runtime_config_fingerprint: str,
        session_factory: sessionmaker,
    ):
        self._embedding_adapter = embedding_adapter
        self._effective_embedding_config = effective_embedding_config
        self._capability_binding_id = capability_binding_id
        self._capability_check_id = capability_check_id
        self._check_expires_at = check_expires_at
        self._runtime_config_fingerprint = runtime_config_fingerprint
        self._session_factory = session_factory

    # ── Public operations (enforce authority before delegating) ──

    async def embed_documents(
        self, texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        """Embed a batch of document texts.

        Validates authority before delegating to the adapter.
        """
        self._validate_authority()
        return await self._embedding_adapter.embed_documents(texts)

    async def embed_query(self, text: str) -> tuple[float, ...]:
        """Embed a single query text.

        Validates authority before delegating to the adapter.
        """
        self._validate_authority()
        return await self._embedding_adapter.embed_query(text)

    # ── Receipt-returning methods (P0.4A2.2) ──────────────────────
    #
    # Persistent production callers MUST use these methods so the
    # authorization evidence is bound to the result.

    async def embed_documents_authorized(
        self, texts: Sequence[str],
    ) -> AuthorizedEmbeddingBatch:
        """Embed documents and return vectors with authorization evidence.

        Validates authority, performs the embedding, and returns an
        immutable receipt with the exact check and binding that
        authorized the operation.

        No public adapter access is introduced.
        """
        self._validate_authority()
        embeddings = await self._embedding_adapter.embed_documents(texts)
        return AuthorizedEmbeddingBatch(
            embeddings=embeddings,
            capability_binding_id=self._capability_binding_id,
            capability_check_id=self._capability_check_id,
            runtime_config_fingerprint=self._runtime_config_fingerprint,
            authorized_at=datetime.now(UTC),
        )

    async def embed_query_authorized(
        self, text: str,
    ) -> AuthorizedQueryEmbedding:
        """Embed a query and return the vector with authorization evidence.

        Validates authority, performs the embedding, and returns an
        immutable receipt with the exact check and binding that
        authorized the operation.
        """
        self._validate_authority()
        embedding = await self._embedding_adapter.embed_query(text)
        return AuthorizedQueryEmbedding(
            embedding=embedding,
            capability_binding_id=self._capability_binding_id,
            capability_check_id=self._capability_check_id,
            runtime_config_fingerprint=self._runtime_config_fingerprint,
            authorized_at=datetime.now(UTC),
        )

    # ── Read-only accessors (no adapter) ──

    @property
    def capability_binding_id(self) -> str:
        return self._capability_binding_id

    @property
    def capability_check_id(self) -> str:
        return self._capability_check_id

    @property
    def check_expires_at(self) -> datetime:
        return self._check_expires_at

    @property
    def effective_embedding_config(self) -> EffectiveEmbeddingConfiguration:
        return self._effective_embedding_config

    # ── Authority validation ──

    def _validate_authority(self) -> None:
        """Raise CapabilityAuthorizationError if authority is invalid.

        Called before every embed_documents / embed_query call.
        """
        now = datetime.now(UTC)

        # 1. Check not expired (derived, not stored)
        expires = self._check_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if now >= expires:
            raise CapabilityAuthorizationError(
                CAPABILITY_CHECK_EXPIRED,
                f"check {self._capability_check_id[:16]}... expired at "
                f"{expires.isoformat()}",
            )

        # 2. Runtime fingerprint unchanged
        if not current_fingerprint_matches(
            self._effective_embedding_config, self._runtime_config_fingerprint
        ):
            raise CapabilityAuthorizationError(
                CAPABILITY_RUNTIME_DRIFT,
                "runtime configuration fingerprint changed since check was issued",
            )

        # 3. Latest authoritative check still passed
        with self._session_factory() as session:
            latest = get_latest_completed_check(
                session,
                embedding_profile_id=self._effective_embedding_config.embedding_profile_id,
                runtime_config_fingerprint=self._runtime_config_fingerprint,
                probe_suite_version=EMBEDDING_PROBE_SUITE_V1,
            )

            if latest is None:
                raise CapabilityAuthorizationError(
                    CAPABILITY_CHECK_NOT_FOUND,
                    "no completed check found for current runtime fingerprint",
                )

            if latest.check_status == STATUS_PASSED:
                # Verify it's our check or a newer pass
                if not is_check_current(latest, now):
                    raise CapabilityAuthorizationError(
                        CAPABILITY_AUTHORITY_REVOKED_AT_USE,
                        f"latest check {latest.check_id[:16]}... is expired",
                    )
                # Binding must match
                if latest.binding_id != self._capability_binding_id:
                    raise CapabilityAuthorizationError(
                        CAPABILITY_BINDING_MISMATCH,
                        f"latest check binding {latest.binding_id[:16] if latest.binding_id else 'NULL'}... "
                        f"!= runtime binding {self._capability_binding_id[:16]}...",
                    )
            elif latest.check_status in (STATUS_FAILED, STATUS_CANCELLED, STATUS_ABANDONED):
                raise CapabilityAuthorizationError(
                    CAPABILITY_CHECK_FAILED,
                    f"latest check {latest.check_id[:16]}... is {latest.check_status}",
                )


def build_verified_embedding_runtime(
    *,
    embedding_adapter: GovernedEmbeddingAdapter,
    effective_config: EffectiveEmbeddingConfiguration,
    session_factory: sessionmaker,
) -> VerifiedEmbeddingRuntime:
    """Construct a VerifiedEmbeddingRuntime from the current configuration.

    Authority rule (fail-closed):
      - Compute current fingerprint
      - Load latest COMPLETED check (not latest passed)
      - If passed AND current AND dual_probe AND binding_id NOT NULL → build
      - If failed/cancelled/abandoned → deny
      - If no check → deny

    Raises CapabilityAuthorizationError on any failure.
    """
    from backend.pipeline.capability.capability_identity import (
        compute_runtime_config_fingerprint,
    )

    fingerprint = compute_runtime_config_fingerprint(effective_config)

    with session_factory() as session:
        latest = get_latest_completed_check(
            session,
            embedding_profile_id=effective_config.embedding_profile_id,
            runtime_config_fingerprint=fingerprint,
            probe_suite_version=EMBEDDING_PROBE_SUITE_V1,
        )

        if latest is None:
            raise CapabilityAuthorizationError(
                CAPABILITY_CHECK_NOT_FOUND,
                "no completed capability check for current runtime fingerprint",
            )

        if latest.check_status == STATUS_PASSED:
            if not is_check_current(latest):
                raise CapabilityAuthorizationError(
                    CAPABILITY_CHECK_EXPIRED,
                    f"latest passed check {latest.check_id[:16]}... has expired",
                )
            if latest.binding_id is None:
                raise CapabilityAuthorizationError(
                    CAPABILITY_BINDING_MISMATCH,
                    f"passed check {latest.check_id[:16]}... has no binding",
                )
            if latest.probe_kind != "dual_probe":
                raise CapabilityAuthorizationError(
                    CAPABILITY_CHECK_FAILED,
                    f"check {latest.check_id[:16]}... is {latest.probe_kind}, "
                    f"not dual_probe",
                )

            return VerifiedEmbeddingRuntime(
                embedding_adapter=embedding_adapter,
                effective_embedding_config=effective_config,
                capability_binding_id=latest.binding_id,
                capability_check_id=latest.check_id,
                check_expires_at=latest.expires_at,  # type: ignore[arg-type]
                runtime_config_fingerprint=fingerprint,
                session_factory=session_factory,
            )

        # failed / cancelled / abandoned
        raise CapabilityAuthorizationError(
            CAPABILITY_CHECK_FAILED,
            f"latest check {latest.check_id[:16]}... is {latest.check_status}",
        )
