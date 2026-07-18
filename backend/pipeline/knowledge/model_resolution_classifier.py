"""Pure model-resolution-posture classifier (P0.4B0.2).

Interprets captured provider evidence (B0.1) conservatively and
deterministically to derive one of three postures:

  exact_revision      immutable provider revision available (e.g. Ollama digest)
  stable_deployment   explicit pinned deployment + enforceable routing
  alias_only          model tag/name/echo only

Per directive P0.4B0.2:

  'A provider capability is activation-eligible only when repository-visible
   evidence proves either an immutable model revision or an explicitly
   pinned deployment. Model names, configured aliases, response echoes,
   and dimensions alone always remain alias-only.'

Purity:
  provider requests     0
  database reads        0
  database writes       0
  environment mutation  0
  binding creation      0
  check creation        0

Output depends only on immutable input values; the same canonical inputs
under the same classifier version always produce an identical decision.
This supports later immutable capability-binding creation in P0.4A1.

This module has NO dependency on the providers themselves — it consumes
only the contract dataclasses from embedding_provider_identity plus its
own context/decision dataclasses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


# ── Classifier version ────────────────────────────────────────────────

MODEL_RESOLUTION_CLASSIFIER_V1 = "model_resolution_classifier_v1"


# ── Context and decision contracts ────────────────────────────────────


@dataclass(frozen=True)
class ModelResolutionContext:
    """Provider-level runtime configuration the classifier interprets.

    Frozen; the same evidence + context + classifier version must produce
    the same decision so future capability bindings can hash these values.

    Fields:
        provider_kind: short identifier of the provider family
            ("openai", "gemini", "ollama", "lmstudio"). Must match the
            evidence's provider_kind or the classifier raises a
            contradiction error.
        sanitized_endpoint_identity: routing-only endpoint fingerprint
            (scheme + canonical host + port + bounded base path). No
            credentials, no query string, no API key. Participates in
            binding identity so endpoint changes invalidate bindings.
        requested_model: the model identifier the caller configured.
        configured_deployment_id: deployment identifier that configuration
            has explicitly pinned (e.g. an Azure deployment name). NULL
            when no deployment is pinned. Populating this field alone is
            NOT sufficient for stable_deployment — see
            ``deployment_is_explicitly_pinned``.
        deployment_is_explicitly_pinned: True ONLY when an operator has
            declared an enforceable deployment pin in current
            configuration (not when the adapter merely observed a
            deployment-looking identifier). The directive is explicit
            that "Do not introduce a fictitious pinning flag solely to
            make the classifier return stable_deployment. The future
            configuration contract must provide real operator intent
            and enforceable routing." B0.2 only sets this True when the
            context genuinely carries that intent (which no current
            runtime configuration does — so this is False in B0).
        adapter_contract_version: the GovernedEmbeddingAdapter contract
            version that captured the evidence. Must be non-NULL; a
            missing version is a contradiction error.
        classifier_version: this classifier's version. Defaults to
            MODEL_RESOLUTION_CLASSIFIER_V1; participates in binding
            fingerprint so a classifier change produces new bindings.
    """

    provider_kind: str
    sanitized_endpoint_identity: str
    requested_model: str
    configured_deployment_id: str | None
    deployment_is_explicitly_pinned: bool
    adapter_contract_version: str
    classifier_version: str = MODEL_RESOLUTION_CLASSIFIER_V1


@dataclass(frozen=True)
class ModelResolutionDecision:
    """The classifier's verdict on one (evidence, context) pair.

    Frozen and hashable so future capability bindings can derive their
    identity from canonical JSON over (decision, context, evidence).

    activation_eligible is derived centrally from posture; callers must
    never override it.

        exact_revision     -> True
        stable_deployment  -> True
        alias_only         -> False
    """

    posture: Literal["exact_revision", "stable_deployment", "alias_only"]
    evidence_code: str
    activation_eligible: bool


# ── Frozen evidence-code vocabulary ───────────────────────────────────
#
# Closed set. Each successful decision has EXACTLY ONE evidence_code.
# Contradictions use the failure_code fields of their exception classes
# (defined below), not these evidence_codes. ``alias_only`` is a valid
# posture, not an error bucket — contradictions never degrade silently
# to alias_only.

EVIDENCE_CODE_IMMUTABLE_PROVIDER_REVISION = "immutable_provider_revision"
EVIDENCE_CODE_OLLAMA_MODEL_DIGEST = "ollama_model_digest"
EVIDENCE_CODE_PINNED_DEPLOYMENT_IDENTITY = "pinned_deployment_identity"

EVIDENCE_CODE_RESPONSE_MODEL_ALIAS_ONLY = "response_model_alias_only"
EVIDENCE_CODE_CONFIGURED_MODEL_ALIAS_ONLY = "configured_model_alias_only"
EVIDENCE_CODE_OLLAMA_MODEL_TAG_ONLY = "ollama_model_tag_only"
EVIDENCE_CODE_LMSTUDIO_MODEL_NAME_ONLY = "lmstudio_model_name_only"
EVIDENCE_CODE_INSUFFICIENT_STABILITY_EVIDENCE = "insufficient_stability_evidence"


_ACTIVATION_BY_POSTURE = {
    "exact_revision": True,
    "stable_deployment": True,
    "alias_only": False,
}


# ── Contradiction failures ────────────────────────────────────────────


class ModelResolutionContradictionError(ValueError):
    """Base for all classifier contradictions.

    Per directive: "A contradiction must not degrade silently to
    alias_only; alias-only is a valid posture, not an error bucket."
    Each contradiction has a bounded ``failure_code`` from a closed
    vocabulary so callers can route them deterministically.
    """

    failure_code: str = "embedding_identity_contradiction"


class EmbeddingIdentityEvidenceConflict(ModelResolutionContradictionError):
    """evidence.provider_kind != context.provider_kind, or requested
    models disagree unexpectedly."""

    failure_code = "embedding_identity_evidence_conflict"


class EmbeddingDeploymentPinIncomplete(ModelResolutionContradictionError):
    """deployment pin claimed (deployment_is_explicitly_pinned=True) but
    no configured_deployment_id, or vice versa."""

    failure_code = "embedding_deployment_pin_incomplete"


class EmbeddingRevisionInvalid(ModelResolutionContradictionError):
    """claimed provider_revision is malformed (e.g. not a valid digest
    format for the provider that produced it)."""

    failure_code = "embedding_revision_invalid"


class EmbeddingProviderUnsupported(ModelResolutionContradictionError):
    """provider_kind is not one of the four supported providers."""

    failure_code = "embedding_provider_unsupported"


class EmbeddingAdapterContractVersionAbsent(ModelResolutionContradictionError):
    """adapter_contract_version missing or empty — required for binding
    fingerprint stability."""

    failure_code = "embedding_adapter_contract_version_absent"


# ── Provider-specific validation helpers ──────────────────────────────

# Ollama digests are "sha256:<64 lowercase hex chars>" (or other algos
# Ollama may add later, but always "<algo>:<hex>"). Conservative: require
# the algo:hexdigest shape so we don't accept arbitrary nonempty text
# as an immutable revision. Source: Ollama manifest digest format.
_OLLAMA_DIGEST_RE = re.compile(r"^[a-z0-9]+:[a-f0-9]{32,}$")


def _valid_ollama_digest(revision: str | None) -> bool:
    if not isinstance(revision, str) or not revision:
        return False
    return bool(_OLLAMA_DIGEST_RE.match(revision))


# ── Per-provider classifiers ──────────────────────────────────────────


def _decision(posture: str, evidence_code: str) -> ModelResolutionDecision:
    """Build a decision with centrally-derived activation_eligible."""
    return ModelResolutionDecision(
        posture=posture,  # type: ignore[arg-type]
        evidence_code=evidence_code,
        activation_eligible=_ACTIVATION_BY_POSTURE[posture],
    )


def _classify_openai(
    evidence: "ProviderModelIdentityEvidence",  # forward for type hint
    context: ModelResolutionContext,
) -> ModelResolutionDecision:
    """OpenAI: response.model echo is alias_only. stable_deployment only
    with an explicit pinned deployment identifier AND enforceable routing."""
    # Pinned-deployment path: requires explicit operator intent in context
    # AND a configured deployment id. A bare deployment_id without the
    # explicit pin flag stays alias_only (directive: do not invent pins).
    if context.deployment_is_explicitly_pinned:
        if not context.configured_deployment_id:
            raise EmbeddingDeploymentPinIncomplete(
                "OpenAI context declares deployment_is_explicitly_pinned but "
                "no configured_deployment_id is set"
            )
        return _decision(
            "stable_deployment",
            EVIDENCE_CODE_PINNED_DEPLOYMENT_IDENTITY,
        )

    # Default: response.model echo or configured name only
    # If the provider reported a model in its response, that's evidence of
    # *something*, but it does not prove an immutable revision. Alias-only.
    if evidence.reported_model is not None:
        return _decision(
            "alias_only",
            EVIDENCE_CODE_RESPONSE_MODEL_ALIAS_ONLY,
        )
    return _decision(
        "alias_only",
        EVIDENCE_CODE_CONFIGURED_MODEL_ALIAS_ONLY,
    )


def _classify_gemini(
    evidence: "ProviderModelIdentityEvidence",
    context: ModelResolutionContext,
) -> ModelResolutionDecision:
    """Gemini: configured/SDK model names are alias_only. Process-global
    SDK configuration is not deployment identity. Only an immutable
    provider_revision (none exposed today) or explicitly pinned deployment
    may upgrade the posture."""
    if context.deployment_is_explicitly_pinned:
        if not context.configured_deployment_id:
            raise EmbeddingDeploymentPinIncomplete(
                "Gemini context declares deployment_is_explicitly_pinned but "
                "no configured_deployment_id is set"
            )
        return _decision(
            "stable_deployment",
            EVIDENCE_CODE_PINNED_DEPLOYMENT_IDENTITY,
        )

    # Gemini exposes no immutable revision today; classifier treats all
    # configured/SDK model names as alias-only.
    return _decision(
        "alias_only",
        EVIDENCE_CODE_CONFIGURED_MODEL_ALIAS_ONLY,
    )


def _classify_ollama(
    evidence: "ProviderModelIdentityEvidence",
    context: ModelResolutionContext,
) -> ModelResolutionDecision:
    """Ollama: a valid immutable model digest is sufficient for
    exact_revision. Without it (or with an invalid one), the model
    tag/name is alias_only."""
    # Pinned deployment is rare for Ollama (local), but supported symmetrically
    if context.deployment_is_explicitly_pinned:
        if not context.configured_deployment_id:
            raise EmbeddingDeploymentPinIncomplete(
                "Ollama context declares deployment_is_explicitly_pinned but "
                "no configured_deployment_id is set"
            )
        return _decision(
            "stable_deployment",
            EVIDENCE_CODE_PINNED_DEPLOYMENT_IDENTITY,
        )

    # Digest path: validate the format before accepting it as immutable revision.
    # The directive: "The classifier should validate the expected digest format
    # rather than accepting arbitrary nonempty text as an immutable revision."
    if evidence.provider_revision is not None:
        if not _valid_ollama_digest(evidence.provider_revision):
            raise EmbeddingRevisionInvalid(
                f"Ollama provider_revision is not a valid digest: "
                f"{evidence.provider_revision!r}"
            )
        return _decision(
            "exact_revision",
            EVIDENCE_CODE_OLLAMA_MODEL_DIGEST,
        )

    # No digest, just the model tag -> alias_only
    return _decision(
        "alias_only",
        EVIDENCE_CODE_OLLAMA_MODEL_TAG_ONLY,
    )


def _classify_lmstudio(
    evidence: "ProviderModelIdentityEvidence",
    context: ModelResolutionContext,
) -> ModelResolutionDecision:
    """LM Studio: configured/served model names AND a deployment_id
    populated from the configured model are all alias_only by themselves.
    stable_deployment requires an explicit deployment-pinning contract,
    not merely a dedicated-looking URL.

    Per directive: "Do not introduce a fictitious pinning flag solely to
    make the classifier return stable_deployment. The future configuration
    contract must provide real operator intent and enforceable routing."
    """
    if context.deployment_is_explicitly_pinned:
        if not context.configured_deployment_id:
            raise EmbeddingDeploymentPinIncomplete(
                "LM Studio context declares deployment_is_explicitly_pinned "
                "but no configured_deployment_id is set"
            )
        return _decision(
            "stable_deployment",
            EVIDENCE_CODE_PINNED_DEPLOYMENT_IDENTITY,
        )

    # Default: alias_only. Configured model name, served model name, and
    # the deployment_id-populated-from-configured-model all collapse to
    # the same alias-only evidence code.
    return _decision(
        "alias_only",
        EVIDENCE_CODE_LMSTUDIO_MODEL_NAME_ONLY,
    )


_PROVIDER_CLASSIFIERS = {
    "openai": _classify_openai,
    "gemini": _classify_gemini,
    "ollama": _classify_ollama,
    "lmstudio": _classify_lmstudio,
}


# ── Public entry point ────────────────────────────────────────────────


def classify_model_resolution(
    evidence: "ProviderModelIdentityEvidence",
    context: ModelResolutionContext,
) -> ModelResolutionDecision:
    """Interpret captured evidence + runtime context into a posture decision.

    Pure: no I/O, no side effects, no environment mutation, no binding
    or check creation. Same inputs always produce the same decision
    under the same classifier version.

    Raises one of the ModelResolutionContradictionError subclasses if the
    evidence is internally inconsistent or the context declares a pin
    without the supporting fields. Never degrades silently to alias_only.
    """
    # ── Cross-cutting contradictions (apply to all providers) ──

    if not context.adapter_contract_version:
        raise EmbeddingAdapterContractVersionAbsent(
            "ModelResolutionContext.adapter_contract_version is required "
            "for binding-fingerprint stability; got empty value"
        )

    if evidence.provider_kind != context.provider_kind:
        raise EmbeddingIdentityEvidenceConflict(
            f"evidence.provider_kind ({evidence.provider_kind!r}) does not "
            f"match context.provider_kind ({context.provider_kind!r})"
        )

    # Requested-model disagreement: the evidence and context should agree
    # on what was requested. (Some providers legitimately rewrite the
    # requested model at runtime; if they do, they record the rewritten
    # name in evidence.requested_model, and the caller's context must
    # carry that same rewritten name. A mismatch here means composition
    # drift.)
    if evidence.requested_model != context.requested_model:
        raise EmbeddingIdentityEvidenceConflict(
            f"evidence.requested_model ({evidence.requested_model!r}) does "
            f"not match context.requested_model "
            f"({context.requested_model!r})"
        )

    # deployment_is_explicitly_pinned without a configured_deployment_id
    # is a contradiction in any provider
    if context.deployment_is_explicitly_pinned and not context.configured_deployment_id:
        raise EmbeddingDeploymentPinIncomplete(
            "context.deployment_is_explicitly_pinned is True but "
            "configured_deployment_id is None/empty"
        )

    # ── Provider-specific classification ──

    classifier = _PROVIDER_CLASSIFIERS.get(context.provider_kind)
    if classifier is None:
        raise EmbeddingProviderUnsupported(
            f"provider_kind {context.provider_kind!r} is not one of the "
            f"four supported providers "
            f"({sorted(_PROVIDER_CLASSIFIERS.keys())})"
        )

    return classifier(evidence, context)
