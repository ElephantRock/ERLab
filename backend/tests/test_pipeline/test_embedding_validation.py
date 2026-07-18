"""Tests for the centralized embedding validation primitives.

Per directive P0.4B0 (validation consolidation), this module is the
single source of truth for embedding-output validation. Tests cover
every frozen rejection rule plus the no-L2-application invariant.
"""

from __future__ import annotations

import math

import pytest

from backend.pipeline.knowledge.embedding_validation import (
    DEFAULT_L2_NORMALIZATION_TOLERANCE,
    EmbeddingDimensionMismatchError,
    EmbeddingElementNonFiniteError,
    EmbeddingElementTypeError,
    EmbeddingNormalizationMismatchError,
    EmbeddingResultCountMismatchError,
    EmbeddingValidationError,
    EmbeddingVectorEmptyError,
    EmbeddingVectorNoneError,
    EmbeddingVectorTypeError,
    EmbeddingZeroVectorError,
    compute_l2_norm,
    validate_document_embeddings,
    validate_embedding_vector,
    validate_l2_normalization,
    validate_query_embedding,
)


# ── compute_l2_norm ──────────────────────────────────────────────────


class TestComputeL2Norm:
    def test_unit_vector(self):
        assert compute_l2_norm([1.0, 0.0, 0.0]) == 1.0
        assert compute_l2_norm([0.0, 1.0]) == 1.0

    def test_known_vector(self):
        # 3-4-5 triangle
        assert compute_l2_norm([3.0, 4.0]) == 5.0

    def test_empty_vector_returns_zero(self):
        assert compute_l2_norm([]) == 0.0

    def test_all_zero_vector_returns_zero(self):
        assert compute_l2_norm([0.0, 0.0, 0.0]) == 0.0

    def test_accepts_int_elements(self):
        # ints are accepted (cast to float)
        assert compute_l2_norm([3, 4]) == 5.0

    def test_is_pure_does_not_mutate_input(self):
        v = [0.1, 0.2, 0.3]
        original = list(v)
        compute_l2_norm(v)
        assert v == original


# ── validate_l2_normalization ────────────────────────────────────────


class TestValidateL2Normalization:
    def test_unit_vector_passes(self):
        # Should not raise
        validate_l2_normalization([1.0, 0.0, 0.0])
        validate_l2_normalization([0.6, 0.8])

    def test_non_unit_vector_raises(self):
        with pytest.raises(EmbeddingNormalizationMismatchError) as excinfo:
            validate_l2_normalization([2.0, 0.0])
        assert "deviates from 1.0" in str(excinfo.value)

    def test_zero_vector_raises(self):
        with pytest.raises(EmbeddingNormalizationMismatchError):
            validate_l2_normalization([0.0, 0.0, 0.0])

    def test_custom_tolerance(self):
        # 0.999 is within 1e-2 but outside 1e-6
        validate_l2_normalization([0.999, 0.0], tolerance=1e-2)
        with pytest.raises(EmbeddingNormalizationMismatchError):
            validate_l2_normalization([0.999, 0.0], tolerance=1e-6)

    def test_default_tolerance_is_exposed_constant(self):
        # Sanity: the module exposes the tolerance constant
        assert DEFAULT_L2_NORMALIZATION_TOLERANCE > 0
        assert DEFAULT_L2_NORMALIZATION_TOLERANCE < 0.1


# ── validate_embedding_vector — frozen rejection rules ───────────────


