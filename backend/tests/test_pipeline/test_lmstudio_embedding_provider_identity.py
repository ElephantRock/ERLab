"""Tests for LMStudioEmbeddingProvider fail-closed repair + identity capture (P0.4B0.1e).

Per directive B0.1e:
  successful request       -> embeddings + resolved model evidence
  provider request failure -> explicit exception
                            -> zero fabricated vectors
  malformed output         -> explicit output-contract failure

This is the most important provider commit per the audit: the pre-B0
adapter silently caught every exception and substituted [0.0]*dimension
placeholder vectors, contradicting EmbeddingService's fail-closed contract.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_CONFIGURED_ONLY,
    EVIDENCE_SOURCE_LMSTUDIO_RESPONSE_MODEL,
    ProviderEmbeddingBatch,
)
from backend.pipeline.knowledge.embedding_providers import (
    LMStudioEmbeddingOutputError,
    LMStudioEmbeddingProvider,
)


def _mock_response(payload: dict, status: int = 200) -> MagicMock:
    r = MagicMock(name="httpx_response")
    r.status_code = status
    r.json.return_value = payload
    r.raise_for_status = MagicMock()
    if status >= 400:
        import httpx
        r.raise_for_status.side_effect = httpx.HTTPStatusError(
            "err", request=MagicMock(), response=r,
        )
    return r


def _embeddings_payload(
    n: int = 1, dim: int = 3, *, model: str | None = "text-embedding-bge-m3-embeddings",
) -> dict:
    """Build a well-formed LM Studio /v1/embeddings response payload."""
    return {
        "model": model,
        "data": [
            {"index": i, "embedding": [float(i + 1) * 0.1] * dim}
            for i in range(n)
        ],
    }


def _provider_with_client(client: Any, **kwargs) -> LMStudioEmbeddingProvider:
    p = LMStudioEmbeddingProvider(**kwargs)
    p._client = client
    return p


class TestFailClosedOnProviderFailure:
    """The core directive requirement: failures propagate, no fabricated zeros."""

    def test_http_error_propagates_no_zero_vectors(self):
        # Pre-B0 this silently returned [0.0, 0.0, 0.0] for the failed batch.
        # B0.1e: explicit exception, no fabricated vectors.
        client = MagicMock()
        client.post = AsyncMock(return_value=_mock_response({}, status=503))

        provider = _provider_with_client(
            client, model="text-embedding-bge-m3-embeddings",
            dimension_override=3, batch_size=8,
        )

        with pytest.raises(Exception):  # httpx.HTTPStatusError
            asyncio.run(provider.embed(["a"]))

        # Critical assertion: no evidence captured for a failed call
        assert provider.last_identity_evidence is None

    def test_network_error_propagates_no_zero_vectors(self):
        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("connection refused"))

        provider = _provider_with_client(client, dimension_override=3)

        with pytest.raises(RuntimeError, match="connection refused"):
            asyncio.run(provider.embed(["a"]))

        assert provider.last_identity_evidence is None

    def test_no_silent_substitution_on_partial_batch_failure(self):
        # Pre-B0 behavior: a failure in batch 1 would still return embeddings
        # for batch 0 plus zero-vectors for batch 1. B0.1e: the whole call
        # fails on the first batch error.
        good_batch = _embeddings_payload(n=2, dim=3)
        client = MagicMock()
        client.post = AsyncMock(side_effect=[
            _mock_response(good_batch),
            RuntimeError("connection dropped on batch 2"),
        ])

        provider = _provider_with_client(
            client, dimension_override=3, batch_size=2,
        )

        with pytest.raises(RuntimeError, match="connection dropped"):
            asyncio.run(provider.embed(["a", "b", "c", "d"]))


class TestMalformedOutputContract:
    def test_missing_data_field_raises_output_error(self):
        client = MagicMock()
        client.post = AsyncMock(
            return_value=_mock_response({"unexpected": "shape"})
        )
        provider = _provider_with_client(client, dimension_override=3)

        with pytest.raises(LMStudioEmbeddingOutputError) as excinfo:
            asyncio.run(provider.embed(["a"]))

        assert "missing 'data' field" in str(excinfo.value)

    def test_non_dict_response_raises_output_error(self):
        client = MagicMock()
        client.post = AsyncMock(
            return_value=_mock_response([1, 2, 3])  # list, not dict
        )
        provider = _provider_with_client(client, dimension_override=3)

        with pytest.raises(LMStudioEmbeddingOutputError):
            asyncio.run(provider.embed(["a"]))


class TestSuccessfulRequestCapturesEvidence:
    def test_returns_embeddings_and_response_model_evidence(self):
        client = MagicMock()
        client.post = AsyncMock(
            return_value=_mock_response(_embeddings_payload(
                n=2, dim=3, model="text-embedding-bge-m3-embeddings",
            ))
        )
        provider = _provider_with_client(
            client, model="text-embedding-bge-m3-embeddings",
            dimension_override=3,
        )

        result = asyncio.run(provider.embed(["a", "b"]))

        # Embeddings returned with ordering preserved
        assert len(result) == 2
        assert result[0] == [0.1, 0.1, 0.1]
        assert result[1] == [0.2, 0.2, 0.2]

        # Evidence captured from response
        evidence = provider.last_identity_evidence
        assert evidence is not None
        assert evidence.provider_kind == "lmstudio"
        assert evidence.requested_model == "text-embedding-bge-m3-embeddings"
        assert evidence.reported_model == "text-embedding-bge-m3-embeddings"
        assert evidence.evidence_source == EVIDENCE_SOURCE_LMSTUDIO_RESPONSE_MODEL

    def test_configured_model_preserved_as_deployment_id(self):
        # The directive: 'The /v1/models rewrite must be preserved as evidence:
        # configured model, resolved served model, resolution source.'
        # The configured (post-rewrite) model is preserved as deployment_id.
        client = MagicMock()
        client.post = AsyncMock(
            return_value=_mock_response(_embeddings_payload(
                n=1, dim=3, model="text-embedding-bge-m3-embeddings",
            ))
        )
        # Simulate the alias-rewrite that service_registry.py:63-77 performs
        # at orchestrator init: caller passes the rewritten name.
        provider = LMStudioEmbeddingProvider(
            model="text-embedding-bge-m3-embeddings",  # already rewritten
            dimension_override=3,
        )
        provider._client = client

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence is not None
        # The configured model is recorded as deployment_id (closest thing
        # LM Studio exposes to a deployment identity). B0.2 decides whether
        # this rises to stable_deployment or stays alias_only.
        assert evidence.deployment_id == "text-embedding-bge-m3-embeddings"

    def test_missing_response_model_handled_honestly(self):
        # Response carries no 'model' field — provider reports NULL honestly
        # rather than fabricating from the request.
        client = MagicMock()
        client.post = AsyncMock(
            return_value=_mock_response(_embeddings_payload(n=1, dim=3, model=None))
        )
        provider = _provider_with_client(
            client, model="text-embedding-bge-m3-embeddings", dimension_override=3,
        )

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence.reported_model is None
        assert evidence.evidence_source == EVIDENCE_SOURCE_CONFIGURED_ONLY

    def test_evidence_none_before_first_call(self):
        provider = _provider_with_client(MagicMock(), dimension_override=3)
        assert provider.last_identity_evidence is None


class TestEmbedWithEvidence:
    def test_returns_batch_with_vectors_and_evidence(self):
        client = MagicMock()
        client.post = AsyncMock(
            return_value=_mock_response(_embeddings_payload(
                n=1, dim=3, model="text-embedding-bge-m3-embeddings",
            ))
        )
        provider = _provider_with_client(
            client, model="text-embedding-bge-m3-embeddings", dimension_override=3,
        )

        batch = asyncio.run(provider.embed_with_evidence(["q"]))

        assert isinstance(batch, ProviderEmbeddingBatch)
        assert batch.embeddings == ((0.1, 0.1, 0.1),)
        assert batch.identity_evidence.provider_kind == "lmstudio"
        assert batch.identity_evidence.reported_model == "text-embedding-bge-m3-embeddings"

    def test_provider_failure_propagates_through_embed_with_evidence(self):
        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("provider down"))
        provider = _provider_with_client(client, dimension_override=3)

        with pytest.raises(RuntimeError, match="provider down"):
            asyncio.run(provider.embed_with_evidence(["q"]))


class TestBatchOrdering:
    def test_multi_batch_preserves_global_ordering(self):
        # Two batches of 2 — items must come back in input order
        client = MagicMock()
        client.post = AsyncMock(side_effect=[
            _mock_response({
                "model": "m",
                "data": [
                    {"index": 0, "embedding": [1.0, 0.0]},
                    {"index": 1, "embedding": [0.0, 1.0]},
                ],
            }),
            _mock_response({
                "model": "m",
                "data": [
                    {"index": 0, "embedding": [2.0, 0.0]},
                    {"index": 1, "embedding": [0.0, 2.0]},
                ],
            }),
        ])
        provider = _provider_with_client(
            client, dimension_override=2, batch_size=2,
        )

        result = asyncio.run(provider.embed(["a", "b", "c", "d"]))

        assert result == [[1.0, 0.0], [0.0, 1.0], [2.0, 0.0], [0.0, 2.0]]
