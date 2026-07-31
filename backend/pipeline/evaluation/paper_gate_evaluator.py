"""Phase 9 / 9C — pure paper gate evaluator.

A standalone, side-effect-free function that evaluates a paper against all
structural gates without requiring a StageContext, database access, or
provider calls. Both the pipeline stage and the remediation orchestrator
can call this function.

Gates evaluated:
  1. provenance       — [SOURCE-N] markers resolve to the source map
  2. scope_alignment  — paper title/abstract overlap with research intent
  3. conclusion_support — empirical claims backed by [RESULT-N] markers
  4. experiment_alignment — abstract/conclusion center the executed method
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaperGateEvaluation:
    """Result of evaluating a paper against all structural gates."""

    status: str  # ready | blocked
    gates: list[dict] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)

    @property
    def has_blocker(self) -> bool:
        return self.status == "blocked"

    @property
    def eligible_for_remediation(self) -> bool:
        """Whether the blocking reasons include text-correctable failures
        and exclude hard evidence/execution failures (Phase 9 / correction #5).

        Eligible triggers:
          - experiment_alignment (semantic mismatch)
          - conclusion_support (unsupported empirical attribution)
          - scope_alignment (off-scope, often co-occurs with alignment)

        NOT eligible (hard evidence/execution failures):
          - provenance (missing sources — needs retrieval, not text editing)
        """
        non_remediable_gates = {"provenance"}
        if not self.blocking_reasons:
            return False
        # Must have at least one remediable gate failure
        has_remediable = False
        for reason in self.blocking_reasons:
            gate_name = reason.split(":")[0].strip()
            if gate_name in non_remediable_gates:
                return False  # hard evidence failure blocks remediation
            if gate_name != "provenance":
                has_remediable = True
        return has_remediable

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "gates": self.gates,
            "blocking_reasons": self.blocking_reasons,
            "eligible_for_remediation": self.eligible_for_remediation,
        }


def evaluate_paper_gates(
    paper_md: str,
    source_map: list[dict] | None = None,
    research_intent: str = "",
    domain: str = "",
    result_markers: list[Any] | None = None,
    spec_method: str = "",
    spec_dataset: str = "",
    spec_baseline: str = "",
    spec_comparison: str = "",
) -> PaperGateEvaluation:
    """Evaluate a paper against all structural gates.

    This is a PURE function — no database writes, no provider calls, no
    pipeline transitions. Both the pipeline stage and the remediation
    orchestrator call this.

    Args:
        paper_md: The paper markdown to evaluate.
        source_map: The frozen source map (list of dicts with marker/source_id).
        research_intent: The research question or intent string.
        domain: The research domain.
        result_markers: List of ResultMarker objects (or None if no experiment).
        spec_method: The experiment spec's analysis method.
        spec_dataset: The experiment spec's dataset name.
        spec_baseline: The experiment spec's baseline method.
        spec_comparison: The experiment spec's comparison model.

    Returns:
        PaperGateEvaluation with gate results and blocking reasons.
    """
    gates: list[dict] = []
    blocking_reasons: list[str] = []

    # ── Gate 1: Provenance ──────────────────────────────────────────
    from backend.pipeline.stages import PaperSynthesisStage
    prov_gate = PaperSynthesisStage.provenance_precondition(
        paper_md, source_map or []
    )
    gates.append({
        "gate": "provenance",
        "passed": prov_gate.passed,
        "reason": prov_gate.reason,
    })
    if not prov_gate.passed:
        blocking_reasons.append(f"provenance: {prov_gate.reason}")

    # ── Gate 2: Scope alignment ─────────────────────────────────────
    from backend.pipeline.evaluation.scope_checker import classify_scope_alignment
    scope_result = classify_scope_alignment(
        research_intent=research_intent or domain,
        paper_title="",
        paper_abstract=paper_md[:2000],
    )
    gates.append({
        "gate": "scope_alignment",
        "classification": scope_result.classification,
        "reason": scope_result.reason,
    })
    if scope_result.classification == "off_scope":
        blocking_reasons.append(f"scope: {scope_result.reason}")

    # ── Gate 3: Conclusion support ──────────────────────────────────
    from backend.pipeline.evaluation.conclusion_checker import classify_conclusion_support
    from backend.pipeline.evaluation.claim_alignment import _extract_abstract, _extract_conclusion
    abstract_text = _extract_abstract(paper_md)
    conclusion_text = _extract_conclusion(paper_md)
    has_empirical = bool(result_markers)
    conclusion_result = classify_conclusion_support(
        abstract=abstract_text,
        conclusion=conclusion_text,
        has_empirical_results=has_empirical,
    )
    gates.append({
        "gate": "conclusion_support",
        "classification": conclusion_result.classification,
        "reason": conclusion_result.reason,
    })
    if conclusion_result.classification == "overstated":
        blocking_reasons.append(f"conclusion: {conclusion_result.reason}")

    # ── Gate 4: Experiment alignment ────────────────────────────────
    exp_alignment_passed = True
    exp_alignment_reason = "Not an empirical run"
    if spec_method and result_markers:
        from backend.pipeline.evaluation.claim_alignment import evaluate_claim_alignment
        claim_result = evaluate_claim_alignment(
            paper_md=paper_md,
            spec_method=spec_method,
            spec_dataset=spec_dataset,
            spec_baseline=spec_baseline,
            spec_comparison=spec_comparison,
        )
        exp_alignment_passed = claim_result.passed
        exp_alignment_reason = f"[{claim_result.finding}] {claim_result.reason}"
    elif spec_method and not result_markers:
        exp_alignment_reason = "No experiment results to check alignment against"

    gates.append({
        "gate": "experiment_alignment",
        "passed": exp_alignment_passed,
        "reason": exp_alignment_reason,
    })
    if not exp_alignment_passed:
        blocking_reasons.append(f"experiment_alignment: {exp_alignment_reason}")

    # ── Gate 5: Claim-to-result semantic validation (Phase 10 correction B) ──
    # Checks that RESULT markers cited in model-claims are actually model markers,
    # not baseline markers. Closes the false-ready defect where "the model achieved
    # [RESULT-1]" passes when RESULT-1 is the baseline accuracy.
    claim_result_passed = True
    claim_result_reason = "No RESULT markers to validate"
    if result_markers:
        from backend.pipeline.evaluation.claim_result_validator import validate_claim_result_alignment
        mismatches = validate_claim_result_alignment(paper_md, result_markers)
        if mismatches:
            claim_result_passed = False
            claim_result_reason = "; ".join(
                f"{m.marker} (role={m.marker_role}) credited to {m.claimed_subject}: {m.reason[:100]}"
                for m in mismatches
            )
    gates.append({
        "gate": "claim_result_alignment",
        "passed": claim_result_passed,
        "reason": claim_result_reason,
    })
    if not claim_result_passed:
        blocking_reasons.append(f"claim_result_alignment: {claim_result_reason}")

    status = "blocked" if blocking_reasons else "ready"
    return PaperGateEvaluation(
        status=status,
        gates=gates,
        blocking_reasons=blocking_reasons,
    )
