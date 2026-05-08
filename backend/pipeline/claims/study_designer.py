"""StudyDesigner — full study proposals with MVP experiments and go/no-go criteria.

AIV v5.3 — BATCH-127
Builds on EvaluationPlanGenerator (B115) but adds hypothesis, MVP experiment,
go/no-go criteria, risk assessment, and publication strategy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MVPExperiment:
    """Minimum viable experiment to validate a hypothesis."""
    name: str
    hypothesis_tested: str
    pseudocode: str
    expected_runtime: str = "< 1 hour"
    required_resources: str = "Single GPU"
    success_criteria: str = ""
    failure_criteria: str = ""


@dataclass
class GoNoGoCriteria:
    """Explicit criteria for deciding whether to proceed."""
    metric: str
    threshold: str
    action_if_pass: str = "Proceed to full experiment"
    action_if_fail: str = "Revise hypothesis or method"


@dataclass
class StudyDesign:
    """A complete study design with MVP experiment and go/no-go criteria."""
    idea_title: str = ""
    hypothesis_main: str = ""
    hypothesis_null: str = ""
    mechanistic_rationale: str = ""
    mvp_experiment: MVPExperiment | None = None
    go_no_go: list[GoNoGoCriteria] = field(default_factory=list)
    risk_assessment: list[str] = field(default_factory=list)
    publication_strategy: str = ""
    timeline_weeks: int = 0


class StudyDesigner:
    """Generate full study designs from research ideas/gaps."""

    def design_from_idea(self, idea: dict) -> StudyDesign:
        """Create a StudyDesign from an idea dict.

        Args:
            idea: Dict with title, problem_statement, proposed_method keys.

        Returns:
            StudyDesign with MVP experiment and go/no-go criteria.
        """
        title = idea.get("title", "Untitled")
        problem = idea.get("problem_statement", "")
        method = idea.get("proposed_method", "")

        return StudyDesign(
            idea_title=title,
            hypothesis_main=f"Applying {method} to {problem} will yield statistically significant improvement over baseline approaches.",
            hypothesis_null=f"Applying {method} to {problem} will yield no significant improvement over baseline approaches.",
            mechanistic_rationale=f"{method} addresses {problem} by introducing novel mechanisms that should improve performance based on theoretical grounds.",
            mvp_experiment=MVPExperiment(
                name=f"MVP: {method} on small-scale benchmark",
                hypothesis_tested=f"Does {method} show any signal on a reduced dataset?",
                pseudocode=f"# Load small dataset\n# Initialize {method}\n# Train for 100 steps\n# Evaluate on held-out set\n# Compare to random baseline",
                expected_runtime="< 30 minutes",
                required_resources="Single GPU / CPU",
                success_criteria="Performance > random baseline (p < 0.05)",
                failure_criteria="Performance <= random baseline",
            ),
            go_no_go=[
                GoNoGoCriteria(
                    metric="Accuracy / Loss",
                    threshold="Statistically better than random (p < 0.05)",
                    action_if_pass="Scale up to full dataset",
                    action_if_fail="Revise method or try different hyperparameters",
                ),
            ],
            risk_assessment=[
                "Method may not generalize to full-scale data",
                "Computational cost may exceed budget",
                "Baseline methods may already be optimized for this problem",
            ],
            publication_strategy="If MVP succeeds, target workshop paper → conference submission",
            timeline_weeks=8,
        )

    def design_from_gap(self, gap: dict) -> StudyDesign:
        """Create a StudyDesign from a research gap dict."""
        return self.design_from_idea({
            "title": gap.get("title", "Gap Study"),
            "problem_statement": gap.get("description", ""),
            "proposed_method": gap.get("suggested_method", "novel approach"),
        })
