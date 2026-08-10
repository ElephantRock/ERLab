"""Novelty data models — structured multi-axis assessment with downstream directives.

Replaces the plain NoveltyReport with Pydantic v2 validated models:
- NoveltyProfile: Complete novelty characterization with 4 axes, search coverage, and prior work
- DownstreamDirectives: Structured parameter changes for 4 downstream stages
- StrategicDirection: LLM-classified category (not threshold-based)

Part of Pillar 6 (Novelty Redesign) in the Comprehensive Solution Design v2.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AxisType(str, Enum):
    """Four axes of novelty decomposition."""
    PROBLEM = "problem"
    METHOD = "method"
    CONTRIBUTION = "contribution"
    COMBINATION = "combination"


class StrategicDirection(str, Enum):
    """LLM-classified strategic direction for a research idea.

    The classification is produced by the thinking provider during novelty
    assessment, NOT derived from mechanical score thresholds.  Each direction
    maps to different downstream directive weights and framing.
    """
    METHODOLOGICAL_INNOVATION = "methodological_innovation"
    CROSS_DOMAIN_BRIDGE = "cross_domain_bridge"
    EMERGENT_PROBLEM_EXPLORATION = "emergent_problem_exploration"
    INCREMENTAL_OPTIMIZATION = "incremental_optimization"
    HIGH_RISK_MOONSHOT = "high_risk_moonshot"


class AxisAssessment(BaseModel):
    """Assessment of novelty along one axis."""
    axis: AxisType
    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_found: list[str] = Field(default_factory=list)
    reasoning: str = ""


class PriorWorkMatch(BaseModel):
    """A prior work entry that was found during novelty search."""
    paper_id: str = ""
    paper_title: str = ""
    overlapping_axis: AxisType = AxisType.METHOD
    similarity: float = Field(0.0, ge=0.0, le=1.0)
    key_difference: str = ""


class SearchCoverage(BaseModel):
    """Track what search queries were run and where blind spots exist."""
    queries_used: list[str] = Field(default_factory=list)
    sources_queried: list[str] = Field(default_factory=list)
    results_per_source: dict[str, int] = Field(default_factory=dict)
    blind_spots_identified: list[str] = Field(default_factory=list)


class NoveltyProfile(BaseModel):
    """Complete novelty characterization of one research idea.

    Replaces NoveltyReport with validated, typed data.  Every field has
    a meaningful default so that partial profiles (e.g. from degraded
    embeddings) are still valid.
    """
    idea_id: str = ""
    strategic_direction: StrategicDirection = StrategicDirection.EMERGENT_PROBLEM_EXPLORATION
    overall_score: float = Field(0.5, ge=0.0, le=1.0)
    overall_confidence: float = Field(0.2, ge=0.0, le=1.0)
    axes: list[AxisAssessment] = Field(default_factory=list)
    closest_prior_work: list[PriorWorkMatch] = Field(default_factory=list)
    differentiations: list[str] = Field(default_factory=list)
    search_coverage: SearchCoverage = Field(default_factory=SearchCoverage)
    novelty_arguments: str = ""
    # P0.3.4F: Retrieval provenance linkage
    retrieval_event_id: int | None = None
    retrieval_mode: str = ""  # governed_vector | legacy_vector | non_vector

    @field_validator("axes")
    @classmethod
    def validate_all_axes_present(cls, v: list) -> list:
        """Warn if not all 4 axes are present, but don't fail."""
        found_axes = {item.axis for item in v}
        required = set(AxisType)
        if found_axes != required:
            missing = required - found_axes
            # Don't fail — degraded profiles may have partial axes
            import logging
            logging.getLogger(__name__).debug(
                "NoveltyProfile: missing axes %s for idea %s",
                missing, "unknown",
            )
        return v


