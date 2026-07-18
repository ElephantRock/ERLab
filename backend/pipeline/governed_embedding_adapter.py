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
import math
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

        Validates:
          * result count equals input count (no silent drops)
          * each result is a non-empty sequence
          * each result matches the configured dimension
          * each element is numeric, non-bool, finite
          * no all-zero vectors

        Failures raise ``GovernedEmbeddingAdapterError`` rather than
        returning fabricated vectors.
        """
        texts_list = list(texts)
        if not texts_list:
            return ()

        try:
            raw_results = await self.embedding_service.embed_texts(texts_list)
        except Exception as exc:
            # Propagate provider failures honestly — the pre-B0
            # LMStudioEmbeddingProvider would silently substitute zero
            # vectors here; the canonical adapter never does.
            raise GovernedEmbeddingAdapterError(
                f"embedding provider raised: {type(exc).__name__}: {exc}"
            ) from exc

        if len(raw_results) != len(texts_list):
            raise GovernedEmbeddingAdapterError(
                f"embedding provider returned {len(raw_results)} vectors for "
                f"{len(texts_list)} inputs; result-count mismatch"
            )

        validated: list[tuple[float, ...]] = []
        for i, vec in enumerate(raw_results):
            validated.append(self._validate_single(vec, role="document", index=i))
        return tuple(validated)

    async def embed_query(
        self,
        text: str,
    ) -> tuple[float, ...]:
        """Embed a single query text.

        Same structural validation as ``embed_documents``; the role label
        is "query" so future role-aware validation can distinguish them.
        """
        try:
            raw_results = await self.embedding_service.embed_texts([text])
        except Exception as exc:
            raise GovernedEmbeddingAdapterError(
                f"embedding provider raised on query: {type(exc).__name__}: {exc}"
            ) from exc

        if not raw_results:
            raise GovernedEmbeddingAdapterError(
                "embedding provider returned empty result list for single query"
            )
        return self._validate_single(raw_results[0], role="query", index=0)

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

    def _validate_single(
        self,
        vec: Any,
        *,
        role: str,
        index: int,
    ) -> tuple[float, ...]:
        if vec is None:
            raise GovernedEmbeddingAdapterError(
                f"{role} vector at index {index} is None"
            )
        if isinstance(vec, (str, bytes)):
            raise GovernedEmbeddingAdapterError(
                f"{role} vector at index {index} is {type(vec).__name__}, not a sequence"
            )
        try:
            as_list = list(vec)
        except TypeError as exc:
            raise GovernedEmbeddingAdapterError(
                f"{role} vector at index {index} is not iterable: {exc}"
            ) from exc

        if not as_list:
            raise GovernedEmbeddingAdapterError(
                f"{role} vector at index {index} is empty"
            )
        if len(as_list) != self.configured_dimension:
            raise GovernedEmbeddingAdapterError(
                f"{role} vector at index {index} has dimension {len(as_list)}; "
                f"expected {self.configured_dimension}"
            )

        # Element-level checks: numeric, non-bool, finite. bool is a subclass
        # of int in Python, so the isinstance check must exclude it explicitly.
        validated_elements: list[float] = []
        for j, v in enumerate(as_list):
            if isinstance(v, bool):
                raise GovernedEmbeddingAdapterError(
                    f"{role} vector at index {index} element {j} is bool"
                )
            if not isinstance(v, (int, float)):
                raise GovernedEmbeddingAdapterError(
                    f"{role} vector at index {index} element {j} is "
                    f"{type(v).__name__}, not numeric"
                )
            f = float(v)
            if math.isnan(f) or math.isinf(f):
                raise GovernedEmbeddingAdapterError(
                    f"{role} vector at index {index} element {j} is non-finite: {f}"
                )
            validated_elements.append(f)

        # All-zero rejection (after normalization to floats). This is the
        # invariant the pre-B0 LMStudio adapter violated.
        if all(v == 0.0 for v in validated_elements):
            raise GovernedEmbeddingAdapterError(
                f"{role} vector at index {index} is all-zero"
            )

        return tuple(validated_elements)
