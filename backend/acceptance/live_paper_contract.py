"""Typed acceptance contract for the live-paper proof.

A ``LivePaperAcceptanceCase`` is a frozen, validated manifest that drives
the existing runner in acceptance mode. It carries the artifact class, the
research input, the provider/model identity, the budget, the execution
policy, and the acceptance gates.

The frozen artifact class is deliberately narrow:

    complete research-synthesis/design paper
    non-empirical
    real literature only
    no asserted experimental results
    proposed method allowed
    evaluation plan allowed

This prevents the pipeline from passing by emitting a proposal, an outline,
a section template, invented benchmark results, or unsupported claims of
improvement.

Validation rejects:
- unknown fields (extra forbidden)
- blank identifiers
- negative budgets
- unsupported artifact classes
- live mode without a provider/model
- frozen-corpus mode without a corpus manifest
- mismatched search and network policies
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ArtifactClass(StrEnum):
    """The kind of paper this acceptance case expects.

    Frozen to ``non_empirical_research_synthesis`` for the first live-proof
    class. ERLab must not manufacture "results" for experiments it did not
    perform.
    """

    NON_EMPIRICAL_RESEARCH_SYNTHESIS = "non_empirical_research_synthesis"


class CorpusMode(StrEnum):
    """How the research evidence enters the pipeline.

    - ``synthetic``: deterministic synthetic papers (hermetic rehearsal only)
    - ``frozen_real``: a fixed, hashed body of real papers (first live proof)
    - ``live_search``: real literature retrieval (Phase C)
    """

    SYNTHETIC = "synthetic"
    FROZEN_REAL = "frozen_real"
    LIVE_SEARCH = "live_search"


class Strategy(StrEnum):
    """The production orchestrator strategy. Frozen to deep_research."""

    DEEP_RESEARCH = "deep_research"


class NetworkPolicy(StrEnum):
    """Network access policy for an acceptance attempt.

    - ``hermetic``: no network access permitted (rehearsal)
    - ``provider_only``: only the configured model/embedding provider
    - ``provider_and_search``: provider + literature search (Phase C)
    """

    HERMETIC = "hermetic"
    PROVIDER_ONLY = "provider_only"
    PROVIDER_AND_SEARCH = "provider_and_search"


class GenerationParameters(BaseModel):
    """Frozen pipeline generation parameters."""

    model_config = ConfigDict(extra="forbid")

    generation_rounds: int = Field(default=1, ge=1)
    ideas_per_round: int = Field(default=1, ge=1)
    max_gaps: int = Field(default=3, ge=1)
    export_format: Literal["markdown", "latex"] = "markdown"


class AcceptanceBudget(BaseModel):
    """Hard budget for a single acceptance attempt.

    Every field is explicit — the live case must not depend on defaults
    hidden in environment variables. ``maximum_cost_usd`` is a HARD ceiling
    enforced before each provider call, not merely reconciled afterward.
    """

    model_config = ConfigDict(extra="forbid")

    maximum_cost_usd: float = Field(ge=0.0)
    maximum_provider_calls: int = Field(ge=1)
    maximum_input_tokens: int = Field(ge=1)
    maximum_output_tokens: int = Field(ge=1)
    maximum_duration_seconds: int = Field(ge=1)
    provider_retry_limit: int = Field(default=3, ge=0)

    @field_validator("maximum_cost_usd")
    @classmethod
    def _nonnegative_cost(cls, v: float) -> float:
        if v < 0.0:
            raise ValueError("maximum_cost_usd must not be negative")
        return v


class ExecutionPolicy(BaseModel):
    """Execution-time requirements enforced before the orchestrator runs."""

    model_config = ConfigDict(extra="forbid")

    require_clean_tree: bool = True
    require_exact_code_sha: bool = True
    require_new_attempt_directory: bool = True
    require_new_database: bool = True
    require_one_run_record: bool = True
    require_one_session_record: bool = True
    require_restart_recovery: bool = True
    network_policy: NetworkPolicy = NetworkPolicy.HERMETIC


class AcceptanceGates(BaseModel):
    """Which hard acceptance gates are active for this case.

    Defaults to the full live-paper gate set. A gate may be disabled only
    when declared in the manifest (e.g. a negative-control case that
    intentionally omits the paper). Disabled gates are still recorded as
    'not_applicable' in the verdict, never silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    code_origin: bool = True
    identity_isolation: bool = True
    pipeline_outcome: bool = True
    mandatory_stages: bool = True
    research_gap: bool = True
    paper_artifact: bool = True
    paper_evaluation: bool = True
    citation_integrity: bool = True
    accounting: bool = True
    export: bool = True
    restart_recovery: bool = True
    human_readability: bool = True