class DownstreamDirectives(BaseModel):
    """Structured parameter changes for downstream stages.

    Generated from NoveltyProfile by NoveltyChecker._build_directives().
    Consumed by FeasibilityScoringStage, ProposalSynthesisStage,
    EvaluationStage, and CitationAuditStage.
    """
    strategic_direction: StrategicDirection = StrategicDirection.EMERGENT_PROBLEM_EXPLORATION
    feasibility_weight_overrides: dict[str, float] = Field(
        default_factory=dict,
        description="Dynamic overrides for feasibility scoring weights.",
    )
    synthesis_framing_directive: str = Field(
        default="",
        description="System prompt injection for proposal synthesizer.",
    )
    evaluation_baseline_requirements: list[str] = Field(
        default_factory=list,
        description="Explicit baselines or validation checks required.",
    )
    required_citations: list[str] = Field(
        default_factory=list,
        description="Paper IDs/DOIs from closest_prior_work that must be cited.",
    )


def build_directives(profile: NoveltyProfile) -> DownstreamDirectives:
    """Translate a NoveltyProfile's strategic direction into downstream directives.

    This is the core mapping function. Each StrategicDirection produces
    different weight overrides, framing text, and baseline requirements.
    """
    direction = profile.strategic_direction
    required_citations = [m.paper_id for m in profile.closest_prior_work if m.paper_id]

    if direction == StrategicDirection.METHODOLOGICAL_INNOVATION:
        return DownstreamDirectives(
            strategic_direction=direction,
            feasibility_weight_overrides={
                "methods": 0.35, "novelty": 0.20,
                "data": 0.10, "compute": 0.10, "eval": 0.15, "impact": 0.10,
            },
            synthesis_framing_directive=(
                "Position this proposal as a methodological breakthrough. "
                "Emphasize the novel technique, provide formal algorithm description, "
                "and include complexity analysis. Cite closest prior work to differentiate."
            ),
            evaluation_baseline_requirements=[
                "Ablation study isolating the novel component",
                "Asymptotic complexity comparison vs prior work",
            ],
            required_citations=required_citations,
        )

    if direction == StrategicDirection.CROSS_DOMAIN_BRIDGE:
        return DownstreamDirectives(
            strategic_direction=direction,
            feasibility_weight_overrides={
                "data": 0.30, "eval": 0.25,
                "methods": 0.10, "compute": 0.10, "novelty": 0.10, "impact": 0.15,
            },
            synthesis_framing_directive=(
                "Frame this as a cross-domain translation. "
                "Show why the source domain's technique applies here, "
                "address distribution shift, and benchmark against both "
                "source and target domain baselines."
            ),
            evaluation_baseline_requirements=[
                "Cross-domain distribution shift test",
                "Comparison against target-domain state-of-the-art",
            ],
            required_citations=required_citations,
        )

    if direction == StrategicDirection.HIGH_RISK_MOONSHOT:
        return DownstreamDirectives(
            strategic_direction=direction,
            feasibility_weight_overrides={
                "novelty": 0.25, "impact": 0.25,
                "methods": 0.15, "data": 0.10, "compute": 0.10, "eval": 0.15,
            },
            synthesis_framing_directive=(
                "Frame as a high-risk, high-reward exploration. "
                "Provide clear success criteria and failure modes. "
                "Include theoretical grounding even if empirical validation is limited."
            ),
            evaluation_baseline_requirements=[
                "Theoretical justification or formal proof sketch",
                "Sensitivity analysis on core assumptions",
            ],
            required_citations=required_citations,
        )

    # Default: INCREMENTAL_OPTIMIZATION or EMERGENT_PROBLEM_EXPLORATION
    return DownstreamDirectives(
        strategic_direction=direction,
        feasibility_weight_overrides={},
        synthesis_framing_directive=(
            "Frame as an incremental improvement. "
            "Provide rigorous empirical comparison against strong baselines. "
            "Quantify improvement with statistical significance."
        ),
        evaluation_baseline_requirements=[
            "Comparison against current state-of-the-art with statistical significance",
        ],
        required_citations=required_citations,
    )
