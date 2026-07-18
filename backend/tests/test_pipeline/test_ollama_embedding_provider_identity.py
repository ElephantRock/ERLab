"""Tests for OllamaEmbeddingProvider identity evidence capture (P0.4B0.1d).

Per directive B0.1d, these tests prove:
  * /api/show probed once for immutable digest evidence
  * digest retained as provider_revision when available
  * embedding-only path (no digest) records honest 'ollama_response' evidence
  * provider failure on /api/show does not block embedding (probe is best-effort)
  * provider failure on /api/embeddings propagates
  * probe is idempotent (only one /api/show call across multiple embed() calls)
  * no fabricated stable identity
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_OLLAMA_API_SHOW_DIGEST,
    EVIDENCE_SOURCE_OLLAMA_RESPONSE,
    ProviderEmbeddingBatch,
)
from backend.pipeline.knowledge.embedding_providers import OllamaEmbeddingProvider


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


def _provider_with_client(client: Any, **kwargs) -> OllamaEmbeddingProvider:
    """Construct an OllamaEmbeddingProvider and override its httpx client."""
    p = OllamaEmbeddingProvider(**kwargs)
    p._client = client
    return p


def _client_routing(show_resp=None, embed_resps=None) -> MagicMock:
    """Build an httpx client mock that dispatches by URL path.

    show_resp:  response payload (dict) for /api/show, or Exception, or None
    embed_resps: list of response payloads (dicts) for successive /api/embeddings calls
    """
    client = MagicMock(name="httpx_async_client")
    embed_iter = iter(embed_resps or [])

    async def _post(url, json=None):
        if url.endswith("/api/show"):
            if isinstance(show_resp, Exception):
                raise show_resp
            return _mock_response(show_resp or {})
        if url.endswith("/api/embeddings"):
            try:
                payload = next(embed_iter)
            except StopIteration:
                raise RuntimeError("no more canned embed responses")
            if isinstance(payload, Exception):
                raise payload
            return _mock_response(payload)
        raise ValueError(f"unexpected URL: {url}")

    client.post = AsyncMock(side_effect=_post)
    return client


class TestDigestProbe:
    def test_show_digest_retained_as_provider_revision(self):
        client = _client_routing(
            show_resp={"digest": "sha256:abc123def456", "details": {"family": "bert"}},
            embed_resps=[{"embedding": [0.1, 0.2, 0.3]}],
        )
        provider = _provider_with_client(client, model="nomic-embed-text")

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence is not None
        assert evidence.provider_kind == "ollama"
        assert evidence.requested_model == "nomic-embed-text"
        assert evidence.provider_revision == "sha256:abc123def456"
        assert evidence.evidence_source == EVIDENCE_SOURCE_OLLAMA_API_SHOW_DIGEST

    def test_show_missing_digest_falls_back_to_response_evidence(self):
        # /api/show reachable but no digest field — fall back to honest
        # 'ollama_response' (we got vectors but no immutable identity)
        client = _client_routing(
            show_resp={"details": {"family": "bert"}},  # no digest
            embed_resps=[{"embedding": [0.1, 0.2]}],
        )
        provider = _provider_with_client(client)

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence is not None
        assert evidence.provider_revision is None
        assert evidence.evidence_source == EVIDENCE_SOURCE_OLLAMA_RESPONSE

    def test_show_failure_does_not_block_embedding(self):
        # /api/show raises (network error, model not loaded, 404, etc.).
        # Probe is best-effort; embedding still proceeds.
        client = _client_routing(
            show_resp=RuntimeError("connection refused"),
            embed_resps=[{"embedding": [0.5, 0.6]}],
        )
        provider = _provider_with_client(client)

        result = asyncio.run(provider.embed(["a"]))

        assert result == [[0.5, 0.6]]
        evidence = provider.last_identity_evidence
        assert evidence is not None
        assert evidence.provider_revision is None
        assert evidence.evidence_source == EVIDENCE_SOURCE_OLLAMA_RESPONSE

    def test_probe_runs_at_most_once_across_multiple_embeds(self):
        # Idempotency: subsequent embed() calls do not re-probe /api/show
        client = _client_routing(
            show_resp={"digest": "sha256:once"},
            embed_resps=[
                {"embedding": [0.1]},
                {"embedding": [0.2]},
                {"embedding": [0.3]},
            ],
        )
        provider = _provider_with_client(client)

        asyncio.run(provider.embed(["a"]))
        asyncio.run(provider.embed(["b"]))
        asyncio.run(provider.embed(["c"]))

        # Count /api/show posts vs /api/embeddings posts
        show_calls = [
            c for c in client.post.call_args_list
            if c.args and str(c.args[0]).endswith("/api/show")
        ]
        embed_calls = [
            c for c in client.post.call_args_list
            if c.args and str(c.args[0]).endswith("/api/embeddings")
        ]
        assert len(show_calls) == 1
        assert len(embed_calls) == 3

    def test_evidence_none_before_first_call(self):
        provider = _provider_with_client(_client_routing())
        assert provider.last_identity_evidence is None


class TestEmbeddingFailure:
    def test_embeddings_endpoint_exception_propagates(self):
        client = _client_routing(
            show_resp={"digest": "sha256:x"},
            embed_resps=[RuntimeError("model not loaded")],
        )
        provider = _provider_with_client(client)

        with pytest.raises(RuntimeError, match="model not loaded"):
            asyncio.run(provider.embed(["a"]))


class TestEmbedWithEvidence:
    def test_returns_batch_with_vectors_and_digest_evidence(self):
        client = _client_routing(
            show_resp={"digest": "sha256:abc"},
            embed_resps=[{"embedding": [0.7, 0.8, 0.9]}],
        )
        provider = _provider_with_client(client, model="nomic-embed-text")

        batch = asyncio.run(provider.embed_with_evidence(["q"]))

        assert isinstance(batch, ProviderEmbeddingBatch)
        assert batch.embeddings == ((0.7, 0.8, 0.9),)
        assert batch.identity_evidence.provider_kind == "ollama"
        assert batch.identity_evidence.provider_revision == "sha256:abc"

    def test_embeddings_returned_as_tuples(self):
        client = _client_routing(
            show_resp={"digest": "sha256:abc"},
            embed_resps=[{"embedding": [0.4, 0.5]}],
        )
        provider = _provider_with_client(client)

        batch = asyncio.run(provider.embed_with_evidence(["q"]))

        assert isinstance(batch.embeddings, tuple)
        assert isinstance(batch.embeddings[0], tuple)


class TestNoFabricatedStableIdentity:
    def test_no_digest_does_not_invent_revision(self):
        # If /api/show returns no digest, the provider MUST NOT fabricate one
        # from the model tag. provider_revision stays NULL.
        client = _client_routing(
            show_resp={"details": {}},
            embed_resps=[{"embedding": [0.1, 0.2]}],
        )
        provider = _provider_with_client(client, model="nomic-embed-text:latest")

        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence.provider_revision is None
        # The model tag includes ':latest' which is mutable; evidence reflects
        # the tag but does NOT promote it to provider_revision.
        assert evidence.requested_model == "nomic-embed-text:latest"
        assert evidence.reported_model == "nomic-embed-text:latest"
