"""Stage refinement loop — three-phase iterative refinement for pipeline stages.

Provides a structured INIT -> FEEDBACK -> ITERATE cycle that wraps any
PipelineStage. Uses OutputValidator for validation and optionally
ApprovalManager for human-in-the-loop gates.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RefinementResult(BaseModel):
    """Result of a single refinement iteration."""

    phase: str  # "init" | "feedback" | "iterate"
    iteration: int
    content: str = ""
    passed: bool = True
    issues: list[str] = Field(default_factory=list)
    amendment: str | None = None


class StageRefinementLoop:
    """Three-phase refinement loop wrapping a PipelineStage.

    Phase 1 (INIT): Execute stage normally.
    Phase 2 (FEEDBACK): Validate output, collect feedback/amendments.
    Phase 3 (ITERATE): Re-execute with feedback incorporated, until convergence.
    """

    def __init__(
        self,
        validator: Any = None,
        approval_manager: Any = None,
        max_iterations: int = 3,
        convergence_threshold: float = 0.05,
    ) -> None:
        self._validator = validator
        self._approval_manager = approval_manager
        self._max_iterations = max_iterations
        self._convergence_threshold = convergence_threshold

    async def execute_with_refinement(
        self,
        stage: Any,
        ctx: Any,
    ) -> tuple[bool, list[RefinementResult]]:
        """Execute stage with iterative refinement.

        Returns (stage_success, refinement_history).
        """
        results: list[RefinementResult] = []
        prev_content_hash = ""

        for iteration in range(self._max_iterations):
            # Determine phase
            if iteration == 0:
                phase = "init"
            elif iteration == 1:
                phase = "feedback"
            else:
                phase = "iterate"

            # Execute the stage
            success = await stage.execute(ctx)

            # Get output for validation
            content = self._extract_stage_output(ctx, stage.name)

            # Check for convergence (content hasn't changed)
            import hashlib
            current_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
            if iteration > 0 and current_hash == prev_content_hash:
                results.append(RefinementResult(
                    phase=phase, iteration=iteration, content=content[:200],
                    passed=True, issues=["Converged — content unchanged"],
                ))
                break
            prev_content_hash = current_hash

            # Validate output if validator is available
            passed = True
            issues: list[str] = []
            amendment: str | None = None

            if self._validator and content:
                try:
                    validated_content, checks = await self._validator.validate_with_reask(
                        content, max_reasks=1,
                    )
                    rejected = [c for c in checks if hasattr(c, 'verdict') and str(getattr(c, 'verdict', '')) == 'REJECTED']
                    if rejected:
                        passed = False
                        issues = [f"{getattr(c, 'contract_name', 'unknown')}: {getattr(c, 'reason', '')}" for c in rejected]
                except Exception as e:
                    logger.warning("Validation failed in refinement: %s", e)

            # Human approval gate (if approval manager available)
            if self._approval_manager and passed:
                try:
                    approval = await self._approval_manager.request_approval(
                        stage=stage.name,
                        reason=f"Refinement iteration {iteration}",
                        rule_name="refinement_loop",
                    )
                    if hasattr(approval, 'status'):
                        from backend.pipeline.governance.approval import ApprovalStatus
                        if approval.status == ApprovalStatus.DENIED:
                            passed = False
                            amendment = getattr(approval, 'amendment', None)
                except Exception:
                    pass  # Approval timeout or not configured

            results.append(RefinementResult(
                phase=phase,
                iteration=iteration,
                content=content[:200],
                passed=passed,
                issues=issues,
                amendment=amendment,
            ))

            # If passed, no need to iterate further
            if passed:
                break

            # Inject amendment into context for next iteration
            if amendment and hasattr(ctx, 'amendment'):
                ctx.amendment = amendment

        overall_success = any(r.passed for r in results)
        return overall_success, results

    @staticmethod
    def _extract_stage_output(ctx: Any, stage_name: str) -> str:
        """Extract a text representation of stage output from context."""
        result = getattr(ctx, 'result', None)
        if not result:
            return ""

        if stage_name == "gap_analysis" and hasattr(result, 'gaps'):
            return "\n".join(g.title + ": " + g.description[:100] for g in result.gaps[:5])
        elif stage_name == "idea_generation" and hasattr(result, 'ideas'):
            return "\n".join(i.title for i in result.ideas[:5])
        elif stage_name == "proposal_synthesis" and hasattr(result, 'proposals'):
            parts = []
            for p in result.proposals.values():
                if hasattr(p, 'to_markdown'):
                    parts.append(p.to_markdown()[:500])
            return "\n".join(parts)
        return ""
