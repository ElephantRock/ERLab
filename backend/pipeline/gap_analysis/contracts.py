"""Canonical typed contract for gap-analysis provider output.

This module is the single source of truth for the shape of gap-analysis
output. The provider schema is generated directly from the Pydantic
models via ``GapAnalysisPayload.model_json_schema()`` — there is no
separately maintained handwritten JSON Schema.

Defense in depth (mandatory):

    Provider schema constraint   (structured_output schema argument)
        ≠ accepted output
    Provider response
        → Pydantic validation    (model_validate)
        → semantic validation    (cluster IDs exist in ClusterReport)
        → ResearchGap

Exception taxonomy:

    GapAnalysisOutputContractError
        The provider returned a structurally non-conforming payload
        (wrong type, missing/blank fields, out-of-range confidence,
        unknown cluster IDs, extra fields). This is a deterministic,
        retryable-by-fixing-the-prompt failure, not a transport failure.

    GapAnalysisExecutionError
        The provider/transport layer failed (timeout, connection error,
        auth error) after the gateway retry policy was exhausted. This
        is not an output-quality problem.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GapType(StrEnum):
    """Controlled vocabulary for the kind of research gap."""

    METHODOLOGICAL = "methodological"
    EMPIRICAL = "empirical"
    THEORETICAL = "theoretical"
    CROSS_DOMAIN = "cross-domain"


class GapAnalysisOutputContractError(RuntimeError):
    """Raised when nonempty gap-analysis output violates the expected schema.

    Carries only safe structural diagnostics (stage, failure category,
    reason). Raw provider output must never be embedded in the message.
    """


class GapAnalysisExecutionError(RuntimeError):
    """Raised when the provider/transport layer fails after retry exhaustion.

    This is distinct from :class:`GapAnalysisOutputContractError`: an
    execution failure means we never obtained a trustworthy payload at
    all, whereas a contract failure means we obtained a payload that does
    not conform. Execution failures must never be silently converted to
    an empty gap list.
    """


def _nonblank(value: str) -> str:
    if not isinstance(value, str):  # defensive: pydantic coerces, but be explicit
        raise ValueError("must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class GapCandidatePayload(BaseModel):
    """A single typed research-gap candidate from the provider.

    Validation rules:
    - extra fields: forbidden
    - strings: stripped and nonblank
    - gap_type: controlled enum
    - related_clusters: list[int], nonnegative, unique
    - confidence: numeric, 0.0–1.0

    No arbitrary character-count thresholds are imposed.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str
    description: str
    gap_type: GapType
    related_clusters: list[int] = Field(default_factory=list)
    potential_impact: str
    confidence: float

    @field_validator("title", "description", "potential_impact")
    @classmethod
    def _blank_check(cls, v: str) -> str:
        return _nonblank(v)

    @field_validator("confidence")
    @classmethod
    def _confidence_bounds(cls, v: float) -> float:
        if v is None:
            raise ValueError("confidence is required")
        try:
            v = float(v)
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence must be numeric") from exc
        if not (0.0 <= v <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v

    @field_validator("related_clusters")
    @classmethod
    def _cluster_rules(cls, v: list[int]) -> list[int]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("related_clusters must be a list of integers")
        normalized: list[int] = []
        for c in v:
            # Accept ints or int-valued floats; reject anything else so a
            # string like "high" cannot slip through as a cluster id.
            if isinstance(c, bool):  # bool is an int subclass — reject explicitly
                raise ValueError("related_clusters must contain integers, not booleans")
            if isinstance(c, float) and c.is_integer():
                c = int(c)
            if not isinstance(c, int):
                raise ValueError("related_clusters must contain integers")
            if c < 0:
                raise ValueError("related_clusters must be nonnegative")
            normalized.append(c)
        if len(set(normalized)) != len(normalized):
            raise ValueError("related_clusters must be unique")
        return normalized


class GapAnalysisPayload(BaseModel):
    """Wrapper payload returned by the provider for gap analysis.

    The canonical shape is ``{"gaps": [GapCandidatePayload, ...]}``.
    A bare gap-shaped dict (no ``gaps`` wrapper) is accepted defensively
    and treated as a single-element payload, so a model that returns one
    gap object is not silently discarded.
    """

    model_config = ConfigDict(extra="forbid")

    gaps: list[GapCandidatePayload] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_bare_gap(cls, data: Any) -> Any:
        """Accept a single bare gap-shaped dict as a one-element payload."""
        if isinstance(data, dict) and "gaps" not in data:
            # Heuristic: a bare gap carries the canonical gap fields.
            gap_fields = {"title", "description", "gap_type", "related_clusters",
                          "potential_impact", "confidence"}
            if gap_fields <= data.keys():
                return {"gaps": [data]}
        return data

    @field_validator("gaps")
    @classmethod
    def _gaps_must_be_list(cls, v: list[GapCandidatePayload]) -> list[GapCandidatePayload]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("gaps must be a list")
        return v


def _inline_refs(schema: dict, defs: dict) -> dict:
    """Resolve ``$ref`` pointers into inline definitions.

    Local model providers (LM Studio, Ollama) and some structured-output
    endpoints do not resolve ``$ref``/``$defs`` references. Inlining makes
    the canonical schema self-contained and provider-portable: the
    ``gap_type`` enum and nested object shape appear directly.
    """
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            target = defs.get(ref_name, {})
            return _inline_refs(target, defs)
        return {k: _inline_refs(v, defs) for k, v in schema.items() if k != "$defs"}
    if isinstance(schema, list):
        return [_inline_refs(item, defs) for item in schema]
    return schema


def gap_analysis_schema() -> dict:
    """Return the canonical provider JSON schema for gap analysis.

    Generated directly from the Pydantic model via
    ``GapAnalysisPayload.model_json_schema()``, with ``$ref``/``$defs``
    inlined for provider portability. There is no separately maintained
    handwritten JSON Schema.
    """
    raw = GapAnalysisPayload.model_json_schema()
    defs = raw.get("$defs", {})
    inlined = _inline_refs(raw, defs)
    return inlined
