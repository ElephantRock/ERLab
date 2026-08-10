"""Tests for OpenAIEmbeddingProvider identity-evidence capture (P0.4B0.1b).

Per directive B0.1b, these tests prove the provider:
  * retains response model field as evidence
  * preserves both requested and reported model
  * handles missing/invalid model evidence honestly (NULL, not fabricated)
  * keeps embedding ordering unchanged from response
  * still propagates provider failures
  * excludes credentials from evidence
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_CONFIGURED_ONLY,
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderEmbeddingBatch,
)
from backend.pipeline.knowledge.embedding_providers import OpenAIEmbeddingProvider


def _mock_openai_response(
    embeddings: list[list[float]],
    *,
    model: str | None = "text-embedding-3-small",
) -> MagicMock:
    """Build a response shaped like openai.AsyncOpenAI().embeddings.create()."""
    response = MagicMock(name="openai_response")
    response.data = [
        MagicMock(embedding=list(vec), index=i) for i, vec in enumerate(embeddings)
    ]
    # Simulate the SDK's response.model field. None means "missing/malformed".
    response.model = model
    return response


def _provider_with_client(client: Any, **kwargs) -> OpenAIEmbeddingProvider:
    """Construct an OpenAIEmbeddingProvider and override its SDK client.

    Passes a placeholder api_key so the SDK doesn't require OPENAI_API_KEY
    in the environment; the constructed client is replaced immediately
    afterward so the placeholder never makes a real network call.
    """
    kwargs.setdefault("api_key", "test-placeholder-not-used")
    p = OpenAIEmbeddingProvider(**kwargs)
    p._client = client
    return p


class TestEmbedCapturesResponseModel:
    def test_response_model_retained_as_reported(self):
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(
            return_value=_mock_openai_response(
                [[0.1, 0.2], [0.3, 0.4]], model="text-embedding-3-small",
            )
        )
        provider = _provider_with_client(client, model="text-embedding-3-small")

        result = asyncio.run(provider.embed(["a", "b"]))

        # Embedding ordering unchanged from response
        assert result == [[0.1, 0.2], [0.3, 0.4]]

        # Evidence captured
        evidence = provider.last_identity_evidence
        assert evidence is not None
        assert evidence.provider_kind == "openai"
        assert evidence.requested_model == "text-embedding-3-small"
        assert evidence.reported_model == "text-embedding-3-small"
        assert evidence.evidence_source == EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL

    def test_requested_and_reported_both_preserved_when_different(self):
        # Simulate a routing layer that serves a different model than requested
        # (e.g. provider upgraded text-embedding-3-small → text-embedding-3-small-v2)
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(
            return_value=_mock_openai_response(
                [[0.1, 0.2]], model="text-embedding-3-small-v2",
            )
        )
        provider = _provider_with_client(client, model="text-embedding-3-small")

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence is not None
        assert evidence.requested_model == "text-embedding-3-small"
        assert evidence.reported_model == "text-embedding-3-small-v2"
        # The provider does NOT promote the echo — both are recorded,
        # B0.2's classifier decides what the echo means.
        assert evidence.deployment_id is None
        assert evidence.provider_revision is None

    def test_missing_model_field_handled_honestly(self):
        # If response.model is None (proxy edge case, future SDK change),
        # the provider reports NULL rather than fabricating the requested model.
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(
            return_value=_mock_openai_response([[0.1, 0.2]], model=None),
        )
        provider = _provider_with_client(client, model="text-embedding-3-small")

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence is not None
        assert evidence.reported_model is None
        # Evidence source honestly reflects "configured only" — no response evidence
        assert evidence.evidence_source == EVIDENCE_SOURCE_CONFIGURED_ONLY

    def test_empty_string_model_field_handled_honestly(self):
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(
            return_value=_mock_openai_response([[0.1, 0.2]], model=""),
        )
        provider = _provider_with_client(client, model="text-embedding-3-small")

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence.reported_model is None
        assert evidence.evidence_source == EVIDENCE_SOURCE_CONFIGURED_ONLY

    def test_evidence_none_before_first_call(self):
        provider = _provider_with_client(MagicMock(), model="text-embedding-3-small")
        assert provider.last_identity_evidence is None


class TestEmbedOrderingUnchanged:
    def test_three_embeddings_preserve_response_order(self):
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(
            return_value=_mock_openai_response(
                [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],
                model="text-embedding-3-small",
            )
        )
        provider = _provider_with_client(client)

        result = asyncio.run(provider.embed(["first", "second", "third"]))

        assert result == [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        # Index order from response also preserved
        assert [d.index for d in client.embeddings.create.return_value.data] == [0, 1, 2]


class TestProviderFailurePropagates:
    def test_sdk_exception_propagates_unchanged(self):
        # The pre-B0 LMStudio adapter silently returned zero vectors on failure.
        # OpenAI's adapter never did, but the directive requires this guarantee
        # be explicit per-provider.
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(side_effect=RuntimeError("rate limited"))

        provider = _provider_with_client(client)

        with pytest.raises(RuntimeError, match="rate limited"):
            asyncio.run(provider.embed(["a"]))

        # Failed call does not leave stale evidence
        assert provider.last_identity_evidence is None


class TestEmbedWithEvidence:
    def test_returns_batch_with_vectors_and_evidence(self):
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(
            return_value=_mock_openai_response(
                [[0.1, 0.2, 0.3]], model="text-embedding-3-small",
            )
        )
        provider = _provider_with_client(client, model="text-embedding-3-small")

        batch = asyncio.run(provider.embed_with_evidence(["a"]))

        assert isinstance(batch, ProviderEmbeddingBatch)
        assert batch.embeddings == ((0.1, 0.2, 0.3),)
        assert batch.identity_evidence.provider_kind == "openai"
        assert batch.identity_evidence.reported_model == "text-embedding-3-small"

    def test_embeddings_returned_as_tuples(self):
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(
            return_value=_mock_open_ai_response_single(),
        )
        provider = _provider_with_client(client)

        batch = asyncio.run(provider.embed_with_evidence(["a"]))

        assert isinstance(batch.embeddings, tuple)
        assert isinstance(batch.embeddings[0], tuple)


def _mock_open_ai_response_single() -> MagicMock:
    return _mock_openai_response([[0.4, 0.5]], model="text-embedding-3-small")


class TestCredentialsExcludedFromEvidence:
    def test_api_key_not_present_in_evidence_fields(self):
        # The ProviderModelIdentityEvidence contract has no field for secrets.
        # Even when the provider is constructed with an api_key, the evidence
        # record contains only identity-bearing fields.
        client = MagicMock()
        client.embeddings = MagicMock()
        client.embeddings.create = AsyncMock(
            return_value=_mock_openai_response([[0.1, 0.2]], model="text-embedding-3-small"),
        )
        provider = OpenAIEmbeddingProvider(
            model="text-embedding-3-small", api_key="sk-test-secret-do-not-leak",
        )
        provider._client = client

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence is not None
        # Walk every field value and ensure no secret leaks
        for field_name in ("provider_kind", "requested_model", "reported_model",
                           "deployment_id", "provider_revision", "evidence_source"):
            value = getattr(evidence, field_name)
            if value is not None:
                assert "sk-test" not in str(value), f"secret leaked in field {field_name}"