class TestValidateEmbeddingVectorRejections:
    def test_none_rejected(self):
        with pytest.raises(EmbeddingVectorNoneError):
            validate_embedding_vector(None)

    def test_str_rejected(self):
        with pytest.raises(EmbeddingVectorTypeError):
            validate_embedding_vector("not a vector")

    def test_bytes_rejected(self):
        with pytest.raises(EmbeddingVectorTypeError):
            validate_embedding_vector(b"not a vector")

    def test_non_iterable_rejected(self):
        with pytest.raises(EmbeddingVectorTypeError):
            validate_embedding_vector(42)

    def test_empty_rejected(self):
        with pytest.raises(EmbeddingVectorEmptyError):
            validate_embedding_vector([])

    def test_dimension_mismatch_rejected(self):
        with pytest.raises(EmbeddingDimensionMismatchError) as excinfo:
            validate_embedding_vector([0.1, 0.2], expected_dimension=3)
        assert "dimension 2" in str(excinfo.value)
        assert "expected 3" in str(excinfo.value)

    def test_dimension_check_skipped_when_none(self):
        # Should not raise — any non-empty dimension is accepted
        validate_embedding_vector([0.1])
        validate_embedding_vector([0.1] * 768)

    def test_bool_element_rejected(self):
        # bool is a subclass of int; must exclude explicitly per directive
        with pytest.raises(EmbeddingElementTypeError) as excinfo:
            validate_embedding_vector([0.1, True, 0.3])
        assert "element 1 is bool" in str(excinfo.value)

    def test_string_element_rejected(self):
        with pytest.raises(EmbeddingElementTypeError) as excinfo:
            validate_embedding_vector([0.1, "oops", 0.3])
        assert "element 1 is str" in str(excinfo.value)
        assert "not numeric" in str(excinfo.value)

    def test_none_element_rejected(self):
        with pytest.raises(EmbeddingElementTypeError):
            validate_embedding_vector([0.1, None, 0.3])

    def test_nan_rejected(self):
        with pytest.raises(EmbeddingElementNonFiniteError) as excinfo:
            validate_embedding_vector([0.1, float("nan"), 0.3])
        assert "non-finite" in str(excinfo.value)

    def test_inf_rejected(self):
        with pytest.raises(EmbeddingElementNonFiniteError):
            validate_embedding_vector([0.1, float("inf"), 0.3])

    def test_negative_inf_rejected(self):
        with pytest.raises(EmbeddingElementNonFiniteError):
            validate_embedding_vector([0.1, float("-inf"), 0.3])

    def test_all_zero_vector_rejected(self):
        with pytest.raises(EmbeddingZeroVectorError):
            validate_embedding_vector([0.0, 0.0, 0.0])

    def test_happy_path_returns_tuple_of_floats(self):
        result = validate_embedding_vector([1, 2, 3])
        assert isinstance(result, tuple)
        assert result == (1.0, 2.0, 3.0)
        assert all(isinstance(x, float) for x in result)

    def test_role_label_appears_in_error_messages(self):
        with pytest.raises(EmbeddingZeroVectorError) as excinfo:
            validate_embedding_vector([0.0], role="document")
        assert "document" in str(excinfo.value)

        with pytest.raises(EmbeddingZeroVectorError) as excinfo:
            validate_embedding_vector([0.0], role="query")
        assert "query" in str(excinfo.value)


# ── validate_document_embeddings (batch) ─────────────────────────────


class TestValidateDocumentEmbeddings:
    def test_happy_path(self):
        batch = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        result = validate_document_embeddings(batch, expected_count=3)
        assert result == ((0.1, 0.2), (0.3, 0.4), (0.5, 0.6))

    def test_result_count_mismatch_rejected(self):
        with pytest.raises(EmbeddingResultCountMismatchError) as excinfo:
            validate_document_embeddings([[0.1, 0.2]], expected_count=3)
        assert "1 vectors" in str(excinfo.value)
        assert "expected 3" in str(excinfo.value)

    def test_per_vector_validation_applies(self):
        # One vector in the batch has wrong dimension
        with pytest.raises(EmbeddingDimensionMismatchError):
            validate_document_embeddings(
                [[0.1, 0.2], [0.3]], expected_count=2, expected_dimension=2,
            )

    def test_per_vector_zero_vector_rejected(self):
        with pytest.raises(EmbeddingZeroVectorError):
            validate_document_embeddings(
                [[0.1, 0.2], [0.0, 0.0]], expected_count=2,
            )

    def test_returns_tuples(self):
        result = validate_document_embeddings([[0.1]], expected_count=1)
        assert isinstance(result, tuple)
        assert isinstance(result[0], tuple)


