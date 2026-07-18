"""Canonical governed embedding adapter (P0.4B0.3).

Consolidates the three byte-identical private ``_EmbeddingAdapter`` classes
that previously lived inline in:

  - backend/pipeline/stages.py:676          (IngestionStage._index_governed)
  - backend/pipeline/vector_runtime.py:99   (build_governed_vector_runtime_from_settings)
  - backend/cli/legacy_vector_cli.py:289    (_execute_reindex)

Per ``docs/p0_4_embedding_access_audit.md`` §3.5 and the P0.4B0 directive,
the canonical adapter:

  * propagates provider failures (no silent zero-vector fallback)
  * rejects invalid result counts
  * rejects invalid vectors
  * exposes effective configuration identity (provider_kind, requested_model,
    configured_dimension, normalization_policy, adapter_contract_version)
  * is still UNVERIFIED during B0 — its purpose is to expose one consistent
    surface for the later handshake. P0.4C will replace it with the
    verified-runtime capability service.

This module depends only on EmbeddingService's ``embed_texts`` interface,
so it can wrap any object exposing that method (the real
``EmbeddingService``, a fake, or B0.3+ adapters from other embedding
paths). It performs structural validation at the adapter boundary so the
governed path's downstream consumers (VectorIndexer, ScopedVectorService)
receive only well-formed vectors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Sequence

logger = logging.getLogger(__name__)


# Adapter contract version — bumped when the adapter's behavior or its
# validation rules change. Participates in the future capability binding
# fingerprint (P0.4A1) so a stale adapter under a new provider cannot
# silently re-use a binding forged under an older adapter contract.
GOVERNED_EMBEDDING_ADAPTER_CONTRACT_VERSION = "governed_embedding_adapter_v1"


class GovernedEmbeddingAdapterError(RuntimeError):
    """Raised when the adapter detects invalid provider output.

    Pre-B0, the LMStudio adapter returned zero vectors on failure and
    left it to the service layer to reject them (or, worse, silently
    propagated them). The canonical adapter performs fail-closed
    structural validation at its own boundary so misbehaving providers
    cannot leak malformed vectors downstream.
    """


@dataclass(frozen=True)
class GovernedEmbeddingAdapter:
    """One consistent adapter surface for governed embedding operations.

    P0.4B0.3 transitional contract. P0.4C will replace this with the
    verified-runtime capability service; the field set here is what
    later waves need to fingerprint effective configuration identity
    without yet performing a capability handshake.
    """

    embedding_service: Any
    provider_kind: str
    requested_model: str
    configured_dimension: int
    normalization_policy: str = "l2"
    adapter_contract_version: str = GOVERNED_EMBEDDING_ADAPTER_CONTRACT_VERSION

    async def embed_documents(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[float, ...], ...]:
        """Embed a batch of document texts.

        Delegates validation to the canonical
        ``backend.pipeline.knowledge.embedding_validation`` module so there
        is exactly one set of rejection rules in the codebase.
        """
        texts_list = list(texts)
        if not texts_list:
            return ()

        try:
            raw_results = await self.embedding_service.embed_texts(texts_list)
        except Exception as exc:
            raise GovernedEmbeddingAdapterError(
                f"embedding provider raised: {type(exc).__name__}: {exc}"
            ) from exc

        from backend.pipeline.knowledge.embedding_validation import (
            validate_document_embeddings,
            EmbeddingValidationError,
        )
        try:
            return validate_document_embeddings(
                raw_results,
                expected_count=len(texts_list),
                expected_dimension=self.configured_dimension,
            )
        except EmbeddingValidationError as exc:
            raise GovernedEmbeddingAdapterError(str(exc)) from exc

    async def embed_query(
        self,
        text: str,
    ) -> tuple[float, ...]:
        """Embed a single query text.

        Delegates validation to the canonical
        ``validate_query_embedding`` function.
        """
        try:
            raw_results = await self.embedding_service.embed_texts([text])
        except Exception as exc:
            raise GovernedEmbeddingAdapterError(
                f"embedding provider raised on query: {type(exc).__name__}: {exc}"
            ) from exc

        from backend.pipeline.knowledge.embedding_validation import (
            validate_query_embedding,
            EmbeddingValidationError,
        )
        try:
            return validate_query_embedding(
                raw_results[0] if raw_results else None,
                expected_dimension=self.configured_dimension,
            )
        except EmbeddingValidationError as exc:
            raise GovernedEmbeddingAdapterError(str(exc)) from exc

    async def embed_single(self, text: str) -> list[float]:
        """Backward-compatible single-text embed used by VectorIndexer.

        Returns a plain ``list[float]`` (not a tuple) so existing callers
        like ``vector_indexer.index_document`` continue to work without
        changes. Prefer ``embed_documents`` or ``embed_query`` for new
        code; B0.9's architectural seal will eventually require the
        role-named methods.
        """
        query_tuple = await self.embed_query(text)
        return list(query_tuple)

    async def embed_documents_with_evidence(
        self,
        texts: Sequence[str],
    ) -> tuple[tuple[tuple[float, ...], ...], Any]:
        """Document embed with identity evidence — same validation path.

        Exercises the SAME canonical validation + post-processing as
        ``embed_documents``, PLUS captures identity evidence from the
        underlying provider's ``embed_with_evidence`` response.

        Used by the capability probe (P0.4A1.4) so the check exercises
        the exact production adapter path rather than duplicating it.

        Returns ``(validated_vectors, identity_evidence)``.
        """
        texts_list = list(texts)
        if not texts_list:
            from backend.pipeline.knowledge.embedding_provider_identity import (
                ProviderModelIdentityEvidence,
            )
            return (), ProviderModelIdentityEvidence(
                provider_kind=self.provider_kind,
                requested_model=self.requested_model,
                evidence_source="configured_only",
            )

        try:
            batch = await self.embedding_service.embed_with_evidence(texts_list)
        except Exception as exc:
            raise GovernedEmbeddingAdapterError(
                f"embedding provider raised: {type(exc).__name__}: {exc}"
            ) from exc

        from backend.pipeline.knowledge.embedding_validation import (
            validate_document_embeddings,
            EmbeddingValidationError,
        )
        try:
            validated = validate_document_embeddings(
                list(batch.embeddings),
                expected_count=len(texts_list),
                expected_dimension=self.configured_dimension,
            )
        except EmbeddingValidationError as exc:
            raise GovernedEmbeddingAdapterError(str(exc)) from exc

        return validated, batch.identity_evidence

    async def embed_query_with_evidence(
        self,
        text: str,
    ) -> tuple[tuple[float, ...], Any]:
        """Query embed with identity evidence — same validation path.

        Query-path equivalent of ``embed_documents_with_evidence``.

        Returns ``(validated_vector, identity_evidence)``.
        """
        try:
            batch = await self.embedding_service.embed_with_evidence([text])
        except Exception as exc:
            raise GovernedEmbeddingAdapterError(
                f"embedding provider raised on query: {type(exc).__name__}: {exc}"
            ) from exc

        from backend.pipeline.knowledge.embedding_validation import (
            validate_query_embedding,
            EmbeddingValidationError,
        )
        try:
            validated = validate_query_embedding(
                batch.embeddings[0] if batch.embeddings else None,
                expected_dimension=self.configured_dimension,
            )
        except EmbeddingValidationError as exc:
            raise GovernedEmbeddingAdapterError(str(exc)) from exc

        return validated, batch.identity_evidence

    def _validate_single(
        self,
        vec: Any,
        *,
        role: str,
        index: int,
    ) -> tuple[float, ...]:
        """Deprecated: delegates to canonical embedding_validation.

        Retained for any callers that have not yet migrated to
        ``embed_documents`` / ``embed_query``. New code must use the
        role-named methods which call the canonical validator directly.
        """
        from backend.pipeline.knowledge.embedding_validation import (
            validate_embedding_vector,
            EmbeddingValidationError,
        )
        try:
            return validate_embedding_vector(
                vec, expected_dimension=self.configured_dimension, role=role,
            )
        except EmbeddingValidationError as exc:
            raise GovernedEmbeddingAdapterError(str(exc)) from exc
