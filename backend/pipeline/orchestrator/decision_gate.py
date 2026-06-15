"""Decision Gate — conditional stage re-execution based on quality.

Evaluates pipeline quality after the evaluation stage and decides whether to:
- continue to finalization stages
- loop back to targeted stages (gap_reflection, idea_reflection, proposal_synthesis)
- abort early if quality is hopeless

Inspired by DeepScientist's research loop: baseline → idea → experiment → analysis → decision (retry or finalize).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.result import PipelineResult

logger = logging.getLogger(__name__)


@dataclass
class DecisionResult:
    """Outcome of a decision gate evaluation."""

    action: str  # "continue" | "retry" | "abort"
    reason: str
    quality_score: float
    provenance_coverage: float | None = None
    target_stages: list[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 1


class DecisionGate:
    """Evaluate pipeline quality after evaluation stage.

    Decides whether to continue, retry targeted stages, or abort.

    Quality signals:
    1. Average idea score (from evaluation_reports)
    2. Provenance coverage ratio (from quality_report.provenance)
    3. Contract violations (from stage_report)
    """

    def __init__(
        self,
        quality_threshold: float = 0.45,
        abort_threshold: float = 0.15,
        max_retries: int = 1,
        provenance_min_coverage: float = 0.4,
    ) -> None:
        self._quality_threshold = quality_threshold
        self._abort_threshold = abort_threshold
        self._max_retries = max_retries
        self._provenance_min_coverage = provenance_min_coverage

    def evaluate(self, result: PipelineResult, retry_count: int) -> DecisionResult:
        """Evaluate whether the pipeline should retry, continue, or abort.

        Args:
            result: Current pipeline result.
            retry_count: How many retries have already occurred.

        Returns:
            DecisionResult with the action to take.
        """
        # Compute quality score from evaluation reports
        quality_score = self._compute_quality_score(result)

        # Compute provenance coverage from quality report
        provenance_coverage = self._compute_provenance_coverage(result)

        # Already exhausted retries
        if retry_count >= self._max_retries:
            logger.info(
                "Decision Gate: max retries reached (%d), continuing with score=%.2f",
                retry_count, quality_score,
            )
            return DecisionResult(
                action="continue",
                reason=f"Max retries reached ({retry_count}/{self._max_retries})",
                quality_score=quality_score,
                provenance_coverage=provenance_coverage,
                retry_count=retry_count,
                max_retries=self._max_retries,
            )

        # Abort threshold — quality is hopeless
        if quality_score < self._abort_threshold:
            logger.warning(
                "Decision Gate: aborting (score=%.2f < %.2f)",
                quality_score, self._abort_threshold,
            )
            return DecisionResult(
                action="abort",
                reason=f"Quality score {quality_score:.2f} below abort threshold {self._abort_threshold}",
                quality_score=quality_score,
                provenance_coverage=provenance_coverage,
                retry_count=retry_count,
                max_retries=self._max_retries,
            )

        # Check quality threshold
        if quality_score < self._quality_threshold:
            target_stages = self._select_retry_stages(result, quality_score)
            logger.info(
                "Decision Gate: retrying (score=%.2f < %.2f, attempt %d/%d). "
                "Re-running: %s",
                quality_score, self._quality_threshold,
                retry_count + 1, self._max_retries, target_stages,
            )
            return DecisionResult(
                action="retry",
                reason=f"Quality score {quality_score:.2f} below threshold {self._quality_threshold}",
                quality_score=quality_score,
                provenance_coverage=provenance_coverage,
                target_stages=target_stages,
                retry_count=retry_count,
                max_retries=self._max_retries,
            )

        # Check provenance threshold (only if quality is acceptable)
        if provenance_coverage is not None and provenance_coverage < self._provenance_min_coverage:
            target_stages = ["gap_reflection", "proposal_synthesis"]
            logger.info(
                "Decision Gate: retrying (provenance=%.0f%% < %.0f%%, attempt %d/%d). "
                "Re-running: %s",
                provenance_coverage * 100, self._provenance_min_coverage * 100,
                retry_count + 1, self._max_retries, target_stages,
            )
            return DecisionResult(
                action="retry",
                reason=f"Provenance coverage {provenance_coverage:.0%} below threshold {self._provenance_min_coverage:.0%}",
                quality_score=quality_score,
                provenance_coverage=provenance_coverage,
                target_stages=target_stages,
                retry_count=retry_count,
                max_retries=self._max_retries,
            )

        # All checks passed — continue
        logger.info(
            "Decision Gate: continuing (score=%.2f >= %.2f)",
            quality_score, self._quality_threshold,
        )
        return DecisionResult(
            action="continue",
            reason=f"Quality score {quality_score:.2f} meets threshold",
            quality_score=quality_score,
            provenance_coverage=provenance_coverage,
            retry_count=retry_count,
            max_retries=self._max_retries,
        )

    def _compute_quality_score(self, result: PipelineResult) -> float:
        """Compute average quality score from evaluation reports."""
        if not result.evaluation_reports:
            # Fall back to idea scores
            if result.ideas:
                scores = [i.score for i in result.ideas if hasattr(i, "score")]
                return sum(scores) / len(scores) if scores else 0.0
            return 0.0

        scores = []
        for report in result.evaluation_reports.values():
            # Try composite_score first
            composite = getattr(report, "composite_score", None)
            if composite is not None:
                scores.append(composite)
                continue

            # Fall back to quality_gate_result
            gate = getattr(report, "quality_gate_result", None)
            if gate and hasattr(gate, "composite_score"):
                scores.append(gate.composite_score)

        return sum(scores) / len(scores) if scores else 0.0

    def _compute_provenance_coverage(self, result: PipelineResult) -> float | None:
        """Extract provenance coverage from quality_report."""
        if not result.quality_report:
            return None

        provenance = result.quality_report.get("provenance")
        if not provenance or not isinstance(provenance, dict):
            return None

        coverages = [
            entry.get("coverage_ratio", 0.0)
            for entry in provenance.values()
            if isinstance(entry, dict)
        ]
        if not coverages:
            return None

        return sum(coverages) / len(coverages)

    def _select_retry_stages(self, result: PipelineResult, quality_score: float) -> list[str]:
        """Select which stages to re-run based on quality failure mode."""
        # If ideas are bad, re-run idea generation
        # If proposals are empty/garbage, re-run proposal synthesis
        # Default: re-run from gap_reflection for a fresh angle

        if not result.proposals or all(
            len(getattr(p, "content_md", "") or str(p)) < 500
            for p in result.proposals.values()
        ):
            # Proposals are empty/garbage → re-run from proposal_synthesis
            return ["proposal_synthesis"]

        if result.ideas and all(i.score < 0.3 for i in result.ideas if hasattr(i, "score")):
            # Ideas are all bad → re-run from idea_generation
            return ["idea_generation", "proposal_synthesis"]

        # Generic quality issue → re-run from gap_reflection for fresh angle
        return ["gap_reflection", "proposal_synthesis"]