# ── validate_query_embedding ─────────────────────────────────────────


class TestValidateQueryEmbedding:
    def test_happy_path(self):
        result = validate_query_embedding([0.5, 0.5])
        assert result == (0.5, 0.5)

    def test_role_label_is_query(self):
        with pytest.raises(EmbeddingZeroVectorError) as excinfo:
            validate_query_embedding([0.0])
        # Role label fixed to 'query'
        assert "query" in str(excinfo.value)

    def test_dimension_check_supported(self):
        with pytest.raises(EmbeddingDimensionMismatchError):
            validate_query_embedding([0.1, 0.2], expected_dimension=3)


# ── No-L2-application invariant ──────────────────────────────────────


class TestNoL2Application:
    """The directive: 'Do not begin applying L2 normalization in this
    refactor. The current declarative/behavior mismatch should remain an
    explicit failure until versioned post-processing is implemented.'

    This module must provide validation primitives only — never a function
    that mutates a vector by normalizing it. This test class enforces
    that invariant by introspecting the module's public surface.
    """

    def test_module_exposes_no_normalization_application_function(self):
        import backend.pipeline.knowledge.embedding_validation as mod

        # Forbidden names — any of these would signal silent L2 application
        forbidden = (
            "apply_l2_normalization",
            "l2_normalize",
            "normalize",
            "normalize_vector",
            "normalize_embeddings",
        )
        for name in forbidden:
            assert not hasattr(mod, name), (
                f"embedding_validation must not expose {name!r} — that would "
                f"silently begin L2 application, which is reserved for the "
                f"versioned post-processing path (P0.4C+)"
            )

    def test_validate_embedding_vector_does_not_mutate_input(self):
        # Critical: validation must not change the input vector's values.
        # (A common bug would be to normalize in place "to be helpful".)
        original = [3.0, 4.0]  # not normalized; norm = 5.0
        validate_embedding_vector(original)
        assert original == [3.0, 4.0]  # unchanged

    def test_validate_document_embeddings_does_not_normalize(self):
        original = [[3.0, 4.0], [0.0, 5.0]]  # both non-normalized
        validate_document_embeddings(original, expected_count=2)
        assert original == [[3.0, 4.0], [0.0, 5.0]]


# ── Exception hierarchy sanity ───────────────────────────────────────


class TestExceptionHierarchy:
    def test_all_validation_errors_inherit_from_base(self):
        for exc_class in (
            EmbeddingVectorNoneError,
            EmbeddingVectorTypeError,
            EmbeddingVectorEmptyError,
            EmbeddingDimensionMismatchError,
            EmbeddingElementTypeError,
            EmbeddingElementNonFiniteError,
            EmbeddingZeroVectorError,
            EmbeddingResultCountMismatchError,
            EmbeddingNormalizationMismatchError,
        ):
            assert issubclass(exc_class, EmbeddingValidationError)

    def test_each_error_has_frozen_failure_code(self):
        # Every concrete subclass must override failure_code (not inherit base)
        for exc_class in (
            EmbeddingVectorNoneError,
            EmbeddingVectorTypeError,
            EmbeddingVectorEmptyError,
            EmbeddingDimensionMismatchError,
            EmbeddingElementTypeError,
            EmbeddingElementNonFiniteError,
            EmbeddingZeroVectorError,
            EmbeddingResultCountMismatchError,
            EmbeddingNormalizationMismatchError,
        ):
            assert exc_class.failure_code != "embedding_validation_failed", (
                f"{exc_class.__name__} must override failure_code"
            )
            # failure_code is a class attribute, not instance state
            assert isinstance(exc_class.failure_code, str)
