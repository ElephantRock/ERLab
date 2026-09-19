"""Regression: Stage-16 evidence-repair rewrite enters the fidelity boundary.

run_31187f170e93 acceptance failure: the legacy evidence-repair loop
replaced the reconciled empirical paper with its own re-rendered text,
reintroducing dropped-decimal corruption (``333333 [RESULT-1]`` /
``966667 [RESULT-3]``) after the synthesis-time fidelity boundary had
clean values. The boundary now re-applies at the Stage-16 integration
point: the repair output is a candidate only — marker-adjacent numbers
are reconciled to the exact persisted values from the LIVE canonical
markers (``ctx.result.result_markers``) and the same-sentence rule is
re-checked before the rewrite becomes authoritative. Unrepairable values
or unbacked empirical conclusions propagate through
``CitationAuditStage.execute`` (fail closed), leaving the previously
valid paper authoritative.

Uses real ``ResultMarker`` objects and live-shaped ctx — the same
authority the experiment stage writes and paper synthesis consumes.
"""
from __future__ import annotations

import asyncio
import re
from types import SimpleNamespace

from backend.pipeline.experiment.manifest import ResultMarker
from backend.pipeline.stages import CitationAuditStage
from backend.pipeline.synthesis.result_marker_fidelity import (
    ResultMarkerFidelityError,
)

AUTHORITATIVE_MARKERS = [
    ResultMarker(
        marker_index=1,
        marker="RESULT-1",
        metric_name="baseline_accuracy",
        observed_value=0.333333,
        artifact_path="metrics.json",
        artifact_sha256="0" * 64,
        experiment_result_id=29,
        role="baseline",
        direction="higher_better",
    ),
    ResultMarker(
        marker_index=2,
        marker="RESULT-2",
        metric_name="improvement",
        observed_value=0.633333,
        artifact_path="metrics.json",
        artifact_sha256="0" * 64,
        experiment_result_id=29,
        role="derived",
        direction="higher_better",
    ),
    ResultMarker(
        marker_index=3,
        marker="RESULT-3",
        metric_name="model_accuracy",
        observed_value=0.966667,
        artifact_path="metrics.json",
        artifact_sha256="0" * 64,
        experiment_result_id=29,
        role="comparison",
        direction="higher_better",
    ),
]

CLEAN_PAPER = (
    "# Paper\n\n## Abstract\nWe evaluate the frozen protocol: the "
    "baseline scored 0.333333 [RESULT-1] and the model 0.966667 "
    "[RESULT-3].\n\n## Results\n"
    + ("The frozen partition is held fixed across every measurement. " * 8)
    + "\n\n## Conclusion\nThe improvement was 0.633333 [RESULT-2] over "
    "the predeclared majority predictor.\n"
)

CORRUPTED_REWRITE = CLEAN_PAPER.replace(
    "0.333333 [RESULT-1]", "333333 [RESULT-1]"
).replace("0.966667 [RESULT-3]", "966667 [RESULT-3]")

PERCENT_REWRITE = CLEAN_PAPER.replace(
    "0.333333 [RESULT-1]", "97% [RESULT-1]"
)

