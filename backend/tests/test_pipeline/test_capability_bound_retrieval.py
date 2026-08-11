"""Tests for P0.4A2.4: capability-bound scoped retrieval.

Proves:
  - Pre-activation: v0 vectors eligible, v1 vectors NOT
  - Post-activation: only active-binding v2 vectors eligible
  - Query binding ≠ active binding → RetrievalBindingMismatch
  - No pre-capability fallback after activation
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.pipeline.capability.capability_bound_retrieval import (
    RetrievalBindingContext,
    RetrievalBindingMismatch,
    build_query_retrieval_evidence,
    is_vector_eligible_for_retrieval,
    resolve_retrieval_binding_context,
)
from backend.pipeline.vector_contracts import (
    EMBEDDING_CONTRACT_CAPABILITY_V1,
    EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
)

_PROFILE_ID = "a" * 64
_BINDING_ID = "b" * 64
_ACTIVATION_ID = "c" * 64


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


def _seed_profile(session):
    session.execute(
        text(
            "INSERT INTO embedding_profiles "
            "(profile_id, profile_schema_version, provider, model_identifier, "
            " dimension, normalization_policy, chunking_schema_version, "
            " collection_name, verification_status, created_at) "
            "VALUES (:pid, 'embedding_profile_v1', 'openai', 'm', 1536, 'none', "
            "        'chunk_v1', 'test_col', 'unverified', '2026-01-01 00:00:00')"
        ),
        {"pid": _PROFILE_ID},
    )
    session.commit()


def _seed_binding(session, binding_id=_BINDING_ID):
    session.execute(
        text(
            "INSERT INTO embedding_capability_bindings "
            "(binding_id, embedding_profile_id, provider_kind, resolved_model, "
            " model_resolution_posture, resolved_dimension, resolved_normalization, "
            " postprocessing_contract_version, resolved_endpoint_identity, "
            " profile_schema_version, provider_adapter_contract_version, "
            " governed_adapter_contract_version, resolution_classifier_version, "
            " binding_schema_version) "
            "VALUES (:bid, :pid, 'openai', 'm', 'configured_match', 1536, 'none', "
            "        'none', 'provider-default://unset', 'embedding_profile_v1', "
            "        'v1', 'v1', 'v1', 'capability_binding_v1')"
        ),
        {"bid": binding_id, "pid": _PROFILE_ID},
    )
    session.commit()


def _seed_active_activation(session, binding_id=_BINDING_ID, activation_id=_ACTIVATION_ID):
    session.execute(
        text(
            "INSERT INTO embedding_profile_binding_activations "
            "(activation_id, embedding_profile_id, embedding_purpose, "
            " capability_binding_id, cutover_id, status, activation_generation, "
            " activated_at) "
            "VALUES (:aid, :pid, 'paper', :bid, 'd' * 64, 'active', 1, "
            "        '2026-01-01 00:00:00')"
        ),
        {"aid": activation_id, "pid": _PROFILE_ID, "bid": binding_id},
    )
    session.commit()


# ── Pre-activation posture ───────────────────────────────────────────


class TestPreActivation:
    def test_no_activation_returns_pre_capability(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)
            ctx = resolve_retrieval_binding_context(session, _PROFILE_ID)

        assert ctx.vector_eligibility_contract_version == EMBEDDING_CONTRACT_PRE_CAPABILITY_V0
        assert ctx.active_binding_id is None

    def test_v0_vectors_eligible_before_activation(self):
        ctx = RetrievalBindingContext(
            embedding_profile_id=_PROFILE_ID,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
            active_binding_id=None,
            activation_id=None,
            activation_generation=None,
        )
        assert is_vector_eligible_for_retrieval(
            vector_binding_id=None,
            vector_contract_version=EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
            binding_context=ctx,
        )

    def test_v1_vectors_not_eligible_before_activation(self):
        """Candidate v2 vectors are NOT eligible for production retrieval."""
        ctx = RetrievalBindingContext(
            embedding_profile_id=_PROFILE_ID,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
            active_binding_id=None,
            activation_id=None,
            activation_generation=None,
        )
        assert not is_vector_eligible_for_retrieval(
            vector_binding_id=_BINDING_ID,
            vector_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            binding_context=ctx,
        )


# ── Post-activation posture ──────────────────────────────────────────


class TestPostActivation:
    def test_active_activation_returns_capability_v1(self):
        engine = _make_engine()
        sf = sessionmaker(bind=engine, expire_on_commit=False)
        with sf() as session:
            _seed_profile(session)
            _seed_binding(session)
            _seed_active_activation(session)
            ctx = resolve_retrieval_binding_context(session, _PROFILE_ID)

        assert ctx.vector_eligibility_contract_version == EMBEDDING_CONTRACT_CAPABILITY_V1
        assert ctx.active_binding_id == _BINDING_ID

    def test_active_binding_vectors_eligible(self):
        ctx = RetrievalBindingContext(
            embedding_profile_id=_PROFILE_ID,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            active_binding_id=_BINDING_ID,
            activation_id=_ACTIVATION_ID,
            activation_generation=1,
        )
        assert is_vector_eligible_for_retrieval(
            vector_binding_id=_BINDING_ID,
            vector_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            binding_context=ctx,
        )

    def test_different_binding_vectors_not_eligible(self):
        ctx = RetrievalBindingContext(
            embedding_profile_id=_PROFILE_ID,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            active_binding_id=_BINDING_ID,
            activation_id=_ACTIVATION_ID,
            activation_generation=1,
        )
        assert not is_vector_eligible_for_retrieval(
            vector_binding_id="x" * 64,
            vector_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            binding_context=ctx,
        )

    def test_no_pre_capability_fallback_after_activation(self):
        """v0 vectors are NOT eligible after activation — no fallback."""
        ctx = RetrievalBindingContext(
            embedding_profile_id=_PROFILE_ID,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            active_binding_id=_BINDING_ID,
            activation_id=_ACTIVATION_ID,
            activation_generation=1,
        )
        assert not is_vector_eligible_for_retrieval(
            vector_binding_id=None,
            vector_contract_version=EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
            binding_context=ctx,
        )


# ── Query binding mismatch ───────────────────────────────────────────


class TestQueryBindingMismatch:
    def test_query_binding_mismatch_raises(self):
        ctx = RetrievalBindingContext(
            embedding_profile_id=_PROFILE_ID,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            active_binding_id=_BINDING_ID,
            activation_id=_ACTIVATION_ID,
            activation_generation=1,
        )
        with pytest.raises(RetrievalBindingMismatch):
            build_query_retrieval_evidence(
                query_binding_id="x" * 64,  # different binding
                query_check_id="y" * 64,
                binding_context=ctx,
            )

    def test_query_matching_binding_succeeds(self):
        ctx = RetrievalBindingContext(
            embedding_profile_id=_PROFILE_ID,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_CAPABILITY_V1,
            active_binding_id=_BINDING_ID,
            activation_id=_ACTIVATION_ID,
            activation_generation=1,
        )
        evidence = build_query_retrieval_evidence(
            query_binding_id=_BINDING_ID,
            query_check_id="y" * 64,
            binding_context=ctx,
        )
        assert evidence.query_embedding_contract_version == EMBEDDING_CONTRACT_CAPABILITY_V1
        assert evidence.binding_activation_id == _ACTIVATION_ID

    def test_transitional_posture_before_activation(self):
        """Before activation: capability_v1 query + pre_capability_v0 vectors."""
        ctx = RetrievalBindingContext(
            embedding_profile_id=_PROFILE_ID,
            vector_eligibility_contract_version=EMBEDDING_CONTRACT_PRE_CAPABILITY_V0,
            active_binding_id=None,
            activation_id=None,
            activation_generation=None,
        )
        evidence = build_query_retrieval_evidence(
            query_binding_id="b" * 64,
            query_check_id="c" * 64,
            binding_context=ctx,
        )
        assert evidence.query_embedding_contract_version == EMBEDDING_CONTRACT_CAPABILITY_V1
        assert evidence.binding_activation_id is None
