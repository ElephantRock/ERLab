"""Centralized embedding output validation primitives (P0.4B0 validation consolidation).

Extracted from the scattered validation implementations identified in
docs/p0_4_embedding_access_audit.md §3.10. Per directive:

  'GovernedEmbeddingAdapter now owns fail-closed validation, but the
   primitives should not remain embedded inside that class if the
   handshake, side channels, indexer, and query path will all need them.'

This module provides the canonical structural primitives that consumers
across the codebase should call. It is the single source of truth for:

  validate_document_embeddings(...)
  validate_query_embedding(...)
  validate_embedding_vector(...)
  compute_l2_norm(...)
  validate_l2_normalization(...)

Frozen rejection rules (directive):
  bool rejected
  nonnumeric rejected
  nonfinite rejected
  empty rejected
  all-zero rejected
  dimension mismatch rejected
  result-count mismatch rejected

CRITICAL directive constraint — DO NOT apply L2 normalization here:

  'Do not begin applying L2 normalization in this refactor. The current
   declarative/behavior mismatch should remain an explicit failure until
   versioned post-processing is implemented.'

This module therefore provides validation primitives only. It computes
norms and validates them but never mutates a vector. The handshake
contract (P0.4C+) will introduce the versioned post-processing path
that actually applies normalization; until then, a declared l2 policy
without runtime enforcement remains an explicit contract mismatch.
"""

from __future__ import annotations

import math
from typing import Any, Sequence


# ── Exception hierarchy ───────────────────────────────────────────────


class EmbeddingValidationError(ValueError):
    """Base for all embedding-output validation failures.

    Subclasses carry a frozen ``failure_code`` from a closed vocabulary
    so callers can route failures deterministically (governed path
    raises, side-channel logs and skips, etc.).
    """

    failure_code: str = "embedding_validation_failed"


class EmbeddingVectorNoneError(EmbeddingValidationError):
    failure_code = "embedding_vector_none"


class EmbeddingVectorTypeError(EmbeddingValidationError):
    failure_code = "embedding_vector_type_invalid"


class EmbeddingVectorEmptyError(EmbeddingValidationError):
    failure_code = "embedding_vector_empty"


class EmbeddingDimensionMismatchError(EmbeddingValidationError):
    failure_code = "embedding_dimension_mismatch"


class EmbeddingElementTypeError(EmbeddingValidationError):
    failure_code = "embedding_element_type_invalid"


class EmbeddingElementNonFiniteError(EmbeddingValidationError):
    failure_code = "embedding_element_non_finite"


class EmbeddingZeroVectorError(EmbeddingValidationError):
    failure_code = "embedding_zero_vector"


class EmbeddingResultCountMismatchError(EmbeddingValidationError):
    failure_code = "embedding_result_count_mismatch"


class EmbeddingNormalizationMismatchError(EmbeddingValidationError):
    failure_code = "embedding_normalization_mismatch"


# ── Norm helpers ──────────────────────────────────────────────────────


def compute_l2_norm(vector: Sequence[float]) -> float:
    """Compute the L2 (Euclidean) norm of a vector.

    Pure: no validation, no mutation. Returns 0.0 for an empty sequence.
    Callers that need validated input should call ``validate_embedding_vector``
    first.
    """
    return math.sqrt(sum(float(v) * float(v) for v in vector))


# Default tolerance for L2 normalization validation. The directive notes
# that "Record the tolerance in the post-processing contract version" —
# the handshake contract (P0.4C+) will pin this. For B0 we expose the
# constant so consumers can reference a single value.
DEFAULT_L2_NORMALIZATION_TOLERANCE = 1e-6


def validate_l2_normalization(
    vector: Sequence[float],
    *,
    tolerance: float = DEFAULT_L2_NORMALIZATION_TOLERANCE,
) -> None:
    """Validate that a vector is L2-normalized (norm ~= 1.0 within tolerance).

    Raises EmbeddingNormalizationMismatchError if the norm deviates from
    1.0 by more than ``tolerance``. Does NOT normalize the vector — per
    directive, normalization is the versioned post-processing path's
    job, not this module's.

    Empty vectors and zero-norm vectors both fail (norm 0.0 != 1.0).
    """
    norm = compute_l2_norm(vector)
    if abs(norm - 1.0) > tolerance:
        raise EmbeddingNormalizationMismatchError(
            f"L2 norm {norm!r} deviates from 1.0 by more than tolerance "
            f"{tolerance!r}; vector is not L2-normalized"
        )


