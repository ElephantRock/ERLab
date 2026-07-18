"""Tests for the provider-neutral identity-evidence contract (P0.4B0.1a)."""

from __future__ import annotations

from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_CONFIGURED_ONLY,
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderEmbeddingBatch,
    ProviderEmbeddingQuery,
    ProviderModelIdentityEvidence,
)


class TestProviderModelIdentityEvidence:
    def test_minimal_evidence_with_required_fields_only(self):
        evidence = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_CONFIGURED_ONLY,
        )
        assert evidence.provider_kind == "openai"
        assert evidence.requested_model == "text-embedding-3-small"
        assert evidence.evidence_source == EVIDENCE_SOURCE_CONFIGURED_ONLY
        # Optional fields default to NULL — honest "no evidence"
        assert evidence.reported_model is None
        assert evidence.deployment_id is None
        assert evidence.provider_revision is None

    def test_frozen(self):
        evidence = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_CONFIGURED_ONLY,
        )
        # frozen=True — identity evidence must be immutable once captured
        try:
            evidence.reported_model = "mutated"  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("evidence record must be frozen")

    def test_full_evidence_with_all_optional_fields(self):
        evidence = ProviderModelIdentityEvidence(
            provider_kind="ollama",
            requested_model="nomic-embed-text",
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
            reported_model="nomic-embed-text:latest",
            deployment_id="deployment-xyz",
            provider_revision="sha256:abc123",
        )
        assert evidence.reported_model == "nomic-embed-text:latest"
        assert evidence.deployment_id == "deployment-xyz"
        assert evidence.provider_revision == "sha256:abc123"

    def test_hashable(self):
        # frozen dataclass with hashable fields is hashable — supports use
        # as a dict key for future binding identity caches.
        evidence = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="m",
            evidence_source="src",
        )
        assert hash(evidence) == hash(evidence)


class TestProviderEmbeddingBatch:
    def test_carries_embeddings_and_evidence(self):
        evidence = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model="text-embedding-3-small",
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
            reported_model="text-embedding-3-small",
        )
        batch = ProviderEmbeddingBatch(
            embeddings=((0.1, 0.2, 0.3), (0.4, 0.5, 0.6)),
            identity_evidence=evidence,
        )
        assert len(batch.embeddings) == 2
        assert batch.embeddings[0] == (0.1, 0.2, 0.3)
        assert batch.identity_evidence.reported_model == "text-embedding-3-small"

    def test_embeddings_are_tuples(self):
        # Tuples, not lists — communicate immutability and make the record hashable.
        evidence = ProviderModelIdentityEvidence(
            provider_kind="x", requested_model="m", evidence_source="s",
        )
        batch = ProviderEmbeddingBatch(
            embeddings=((1.0,),),
            identity_evidence=evidence,
        )
        assert isinstance(batch.embeddings, tuple)
        assert isinstance(batch.embeddings[0], tuple)


class TestProviderEmbeddingQuery:
    def test_carries_single_vector_and_evidence(self):
        evidence = ProviderModelIdentityEvidence(
            provider_kind="gemini",
            requested_model="models/embedding-001",
            evidence_source="gemini_configured_model",
        )
        result = ProviderEmbeddingQuery(
            embedding=(0.1, 0.2, 0.3),
            identity_evidence=evidence,
        )
        assert result.embedding == (0.1, 0.2, 0.3)
        assert result.identity_evidence.provider_kind == "gemini"

    def test_distinct_type_from_batch(self):
        # Role-aware validation (B0.3 adapter, future verified runtime)
        # distinguishes documents from queries by type, not by length.
        evidence = ProviderModelIdentityEvidence(
            provider_kind="x", requested_model="m", evidence_source="s",
        )
        batch = ProviderEmbeddingBatch(embeddings=((1.0,),), identity_evidence=evidence)
        query = ProviderEmbeddingQuery(embedding=(1.0,), identity_evidence=evidence)
        assert not isinstance(batch, ProviderEmbeddingQuery)
        assert not isinstance(query, ProviderEmbeddingBatch)
