"""Tests for P0.4A1.2: capability identity, fingerprint, and binding resolution.

Proves:
  - Runtime config fingerprint is deterministic and field-sensitive
  - Binding ID is deterministic, covers ALL semantic-space fields,
    and is independent of check_id/timestamps
  - Resolution classifier produces correct postures
  - resolve_or_create_binding is idempotent and detects drift
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.models
from backend.db.database import Base
from backend.db.models import EmbeddingProfile
from backend.pipeline.capability.capability_identity import (
    compute_capability_binding_id,
    compute_check_expiry,
    compute_check_id,
    compute_runtime_config_fingerprint,
)
from backend.pipeline.capability.capability_repository import (
    CapabilityBindingDriftError,
    resolve_or_create_binding,
)
from backend.pipeline.capability.capability_resolution import (
    POSTURE_CONFIGURED_MATCH,
    POSTURE_CONFIGURED_ONLY,
    POSTURE_EXACT_REVISION,
    ResolvedBindingInput,
    classify_resolution,
)
from backend.pipeline.knowledge.embedding_configuration import (
    EffectiveEmbeddingConfiguration,
)
from backend.pipeline.knowledge.embedding_provider_identity import (
    ProviderModelIdentityEvidence,
)

# ── Helpers ───────────────────────────────────────────────────────────


def _make_effective_config(**overrides) -> EffectiveEmbeddingConfiguration:
    defaults = dict(
        embedding_profile_id="a" * 64,
        profile_schema_version="embedding_profile_v1",
        provider_kind="openai",
        requested_model="text-embedding-3-small",
        expected_dimension=1536,
        declared_normalization_policy="none",
        implemented_postprocessing_policy="none",
        document_task=None,
        query_task=None,
        sanitized_endpoint_identity="https://api.openai.com",
        configured_deployment_id=None,
        deployment_is_explicitly_pinned=False,
        provider_adapter_contract_version="openai_v1",
        governed_adapter_contract_version="governed_v1",
    )
    defaults.update(overrides)
    return EffectiveEmbeddingConfiguration(**defaults)


def _make_evidence(**overrides) -> ProviderModelIdentityEvidence:
    defaults = dict(
        provider_kind="openai",
        requested_model="text-embedding-3-small",
        evidence_source="openai_response_model",
        reported_model=None,
        deployment_id=None,
        provider_revision=None,
    )
    defaults.update(overrides)
    return ProviderModelIdentityEvidence(**defaults)


# ── 1. Runtime config fingerprint ─────────────────────────────────────


class TestRuntimeConfigFingerprint:
    def test_deterministic(self):
        cfg = _make_effective_config()
        assert compute_runtime_config_fingerprint(cfg) == compute_runtime_config_fingerprint(cfg)

    def test_is_sha256_hex(self):
        fp = compute_runtime_config_fingerprint(_make_effective_config())
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_differs_on_provider(self):
        c1 = _make_effective_config(provider_kind="openai")
        c2 = _make_effective_config(provider_kind="gemini")
        assert compute_runtime_config_fingerprint(c1) != compute_runtime_config_fingerprint(c2)

    def test_differs_on_model(self):
        c1 = _make_effective_config(requested_model="text-embedding-3-small")
        c2 = _make_effective_config(requested_model="text-embedding-3-large")
        assert compute_runtime_config_fingerprint(c1) != compute_runtime_config_fingerprint(c2)

    def test_differs_on_dimension(self):
        c1 = _make_effective_config(expected_dimension=1536)
        c2 = _make_effective_config(expected_dimension=3072)
        assert compute_runtime_config_fingerprint(c1) != compute_runtime_config_fingerprint(c2)

    def test_differs_on_endpoint(self):
        c1 = _make_effective_config(sanitized_endpoint_identity="https://api.openai.com")
        c2 = _make_effective_config(sanitized_endpoint_identity="https://proxy.example.com")
        assert compute_runtime_config_fingerprint(c1) != compute_runtime_config_fingerprint(c2)

    def test_differs_on_document_task(self):
        c1 = _make_effective_config(document_task=None)
        c2 = _make_effective_config(document_task="retrieval_document")
        assert compute_runtime_config_fingerprint(c1) != compute_runtime_config_fingerprint(c2)

    def test_differs_on_normalization(self):
        c1 = _make_effective_config(declared_normalization_policy="none")
        c2 = _make_effective_config(declared_normalization_policy="l2")
        assert compute_runtime_config_fingerprint(c1) != compute_runtime_config_fingerprint(c2)

    def test_differs_on_contract_version(self):
        c1 = _make_effective_config(provider_adapter_contract_version="v1")
        c2 = _make_effective_config(provider_adapter_contract_version="v2")
        assert compute_runtime_config_fingerprint(c1) != compute_runtime_config_fingerprint(c2)

    def test_differs_on_deployment_pin(self):
        c1 = _make_effective_config(deployment_is_explicitly_pinned=False)
        c2 = _make_effective_config(deployment_is_explicitly_pinned=True)
        assert compute_runtime_config_fingerprint(c1) != compute_runtime_config_fingerprint(c2)


# ── 2. Binding identity ───────────────────────────────────────────────


class TestCapabilityBindingId:
    def _binding_kwargs(self, **overrides):
        defaults = dict(
            embedding_profile_id="a" * 64,
            profile_schema_version="embedding_profile_v1",
            provider_kind="openai",
            resolved_model="text-embedding-3-small",
            provider_revision=None,
            model_resolution_posture="configured_match",
            resolved_deployment_id=None,
            resolved_document_task=None,
            resolved_query_task=None,
            resolved_dimension=1536,
            resolved_normalization="none",
            postprocessing_contract_version="none",
            sanitized_endpoint_identity="https://api.openai.com",
            provider_adapter_contract_version="openai_v1",
            governed_adapter_contract_version="governed_v1",
        )
        defaults.update(overrides)
        return defaults

    def test_deterministic(self):
        kw = self._binding_kwargs()
        assert compute_capability_binding_id(**kw) == compute_capability_binding_id(**kw)

    def test_is_sha256_hex(self):
        bid = compute_capability_binding_id(**self._binding_kwargs())
        assert len(bid) == 64
        assert all(c in "0123456789abcdef" for c in bid)

    def test_differs_on_revision(self):
        k1 = self._binding_kwargs(provider_revision=None)
        k2 = self._binding_kwargs(provider_revision="sha256:abc123")
        assert compute_capability_binding_id(**k1) != compute_capability_binding_id(**k2)

    def test_differs_on_posture(self):
        k1 = self._binding_kwargs(model_resolution_posture="configured_match")
        k2 = self._binding_kwargs(model_resolution_posture="configured_only")
        assert compute_capability_binding_id(**k1) != compute_capability_binding_id(**k2)

    def test_differs_on_document_task(self):
        k1 = self._binding_kwargs(resolved_document_task=None)
        k2 = self._binding_kwargs(resolved_document_task="retrieval_document")
        assert compute_capability_binding_id(**k1) != compute_capability_binding_id(**k2)

    def test_independent_of_timestamps(self):
        """Binding ID must not change if only timestamps differ."""
        kw = self._binding_kwargs()
        bid = compute_capability_binding_id(**kw)
        # Recompute — should be identical (no timestamp input)
        assert compute_capability_binding_id(**kw) == bid


# ── 3. Check ID and expiry ────────────────────────────────────────────


class TestCheckIdAndExpiry:
    def test_check_id_is_uuid_hex(self):
        cid = compute_check_id()
        assert len(cid) == 32  # uuid4().hex
        assert all(c in "0123456789abcdef" for c in cid)

    def test_check_id_is_unique(self):
        ids = {compute_check_id() for _ in range(100)}
        assert len(ids) == 100

    def test_check_expiry(self):
        probed = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        expiry = compute_check_expiry(probed, ttl_seconds=3600)
        assert expiry == datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)


# ── 4. Resolution classifier ──────────────────────────────────────────


class TestClassifyResolution:
    def test_exact_revision_when_provider_revision_present(self):
        cfg = _make_effective_config()
        doc_ev = _make_evidence(provider_revision="sha256:abc")
        query_ev = _make_evidence()
        decision = classify_resolution(cfg, doc_ev, query_ev, 1536, 1536)
        assert decision.posture == POSTURE_EXACT_REVISION
        assert decision.binding_input.provider_revision == "sha256:abc"

    def test_configured_match_when_reported_model_matches(self):
        cfg = _make_effective_config()
        doc_ev = _make_evidence(reported_model="text-embedding-3-small")
        query_ev = _make_evidence()
        decision = classify_resolution(cfg, doc_ev, query_ev, 1536, 1536)
        assert decision.posture == POSTURE_CONFIGURED_MATCH

    def test_configured_only_when_no_evidence(self):
        cfg = _make_effective_config()
        doc_ev = _make_evidence(evidence_source="configured_only", reported_model=None)
        query_ev = _make_evidence(evidence_source="configured_only", reported_model=None)
        decision = classify_resolution(cfg, doc_ev, query_ev, 1536, 1536)
        assert decision.posture == POSTURE_CONFIGURED_ONLY
        assert decision.binding_input.provider_revision is None

    def test_binding_input_carries_all_fields(self):
        cfg = _make_effective_config()
        doc_ev = _make_evidence()
        query_ev = _make_evidence()
        decision = classify_resolution(cfg, doc_ev, query_ev, 1536, 1536)
        bi = decision.binding_input
        assert bi.embedding_profile_id == cfg.embedding_profile_id
        assert bi.provider_kind == cfg.provider_kind
        assert bi.resolved_model == cfg.requested_model
        assert bi.resolved_dimension == cfg.expected_dimension


# ── 5. resolve_or_create_binding ──────────────────────────────────────


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


def _seed_profile(session, profile_id="a" * 64):
    session.execute(
        text(
            "INSERT INTO embedding_profiles "
            "(profile_id, profile_schema_version, provider, model_identifier, "
            " dimension, normalization_policy, chunking_schema_version, "
            " collection_name, verification_status, created_at) "
            "VALUES (:pid, 'embedding_profile_v1', 'openai', 'text-embedding-3-small', "
            "        1536, 'none', 'chunk_v1', 'test_col', 'unverified', "
            "        '2026-01-01 00:00:00')"
        ),
        {"pid": profile_id},
    )
    session.commit()


class TestResolveOrCreateBinding:
    def test_creates_binding_on_first_call(self):
        engine = _make_engine()
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        _seed_profile(session)

        cfg = _make_effective_config()
        doc_ev = _make_evidence()
        query_ev = _make_evidence()
        decision = classify_resolution(cfg, doc_ev, query_ev, 1536, 1536)

        binding_id = resolve_or_create_binding(session, decision)
        session.commit()

        assert len(binding_id) == 64

    def test_idempotent_on_second_call(self):
        engine = _make_engine()
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        _seed_profile(session)

        cfg = _make_effective_config()
        doc_ev = _make_evidence()
        query_ev = _make_evidence()
        decision = classify_resolution(cfg, doc_ev, query_ev, 1536, 1536)

        bid1 = resolve_or_create_binding(session, decision)
        session.commit()

        bid2 = resolve_or_create_binding(session, decision)
        session.commit()

        assert bid1 == bid2

    def test_drift_detected_on_different_fields(self):
        """If a binding exists for the profile but a new decision computes
        a different binding_id, raise CapabilityBindingDriftError."""
        engine = _make_engine()
        session = sessionmaker(bind=engine, expire_on_commit=False)()
        _seed_profile(session)

        # First resolution: configured_only posture
        cfg = _make_effective_config()
        doc_ev = _make_evidence(evidence_source="configured_only", reported_model=None)
        query_ev = _make_evidence(evidence_source="configured_only", reported_model=None)
        decision1 = classify_resolution(cfg, doc_ev, query_ev, 1536, 1536)
        bid1 = resolve_or_create_binding(session, decision1)
        session.commit()

        # Second resolution: exact_revision posture (different identity)
        doc_ev2 = _make_evidence(provider_revision="sha256:abc")
        decision2 = classify_resolution(cfg, doc_ev2, query_ev, 1536, 1536)

        with pytest.raises(CapabilityBindingDriftError):
            resolve_or_create_binding(session, decision2)
        session.rollback()
        session.close()
