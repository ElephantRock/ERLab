"""Stage output contracts — verify every stage produces expected output.

Each stage has a contract declaring what outputs it must produce.
The orchestrator checks these after each stage runs, producing explicit
violations instead of silent no-ops.

Phase D: Runtime Observability
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StageContract:
    """Expected output contract for a pipeline stage."""
    stage_name: str
    required_outputs: list[str]  # e.g. ["novelty_profiles", "novelty_reports"]
    min_output_size: dict[str, int] = field(default_factory=dict)  # e.g. {"novelty_profiles": 1}
    required_llm_calls: tuple[int, int] = (0, 999)  # (min, max)
    optional: bool = False  # If True, violation is a warning not an error


@dataclass
class ContractViolation:
    """Details of a contract violation."""
    stage_name: str
    violations: list[str]
    severity: str  # "error" or "warning"

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


def verify_contract(
    stage_name: str,
    result,  # PipelineResult
    contract: StageContract,
) -> ContractViolation | None:
    """Verify a stage's output against its contract.

    Returns None if OK, ContractViolation if not.
    """
    violations = []

    # Check required outputs exist and have content
    for output_name in contract.required_outputs:
        value = getattr(result, output_name, None)
        if value is None:
            violations.append(f"Missing output: {output_name}")
        elif isinstance(value, (dict, list)) and len(value) == 0:
            violations.append(f"Empty output: {output_name}")
        elif isinstance(value, (int, float)) and value == 0:
            # Allow zero counts for some outputs
            pass

    # Check minimum sizes
    for output_name, min_size in contract.min_output_size.items():
        value = getattr(result, output_name, None)
        if value is not None:
            actual = len(value) if hasattr(value, '__len__') else 0
            if actual < min_size:
                violations.append(
                    f"Output {output_name} has {actual} items, minimum {min_size}"
                )

    # Phase 3: Content quality checks (catch empty LLM responses)
    quality_violations = _check_content_quality(stage_name, result)
    violations.extend(quality_violations)

    if not violations:
        return None

    severity = "warning" if contract.optional else "error"
    return ContractViolation(
        stage_name=stage_name,
        violations=violations,
        severity=severity,
    )


def _check_content_quality(stage_name: str, result) -> list[str]:
    """Check content quality beyond just existence.

    Catches issues like:
    - Gaps with very low confidence (< 0.2)
    - Ideas with very low scores (< 0.2)
    - Proposals with very short content (< 100 chars, indicating empty LLM response)
    """
    violations = []

    if stage_name == "gap_analysis":
        gaps = getattr(result, "gaps", None)
        if gaps and len(gaps) > 0:
            max_conf = max((g.confidence for g in gaps if hasattr(g, 'confidence')), default=0)
            if max_conf < 0.2:
                violations.append(
                    f"All gaps have very low confidence (max={max_conf:.2f}) "
                    "— possible LLM quality issue"
                )

    elif stage_name == "idea_generation":
        ideas = getattr(result, "ideas", None)
        if ideas and len(ideas) > 0:
            scores = [i.score for i in ideas if hasattr(i, 'score')]
            if scores:
                max_score = max(scores)
                if max_score < 0.2:
                    violations.append(
                        f"All ideas have very low scores (max={max_score:.2f}) "
                        "— possible LLM quality issue"
                    )

    elif stage_name == "proposal_synthesis":
        proposals = getattr(result, "proposals", None)
        if proposals and len(proposals) > 0:
            short_count = 0
            for prop in proposals.values():
                text = (
                    getattr(prop, 'content_md', '')
                    or getattr(prop, 'methodology', '')
                    or str(prop)
                )
                if len(text) < 100:
                    short_count += 1
            if short_count == len(proposals):
                violations.append(
                    f"All {short_count} proposals have very short content (<100 chars) "
                    "— likely empty LLM responses"
                )

    return violations


# ── Contracts for all 17 stages ──────────────────────────────────

STAGE_CONTRACTS: dict[str, StageContract] = {
    "literature_search": StageContract(
        stage_name="literature_search",
        required_outputs=["papers_found"],
        min_output_size={"papers_found": 1},
        required_llm_calls=(0, 0),
    ),
    "ingestion": StageContract(
        stage_name="ingestion",
        required_outputs=[],  # May have no papers to ingest
        required_llm_calls=(0, 30),
        optional=True,
    ),
    "trimmer": StageContract(
        stage_name="trimmer",
        required_outputs=[],
        required_llm_calls=(0, 0),
        optional=True,
    ),
    "gap_analysis": StageContract(
        stage_name="gap_analysis",
        required_outputs=["gaps"],
        min_output_size={"gaps": 1},
        required_llm_calls=(1, 1),
    ),
    "gap_reflection": StageContract(
        stage_name="gap_reflection",
        required_outputs=[],
        required_llm_calls=(1, 3),
        optional=True,
    ),
    "idea_generation": StageContract(
        stage_name="idea_generation",
        required_outputs=["ideas"],
        min_output_size={"ideas": 1},
        required_llm_calls=(2, 18),
    ),
    "idea_reflection": StageContract(
        stage_name="idea_reflection",
        required_outputs=[],
        required_llm_calls=(1, 3),
        optional=True,
    ),
    "novelty_checking": StageContract(
        stage_name="novelty_checking",
        required_outputs=["novelty_profiles", "novelty_reports", "downstream_directives"],
        min_output_size={"novelty_profiles": 1},
        required_llm_calls=(1, 3),
    ),
    "feasibility_scoring": StageContract(
        stage_name="feasibility_scoring",
        required_outputs=["feasibility_reports"],
        min_output_size={"feasibility_reports": 1},
        required_llm_calls=(1, 2),
    ),
    "mechanical_metrics": StageContract(
        stage_name="mechanical_metrics",
        required_outputs=["mechanical_metrics"],
        required_llm_calls=(0, 0),
    ),
    "proposal_synthesis": StageContract(
        stage_name="proposal_synthesis",
        required_outputs=["proposals"],
        min_output_size={"proposals": 1},
        required_llm_calls=(1, 6),
    ),
    "adversarial_review": StageContract(
        stage_name="adversarial_review",
        required_outputs=[],
        required_llm_calls=(0, 2),
        optional=True,
    ),
    "evaluation": StageContract(
        stage_name="evaluation",
        required_outputs=["evaluation_reports"],
        min_output_size={"evaluation_reports": 1},
        required_llm_calls=(1, 2),
    ),
    "paper_synthesis": StageContract(
        stage_name="paper_synthesis",
        required_outputs=[],
        required_llm_calls=(1, 2),
        optional=True,
    ),
    "citation_audit": StageContract(
        stage_name="citation_audit",
        required_outputs=[],
        required_llm_calls=(0, 30),
        optional=True,
    ),
    "proposal_deepening": StageContract(
        stage_name="proposal_deepening",
        required_outputs=[],
        required_llm_calls=(0, 5),
        optional=True,
    ),
    "export": StageContract(
        stage_name="export",
        required_outputs=["export_paths"],
        min_output_size={"export_paths": 1},
        required_llm_calls=(0, 0),
    ),
}
