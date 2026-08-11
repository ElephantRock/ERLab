"""Tests for the pure model-resolution-posture classifier (P0.4B0.2).

Per directive, these prove:
  * exact_revision / stable_deployment -> activation_eligible True
  * alias_only                          -> activation_eligible False
  * caller cannot override activation_eligible
  * OpenAI response.model only = alias_only; explicit deployment = stable_deployment
  * Gemini configured/SDK model only = alias_only
  * Ollama valid digest = exact_revision; tag only = alias_only;
    invalid digest = bounded failure; probe unavailable = alias_only
  * LM Studio configured/served name only = alias_only
  * contradictions never degrade to alias_only
  * determinism: same canonical inputs -> identical decision
"""

from __future__ import annotations

import pytest

from backend.pipeline.governed_embedding_adapter import (
    GOVERNED_EMBEDDING_ADAPTER_CONTRACT_VERSION,
)
from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_CONFIGURED_ONLY,
    EVIDENCE_SOURCE_LMSTUDIO_RESPONSE_MODEL,
    EVIDENCE_SOURCE_OLLAMA_API_SHOW_DIGEST,
    EVIDENCE_SOURCE_OLLAMA_RESPONSE,
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderModelIdentityEvidence,
)
from backend.pipeline.knowledge.model_resolution_classifier import (
    EVIDENCE_CODE_CONFIGURED_MODEL_ALIAS_ONLY,
    EVIDENCE_CODE_LMSTUDIO_MODEL_NAME_ONLY,
    EVIDENCE_CODE_OLLAMA_MODEL_DIGEST,
    EVIDENCE_CODE_OLLAMA_MODEL_TAG_ONLY,
    EVIDENCE_CODE_PINNED_DEPLOYMENT_IDENTITY,
    EVIDENCE_CODE_RESPONSE_MODEL_ALIAS_ONLY,
    MODEL_RESOLUTION_CLASSIFIER_V1,
    EmbeddingAdapterContractVersionAbsent,
    EmbeddingDeploymentPinIncomplete,
    EmbeddingIdentityEvidenceConflict,
    EmbeddingProviderUnsupported,
    EmbeddingRevisionInvalid,
    ModelResolutionContext,
    classify_model_resolution,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _ctx(
    provider_kind: str,
    requested_model: str = "any-model",
    *,
    configured_deployment_id: str | None = None,
    deployment_is_explicitly_pinned: bool = False,
    adapter_contract_version: str = GOVERNED_EMBEDDING_ADAPTER_CONTRACT_VERSION,
    sanitized_endpoint_identity: str = "https://provider.example/v1",
) -> ModelResolutionContext:
    return ModelResolutionContext(
        provider_kind=provider_kind,
        sanitized_endpoint_identity=sanitized_endpoint_identity,
        requested_model=requested_model,
        configured_deployment_id=configured_deployment_id,
        deployment_is_explicitly_pinned=deployment_is_explicitly_pinned,
        adapter_contract_version=adapter_contract_version,
    )


def _evidence(
    provider_kind: str,
    requested_model: str = "any-model",
    *,
    reported_model: str | None = None,
    deployment_id: str | None = None,
    provider_revision: str | None = None,
    evidence_source: str = EVIDENCE_SOURCE_CONFIGURED_ONLY,
) -> ProviderModelIdentityEvidence:
    return ProviderModelIdentityEvidence(
        provider_kind=provider_kind,
        requested_model=requested_model,
        reported_model=reported_model,
        deployment_id=deployment_id,
        provider_revision=provider_revision,
        evidence_source=evidence_source,
    )


# ── Generic activation rules ──────────────────────────────────────────


class TestActivationDerivation:
    def test_exact_revision_is_activation_eligible(self):
        decision = classify_model_resolution(
            _evidence(
                "ollama", "nomic-embed-text",
                provider_revision="sha256:" + "a" * 64,
                reported_model="nomic-embed-text",
                evidence_source=EVIDENCE_SOURCE_OLLAMA_API_SHOW_DIGEST,
            ),
            _ctx("ollama", "nomic-embed-text"),
        )
        assert decision.posture == "exact_revision"
        assert decision.activation_eligible is True

    def test_stable_deployment_is_activation_eligible(self):
        decision = classify_model_resolution(
            _evidence("openai", "text-embedding-3-small",
                      reported_model="text-embedding-3-small",
                      evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL),
            _ctx("openai", "text-embedding-3-small",
                 configured_deployment_id="deployment-prod-1",
                 deployment_is_explicitly_pinned=True),
        )
        assert decision.posture == "stable_deployment"
        assert decision.activation_eligible is True

    def test_alias_only_is_not_activation_eligible(self):
        decision = classify_model_resolution(
            _evidence("openai", "text-embedding-3-small",
                      reported_model="text-embedding-3-small"),
            _ctx("openai", "text-embedding-3-small"),
        )
        assert decision.posture == "alias_only"
        assert decision.activation_eligible is False

    def test_decision_is_frozen(self):
        decision = classify_model_resolution(
            _evidence("openai", "m", reported_model="m"),
            _ctx("openai", "m"),
        )
        with pytest.raises(AttributeError):
            decision.activation_eligible = True  # type: ignore[misc]
        with pytest.raises(AttributeError):
            decision.posture = "exact_revision"  # type: ignore[misc]


# ── OpenAI ────────────────────────────────────────────────────────────


class TestOpenAIClassification:
    def test_response_model_only_is_alias_only(self):
        decision = classify_model_resolution(
            _evidence("openai", "text-embedding-3-small",
                      reported_model="text-embedding-3-small",
                      evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL),
            _ctx("openai", "text-embedding-3-small"),
        )
        assert decision.posture == "alias_only"
        assert decision.evidence_code == EVIDENCE_CODE_RESPONSE_MODEL_ALIAS_ONLY

    def test_configured_only_is_alias_only(self):
        # response.model missing -> NULL honestly -> configured-only evidence
        decision = classify_model_resolution(
            _evidence("openai", "text-embedding-3-small", reported_model=None),
            _ctx("openai", "text-embedding-3-small"),
        )
        assert decision.posture == "alias_only"
        assert decision.evidence_code == EVIDENCE_CODE_CONFIGURED_MODEL_ALIAS_ONLY

    def test_explicit_pinned_deployment_is_stable(self):
        decision = classify_model_resolution(
            _evidence("openai", "text-embedding-3-small",
                      reported_model="text-embedding-3-small"),
            _ctx("openai", "text-embedding-3-small",
                 configured_deployment_id="azure-deployment-1",
                 deployment_is_explicitly_pinned=True),
        )
        assert decision.posture == "stable_deployment"
        assert decision.evidence_code == EVIDENCE_CODE_PINNED_DEPLOYMENT_IDENTITY
        assert decision.activation_eligible is True

    def test_deployment_id_without_pin_stays_alias_only(self):
        # Per directive: 'deployment ID without pin -> alias_only or
        # contract rejection'. We choose alias_only rather than reject —
        # a deployment-looking identifier without operator pin intent
        # is not enforceable routing.
        decision = classify_model_resolution(
            _evidence("openai", "m", reported_model="m",
                      deployment_id="deployment-looking"),
            _ctx("openai", "m",
                 configured_deployment_id="deployment-looking",
                 deployment_is_explicitly_pinned=False),
        )
        assert decision.posture == "alias_only"

    def test_response_echo_not_promoted_to_stable(self):
        # The directive: 'Do not classify ordinary OpenAI model names as
        # stable merely because the response echoes them.'
        decision = classify_model_resolution(
            _evidence("openai", "text-embedding-3-small",
                      reported_model="text-embedding-3-small"),
            _ctx("openai", "text-embedding-3-small"),
        )
        assert decision.posture != "stable_deployment"
        assert decision.posture != "exact_revision"


# ── Gemini ────────────────────────────────────────────────────────────


class TestGeminiClassification:
    def test_configured_model_only_is_alias_only(self):
        decision = classify_model_resolution(
            _evidence("gemini", "models/embedding-001",
                      evidence_source="gemini_configured_model"),
            _ctx("gemini", "models/embedding-001"),
        )
        assert decision.posture == "alias_only"
        assert decision.evidence_code == EVIDENCE_CODE_CONFIGURED_MODEL_ALIAS_ONLY

    def test_sdk_reported_model_name_is_alias_only(self):
        # Even if a future SDK revision starts populating reported_model,
        # the directive says SDK-reported model names alone are alias_only.
        decision = classify_model_resolution(
            _evidence("gemini", "models/embedding-001",
                      reported_model="models/embedding-001"),
            _ctx("gemini", "models/embedding-001"),
        )
        assert decision.posture == "alias_only"


# ── Ollama ────────────────────────────────────────────────────────────


class TestOllamaClassification:
    def test_valid_digest_is_exact_revision(self):
        decision = classify_model_resolution(
            _evidence("ollama", "nomic-embed-text",
                      provider_revision="sha256:" + "abcdef0123456789" * 4,
                      reported_model="nomic-embed-text",
                      evidence_source=EVIDENCE_SOURCE_OLLAMA_API_SHOW_DIGEST),
            _ctx("ollama", "nomic-embed-text"),
        )
        assert decision.posture == "exact_revision"
        assert decision.evidence_code == EVIDENCE_CODE_OLLAMA_MODEL_DIGEST
        assert decision.activation_eligible is True

    def test_tag_without_digest_is_alias_only(self):
        decision = classify_model_resolution(
            _evidence("ollama", "nomic-embed-text:latest",
                      reported_model="nomic-embed-text:latest",
                      evidence_source=EVIDENCE_SOURCE_OLLAMA_RESPONSE),
            _ctx("ollama", "nomic-embed-text:latest"),
        )
        assert decision.posture == "alias_only"
        assert decision.evidence_code == EVIDENCE_CODE_OLLAMA_MODEL_TAG_ONLY

    def test_invalid_digest_raises_bounded_failure(self):
        # Per directive: 'invalid digest -> bounded validation failure'
        with pytest.raises(EmbeddingRevisionInvalid) as excinfo:
            classify_model_resolution(
                _evidence("ollama", "nomic-embed-text",
                          provider_revision="not-a-real-digest"),
                _ctx("ollama", "nomic-embed-text"),
            )
        assert excinfo.value.failure_code == "embedding_revision_invalid"

    def test_best_effort_probe_unavailable_is_alias_only(self):
        # When /api/show failed or returned no digest, the provider leaves
        # provider_revision NULL. Classifier returns alias_only honestly.
        decision = classify_model_resolution(
            _evidence("ollama", "nomic-embed-text",
                      provider_revision=None,
                      reported_model="nomic-embed-text",
                      evidence_source=EVIDENCE_SOURCE_OLLAMA_RESPONSE),
            _ctx("ollama", "nomic-embed-text"),
        )
        assert decision.posture == "alias_only"

    def test_short_hex_digest_rejected(self):
        # 32 hex chars is the minimum; 16 is too short.
        with pytest.raises(EmbeddingRevisionInvalid):
            classify_model_resolution(
                _evidence("ollama", "m", provider_revision="sha256:0123456789abcdef"),
                _ctx("ollama", "m"),
            )

    def test_non_sha256_algo_digest_accepted(self):
        # Ollama could introduce other digest algorithms. The classifier
        # accepts "<algo>:<32+ hex>" rather than hard-coding sha256.
        decision = classify_model_resolution(
            _evidence("ollama", "m",
                      provider_revision="blake3:" + "a" * 64),
            _ctx("ollama", "m"),
        )
        assert decision.posture == "exact_revision"


# ── LM Studio ─────────────────────────────────────────────────────────


class TestLMStudioClassification:
    def test_configured_model_only_is_alias_only(self):
        decision = classify_model_resolution(
            _evidence("lmstudio", "text-embedding-bge-m3-embeddings",
                      deployment_id="text-embedding-bge-m3-embeddings",
                      reported_model="text-embedding-bge-m3-embeddings",
                      evidence_source=EVIDENCE_SOURCE_LMSTUDIO_RESPONSE_MODEL),
            _ctx("lmstudio", "text-embedding-bge-m3-embeddings"),
        )
        assert decision.posture == "alias_only"
        assert decision.evidence_code == EVIDENCE_CODE_LMSTUDIO_MODEL_NAME_ONLY

    def test_resolved_model_rewrite_alone_is_alias_only(self):
        # service_registry.py:63-77 rewrites the configured model name via
        # /v1/models. That rewrite alone does not prove stability.
        decision = classify_model_resolution(
            _evidence("lmstudio", "text-embedding-bge-m3-embeddings",
                      deployment_id="text-embedding-bge-m3-embeddings",
                      reported_model="text-embedding-bge-m3-embeddings"),
            _ctx("lmstudio", "text-embedding-bge-m3-embeddings"),
        )
        assert decision.posture == "alias_only"

    def test_dedicated_looking_url_does_not_promote(self):
        # A dedicated-looking endpoint URL alone is not enforceable routing
        decision = classify_model_resolution(
            _evidence("lmstudio", "m", reported_model="m"),
            _ctx("lmstudio", "m",
                 sanitized_endpoint_identity="http://gpu-box-1.local:1234/v1"),
        )
        assert decision.posture == "alias_only"

    def test_no_fictitious_pinning_flag_introduced(self):
        # Per directive: 'Do not introduce a fictitious pinning flag solely
        # to make the classifier return stable_deployment.'
        # Confirm: without context.deployment_is_explicitly_pinned=True,
        # LM Studio is always alias_only regardless of evidence shape.
        for evidence in [
            _evidence("lmstudio", "m", reported_model="m"),
            _evidence("lmstudio", "m", deployment_id="dep", reported_model="m"),
            _evidence("lmstudio", "m", provider_revision="sha256:" + "0" * 64),
        ]:
            decision = classify_model_resolution(
                evidence,
                _ctx("lmstudio", "m",
                     deployment_is_explicitly_pinned=False),
            )
            assert decision.posture == "alias_only", (
                f"LM Studio must remain alias_only without explicit pin; "
                f"got {decision.posture} for evidence {evidence}"
            )


# ── Contradictions ────────────────────────────────────────────────────


class TestContradictionsNeverDegradeToAliasOnly:
    def test_provider_kind_mismatch_raises(self):
        with pytest.raises(EmbeddingIdentityEvidenceConflict) as excinfo:
            classify_model_resolution(
                _evidence("openai", "m", reported_model="m"),
                _ctx("gemini", "m"),  # context says gemini, evidence says openai
            )
        assert excinfo.value.failure_code == "embedding_identity_evidence_conflict"

    def test_requested_model_mismatch_raises(self):
        with pytest.raises(EmbeddingIdentityEvidenceConflict) as excinfo:
            classify_model_resolution(
                _evidence("openai", "requested-A", reported_model="A"),
                _ctx("openai", "requested-B"),  # different requested model
            )
        assert excinfo.value.failure_code == "embedding_identity_evidence_conflict"

    def test_pin_claimed_but_deployment_id_absent_raises(self):
        with pytest.raises(EmbeddingDeploymentPinIncomplete) as excinfo:
            classify_model_resolution(
                _evidence("openai", "m", reported_model="m"),
                _ctx("openai", "m",
                     configured_deployment_id=None,
                     deployment_is_explicitly_pinned=True),
            )
        assert excinfo.value.failure_code == "embedding_deployment_pin_incomplete"

    def test_unsupported_provider_raises(self):
        with pytest.raises(EmbeddingProviderUnsupported) as excinfo:
            classify_model_resolution(
                _evidence("cohere", "m", reported_model="m"),
                _ctx("cohere", "m"),
            )
        assert excinfo.value.failure_code == "embedding_provider_unsupported"

    def test_missing_adapter_contract_version_raises(self):
        with pytest.raises(EmbeddingAdapterContractVersionAbsent) as excinfo:
            classify_model_resolution(
                _evidence("openai", "m", reported_model="m"),
                _ctx("openai", "m", adapter_contract_version=""),
            )
        assert excinfo.value.failure_code == "embedding_adapter_contract_version_absent"

    def test_invalid_ollama_revision_does_not_silently_become_alias_only(self):
        # This is the core directive requirement: invalid revision MUST
        # raise, not degrade to alias_only.
        with pytest.raises(EmbeddingRevisionInvalid):
            classify_model_resolution(
                _evidence("ollama", "m", provider_revision="garbage"),
                _ctx("ollama", "m"),
            )


# ── Determinism ───────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_inputs_produce_equal_decisions(self):
        ev = _evidence("openai", "text-embedding-3-small",
                       reported_model="text-embedding-3-small")
        ctx = _ctx("openai", "text-embedding-3-small")

        d1 = classify_model_resolution(ev, ctx)
        d2 = classify_model_resolution(ev, ctx)
        d3 = classify_model_resolution(ev, ctx)

        assert d1 == d2 == d3
        # Hashable and equal hash (supports binding-fingerprint use)
        assert hash(d1) == hash(d2) == hash(d3)

    def test_classifier_version_in_context_participates_in_decision_identity(self):
        # Per directive: 'changed classifier version -> new future binding
        # identity'. The decision itself is the same posture, but the
        # context that produced it carries a different classifier_version,
        # so a future binding hash over (decision + context) will differ.
        ev = _evidence("openai", "m", reported_model="m")
        ctx_v1 = _ctx("openai", "m")
        ctx_v2 = ModelResolutionContext(
            provider_kind="openai",
            sanitized_endpoint_identity="https://provider.example/v1",
            requested_model="m",
            configured_deployment_id=None,
            deployment_is_explicitly_pinned=False,
            adapter_contract_version=GOVERNED_EMBEDDING_ADAPTER_CONTRACT_VERSION,
            classifier_version="model_resolution_classifier_v2_EXPERIMENTAL",
        )
        d1 = classify_model_resolution(ev, ctx_v1)
        d2 = classify_model_resolution(ev, ctx_v2)

        # Same posture, same activation — but produced under different
        # classifier versions, so the inputs that generated them are
        # distinct and a binding hash that includes context would differ.
        assert d1.posture == d2.posture
        assert d1.activation_eligible == d2.activation_eligible
        assert ctx_v1.classifier_version != ctx_v2.classifier_version
        assert ctx_v1.classifier_version == MODEL_RESOLUTION_CLASSIFIER_V1
