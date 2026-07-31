"""Phase 13 / 13A+13B — typed empirical claim composition.

The model may generate prose but may NOT generate RESULT markers, empirical
values, or achievement/comparison claims. Those are owned by deterministic
renderers and inserted during initial assembly.

13A: deterministic paper components from frozen evidence
13B: provider contract with semantic slots + rejection of provider-created markers
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.evaluation.deterministic_finalizer import (
    build_canonical_title, render_result_claim, render_result_section,
)

logger = logging.getLogger(__name__)

# Semantic slots the provider must include verbatim
SLOT_METHOD = "{{EMPIRICAL_METHOD}}"
SLOT_RESULTS = "{{EMPIRICAL_RESULTS}}"
SLOT_CONCLUSION = "{{EMPIRICAL_CONCLUSION}}"

ALL_SLOTS = [SLOT_METHOD, SLOT_RESULTS, SLOT_CONCLUSION]


@dataclass
class TypedEmpiricalPaper:
    """A paper assembled from deterministic empirical components + model prose."""

    title: str
    abstract: str
    introduction: str
    related_work: str
    methods_block: str  # deterministic
    results_block: str  # deterministic
    discussion: str
    limitations: str
    conclusion_block: str  # deterministic
    references: str

    def assemble(self) -> str:
        """Assemble the complete paper."""
        parts = [
            self.title,
            "",
            self.abstract,
            "",
            "## Introduction",
            self.introduction,
            "",
            "## Related Work",
            self.related_work,
            "",
            "## Methods",
            self.methods_block,
            "",
            "## Results",
            self.results_block,
            "",
            "## Discussion",
            self.discussion,
            "",
            "## Limitations",
            self.limitations,
            "",
            "## Conclusion",
            self.conclusion_block,
            "",
            "## References",
            self.references,
        ]
        return "\n".join(parts)


def build_deterministic_components(
    spec: Any,
    result_markers: list,
) -> dict[str, str]:
    """Build all deterministic paper components from frozen evidence.

    Returns a dict with keys: title, methods_block, results_block, conclusion_block.
    """
    # Title
    title = build_canonical_title(
        dataset_name=spec.dataset_name,
        task_type=spec.task_type or "classification",
        executed_method=spec.analysis_method,
        baseline_method=spec.baseline_method or "baseline",
        primary_metric=spec.primary_metric or "accuracy",
    )

    # Methods block
    method_short = spec.analysis_method.split("(")[0].strip().split(" vs ")[0].strip()
    baseline_short = (spec.baseline_method or "baseline").split("(")[0].strip()
    methods_lines = [
        f"This study evaluates {method_short} against a {baseline_short} baseline.",
        f"Dataset: {spec.dataset_name} ({spec.dataset_name})",
        f"Task: {spec.task_type or 'classification'}",
        f"Split: {spec.split_method} (seed={spec.random_seed})",
        f"Primary metric: {spec.primary_metric or 'accuracy'}",
    ]
    methods_block = "\n".join(methods_lines)

    # Results block (deterministic)
    results_block = render_result_section(
        result_markers,
        executed_method=spec.analysis_method,
        baseline_method=spec.baseline_method or "baseline",
    )

    # Conclusion block (deterministic)
    comparison_markers = [m for m in result_markers if getattr(m, "role", "") == "comparison"]
    baseline_markers = [m for m in result_markers if getattr(m, "role", "") == "baseline"]

    conclusion_lines = []
    if comparison_markers and baseline_markers:
        # Find the primary comparison marker
        primary = comparison_markers[0]
        baseline = baseline_markers[0]
        primary_direction = getattr(primary, "direction", "higher_better")
        primary_metric = getattr(primary, "metric_name", "performance")
        primary_value = getattr(primary, "observed_value", 0)
        baseline_value = getattr(baseline, "observed_value", 0)

        method_short = spec.analysis_method.split("(")[0].strip().split(" vs ")[0].strip()

        if primary_direction == "higher_better":
            if primary_value > baseline_value:
                conclusion_lines.append(
                    f"The {method_short} outperformed the baseline on {primary_metric} "
                    f"({primary_value:.6g} vs {baseline_value:.6g}). "
                    f"[{primary.marker}]"
                )
            else:
                conclusion_lines.append(
                    f"The {method_short} did not outperform the baseline on {primary_metric} "
                    f"({primary_value:.6g} vs {baseline_value:.6g}). "
                    f"[{primary.marker}]"
                )
        elif primary_direction == "lower_better":
            if primary_value < baseline_value:
                conclusion_lines.append(
                    f"The {method_short} achieved lower {primary_metric} than the baseline "
                    f"({primary_value:.6g} vs {baseline_value:.6g}), indicating improvement. "
                    f"[{primary.marker}]"
                )
            else:
                conclusion_lines.append(
                    f"The {method_short} did not achieve lower {primary_metric} than the baseline "
                    f"({primary_value:.6g} vs {baseline_value:.6g}). "
                    f"[{primary.marker}]"
                )
    conclusion_block = "\n".join(conclusion_lines) if conclusion_lines else "See results above."

    return {
        "title": f"# {title}",
        "methods_block": methods_block,
        "results_block": results_block,
        "conclusion_block": conclusion_block,
    }


def validate_provider_output(raw: str) -> tuple[bool, list[str]]:
    """Validate that provider output does not contain forbidden content.

    Rejects:
      - any [RESULT-N] or [RESULT-NN] marker
      - any standalone decimal that looks like an empirical value
      - achievement/comparison claims without a slot
    """
    violations = []

    # 1. Reject any RESULT marker
    if re.search(r'\[RESULT-\d+\]', raw):
        violations.append("Provider output contains [RESULT-N] markers — these are owned by deterministic renderers")

    # 2. Reject achievement claims outside slots
    achievement_patterns = [
        r'(?i)\bachieved\s+(an?\s+)?\d',
        r'(?i)\boutperformed?\s',
        r'(?i)\bsignificantly\s+(improves?|reduces?)\s',
        r'(?i)\bimproved?\s+by\s+\d',
    ]
    for pattern in achievement_patterns:
        if re.search(pattern, raw):
            violations.append(f"Provider output contains an unauthorized empirical achievement claim")

    return (len(violations) == 0, violations)


def build_slot_prompt(
    spec: Any,
    source_papers: list[str],
    proposal_text: str,
    domain: str = "machine learning",
) -> str:
    """Build the provider prompt using semantic slots.

    The provider must include {{EMPIRICAL_METHOD}}, {{EMPIRICAL_RESULTS}},
    and {{EMPIRICAL_CONCLUSION}} verbatim. It must NOT generate RESULT markers
    or empirical values.
    """
    lines = [
        f"## Research Domain\n{domain}\n",
        "## INSTRUCTIONS",
        "",
        "Write an academic paper about the following experiment.",
        "You MUST include these three placeholders EXACTLY as written:",
        f"  {SLOT_METHOD} — in the Methods section",
        f"  {SLOT_RESULTS} — in the Results section",
        f"  {SLOT_CONCLUSION} — in the Conclusion section",
        "",
        "CRITICAL RULES:",
        "1. Do NOT write [RESULT-N] markers. The system will fill them.",
        "2. Do NOT write specific experimental values (like 0.95 or 12.3).",
        "3. Do NOT claim the model 'achieved' or 'outperformed' with specific numbers.",
        "4. Write the abstract, introduction, related work, discussion, and limitations.",
        "5. Include the three placeholders exactly where the deterministic content goes.",
        "",
        f"## Experiment Context",
        f"Dataset: {spec.dataset_name}",
        f"Task: {spec.task_type or 'classification'}",
        f"Method: {spec.analysis_method}",
        f"Baseline: {spec.baseline_method or 'baseline'}",
        f"Primary metric: {spec.primary_metric or 'accuracy'}",
        f"Research question: {spec.research_question}",
        "",
    ]

    if source_papers:
        lines.append("## Supporting Literature (CLOSED-BOOK)\n")
        lines.extend(source_papers)

    if proposal_text:
        lines.append("\n## Research Proposal (for motivation only)\n")
        lines.append(proposal_text)

    lines.append("\n## Paper to Write\n")
    lines.append("Write the paper with the three placeholders. The system will fill them with")
    lines.append("the actual experiment results. Write all non-empirical prose yourself.")

    return "\n".join(lines)


def assemble_typed_paper(
    provider_output: str,
    deterministic: dict[str, str],
) -> tuple[str, list[str]]:
    """Assemble the final paper by filling slots with deterministic content.

    Returns (assembled_paper, warnings).
    """
    warnings = []

    # Validate provider output
    ok, violations = validate_provider_output(provider_output)
    if not ok:
        return "", violations

    # Check all slots present
    missing_slots = [s for s in ALL_SLOTS if s not in provider_output]
    if missing_slots:
        return "", [f"Missing required slots: {missing_slots}"]

    # Fill slots
    paper = provider_output
    paper = paper.replace(SLOT_METHOD, deterministic["methods_block"])
    paper = paper.replace(SLOT_RESULTS, deterministic["results_block"])
    paper = paper.replace(SLOT_CONCLUSION, deterministic["conclusion_block"])

    # Prepend canonical title if provider didn't start with it
    if not paper.strip().startswith("#"):
        paper = deterministic["title"] + "\n\n" + paper
    else:
        # Replace the provider's title line with the canonical title
        paper = re.sub(r'^#[^\n]*', deterministic["title"], paper, count=1)

    return paper, warnings
