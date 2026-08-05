"""Pipeline result dataclass — shared across pipeline modules."""

from __future__ import annotations

import json as _json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport
from backend.pipeline.gap_analysis.models import ClusterReport, ResearchGap
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

if TYPE_CHECKING:
    from backend.pipeline.evaluation.pipeline_evaluator import UnifiedEvaluationReport


class PipelineOutcome(StrEnum):
    """Authoritative terminal outcome of a pipeline run.

    Replaces inference-from-empty-collections. A run starts ``running`` and
    transitions to exactly one terminal value when the pipeline halts.

    - ``running``: not yet terminal (in progress)
    - ``succeeded``: all selected stages completed and produced artifacts
    - ``no_research_gap``: a stage correctly identified no research gap;
      transport-completed but no paper is produced
    - ``failed_output_contract``: a stage's output failed the typed contract
    - ``failed_execution``: a stage's provider/transport failed after retries
    """

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    NO_RESEARCH_GAP = "no_research_gap"
    FAILED_OUTPUT_CONTRACT = "failed_output_contract"
    FAILED_EXECUTION = "failed_execution"

    @property
    def is_terminal(self) -> bool:
        return self is not PipelineOutcome.RUNNING

    @property
    def is_failure(self) -> bool:
        return self in {
            PipelineOutcome.FAILED_OUTPUT_CONTRACT,
            PipelineOutcome.FAILED_EXECUTION,
        }


@dataclass
class StageReport:
    """Per-stage execution report for observability (BATCH-173).

    Status vocabulary (8 states):
    - "executed": Stage ran and completed
    - "skipped_by_strategy": Stage not in strategy preset
    - "skipped_by_gate": Stage disabled by run_* boolean
    - "skipped_by_doom": Optional stage skipped due to doom loop
    - "skipped_by_error": Stage raised exception, caught by HB-02
    - "skipped_by_policy": Stage denied by governance/approval gate
    - "not_reached": Stage after a fatal error or terminalization
    - "contract_violation": Stage ran but output failed contract check
    - "execution_failed": Stage's provider/transport failed after retries
    """

    name: str
    status: str
    elapsed_s: float = 0.0
    error: str | None = None
    skip_reason: str | None = None
    retries_used: int = 0  # BATCH-176: LLM rate-limit retries consumed
    contract_violations: list[str] | None = None  # Phase D: contract check results
    data_quality: dict | None = None  # Phase E: output quality metrics
    stage_name: str = ""  # Canonical stage name from _STAGE_ORDER

    def to_dict(self) -> dict:
        return asdict(self)




@dataclass
class PipelineResult:
    """Complete output of a pipeline run."""

    ideas: list[ResearchIdea] = field(default_factory=list)
    novelty_reports: dict[int, NoveltyReport] = field(default_factory=dict)
    novelty_profiles: dict[int, Any] = field(default_factory=dict)   # dict[int, NoveltyProfile]
    downstream_directives: dict[int, Any] = field(default_factory=dict)  # dict[int, DownstreamDirectives]
    feasibility_reports: dict[int, FeasibilityReport] = field(default_factory=dict)
    proposals: dict[int, ResearchProposal] = field(default_factory=dict)
    gaps: list[ResearchGap] = field(default_factory=list)
    cluster_report: ClusterReport | None = None
    papers_found: int = 0
    export_paths: dict[int, str] = field(default_factory=dict)
    critique_history: dict[int, list] = field(default_factory=dict)
    refinement_history: dict[int, list[dict]] = field(default_factory=dict)
    evaluation_reports: dict[int, UnifiedEvaluationReport] = field(default_factory=dict)
    mechanical_metrics: dict[int, dict[str, float]] = field(default_factory=dict)  # BATCH-64
    # Phase 5: empirical experiment results (proposal_idx -> manifest)
    experiments: dict[int, Any] = field(default_factory=dict)  # dict[int, ExperimentManifest]
    result_markers: dict[int, list] = field(default_factory=dict)  # dict[int, list[ResultMarker]]
    run_id: str = ""
    params_used: dict = field(default_factory=dict)
    persistence_warnings: list[str] = field(default_factory=list)
    tree_data: dict | None = None  # Serialized tree structure for frontend (HB-03: max 500KB)
    quality_report: dict | None = None  # Phase 8: Pipeline quality evaluation results
    stage_report: list = field(default_factory=list)  # list[StageReport] (BATCH-173)
    # Typed terminal outcome (replaces inference from empty collections).
    # StrEnum members are immutable, so they are safe as dataclass defaults.
    outcome: PipelineOutcome = PipelineOutcome.RUNNING
    terminal_stage: str | None = None
    terminal_reason: str | None = None