UNBACKED_REWRITE = CLEAN_PAPER.replace(
    "## Conclusion\n",
    "## Conclusion\nThese observed gaps demonstrate that the classifier "
    "recovers all signal without any marker here. ",
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
    """Returns the scripted rewrite for every repair() call."""

    def __init__(self, rewritten):
        self._rewritten = rewritten
        self.calls = 0

    def repair(self, validation_results, original_text):
        self.calls += 1
        return SimpleNamespace(
            repaired_text=self._rewritten,
            to_dict=lambda: {"repairs": 1},
            original_survival_rate=0.08,
            repaired_survival_rate=0.18,
        )


class _StubAuditor:
    def __init__(self):
        self.calls = 0

    async def audit(self, proposal_text, source_papers, proposal_id):
        self.calls += 1
        return SimpleNamespace(
            to_dict=lambda: {"trust_score": 0.9},
            trust_score=0.9,
            fabricated_citations=0,
            context_mismatches=0,
            quantitative_errors=0,
            items=[],
        )


def _live_ctx(markers, proposal):
    """Live-shaped ctx: proposals + result_markers exactly as the
    experiment stage leaves them."""
    from backend.pipeline.result import PipelineResult

    result = PipelineResult()
    result.proposals = {0: proposal}
    result.result_markers = {0: list(markers)}
    return SimpleNamespace(params={}, result=result, all_papers=[], run_id=None)


def _make_proposal(paper_md: str):
    return SimpleNamespace(
        metadata={"full_paper": {"paper_markdown": paper_md, "word_count": 200}},
        to_markdown=lambda: "proposal text",
    )


def _run_stage(monkeypatch, ctx, rewritten):
    from backend.pipeline.gateway import claim_evidence_validator, evidence_repair

    repair = _StubRepair(rewritten)
    monkeypatch.setattr(
        claim_evidence_validator, "ClaimEvidenceValidator", _StubValidator
    )
    monkeypatch.setattr(
        evidence_repair,
        "EvidenceRepairLoop",
        lambda corpus_texts: repair,
    )

    stage = CitationAuditStage(auditor=_StubAuditor())
    exc = None
    try:
        asyncio.run(stage.execute(ctx))
    except ResultMarkerFidelityError as e:
        exc = e
    return repair, stage, exc


def test_stage16_rewrite_reconciled_to_exact_values(monkeypatch):
    """The exact bypass: a Stage-16 rewrite carrying 333333/966667 is
    reconciled to the persisted 0.333333/0.966667 before it becomes
    authoritative."""
    proposal = _make_proposal(CLEAN_PAPER)
    ctx = _live_ctx(AUTHORITATIVE_MARKERS, proposal)
    repair, stage, exc = _run_stage(monkeypatch, ctx, CORRUPTED_REWRITE)

    assert exc is None
    final = proposal.metadata["full_paper"]["paper_markdown"]
    assert "0.333333 [RESULT-1]" in final
    assert "0.966667 [RESULT-3]" in final
    assert not re.search(r"(?<![\d.])333333 \[RESULT-1\]", final)
    assert not re.search(r"(?<![\d.])966667 \[RESULT-3\]", final)


def test_stage16_unrelated_percentage_propagates_and_keeps_valid_paper(monkeypatch):
    """A 97% rewrite fails closed through CitationAuditStage.execute and
    the previously valid paper remains authoritative (candidate-only
    assignment)."""
    proposal = _make_proposal(CLEAN_PAPER)
    ctx = _live_ctx(AUTHORITATIVE_MARKERS, proposal)
    repair, stage, exc = _run_stage(monkeypatch, ctx, PERCENT_REWRITE)

    assert isinstance(exc, ResultMarkerFidelityError)
    # The invalid candidate never became authoritative.
    assert proposal.metadata["full_paper"]["paper_markdown"] == CLEAN_PAPER
    assert "97% [RESULT-1]" not in proposal.metadata["full_paper"]["paper_markdown"]
    # Not downgraded to a skipped audit.
    assert proposal.metadata.get("citation_audit", {}).get("status") != "skipped"


def test_stage16_unbacked_claim_reintroduced_fails_closed(monkeypatch):
    proposal = _make_proposal(CLEAN_PAPER)
    ctx = _live_ctx(AUTHORITATIVE_MARKERS, proposal)
    repair, stage, exc = _run_stage(monkeypatch, ctx, UNBACKED_REWRITE)

    assert isinstance(exc, ResultMarkerFidelityError)
    assert proposal.metadata["full_paper"]["paper_markdown"] == CLEAN_PAPER


def test_non_empirical_repair_path_unaffected(monkeypatch):
    """Without canonical markers on the context the repair path behaves as
    before (no fidelity enforcement)."""
    proposal = _make_proposal(CLEAN_PAPER)
    ctx = _live_ctx([], proposal)
    repair, stage, exc = _run_stage(monkeypatch, ctx, CORRUPTED_REWRITE)

    assert exc is None
    final = proposal.metadata["full_paper"]["paper_markdown"]
    assert re.search(r"(?<![\d.])333333 \[RESULT-1\]", final)
