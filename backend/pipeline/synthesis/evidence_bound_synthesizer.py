"""Phase 12 / 12B+12C — evidence-bound paper synthesis.

Generates a paper with deterministic empirical sections injected before the
LLM call. The title, result sentences, and key empirical claims are fixed
from persisted evidence — the LLM cannot override them.

12B: deterministic title + RESULT renderers at synthesis time
12C: evidence-bound paper skeleton
12D: proposal creativity separated into evaluated vs future work
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.evaluation.deterministic_finalizer import (
    build_canonical_title, render_result_claim, render_result_section,
)

logger = logging.getLogger(__name__)


@dataclass
class EvidenceBoundContext:
    """All deterministic content injected into the synthesis prompt."""

    canonical_title: str
    experiment_description: str
    result_sentences: str
    methods_description: str
    abstract_constraints: str
    conclusion_constraints: str
    proposal_creativity_note: str

    def build_evidence_bound_prompt_block(self) -> str:
        """Build the evidence-bound block that constrains the LLM."""
        lines = [
            "## EVIDENCE-BOUND CONTENT (these sections are FIXED — do not change them)",
            "",
            "### TITLE (use exactly this):",
            self.canonical_title,
            "",
            "### RESULTS SECTION (include these sentences verbatim):",
            self.result_sentences,
            "",
            "### EXPERIMENT DESCRIPTION (the paper's central experiment):",
            self.experiment_description,
            "",
            "### ABSTRACT REQUIREMENTS:",
            self.abstract_constraints,
            "",
            "### CONCLUSION REQUIREMENTS:",
            self.conclusion_constraints,
            "",
            "### PROPOSAL CREATIVITY:",
            self.proposal_creativity_note,
        ]
        return "\n".join(lines)


def build_evidence_bound_context(
    spec: Any,  # ExperimentSpec
    result_markers: list,  # list of ResultMarker
    source_map: list[dict] | None = None,
    proposal_text: str = "",
) -> EvidenceBoundContext:
    """Build deterministic content from persisted evidence.

    This is the Phase 12 entry point — called BEFORE the LLM synthesis call
    to produce fixed empirical sections that constrain the paper's identity.
    """
    # 12B: Canonical title from spec
    canonical_title = build_canonical_title(
        dataset_name=spec.dataset_name,
        task_type=spec.task_type or "classification",
        executed_method=spec.analysis_method,
        baseline_method=spec.baseline_method or "baseline",
        primary_metric=spec.primary_metric or "accuracy",
    )

    # 12B: Typed RESULT sentences from marker semantics
    result_sentences = render_result_section(
        result_markers,
        executed_method=spec.analysis_method,
        baseline_method=spec.baseline_method or "baseline",
    )

    # 12C: Experiment description (methods section basis)
    methods_lines = [
        f"Dataset: {spec.dataset_name}",
        f"Task: {spec.task_type or 'classification'}",
        f"Target: {spec.target_name or 'not specified'}",
        f"Executed method: {spec.analysis_method}",
        f"Baseline: {spec.baseline_method or 'not specified'}",
        f"Comparison model: {spec.comparison_method or 'not specified'}",
        f"Primary metric: {spec.primary_metric or 'not specified'}",
        f"Split: {spec.split_method} (seed={spec.random_seed})",
    ]
    methods_description = "\n".join(methods_lines)

    # 12C: Experiment description (for abstract/introduction context)
    experiment_lines = [
        f"Research question: {spec.research_question}",
        f"Dataset: {spec.dataset_name}",
        f"Executed method: {spec.analysis_method}",
        f"Baseline: {spec.baseline_method or 'not specified'}",
    ]
    experiment_description = "\n".join(experiment_lines)

    # Abstract constraints
    abstract_constraints = (
        f"The abstract MUST name the dataset ({spec.dataset_name}), the executed "
        f"method ({spec.analysis_method.split('(')[0].strip()}), and the primary "
        f"metric ({spec.primary_metric or 'accuracy'}). "
        f"Do NOT present an unexecuted method as the paper's central contribution. "
        f"Any broader architectural discussion MUST be labeled as 'background' "
        f"or 'future work'."
    )

    # Conclusion constraints
    conclusion_constraints = (
        f"The conclusion MUST attribute all observed results to the executed "
        f"method ({spec.analysis_method.split('(')[0].strip()}). "
        f"Do NOT credit an unexecuted method with the observed outcomes."
    )

    # 12D: Proposal creativity note
    proposal_creativity_note = (
        "The research proposal may contain creative ideas beyond the executed "
        "experiment. These ideas are valuable as motivation and future work, but "
        "they MUST be explicitly labeled as 'proposed but not evaluated' or "
        "'future work'. They must NOT appear in the title, central contribution "
        "statement, or empirical-result attribution."
    )

    return EvidenceBoundContext(
        canonical_title=f"# {canonical_title}",
        experiment_description=experiment_description,
        result_sentences=result_sentences,
        methods_description=methods_description,
        abstract_constraints=abstract_constraints,
        conclusion_constraints=conclusion_constraints,
        proposal_creativity_note=proposal_creativity_note,
    )


def build_evidence_bound_synthesis_prompt(
    proposal_text: str,
    source_papers: list[str],
    evidence_context: EvidenceBoundContext,
    domain: str = "machine learning",
) -> str:
    """Build the complete synthesis prompt with evidence-bound content FIRST.

    The evidence-bound block appears BEFORE the proposal text, so the LLM
    sees the experiment identity as the primary framing and the proposal as
    supplementary context.
    """
    parts = [
        f"## Research Domain\n{domain}\n",
        evidence_context.build_evidence_bound_prompt_block(),
        "",
        "## Supporting Literature (CLOSED-BOOK — cite only these)\n",
    ]

    if source_papers:
        for paper_str in source_papers:
            parts.append(paper_str)
    else:
        parts.append("No specific supporting papers provided.")

    parts.append("\n## Research Proposal (use for motivation and related work)\n")
    parts.append(proposal_text)
    parts.append(
        "\n\nNow write a complete academic paper. The EVIDENCE-BOUND CONTENT "
        "above defines the paper's empirical identity — the title, results, "
        "and experiment description are FIXED. Expand around them using the "
        "proposal for motivation, the literature for related work, and your "
        "own academic prose for the remaining sections. Do NOT override the "
        "fixed title, result sentences, or experiment description."
    )

    return "\n".join(parts)
