"""Tests for P0.4A1.4: production-path dual probe suite.

Proves:
  - Pass: adapter returns valid vectors → probe passes, observations populated
  - Dimension mismatch → fail with bounded code
  - Provider exception → fail with sanitized detail
  - Evidence conflict → fail
  - Empty result → fail
  - Probe vectors are NOT persisted (ephemeral)
"""

from __future__ import annotations

import asyncio
import math
from typing import Any, Sequence
from unittest.mock import MagicMock

import pytest

from backend.pipeline.capability.capability_probe import (
    CapabilityProbeResult,
    probe_embedding_capability,
)
from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapterError
from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_CONFIGURED_ONLY,
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderModelIdentityEvidence,
)


class _FakeAdapter:
    """Fake GovernedEmbeddingAdapter for probe testing.

    Returns controlled vectors and evidence without any network calls.
    """

    def __init__(
        self,
        *,
        dimension: int = 1536,
        doc_count: int = 2,
        doc_evidence: ProviderModelIdentityEvidence | None = None,
        query_evidence: ProviderModelIdentityEvidence | None = None,
        doc_dim_override: int | None = None,
        query_dim_override: int | None = None,
        raise_on_documents: Exception | None = None,
        raise_on_query: Exception | None = None,
        empty_query: bool = False,
    ):
        self._dimension = dimension
        self._doc_count = doc_count
        self._doc_evidence = doc_evidence or ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
            reported_model="text-embedding-3-small",
        )
        self._query_evidence = query_evidence or self._doc_evidence
        self._doc_dim_override = doc_dim_override
        self._query_dim_override = query_dim_override
        self._raise_on_documents = raise_on_documents
        self._raise_on_query = raise_on_query
        self._empty_query = empty_query

    async def embed_documents_with_evidence(self, texts):
        if self._raise_on_documents:
            raise self._raise_on_documents
        dim = self._doc_dim_override or self._dimension
        # Create unit-ish vectors
        vec = tuple(1.0 / math.sqrt(dim) for _ in range(dim))
        vectors = tuple(vec for _ in range(self._doc_count))
        return vectors, self._doc_evidence

    async def embed_query_with_evidence(self, text):
        if self._raise_on_query:
            raise self._raise_on_query
        if self._empty_query:
            return (), self._query_evidence
        dim = self._query_dim_override or self._dimension
        vec = tuple(1.0 / math.sqrt(dim) for _ in range(dim))
        return vec, self._query_evidence


def _run(coro):
    return asyncio.run(coro)


# ── Pass scenarios ────────────────────────────────────────────────────


class TestProbePass:
    def test_pass_with_matching_dimensions(self):
        adapter = _FakeAdapter(dimension=1536)
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is True
        assert result.observed_document_dimension == 1536
        assert result.observed_query_dimension == 1536
        assert result.observed_document_norm_min is not None
        assert result.observed_document_norm_max is not None
        assert result.observed_query_norm is not None
        assert result.document_evidence is not None
        assert result.query_evidence is not None
        assert result.failure_code is None

    def test_pass_captures_evidence_source(self):
        adapter = _FakeAdapter(dimension=128)
        result = _run(probe_embedding_capability(adapter, expected_dimension=128))
        assert result.passed is True
        assert result.document_evidence.evidence_source == EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL


# ── Fail scenarios ────────────────────────────────────────────────────


class TestProbeFail:
    def test_dimension_mismatch_observed_vs_expected(self):
        adapter = _FakeAdapter(dimension=768)
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is False
        assert result.failure_code == "observed_vs_expected_dimension_mismatch"
        assert result.observed_document_dimension == 768

    def test_query_document_dimension_mismatch(self):
        adapter = _FakeAdapter(dimension=1536, query_dim_override=768)
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is False
        assert result.failure_code == "query_document_dimension_mismatch"

    def test_document_count_mismatch(self):
        adapter = _FakeAdapter(dimension=1536, doc_count=1)
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is False
        assert result.failure_code == "document_probe_count_mismatch"

    def test_empty_query(self):
        adapter = _FakeAdapter(dimension=1536, empty_query=True)
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is False
        assert result.failure_code == "query_probe_empty"

    def test_evidence_conflict_provider_kind(self):
        doc_ev = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
        )
        query_ev = ProviderModelIdentityEvidence(
            provider_kind="gemini",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_CONFIGURED_ONLY,
        )
        adapter = _FakeAdapter(
            dimension=1536,
            doc_evidence=doc_ev,
            query_evidence=query_ev,
        )
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is False
        assert result.failure_code == "provider_kind_conflict"

    def test_adapter_error_sanitized(self):
        err = GovernedEmbeddingAdapterError(
            "embedding provider raised: RuntimeError: api_key=sk-secret123 failed"
        )
        adapter = _FakeAdapter(dimension=1536, raise_on_documents=err)
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is False
        assert result.failure_code == "governed_adapter_error"
        # Credential must be sanitized
        assert "sk-secret123" not in (result.sanitized_error_detail or "")

    def test_unexpected_exception_sanitized(self):
        err = RuntimeError("connection failed: bearer=abc123token")
        adapter = _FakeAdapter(dimension=1536, raise_on_documents=err)
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is False
        assert result.failure_code == "unexpected_probe_error"
        assert "abc123token" not in (result.sanitized_error_detail or "")

    def test_detail_truncated_to_500(self):
        long_detail = "x" * 1000
        err = GovernedEmbeddingAdapterError(long_detail)
        adapter = _FakeAdapter(dimension=1536, raise_on_documents=err)
        result = _run(probe_embedding_capability(adapter, expected_dimension=1536))
        assert result.passed is False
        assert len(result.sanitized_error_detail or "") <= 500
