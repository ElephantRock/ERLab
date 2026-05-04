"""Pipeline result dataclass — shared across pipeline modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport
from backend.pipeline.gap_analysis.models import ClusterReport, ResearchGap
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

if TYPE_CHECKING:
    from backend.pipeline.evaluation.pipeline_evaluator import UnifiedEvaluationReport


@dataclass
class PipelineResult:
    """Complete output of a pipeline run."""

    ideas: list[ResearchIdea] = field(default_factory=list)
    novelty_reports: dict[int, NoveltyReport] = field(default_factory=dict)
    feasibility_reports: dict[int, FeasibilityReport] = field(default_factory=dict)
    proposals: dict[int, ResearchProposal] = field(default_factory=dict)
    gaps: list[ResearchGap] = field(default_factory=list)
    cluster_report: ClusterReport | None = None
    papers_found: int = 0
    export_paths: dict[int, str] = field(default_factory=dict)
    critique_history: dict[int, list] = field(default_factory=dict)
    refinement_history: dict[int, list[dict]] = field(default_factory=dict)
    evaluation_reports: dict[int, UnifiedEvaluationReport] = field(default_factory=dict)
    run_id: str = ""
    params_used: dict = field(default_factory=dict)
    persistence_warnings: list[str] = field(default_factory=list)
    tree_data: dict | None = None  # Serialized tree structure for frontend (HB-03: max 500KB)