class LivePaperAcceptanceCase(BaseModel):
    """Canonical typed manifest for one live-paper acceptance attempt."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["erlab.live-paper-acceptance.v1"] = "erlab.live-paper-acceptance.v1"
    case_id: str
    artifact_class: ArtifactClass = ArtifactClass.NON_EMPIRICAL_RESEARCH_SYNTHESIS
    research_domain: str
    research_question: str

    expected_code_sha: str
    strategy: Strategy = Strategy.DEEP_RESEARCH

    corpus_mode: CorpusMode
    corpus_manifest_path: str | None = None

    provider: str
    model: str
    embedding_provider: str
    embedding_model: str

    generation_parameters: GenerationParameters = Field(default_factory=GenerationParameters)
    budget: AcceptanceBudget
    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    gates: AcceptanceGates = Field(default_factory=AcceptanceGates)

    # ── Validation ────────────────────────────────────────────────────

    @field_validator("case_id", "research_domain", "research_question",
                     "expected_code_sha", "provider", "model",
                     "embedding_provider", "embedding_model")
    @classmethod
    def _nonblank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a nonblank string")
        return v.strip()

    @field_validator("expected_code_sha")
    @classmethod
    def _sha_shape(cls, v: str) -> str:
        v = v.strip()
        # A git SHA is a 40-char hex string (full) or a short prefix (>=7).
        if len(v) < 7 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("expected_code_sha must be a hex git SHA (>=7 chars)")
        return v

    @model_validator(mode="after")
    def _check_corpus_and_network(self) -> LivePaperAcceptanceCase:
        # frozen_real REQUIRES a corpus manifest path.
        if self.corpus_mode is CorpusMode.FROZEN_REAL and not self.corpus_manifest_path:
            raise ValueError(
                "frozen_real corpus_mode requires corpus_manifest_path"
            )
        # live_search must use a network policy that permits search.
        if (
            self.corpus_mode is CorpusMode.LIVE_SEARCH
            and self.execution.network_policy is NetworkPolicy.HERMETIC
        ):
            raise ValueError(
                "live_search corpus_mode is incompatible with hermetic network_policy"
            )
        # provider_only with live_search is also inconsistent.
        if (
            self.corpus_mode is CorpusMode.LIVE_SEARCH
            and self.execution.network_policy is NetworkPolicy.PROVIDER_ONLY
        ):
            raise ValueError(
                "live_search corpus_mode requires provider_and_search network_policy"
            )
        return self

    # ── Loading helpers ───────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path) -> LivePaperAcceptanceCase:
        """Load and validate a case manifest from a JSON file."""
        text = Path(path).read_text(encoding="utf-8")
        return cls.model_validate_json(text)


# Convenience re-exports for the verdict layer (Phase A3).
__all__ = [
    "ArtifactClass",
    "CorpusMode",
    "Strategy",
    "NetworkPolicy",
    "GenerationParameters",
    "AcceptanceBudget",
    "ExecutionPolicy",
    "AcceptanceGates",
    "LivePaperAcceptanceCase",
]
