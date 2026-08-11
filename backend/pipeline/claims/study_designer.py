"""StudyDesigner — LLM-grounded study design generation.

AIV v5.3 — BATCH-127 (original) → BATCH-134 (LLM deepening)
Falls back to template generation on LLM failure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from backend.pipeline.utils.json_extraction import extract_json

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "study_design.md"


@dataclass
class MVPExperiment:
    name: str
    hypothesis_tested: str
    pseudocode: str
    expected_runtime: str = "< 1 hour"
    required_resources: str = "Single GPU"
    success_criteria: str = ""
    failure_criteria: str = ""
    interpretation_if_success: str = ""  # Pre-registered: what success means
    interpretation_if_failure: str = ""  # Pre-registered: what failure means
    next_step_if_success: str = ""   # Action on success
    next_step_if_failure: str = ""   # Action on failure


@dataclass
class GoNoGoCriteria:
    metric: str
    threshold: str
    action_if_pass: str = "Proceed"
    action_if_fail: str = "Revise"


@dataclass
class StudyDesign:
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
    """Generate full study designs from research ideas using LLM."""

    def __init__(self, provider=None) -> None:
        self._provider = provider
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text(encoding="utf-8")
        return "Generate a study design for this idea:\n\nTitle: {title}\nProblem: {problem_statement}\nMethod: {proposed_method}"

    def design_from_idea(self, idea: dict) -> StudyDesign:
        """Create a StudyDesign from an idea dict."""
        title = idea.get("title", "Untitled")
        problem = idea.get("problem_statement", "")
        method = idea.get("proposed_method", "")

        if self._provider is not None:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                return self._design_template(title, problem, method)
            else:
                try:
                    return asyncio.run(self._design_with_llm(title, problem, method))
                except Exception as e:
                    logger.warning("LLM study design failed, falling back to template: %s", e)
                    return self._design_template(title, problem, method)
        else:
            return self._design_template(title, problem, method)

    async def _design_with_llm(self, title: str, problem: str, method: str) -> StudyDesign:
        """Use LLM to generate a grounded study design."""
        prompt = self._prompt_template
        prompt = prompt.replace("{title}", title)
        prompt = prompt.replace("{problem_statement}", problem)
        prompt = prompt.replace("{proposed_method}", method)

        messages = [{"role": "user", "content": prompt}]
        response = await self._provider.complete(messages, temperature=0.3, max_tokens=1024)

        # Parse JSON from response
        result = extract_json(response)

        mvp_data = result.get("mvp_experiment", {})
        mvp = MVPExperiment(
            name=mvp_data.get("name", f"MVP: {method}"),
            hypothesis_tested=mvp_data.get("hypothesis_tested", ""),
            pseudocode=mvp_data.get("pseudocode", ""),
            expected_runtime=mvp_data.get("expected_runtime", "< 1 hour"),
            required_resources=mvp_data.get("required_resources", "Single GPU"),
            success_criteria=mvp_data.get("success_criteria", ""),
            failure_criteria=mvp_data.get("failure_criteria", ""),
            interpretation_if_success=mvp_data.get("interpretation_if_success", ""),
            interpretation_if_failure=mvp_data.get("interpretation_if_failure", ""),
            next_step_if_success=mvp_data.get("next_step_if_success", ""),
            next_step_if_failure=mvp_data.get("next_step_if_failure", ""),
        )

        go_no_go = [
            GoNoGoCriteria(
                metric=g.get("metric", ""),
                threshold=g.get("threshold", ""),
                action_if_pass=g.get("action_if_pass", "Proceed"),
                action_if_fail=g.get("action_if_fail", "Revise"),
            )
            for g in result.get("go_no_go", [])
        ]

        return StudyDesign(
            idea_title=title,
            hypothesis_main=result.get("hypothesis_main", ""),
            hypothesis_null=result.get("hypothesis_null", ""),
            mechanistic_rationale=result.get("mechanistic_rationale", ""),
            mvp_experiment=mvp,
            go_no_go=go_no_go,
            risk_assessment=result.get("risk_assessment", []),
            publication_strategy=result.get("publication_strategy", ""),
            timeline_weeks=result.get("timeline_weeks", 8),
        )

    @staticmethod
    def _design_template(title: str, problem: str, method: str) -> StudyDesign:
        """Fallback template generation."""
        return StudyDesign(
            idea_title=title,
            hypothesis_main=f"Applying {method} to {problem} will yield statistically significant improvement over baseline approaches.",
            hypothesis_null=f"Applying {method} to {problem} will yield no significant improvement.",
            mechanistic_rationale=f"{method} addresses {problem} by introducing novel mechanisms.",
            mvp_experiment=MVPExperiment(
                name=f"MVP: {method} on small-scale benchmark",
                hypothesis_tested=f"Does {method} show signal on reduced data?",
                pseudocode=f"# Load small dataset\n# Initialize {method}\n# Train for 100 steps\n# Evaluate",
                success_criteria="Performance > random baseline (p < 0.05)",
                failure_criteria="Performance <= random baseline",
                interpretation_if_success=f"{method} shows promise on {problem} — proceed to full-scale experiment",
                interpretation_if_failure=f"{method} does not show signal on {problem} — revisit approach or hyperparameters",
                next_step_if_success="Scale to full dataset with hyperparameter search",
                next_step_if_failure="Debug implementation, try different hyperparameters",
            ),
            go_no_go=[GoNoGoCriteria(metric="Accuracy", threshold="p < 0.05")],
            risk_assessment=["Method may not generalize", "Compute cost may exceed budget"],
            publication_strategy="Workshop paper → conference",
            timeline_weeks=8,
        )

    def design_from_gap(self, gap: dict) -> StudyDesign:
        return self.design_from_idea({
            "title": gap.get("title", "Gap Study"),
            "problem_statement": gap.get("description", ""),
            "proposed_method": gap.get("suggested_method", "novel approach"),
        })
