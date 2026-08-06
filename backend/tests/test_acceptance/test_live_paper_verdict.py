"""Tests for the live-paper verdict layer.

Freezes the PASS/FAIL/INCONCLUSIVE/INVALID_CASE classification and every
exit code, plus the gate-evaluation matrix. These tests define the verdict
behavior before the runner is wired to it (Phase A2).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from backend.acceptance.live_paper_verdict import (
    EXIT_CODES,
    MANDATORY_STAGES,
    AcceptanceVerdict,
    evaluate_gates,
    inconclusive,
    invalid_case,
)
from backend.pipeline.result import PipelineOutcome, PipelineResult

# ── Fixtures ─────────────────────────────────────────────────────────


def _case():
    """A minimal case with all gates active."""
    from backend.acceptance.live_paper_contract import LivePaperAcceptanceCase
    return LivePaperAcceptanceCase.model_validate({
        "schema_version": "erlab.live-paper-acceptance.v1",
        "case_id": "vtest",
        "research_domain": "MT",
        "research_question": "How can transfer help low-resource MT?",
        "expected_code_sha": "abcdef1234567890abcdef1234567890abcdef12",
        "corpus_mode": "synthetic",
        "provider": "zai",
        "model": "glm-4.6",
        "embedding_provider": "lmstudio",
        "embedding_model": "text-embedding-qwen3-embedding-0.6b",
        "execution": {"network_policy": "hermetic"},
        "budget": {
            "maximum_cost_usd": 5.0, "maximum_provider_calls": 200,
            "maximum_input_tokens": 1000, "maximum_output_tokens": 500,
            "maximum_duration_seconds": 1800,
        },
    })


def _passing_result(tmp_path) -> PipelineResult:
    """A PipelineResult that passes every gate."""
    res = PipelineResult()
    res.outcome = PipelineOutcome.SUCCEEDED
    res.terminal_stage = None
    res.gaps = [SimpleNamespace(title="G")]
    res.export_paths = {}
    # Every mandatory stage executed.
    res.stage_report = [
        SimpleNamespace(name=s, status="executed") for s in MANDATORY_STAGES
    ]
    # A proposal with a valid paper, evaluation, and citation audit.
    paper_text = "# Title\n\nA complete non-empirical synthesis [SOURCE-1]."
    export_path = tmp_path / "paper.md"
    export_path.write_text(paper_text, encoding="utf-8")
    res.export_paths = {0: str(export_path)}
    metadata = {
        "full_paper": {
            "paper_markdown": paper_text,
            "word_count": 6,
            "synthesis_state": "ready",
            "source_map": [{"marker_index": 1, "mapping_status": "mapped", "source_id": "p1"}],
        },
        "synthesis_state": "ready",
        "paper_evaluation": {
            "scope": "paper", "status": "ready", "blocking_reasons": [],
            "dimensions": {d: {"score": 0.7, "justification": "ok"} for d in (
                "novelty", "feasibility", "completeness", "rigor",
                "clarity", "baseline_adequacy", "compute_realism",
            )},
        },
        "citation_audit": {
            "status": "complete", "total_citations": 1, "fabricated_citations": 0,
        },
    }
    proposal = SimpleNamespace(metadata=json.dumps(metadata))
    res.proposals = {0: proposal}
    return res


# ── Verdict values and exit codes ────────────────────────────────────


class TestVerdictEnum:
    def test_verdict_members(self):
        assert {v.value for v in AcceptanceVerdict} == {
            "pass", "fail", "inconclusive", "invalid_case",
        }

    def test_exit_codes_nonzero_except_pass(self):
        assert EXIT_CODES[AcceptanceVerdict.PASS] == 0
        assert EXIT_CODES[AcceptanceVerdict.FAIL] != 0
        assert EXIT_CODES[AcceptanceVerdict.INCONCLUSIVE] != 0
        assert EXIT_CODES[AcceptanceVerdict.INVALID_CASE] != 0
        assert EXIT_CODES[AcceptanceVerdict.FAIL] == 1
        assert EXIT_CODES[AcceptanceVerdict.INCONCLUSIVE] == 2
        assert EXIT_CODES[AcceptanceVerdict.INVALID_CASE] == 3


# ── PASS ─────────────────────────────────────────────────────────────


class TestPassVerdict:
    def test_all_gates_pass_yields_pass(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        report = evaluate_gates(case, result, restart_recovery_ok=True, accounting_ok=True)
        assert report.verdict is AcceptanceVerdict.PASS
        assert report.exit_code == 0
        assert not report.failed_gates

    def test_pass_records_passed_gates(self, tmp_path):
        case = _case()
        report = evaluate_gates(case, _passing_result(tmp_path), restart_recovery_ok=True)
        gate_names = {g.gate for g in report.passed_gates}
        # human_readability is always not_applicable (procedural).
        assert "human_readability" not in gate_names
        assert "paper_artifact" in gate_names


# ── FAIL matrix ──────────────────────────────────────────────────────


class TestFailMatrix:
    def test_outcome_not_succeeded_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        result.outcome = PipelineOutcome.FAILED_OUTPUT_CONTRACT
        result.terminal_stage = "gap_analysis"
        report = evaluate_gates(case, result)
        assert report.verdict is AcceptanceVerdict.FAIL
        assert any(g.gate == "pipeline_outcome" for g in report.failed_gates)

    def test_no_research_gap_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        result.gaps = []
        report = evaluate_gates(case, result)
        assert report.verdict is AcceptanceVerdict.FAIL
        assert any(g.gate == "research_gap" and g.reason_code == "no_research_gap"
                   for g in report.failed_gates)

    def test_missing_mandatory_stage_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        # Drop one stage from the report.
        result.stage_report = [
            r for r in result.stage_report if r.name != "novelty_checking"
        ]
        report = evaluate_gates(case, result)
        assert report.verdict is AcceptanceVerdict.FAIL
        failed = [g for g in report.failed_gates if g.gate == "mandatory_stages"]
        assert failed and "novelty_checking" in failed[0].detail

    def test_blank_paper_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        proposal = result.proposals[0]
        md = json.loads(proposal.metadata)
        md["full_paper"]["paper_markdown"] = ""
        proposal.metadata = json.dumps(md)
        report = evaluate_gates(case, result)
        assert any(g.gate == "paper_artifact" for g in report.failed_gates)

    def test_paper_with_placeholders_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        proposal = result.proposals[0]
        md = json.loads(proposal.metadata)
        md["full_paper"]["paper_markdown"] = "Real text. TODO: insert method here."
        proposal.metadata = json.dumps(md)
        report = evaluate_gates(case, result)
        assert any(g.gate == "paper_artifact" and "placeholder" in g.reason_code
                   for g in report.failed_gates)

    def test_missing_evaluation_dimension_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        proposal = result.proposals[0]
        md = json.loads(proposal.metadata)
        del md["paper_evaluation"]["dimensions"]["compute_realism"]
        proposal.metadata = json.dumps(md)
        report = evaluate_gates(case, result)
        assert any(g.gate == "paper_evaluation" for g in report.failed_gates)

    def test_blocking_evaluation_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        proposal = result.proposals[0]
        md = json.loads(proposal.metadata)
        md["paper_evaluation"]["status"] = "blocked"
        md["paper_evaluation"]["blocking_reasons"] = ["conclusion overstated"]
        proposal.metadata = json.dumps(md)
        report = evaluate_gates(case, result)
        assert any(g.gate == "paper_evaluation" and "blocking" in g.reason_code
                   for g in report.failed_gates)

    def test_unmapped_citation_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        proposal = result.proposals[0]
        md = json.loads(proposal.metadata)
        # Add an unmapped marker to the paper that isn't in the source map.
        md["full_paper"]["paper_markdown"] = "Text [SOURCE-1] and [SOURCE-99]."
        proposal.metadata = json.dumps(md)
        report = evaluate_gates(case, result)
        assert any(g.gate == "citation_integrity" for g in report.failed_gates)

    def test_fabricated_source_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        proposal = result.proposals[0]
        md = json.loads(proposal.metadata)
        md["citation_audit"]["fabricated_citations"] = 1
        proposal.metadata = json.dumps(md)
        report = evaluate_gates(case, result)
        assert any(g.gate == "citation_integrity" and "fabricated" in g.reason_code
                   for g in report.failed_gates)

    def test_export_file_missing_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        result.export_paths = {0: str(tmp_path / "nonexistent.md")}
        report = evaluate_gates(case, result)
        assert any(g.gate == "export" for g in report.failed_gates)

    def test_restart_recovery_failure_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        report = evaluate_gates(case, result, restart_recovery_ok=False)
        assert any(g.gate == "restart_recovery" for g in report.failed_gates)
        assert report.verdict is AcceptanceVerdict.FAIL

    def test_accounting_mismatch_fails(self, tmp_path):
        case = _case()
        result = _passing_result(tmp_path)
        report = evaluate_gates(case, result, accounting_ok=False)
        assert any(g.gate == "accounting" for g in report.failed_gates)


# ── INVALID_CASE ─────────────────────────────────────────────────────


class TestInvalidCase:
    def test_invalid_case_verdict_and_exit(self):
        report = invalid_case("c1", "sha_mismatch", detail="abc != def")
        assert report.verdict is AcceptanceVerdict.INVALID_CASE
        assert report.exit_code == 3
        assert report.failed_gates[0].reason_code == "sha_mismatch"


# ── INCONCLUSIVE ─────────────────────────────────────────────────────


class TestInconclusive:
    def test_inconclusive_for_external_interruption(self):
        report = inconclusive("c1", "provider_auth_service_unavailable")
        assert report.verdict is AcceptanceVerdict.INCONCLUSIVE
        assert report.exit_code == 2
        assert report.external_interruption == "provider_auth_service_unavailable"


# ── Disabled gates are recorded, not dropped ─────────────────────────


class TestDisabledGates:
    def test_disabled_gate_recorded_as_not_applicable(self, tmp_path):
        from backend.acceptance.live_paper_contract import LivePaperAcceptanceCase
        case = LivePaperAcceptanceCase.model_validate({
            **_case().model_dump(),
            "gates": {"paper_evaluation": False},
        })
        report = evaluate_gates(case, _passing_result(tmp_path), restart_recovery_ok=True)
        assert "paper_evaluation" in report.not_applicable_gates
        assert not any(g.gate == "paper_evaluation" for g in report.failed_gates)


# ── Machine-readable serialization ───────────────────────────────────


class TestSerialization:
    def test_verdict_dict_excludes_raw_payloads(self, tmp_path):
        case = _case()
        report = evaluate_gates(case, _passing_result(tmp_path), restart_recovery_ok=True)
        d = report.to_dict()
        # No raw provider content should ever appear.
        blob = json.dumps(d)
        assert "SECRETRAWPAYLOAD" not in blob
        assert d["verdict"] in ("pass", "fail", "inconclusive", "invalid_case")
