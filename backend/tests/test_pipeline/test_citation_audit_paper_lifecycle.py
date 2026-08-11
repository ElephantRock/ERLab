"""Stage-16 paper lifecycle consistency regression tests.

The citation-audit legacy repair path may replace full_paper.paper_markdown.
When it does, the Stage-15 paper evaluation belongs to the old text and must
be recomputed before the repaired paper is persisted as the canonical current
paper.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import CitationAuditStage, StageContext
from backend.pipeline.verification.citation_claim_auditor import CitationAuditReport

_VALID_EVAL = (
    "NOVELTY_SCORE: 0.7\nNOVELTY_JUSTIFICATION: Novel.\n"
    "FEASIBILITY_SCORE: 0.7\nFEASIBILITY_JUSTIFICATION: Feasible.\n"
    "COMPLETENESS_SCORE: 0.7\nCOMPLETENESS_JUSTIFICATION: Complete.\n"
    "RIGOR_SCORE: 0.7\nRIGOR_JUSTIFICATION: Rigorous.\n"
    "CLARITY_SCORE: 0.7\nCLARITY_JUSTIFICATION: Clear.\n"
    "BASELINE_ADEQUACY_SCORE: 0.7\nBASELINE_ADEQUACY_JUSTIFICATION: Adequate.\n"
    "COMPUTE_REALISM_SCORE: 0.7\nCOMPUTE_REALISM_JUSTIFICATION: Realistic.\n"
    "OVERALL_SCORE: 0.7\n"
)


class RecordingEvaluationProvider:
    def __init__(self):
        self.calls = []

    async def complete(self, messages, temperature=0.7, max_tokens=4096, **kwargs):
        self.calls.append(messages)
        return _VALID_EVAL

    @property
    def default_model(self):
        return "recording-eval"


class StubAuditor:
    async def audit(self, proposal_text, source_papers, proposal_id=0):
        return CitationAuditReport(
            proposal_id=proposal_id,
            total_citations=0,
            verified_citations=0,
            fabricated_citations=0,
            context_mismatches=0,
            quantitative_errors=0,
            trust_score=1.0,
            items=[],
            model_used="stub",
            status="complete",
        )


def _ctx():
    result = PipelineResult()
    return StageContext(
        result=result,
        all_papers=[],
        domain="AI/NLP",
        research_question="graph reasoning for language models",
    )


def _proposal(paper_md: str):
    return SimpleNamespace(
        metadata={
            "full_paper": {
                "paper_markdown": paper_md,
                "source_map": [],
            },
            "paper_evaluation": {
                "status": "ready",
                "scope": "paper",
                "dimensions": {"overall": 0.1},
                "evaluated_object": "final_paper",
                "gates": [],
            },
        },
        sections={},
        to_markdown=lambda: "# Proposal\n",
    )


def _repaired_paper():
    return (
        "# Graph Reasoning for Language Models\n\n"
        "## Abstract\n"
        "We study graph reasoning for language models using explicit graph "
        "structure to support relational inference. REPAIRED-SENTINEL\n\n"
        "## Conclusion\n"
        "Graph reasoning is a useful direction for language-model reasoning; "
        "further empirical work is warranted.\n"
    )


def test_changed_paper_is_reevaluated_on_repaired_text():
    provider = RecordingEvaluationProvider()
    stage = CitationAuditStage(provider=provider, auditor=StubAuditor())
    proposal = _proposal(
        "# Graph Reasoning for Language Models\n\n"
        "## Abstract\nOriginal draft about graph reasoning.\n"
    )
    ctx = _ctx()

    def mutate(_idx, _proposal_text, _corpus, metadata, full_paper):
        full_paper["paper_markdown"] = _repaired_paper()
        metadata["full_paper"] = full_paper

    with patch.object(
        CitationAuditStage,
        "_run_legacy_validation_and_repair",
        side_effect=mutate,
    ):
        asyncio.run(stage._audit_proposal(0, proposal, ctx, stage._auditor, []))

    assert proposal.metadata["full_paper"]["paper_markdown"] == _repaired_paper()
    assert proposal.metadata["paper_evaluation"]["status"] == "ready"
    assert proposal.metadata["paper_evaluation"]["dimensions"]["overall"] == 0.7
    assert len(provider.calls) == 1
    rendered_messages = "\n".join(
        str(message.get("content", ""))
        for message in provider.calls[0]
    )
    assert "REPAIRED-SENTINEL" in rendered_messages
    assert "Original draft about graph reasoning" not in rendered_messages


def test_unchanged_paper_keeps_existing_evaluation_without_reevaluation():
    provider = RecordingEvaluationProvider()
    stage = CitationAuditStage(provider=provider, auditor=StubAuditor())
    proposal = _proposal(
        "# Graph Reasoning for Language Models\n\n"
        "## Abstract\nStable graph reasoning paper.\n"
    )
    original_evaluation = dict(proposal.metadata["paper_evaluation"])
    ctx = _ctx()

    with patch.object(
        CitationAuditStage,
        "_run_legacy_validation_and_repair",
        return_value=None,
    ):
        asyncio.run(stage._audit_proposal(0, proposal, ctx, stage._auditor, []))

    assert proposal.metadata["paper_evaluation"] == original_evaluation
    assert provider.calls == []


def test_post_repair_evaluation_failure_never_leaves_old_evaluation_attached():
    stage = CitationAuditStage(auditor=StubAuditor())
    proposal = _proposal(
        "# Graph Reasoning for Language Models\n\n"
        "## Abstract\nOriginal paper.\n"
    )
    ctx = _ctx()

    def mutate(_idx, _proposal_text, _corpus, metadata, full_paper):
        full_paper["paper_markdown"] = _repaired_paper()
        metadata["full_paper"] = full_paper

    with (
        patch.object(
            CitationAuditStage,
            "_run_legacy_validation_and_repair",
            side_effect=mutate,
        ),
        patch.object(
            stage,
            "_reevaluate_repaired_paper",
            new=AsyncMock(side_effect=RuntimeError("evaluation unavailable")),
        ),
    ):
        asyncio.run(stage._audit_proposal(0, proposal, ctx, stage._auditor, []))

    evaluation = proposal.metadata["paper_evaluation"]
    assert evaluation["status"] == "failed"
    assert evaluation["scope"] == "paper"
    assert "Post-repair evaluation failed" in evaluation["error"]
    assert evaluation.get("dimensions", {}).get("overall") != 0.1