# ── Single-vector validation ──────────────────────────────────────────


def validate_embedding_vector(
    vector: Any,
    *,
    expected_dimension: int | None = None,
    role: str = "embedding",
) -> tuple[float, ...]:
    """Validate one embedding vector and return it as a tuple of floats.

    Frozen rejection rules (directive):
      None           -> EmbeddingVectorNoneError
      str/bytes      -> EmbeddingVectorTypeError
      non-iterable   -> EmbeddingVectorTypeError
      empty          -> EmbeddingVectorEmptyError
      dim mismatch   -> EmbeddingDimensionMismatchError (when expected_dimension given)
      bool element   -> EmbeddingElementTypeError (bool is a subclass of int; exclude explicitly)
      non-numeric    -> EmbeddingElementTypeError
      NaN/Inf        -> EmbeddingElementNonFiniteError
      all-zero       -> EmbeddingZeroVectorError

    Args:
        vector: the candidate vector (any shape).
        expected_dimension: if provided, validate len == expected_dimension.
            If None, dimension is not checked.
        role: short label included in error messages ("document",
            "query", "cache_key", etc.) for actionable diagnostics.

    Returns:
        tuple[float, ...]: the validated vector, normalized to floats.
        Tuple (not list) communicates immutability.
    """
    if vector is None:
        raise EmbeddingVectorNoneError(f"{role} vector is None")
    if isinstance(vector, (str, bytes)):
        raise EmbeddingVectorTypeError(
            f"{role} vector is {type(vector).__name__}, not a numeric sequence"
        )
    try:
        as_list = list(vector)
    except TypeError as exc:
        raise EmbeddingVectorTypeError(
            f"{role} vector is not iterable: {exc}"
        ) from exc

    if not as_list:
        raise EmbeddingVectorEmptyError(f"{role} vector is empty")

    if expected_dimension is not None and len(as_list) != expected_dimension:
        raise EmbeddingDimensionMismatchError(
            f"{role} vector has dimension {len(as_list)}; expected "
            f"{expected_dimension}"
        )

    validated: list[float] = []
    for i, v in enumerate(as_list):
        # bool is a subclass of int in Python; exclude explicitly per directive.
        if isinstance(v, bool):
            raise EmbeddingElementTypeError(
                f"{role} vector element {i} is bool"
            )
        if not isinstance(v, (int, float)):
            raise EmbeddingElementTypeError(
                f"{role} vector element {i} is {type(v).__name__}, not numeric"
            )
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            raise EmbeddingElementNonFiniteError(
                f"{role} vector element {i} is non-finite: {f}"
            )
        validated.append(f)

    if all(v == 0.0 for v in validated):
        raise EmbeddingZeroVectorError(f"{role} vector is all-zero")

    return tuple(validated)


# ── Batch / role-aware validation ─────────────────────────────────────


def validate_document_embeddings(
    embeddings: Any,
    expected_count: int,
    *,
    expected_dimension: int | None = None,
) -> tuple[tuple[float, ...], ...]:
    """Validate a batch of document embeddings.

    Frozen rejection rules:
      all single-vector rules (per vector)
      result-count mismatch  -> EmbeddingResultCountMismatchError
                                 (len(embeddings) != expected_count)

    Args:
        embeddings: the candidate batch.
        expected_count: required number of vectors (typically len(input texts)).
        expected_dimension: if provided, every vector's dimension must match.

    Returns:
        tuple[tuple[float, ...], ...]: the validated batch.
    """
    try:
        as_list = list(embeddings)
    except TypeError as exc:
        raise EmbeddingVectorTypeError(
            f"document embeddings batch is not iterable: {exc}"
        ) from exc

    if len(as_list) != expected_count:
        raise EmbeddingResultCountMismatchError(
            f"document embeddings batch has {len(as_list)} vectors; expected "
            f"{expected_count}"
        )

    return tuple(
        validate_embedding_vector(
            v, expected_dimension=expected_dimension, role="document"
        )
        for v in as_list
    )


def validate_query_embedding(
    embedding: Any,
    *,
    expected_dimension: int | None = None,
) -> tuple[float, ...]:
    """Validate a single query embedding.

    Same structural rules as ``validate_embedding_vector`` but with the
    role label fixed to "query" so error messages are unambiguous. Kept
    as a distinct function so role-aware consumers (governed adapter,
    scoped retrieval, future verified runtime) can express intent in
    their call sites.
    """
    return validate_embedding_vector(
        embedding, expected_dimension=expected_dimension, role="query"
    )
