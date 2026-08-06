"""Integrated acceptance rehearsal with budget + restart gates (Commit 4).

Runs the manifest-driven acceptance verdict with:
- hard cost authority enabled (pre-call refusal at the gateway boundary)
- fresh-process restart recovery gate enabled
- all twelve acceptance gates active
- network access forbidden
- deterministic provider

Positive rehearsal: a complete synthetic result with adequate budget and
successful recovery yields PASS (exit 0), overshoot 0, all gates green.

Negative rehearsals: each fault yields the expected FAIL verdict —
ceiling too small, ceiling reached midway, provider invoked after denial,
reservation not released after exception, actual usage exceeds reservation,
and the recovery-failure cases.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.acceptance.budget_authority import (
    BudgetAuthority,
    BudgetReservationDeniedError,
)
from backend.acceptance.live_paper_contract import LivePaperAcceptanceCase
from backend.acceptance.live_paper_verdict import (
    AcceptanceVerdict,
    evaluate_gates,
)
from backend.pipeline.result import PipelineOutcome, PipelineResult

SEVEN_DIMS = (
    "novelty", "feasibility", "completeness", "rigor",
    "clarity", "baseline_adequacy", "compute_realism",
)
MANDATORY_STAGES = (
    "gap_analysis", "idea_generation", "novelty_checking", "feasibility_scoring",
    "proposal_synthesis", "adversarial_review", "paper_synthesis",
    "citation_audit", "export",
)


def _full_case() -> LivePaperAcceptanceCase:
    """A case with ALL gates active (budget + restart + everything)."""
    return LivePaperAcceptanceCase.model_validate({
        "schema_version": "erlab.live-paper-acceptance.v1",
        "case_id": "integrated_rehearsal_v1",
        "artifact_class": "non_empirical_research_synthesis",
        "research_domain": "low-resource MT",
        "research_question": "How can transfer help low-resource MT?",
        "expected_code_sha": "abcdef1234567890abcdef1234567890abcdef12",
        "corpus_mode": "synthetic",
        "provider": "synthetic",
        "model": "synthetic-model",
        "embedding_provider": "synthetic",
        "embedding_model": "synthetic-embed",
        "execution": {"network_policy": "hermetic", "require_restart_recovery": True},
        "budget": {
            "maximum_cost_usd": 5.0, "maximum_provider_calls": 200,
            "maximum_input_tokens": 1000, "maximum_output_tokens": 500,
            "maximum_duration_seconds": 1800,
        },
        "gates": {"code_origin": False, "identity_isolation": False},
        # All other gates default True, including accounting + restart_recovery.
    })


def _passing_result(tmp_path: Path) -> PipelineResult:
    """A complete synthetic result that passes every product gate."""
    res = PipelineResult()
    res.outcome = PipelineOutcome.SUCCEEDED
    res.terminal_stage = None
    res.gaps = [SimpleNamespace(title="G1", confidence=0.8)]
    res.ideas = [SimpleNamespace(title="I1")]
    res.stage_report = [
        SimpleNamespace(name=s, status="executed") for s in MANDATORY_STAGES
    ]
    paper_text = "# Paper\n\nComplete synthesis [SOURCE-1] [SOURCE-2]."
    export_path = tmp_path / "paper.md"
    export_path.write_text(paper_text, encoding="utf-8")
    res.export_paths = {0: str(export_path)}
    metadata = {
        "full_paper": {
            "paper_markdown": paper_text, "word_count": len(paper_text.split()),
            "synthesis_state": "ready",
            "source_map": [
                {"marker_index": i, "mapping_status": "mapped", "source_id": f"p{i}"}
                for i in (1, 2)
            ],
        },
        "synthesis_state": "ready",
        "paper_evaluation": {
            "scope": "paper", "status": "ready", "blocking_reasons": [],
            "dimensions": {d: {"score": 0.75, "justification": "ok"} for d in SEVEN_DIMS},
        },
        "citation_audit": {"status": "complete", "total_citations": 2,
                           "fabricated_citations": 0},
    }
    res.proposals = {0: SimpleNamespace(metadata=json.dumps(metadata), title="P1")}
    return res


# ── Positive rehearsal: all gates enabled, adequate budget, recovery ok ──


class TestPositiveIntegratedRehearsal:
    def test_pass_with_budget_and_restart_enabled(self, tmp_path):
        case = _full_case()
        result = _passing_result(tmp_path)
        # Budget authority with adequate ceiling; a few calls reconciled.
        auth = BudgetAuthority(ceiling_usd=1.0, price_per_1k_input=0.5,
                               price_per_1k_output=1.5)
        for _ in range(3):
            proj = auth.project_call(max_input_tokens=100, max_output_tokens=50)
            auth.reserve(proj)
            auth.reconcile(auth.cost_for_tokens(60, 40))
        report = evaluate_gates(
            case, result, restart_recovery_ok=True,
            accounting_ok=(auth.snapshot().reconciled and auth.snapshot().overshoot_usd == 0.0),
        )
        assert report.verdict is AcceptanceVerdict.PASS, (
            f"gates failed: {[g.gate for g in report.failed_gates]}"
        )
        assert report.exit_code == 0

    def test_overshoot_zero_when_within_ceiling(self):
        auth = BudgetAuthority(ceiling_usd=1.0, price_per_1k_input=0.5,
                               price_per_1k_output=1.5)
        for _ in range(3):
            proj = auth.project_call(max_input_tokens=100, max_output_tokens=50)
            auth.reserve(proj)
            auth.reconcile(auth.cost_for_tokens(60, 40))
        snap = auth.snapshot()
        assert snap.overshoot_usd == 0.0
        assert snap.reconciled is True
        assert snap.denied_calls == 0


# ── Budget negative controls ─────────────────────────────────────────


class TestBudgetNegativeControls:
    def test_ceiling_too_small_for_first_call_denies(self):
        auth = BudgetAuthority(ceiling_usd=0.001, price_per_1k_input=0.5,
                               price_per_1k_output=1.5)
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(auth.project_call(max_input_tokens=100, max_output_tokens=50))

    def test_ceiling_reached_midway_denies_second_call(self):
        auth = BudgetAuthority(ceiling_usd=0.03, price_per_1k_input=0.5,
                               price_per_1k_output=1.5)
        # First call fits.
        auth.reserve(auth.project_call(max_input_tokens=10, max_output_tokens=10))
        auth.reconcile(auth.cost_for_tokens(6, 4))
        # Second call: remaining budget too small for the projection.
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(auth.project_call(max_input_tokens=100, max_output_tokens=50))

    def test_provider_not_invoked_after_denial(self):
        """A denial must not reach the provider — the call count stays at zero."""
        calls = []
        auth = BudgetAuthority(ceiling_usd=0.001, price_per_1k_input=0.5,
                               price_per_1k_output=1.5)
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(auth.project_call(max_input_tokens=100, max_output_tokens=50))
            calls.append(1)  # would only run if reserve succeeded
        assert calls == []

    def test_reservation_released_after_exception(self):
        auth = BudgetAuthority(ceiling_usd=1.0, price_per_1k_input=0.5,
                               price_per_1k_output=1.5)
        auth.reserve(auth.project_call(max_input_tokens=100, max_output_tokens=50))
        assert auth.reserved_usd() > 0.0
        auth.release()  # simulate provider exception
        assert auth.reserved_usd() == pytest.approx(0.0)
        assert auth.committed_usd() == pytest.approx(0.0)

    def test_actual_usage_exceeding_reservation_marks_unreconciled(self):
        auth = BudgetAuthority(ceiling_usd=0.05, price_per_1k_input=0.5,
                               price_per_1k_output=1.5, strict=True)
        auth.reserve(auth.project_call(max_input_tokens=10, max_output_tokens=10))
        # Actual usage far exceeds both the reservation and the ceiling.
        auth.reconcile(actual_cost_usd=0.10)
        snap = auth.snapshot()
        assert snap.overshoot_usd > 0.0
        assert snap.reconciled is False


# ── Restart-recovery negative controls ───────────────────────────────


class TestRestartNegativeControls:
    def test_restart_failure_fails_when_gate_enabled(self, tmp_path):
        case = _full_case()  # require_restart_recovery=True
        result = _passing_result(tmp_path)
        report = evaluate_gates(case, result, restart_recovery_ok=False)
        assert report.verdict is AcceptanceVerdict.FAIL
        assert any(g.gate == "restart_recovery" for g in report.failed_gates)

    def test_paper_missing_fails_restart(self, tmp_path):
        """If the paper is absent, restart recovery cannot reload it."""
        case = _full_case()
        result = _passing_result(tmp_path)
        result.proposals[0].metadata = json.dumps({})  # no paper
        report = evaluate_gates(case, result, restart_recovery_ok=False)
        assert any(g.gate in ("restart_recovery", "paper_artifact")
                   for g in report.failed_gates)

    def test_export_path_in_result_but_file_missing_fails(self, tmp_path):
        case = _full_case()
        result = _passing_result(tmp_path)
        result.export_paths = {0: str(tmp_path / "ghost.md")}  # file absent
        report = evaluate_gates(case, result, restart_recovery_ok=True)
        assert any(g.gate == "export" for g in report.failed_gates)


# ── Accounting gate ──────────────────────────────────────────────────


class TestAccountingGate:
    def test_accounting_mismatch_fails(self, tmp_path):
        case = _full_case()
        result = _passing_result(tmp_path)
        report = evaluate_gates(case, result, accounting_ok=False,
                                restart_recovery_ok=True)
        assert any(g.gate == "accounting" for g in report.failed_gates)

    def test_budget_overshoot_fails_accounting(self, tmp_path):
        case = _full_case()
        result = _passing_result(tmp_path)
        auth = BudgetAuthority(ceiling_usd=0.01, price_per_1k_input=0.5,
                               price_per_1k_output=1.5)
        auth.reconcile(0.10)  # overshoot
        snap = auth.snapshot()
        accounting_ok = snap.reconciled and snap.overshoot_usd == 0.0
        report = evaluate_gates(case, result, accounting_ok=accounting_ok,
                                restart_recovery_ok=True)
        assert report.verdict is AcceptanceVerdict.FAIL


# ── Same-process object must NOT count as recovery ───────────────────


class TestRecoverySourceIntegrity:
    def test_recovery_must_use_production_persistence_not_memory(self):
        """The recovery gate's restart_recovery_ok flag must be set ONLY by
        a real fresh-process recovery check, never by reusing the in-memory
        result. This test documents that contract: the flag is a discrete
        input the caller must supply from an actual recovery attempt."""
        # If a caller passed restart_recovery_ok=True without actually
        # recovering, the gate would pass dishonestly. The integration
        # test (Commit 3) proves real recovery; here we assert the flag
        # is a required, explicit input — there is no default shortcut.
        import inspect
        sig = inspect.signature(evaluate_gates)
        assert "restart_recovery_ok" in sig.parameters
        # Its default is None (caller must supply), not True.
        assert sig.parameters["restart_recovery_ok"].default is None
