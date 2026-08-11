"""Verdict layer for the live-paper acceptance program.

The verdict layer is NOT a second orchestration harness. It receives the
production result and persisted records and evaluates the hard acceptance
gates defined by the case manifest. It never generates research content.

Verdict values and exit codes:
    PASS           0   all hard gates pass
    FAIL           1   product or implementation failure
    INCONCLUSIVE   2   verified external interruption
    INVALID_CASE   3   the attempt should never have started (preflight)

Every non-PASS outcome is nonzero.

The machine-readable gate result excludes raw provider responses and
credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from backend.acceptance.live_paper_artifacts import (
    CitationAuditView,
    PaperArtifactView,
    PaperEvaluationView,
    first_proposal,
    mapped_source_indices,
    source_markers_in_paper,
    stage_statuses,
    unmapped_source_indices,
)
from backend.acceptance.live_paper_contract import AcceptanceGates, LivePaperAcceptanceCase

# Mandatory deep_research stages for the frozen-corpus paper-production case.
# (Matches the downstream portion of PipelineOrchestrator._STAGE_ORDER that a
# paper-producing run must traverse.)
MANDATORY_STAGES = (
    "gap_analysis",
    "idea_generation",
    "novelty_checking",
    "feasibility_scoring",
    "proposal_synthesis",
    "adversarial_review",
    "paper_synthesis",
    "citation_audit",
    "export",
)


class AcceptanceVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    INVALID_CASE = "invalid_case"


# Exit code mapping. Every non-PASS outcome is nonzero.
EXIT_CODES: dict[AcceptanceVerdict, int] = {
    AcceptanceVerdict.PASS: 0,
    AcceptanceVerdict.FAIL: 1,
    AcceptanceVerdict.INCONCLUSIVE: 2,
    AcceptanceVerdict.INVALID_CASE: 3,
}


@dataclass
class GateResult:
    """The outcome of a single acceptance gate."""

    gate: str
    passed: bool
    reason_code: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "passed": self.passed,
            "reason_code": self.reason_code,
            "detail": self.detail,
        }


@dataclass
class VerdictReport:
    """The complete machine-readable verdict."""

    verdict: AcceptanceVerdict
    case_id: str
    attempt_id: str = ""
    failed_gates: list[GateResult] = field(default_factory=list)
    passed_gates: list[GateResult] = field(default_factory=list)
    not_applicable_gates: list[str] = field(default_factory=list)
    external_interruption: str | None = None
    exit_code: int = 0

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "case_id": self.case_id,
            "attempt_id": self.attempt_id,
            "failed_gates": [g.to_dict() for g in self.failed_gates],
            "passed_gates": [g.to_dict() for g in self.passed_gates],
            "not_applicable_gates": list(self.not_applicable_gates),
            "external_interruption": self.external_interruption,
            "exit_code": EXIT_CODES[self.verdict],
        }


# ── Classification helpers ───────────────────────────────────────────


def invalid_case(case_id: str, reason_code: str, detail: str = "") -> VerdictReport:
    """Build an INVALID_CASE verdict (preflight rejection)."""
    return VerdictReport(
        verdict=AcceptanceVerdict.INVALID_CASE,
        case_id=case_id,
        failed_gates=[GateResult(gate="preflight", passed=False,
                                 reason_code=reason_code, detail=detail)],
        exit_code=EXIT_CODES[AcceptanceVerdict.INVALID_CASE],
    )


def inconclusive(case_id: str, interruption: str) -> VerdictReport:
    """Build an INCONCLUSIVE verdict for a verified external interruption."""
    return VerdictReport(
        verdict=AcceptanceVerdict.INCONCLUSIVE,
        case_id=case_id,
        external_interruption=interruption,
        exit_code=EXIT_CODES[AcceptanceVerdict.INCONCLUSIVE],
    )


# ── Gate evaluation ──────────────────────────────────────────────────


def evaluate_gates(
    case: LivePaperAcceptanceCase,
    result: Any,
    *,
    attempt_id: str = "",
    code_origin_ok: bool = True,
    identity_isolation_ok: bool = True,
    restart_recovery_ok: bool | None = None,
    accounting_ok: bool | None = None,
    export_paths: dict[int, str] | None = None,
) -> VerdictReport:
    """Evaluate the active acceptance gates against a production result.

    Each ``*_ok`` parameter is a pre-computed preflight/post-run fact supplied
    by the runner. Gates not active in ``case.gates`` are recorded as
    not_applicable (never silently dropped).

    Returns a VerdictReport. PASS only if every active gate passes.
    """
    gates: AcceptanceGates = case.gates
    failed: list[GateResult] = []
    passed: list[GateResult] = []
    not_applicable: list[str] = []

    def record(gate_name: str, ok: bool, reason_code: str = "", detail: str = "") -> None:
        active = getattr(gates, gate_name, True)
        if not active:
            not_applicable.append(gate_name)
            return
        gr = GateResult(gate=gate_name, passed=ok, reason_code=reason_code, detail=detail)
        (passed if ok else failed).append(gr)

    # ── Gate 1: code origin ──
    record("code_origin", code_origin_ok,
           reason_code="" if code_origin_ok else "code_origin_mismatch")

    # ── Gate 2: identity isolation ──
    record("identity_isolation", identity_isolation_ok,
           reason_code="" if identity_isolation_ok else "identity_not_isolated")

    # ── Gate 3: pipeline outcome ──
    outcome_ok, outcome_reason = _check_pipeline_outcome(result)
    record("pipeline_outcome", outcome_ok, reason_code=outcome_reason)

    # ── Gate 4: mandatory stages ──
    stages_ok, stage_reason, stage_detail = _check_mandatory_stages(result)
    record("mandatory_stages", stages_ok, reason_code=stage_reason, detail=stage_detail)

    # ── Gate 5: research gap ──
    gap_ok, gap_reason = _check_research_gap(result)
    record("research_gap", gap_ok, reason_code=gap_reason)

    # ── Gates 6, 7, 8: paper artifact, evaluation, citations ──
    proposal = first_proposal(result)
    paper_view = _paper_view(proposal)

    paper_ok, paper_reason = _check_paper_artifact(paper_view)
    record("paper_artifact", paper_ok, reason_code=paper_reason)

    eval_ok, eval_reason = _check_paper_evaluation(proposal)
    record("paper_evaluation", eval_ok, reason_code=eval_reason)

    cite_ok, cite_reason = _check_citation_integrity(proposal, paper_view)
    record("citation_integrity", cite_ok, reason_code=cite_reason)

    # ── Gate 9: accounting ──
    # When the accounting gate is active but the runner did not supply a
    # verified result (accounting_ok is None), fail-closed instead of
    # silently passing. This prevents execution without budget enforcement
    # from reporting PASS on an active accounting gate.
    if accounting_ok is None:
        accounting_ok = not getattr(gates, "accounting", True)
    record("accounting", accounting_ok,
           reason_code="" if accounting_ok else "accounting_not_enforced")

    # ── Gate 10: export ──
    export_ok, export_reason = _check_export(result, paper_view, export_paths)
    record("export", export_ok, reason_code=export_reason)

    # ── Gate 11: restart recovery ──
    # Same fail-closed principle: when restart_recovery is active but the
    # runner did not supply a verified result, fail-closed.
    if restart_recovery_ok is None:
        restart_recovery_ok = not getattr(gates, "restart_recovery", True)
    record("restart_recovery", restart_recovery_ok,
           reason_code="" if restart_recovery_ok else "restart_recovery_failed")

    # ── Gate 12: human readability ──
    # Procedural — recorded as not_applicable in the machine verdict; the
    # human_review.md template is emitted separately and cannot override a
    # failed machine gate.
    not_applicable.append("human_readability")

    verdict = AcceptanceVerdict.PASS if not failed else AcceptanceVerdict.FAIL
    return VerdictReport(
        verdict=verdict,
        case_id=case.case_id,
        attempt_id=attempt_id,
        failed_gates=failed,
        passed_gates=passed,
        not_applicable_gates=not_applicable,
        exit_code=EXIT_CODES[verdict],
    )


# ── Individual gate checks ───────────────────────────────────────────


def _check_pipeline_outcome(result: Any) -> tuple[bool, str]:
    """Gate 3: outcome must be SUCCEEDED, terminal_stage None."""
    try:
        from backend.pipeline.result import PipelineOutcome
    except Exception:  # pragma: no cover - import guard
        return False, "outcome_enum_unavailable"
    outcome = getattr(result, "outcome", None)
    if outcome != PipelineOutcome.SUCCEEDED:
        return False, f"outcome_not_succeeded:{outcome}"
    if getattr(result, "terminal_stage", None) is not None:
        return False, "terminal_stage_set"
    return True, ""


def _check_mandatory_stages(result: Any) -> tuple[bool, str, str]:
    """Gate 4: every mandatory stage recorded an executed status."""
    statuses = stage_statuses(result)
    missing = [s for s in MANDATORY_STAGES if statuses.get(s) != "executed"]
    if missing:
        return False, "stages_not_executed", ",".join(missing)
    return True, "", ""


def _paper_view(proposal: Any | None) -> PaperArtifactView:
    """Build a PaperArtifactView, returning an empty view when no proposal."""
    if proposal is None:
        view = PaperArtifactView.__new__(PaperArtifactView)  # type: ignore[call-arg]
        view._d = {}  # type: ignore[attr-defined]
        view._md = {}  # type: ignore[attr-defined]
        return view
    return PaperArtifactView(proposal)


def _check_research_gap(result: Any) -> tuple[bool, str]:
    """Gate 5: at least one validated ResearchGap."""
    gaps = getattr(result, "gaps", None) or []
    if not gaps:
        return False, "no_research_gap"
    return True, ""


def _check_paper_artifact(paper_view: PaperArtifactView) -> tuple[bool, str]:
    """Gate 6: a complete, non-stub paper."""
    if not paper_view.exists:
        return False, "no_paper_artifact"
    md = paper_view.paper_markdown.strip()
    if not md:
        return False, "blank_paper_markdown"
    if paper_view.synthesis_state and paper_view.synthesis_state != "ready":
        return False, f"synthesis_state_not_ready:{paper_view.synthesis_state}"
    # Stub detection: an outline/proposal is not a paper.
    lower = md.lower()
    stub_markers = ("todo:", "placeholder", "[insert", "[section template",
                    "your text here", "lorem ipsum")
    if any(m in lower for m in stub_markers):
        return False, "paper_contains_placeholders"
    return True, ""


def _check_paper_evaluation(proposal: Any | None) -> tuple[bool, str]:
    """Gate 7: seven-dimensional, paper-scoped, non-blocking evaluation."""
    if proposal is None:
        return False, "no_proposal"
    ev = PaperEvaluationView(proposal)
    if not ev.exists:
        return False, "no_paper_evaluation"
    if ev.scope and ev.scope != "paper":
        return False, f"evaluation_scope_not_paper:{ev.scope}"
    if not ev.all_dimensions_present():
        return False, "missing_evaluation_dimensions"
    # Each dimension score must be numeric and bounded.
    from backend.acceptance.live_paper_artifacts import SEVEN_DIMENSIONS
    for dim in SEVEN_DIMENSIONS:
        score = ev.dimension_score(dim)
        if score is None:
            return False, f"dimension_score_missing:{dim}"
        if not (0.0 <= score <= 1.0):
            return False, f"dimension_score_out_of_bounds:{dim}"
        if not ev.dimension_justification(dim):
            return False, f"dimension_justification_missing:{dim}"
    if ev.has_blocking_gate():
        return False, "blocking_evaluation_gate"
    return True, ""


def _check_citation_integrity(
    proposal: Any | None, paper_view: PaperArtifactView,
) -> tuple[bool, str]:
    """Gate 8: every citation mapped, no fabricated sources."""
    if proposal is None:
        return False, "no_proposal"
    audit = CitationAuditView(proposal)
    if not audit.exists:
        return False, "no_citation_audit"
    if audit.fabricated_citations > 0:
        return False, "fabricated_citations"
    # Every [SOURCE-N] marker in the paper must be mapped.
    markers = source_markers_in_paper(paper_view.paper_markdown)
    mapped = mapped_source_indices(paper_view.source_map)
    # A paper with zero citation markers has no literature grounding.
    if not markers:
        return False, "no_source_markers_in_paper"
    # A source map with zero mapped sources means citations were not
    # resolved to any literature.
    if not mapped:
        return False, "no_mapped_sources"
    unmapped_in_paper = markers - mapped
    if unmapped_in_paper:
        return False, f"unmapped_source_markers:{sorted(unmapped_in_paper)}"
    if unmapped_source_indices(paper_view.source_map):
        return False, "out_of_range_source_markers"
    return True, ""


def _check_export(
    result: Any,
    paper_view: PaperArtifactView,
    export_paths: dict[int, str] | None,
) -> tuple[bool, str]:
    """Gate 10: export file exists and contains the paper."""
    paths = export_paths if export_paths is not None else getattr(result, "export_paths", {}) or {}
    if not paths:
        return False, "no_export_paths"
    from pathlib import Path
    for path in paths.values():
        if not Path(path).exists():
            return False, f"export_file_missing:{path}"
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as e:
            return False, f"export_file_unreadable:{e}"
        if paper_view.exists and paper_view.paper_markdown.strip():
            # The export should contain a recognizable chunk of the paper.
            first_chunk = paper_view.paper_markdown.strip().split("\n\n")[0]
            if first_chunk and first_chunk[:80] not in text:
                return False, "export_missing_paper_text"
    return True, ""
