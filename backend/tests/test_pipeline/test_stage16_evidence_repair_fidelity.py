"""Regression: Stage-16 evidence-repair rewrite enters the fidelity boundary.

run_31187f170e93 acceptance failure: the legacy evidence-repair loop
replaced the reconciled empirical paper with its own re-rendered text,
reintroducing dropped-decimal corruption (``333333 [RESULT-1]`` /
``966667 [RESULT-3]``) after the synthesis-time fidelity boundary had
clean values. The boundary now re-applies at the Stage-16 integration
point: marker-adjacent numbers are restored to the exact persisted values
and the same-sentence rule is re-checked; unrepairable values or unbacked
empirical conclusions fail closed (the stage's broad non-fatal handler
must NOT swallow them).

These tests exercise the actual integration point
(``CitationAuditStage._run_legacy_validation_and_repair``) with stubbed
validator/repair-loop classes, not ``result_marker_fidelity`` in
isolation. Use asyncio-free, plain calls — the function is synchronous.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from backend.pipeline.stages import CitationAuditStage
from backend.pipeline.synthesis.result_marker_fidelity import (
    ResultMarkerFidelityError,
)

AUTHORITATIVE = [
    {
        "marker": "RESULT-1",
        "metric_id": "baseline_accuracy",
        "observed_value": 0.333333,
        "experiment_result_id": 29,
        "role": "baseline",
    },
    {
        "marker": "RESULT-2",
        "metric_id": "improvement",
        "observed_value": 0.633333,
        "experiment_result_id": 29,
        "role": "derived",
    },
    {
        "marker": "RESULT-3",
        "metric_id": "model_accuracy",
        "observed_value": 0.966667,
        "experiment_result_id": 29,
        "role": "comparison",
    },
]

CLEAN_PAPER = (
    "# Paper\n\n## Abstract\nWe evaluate the frozen protocol: the "
    "baseline scored 0.333333 [RESULT-1] and the model 0.966667 "
    "[RESULT-3].\n\n## Results\n"
    + ("The frozen partition is held fixed across every measurement. " * 8)
    + "\n\n## Conclusion\nThe improvement was 0.633333 [RESULT-2] over "
    "the predeclared majority predictor.\n"
)

CORRUPTED_REWRITE = (
    "# Paper\n\n## Abstract\nWe evaluate the frozen protocol: the "
    "baseline scored 333333 [RESULT-1] and the model 966667 [RESULT-3].\n\n"
    "## Results\n"
    + ("The frozen partition is held fixed across every measurement. " * 8)
    + "\n\n## Conclusion\nThe improvement was 0.633333 [RESULT-2] over "
    "the predeclared majority predictor.\n"
)


class _StubValidator:
    def __init__(self, corpus_ids):
        pass

    def validate_document(self, text, provided_evidence_ids, evidence_texts):
        return SimpleNamespace(
            total_claims=2,
            valid_claims=1,
            results=[SimpleNamespace(), SimpleNamespace()],
            to_dict=lambda: {"claims": 2},
        )


class _StubRepair:
    def __init__(self, corpus_texts):
        pass

    def repair(self, validation_results, original_text):
        return SimpleNamespace(
            repaired_text=CORRUPTED_REWRITE,
            to_dict=lambda: {"repairs": 2},
            original_survival_rate=0.08,
            repaired_survival_rate=0.18,
        )


class _StubRepair97:
    def __init__(self, corpus_texts):
        pass

    def repair(self, validation_results, original_text):
        rewritten = CORRUPTED_REWRITE.replace(
            "333333 [RESULT-1]", "97% [RESULT-1]"
        )
        return SimpleNamespace(
            repaired_text=rewritten,
            to_dict=lambda: {"repairs": 1},
            original_survival_rate=0.08,
            repaired_survival_rate=0.18,
        )


class _StubRepairUnbacked:
    def __init__(self, corpus_texts):
        pass

    def repair(self, validation_results, original_text):
        rewritten = CLEAN_PAPER.replace(
            "## Conclusion\n",
            "## Conclusion\nThese observed gaps demonstrate that the "
            "classifier recovers all signal without any marker here. ",
        )
        return SimpleNamespace(
            repaired_text=rewritten,
            to_dict=lambda: {"repairs": 1},
            original_survival_rate=0.08,
            repaired_survival_rate=0.18,
        )


def _metadata():
    return {
        "result_markers": AUTHORITATIVE,
        "full_paper": {"paper_markdown": CLEAN_PAPER, "word_count": 200},
    }


def _patch_gateway(monkeypatch, repair_cls):
    from backend.pipeline.gateway import claim_evidence_validator, evidence_repair

    monkeypatch.setattr(
        claim_evidence_validator, "ClaimEvidenceValidator", _StubValidator
    )
    monkeypatch.setattr(evidence_repair, "EvidenceRepairLoop", repair_cls)


def test_stage16_rewrite_reconciled_to_exact_values(monkeypatch):
    """The exact bypass: a Stage-16 rewrite carrying 333333/966667 is
    reconciled to the persisted 0.333333/0.966667 before becoming
    authoritative."""
    _patch_gateway(monkeypatch, _StubRepair)
    metadata = _metadata()
    full_paper = metadata["full_paper"]

    CitationAuditStage._run_legacy_validation_and_repair(
        0, CLEAN_PAPER, {"s1": "evidence"}, metadata, full_paper
    )

    final = full_paper["paper_markdown"]
    assert "0.333333 [RESULT-1]" in final
    assert "0.966667 [RESULT-3]" in final
    assert not re.search(r"(?<![\d.])333333 \[RESULT-1\]", final)
    assert not re.search(r"(?<![\d.])966667 \[RESULT-3\]", final)


def test_stage16_unrelated_percentage_fails_closed(monkeypatch):
    _patch_gateway(monkeypatch, _StubRepair97)
    metadata = _metadata()
    full_paper = metadata["full_paper"]

    with pytest.raises(ResultMarkerFidelityError):
        CitationAuditStage._run_legacy_validation_and_repair(
            0, CLEAN_PAPER, {"s1": "evidence"}, metadata, full_paper
        )
    assert "97% [RESULT-1]" in full_paper["paper_markdown"]  # untouched


def test_stage16_unbacked_claim_reintroduced_fails_closed(monkeypatch):
    _patch_gateway(monkeypatch, _StubRepairUnbacked)
    metadata = _metadata()
    full_paper = metadata["full_paper"]

    with pytest.raises(ResultMarkerFidelityError):
        CitationAuditStage._run_legacy_validation_and_repair(
            0, CLEAN_PAPER, {"s1": "evidence"}, metadata, full_paper
        )


def test_non_empirical_repair_path_unaffected(monkeypatch):
    """Without authoritative result markers the repair path behaves as
    before (no fidelity enforcement)."""
    _patch_gateway(monkeypatch, _StubRepair)
    metadata = {"full_paper": {"paper_markdown": CLEAN_PAPER}}

    CitationAuditStage._run_legacy_validation_and_repair(
        0, CLEAN_PAPER, {"s1": "evidence"}, metadata,
        metadata["full_paper"],
    )
    assert "333333 [RESULT-1]" in metadata["full_paper"]["paper_markdown"]


def test_stage16_fail_closed_not_swallowed_by_nonfatal_handler(monkeypatch):
    """The stage's broad non-fatal handler must not convert the
    fail-closed fidelity error into a warning + error marker."""
    _patch_gateway(monkeypatch, _StubRepair97)
    metadata = _metadata()
    full_paper = metadata["full_paper"]

    with pytest.raises(ResultMarkerFidelityError):
        CitationAuditStage._run_legacy_validation_and_repair(
            0, CLEAN_PAPER, {"s1": "evidence"}, metadata, full_paper
        )
    assert "evidence_repair" not in metadata or metadata[
        "evidence_repair"
    ].get("status") != "error"

