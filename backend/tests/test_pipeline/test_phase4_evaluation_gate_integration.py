"""Phase 4 / WP-4D/4E/4F — end-to-end gate integration through _evaluate_paper.

These tests drive the real ``_evaluate_paper`` with a fake provider and assert
that the false-confidence cases observed in all six Phase 3 papers are no longer
possible: a paper with missing provenance / scope drift / conclusion overreach
is recorded as ``status="blocked"``, never ``status="ready"``. Artifact
generation remains accessible (the gate does not raise).

The tests are SYNCHRONOUS (using asyncio.run) so they pass under BOTH the
default asyncio plugin and the canonical selector's ``-p no:asyncio`` flag
(the WP-4G canonical-run mode). The Phase 3 async tests fail under
``-p no:asyncio``; these tests deliberately avoid that failure mode.
"""

import asyncio
from types import SimpleNamespace

import pytest

from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import PaperSynthesisStage, StageContext


def _ctx(research_question="graph reasoning for LLMs", domain="AI/NLP"):
    return StageContext(
        result=PipelineResult(),
        domain=domain,
        research_question=research_question,
    )


def _proposal(paper_md, source_map=None):
    md = {"full_paper": {"paper_markdown": paper_md}}
    if source_map is not None:
        md["full_paper"]["source_map"] = source_map
    return SimpleNamespace(metadata=md)


def _evaluate(stage, ctx, proposal):
    """Run the async _evaluate_paper gate synchronously."""
    return asyncio.run(stage._evaluate_paper(ctx, proposal, proposal.metadata, 1))


@pytest.fixture
def stage(fake_provider):
    # B-EVAL-01: the evaluator now rejects unparseable responses (Commit 3).
    # These gate tests exercise gate logic, not eval parsing, so the fake
    # provider must return a valid tagged evaluation response.
    from backend.tests.conftest import FakeLLMProvider
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
    s = PaperSynthesisStage()
    s._provider = FakeLLMProvider(responses={"complete": _VALID_EVAL})
    return s


class TestFalseConfidenceBlocked:
    """The Phase 3 false-confidence cases are now blocked."""

    def test_markers_without_map_is_blocked_not_ready(self, stage):
        """A paper citing [SOURCE-N] with no map → blocked, not ready."""
        ctx = _ctx()
        proposal = _proposal(
            "# Title\n\nAbstract about reasoning.\n\nBody [SOURCE-1].",
            source_map=[],  # no persisted map
        )
        _evaluate(stage, ctx, proposal)
        eval_state = proposal.metadata["paper_evaluation"]
        assert eval_state["status"] == "blocked"
        assert eval_state["scope"] == "paper"
        assert any("provenance" in r for r in eval_state["blocking_reasons"])

    def test_all_unmapped_markers_is_blocked(self, stage):
        ctx = _ctx()
        proposal = _proposal(
            "[SOURCE-1] [SOURCE-2]",
            source_map=[
                {"marker_index": 1, "marker": "SOURCE-1", "mapping_status": "unmapped"},
                {"marker_index": 2, "marker": "SOURCE-2", "mapping_status": "unmapped"},
            ],
        )
        _evaluate(stage, ctx, proposal)
        assert proposal.metadata["paper_evaluation"]["status"] == "blocked"

    def test_off_scope_paper_is_blocked(self, stage):
        """The Q-Sym drift pattern: neuro-symbolic verifiability → quantization."""
        ctx = _ctx(research_question="neuro-symbolic verifiability for safety-critical systems")
        paper_md = (
            "# Quantization-Aware Training for Efficient Inference\n\n"
            "## Abstract\n"
            "We propose a quantization method that compresses neural networks "
            "for faster inference on edge devices, reducing memory footprint.\n\n"
            "Cites [SOURCE-1]."
        )
        proposal = _proposal(paper_md, source_map=[
            {"marker_index": 1, "marker": "SOURCE-1", "mapping_status": "mapped"},
        ])
        _evaluate(stage, ctx, proposal)
        eval_state = proposal.metadata["paper_evaluation"]
        assert eval_state["status"] == "blocked"
        assert any("scope" in r for r in eval_state["blocking_reasons"])

    def test_overstated_conclusion_is_blocked(self, stage):
        """A design+projection paper claiming demonstration without results."""
        ctx = _ctx(research_question="verifiable reasoning systems")
        paper_md = (
            "# A Conceptual Framework for Verifiable Reasoning\n\n"
            "## Abstract\n"
            "We propose a conceptual framework for verifiable reasoning.\n\n"
            "## Conclusion\n"
            "We validate our approach and demonstrate that it significantly "
            "improves verifiability, proving graph-based methods are superior.\n\n"
            "Cites [SOURCE-1]."
        )
        proposal = _proposal(paper_md, source_map=[
            {"marker_index": 1, "marker": "SOURCE-1", "mapping_status": "mapped"},
        ])
        _evaluate(stage, ctx, proposal)
        eval_state = proposal.metadata["paper_evaluation"]
        assert eval_state["status"] == "blocked"
        assert any("conclusion" in r for r in eval_state["blocking_reasons"])

    def test_grounded_on_scope_paper_is_ready(self, stage):
        """A paper with mapped provenance, on scope, and no overreach is ready."""
        ctx = _ctx(research_question="graph reasoning for LLMs")
        paper_md = (
            "# Graph Reasoning for Large Language Models\n\n"
            "## Abstract\n"
            "We explore graph-based reasoning methods for LLMs, building on "
            "graph structures to support reasoning over complex relationships.\n\n"
            "## Results\n"
            "On three benchmarks our graph reasoning approach improves accuracy.\n\n"
            "## Conclusion\n"
            "Our graph reasoning approach shows promise for LLM reasoning tasks. "
            "Further empirical study is warranted.\n\n"
            "Cites [SOURCE-1]."
        )
        proposal = _proposal(paper_md, source_map=[
            {"marker_index": 1, "marker": "SOURCE-1", "mapping_status": "mapped"},
        ])
        _evaluate(stage, ctx, proposal)
        eval_state = proposal.metadata["paper_evaluation"]
        assert eval_state["status"] == "ready"
        # Gates still recorded as diagnostics.
        assert "gates" in eval_state

    def test_artifact_generation_accessible_when_eval_blocked(self, stage):
        """WP-4D: paper generation remains accessible when evaluation fails.

        The full_paper artifact is untouched by the gate; only paper_evaluation
        is downgraded. This is the truth rule that keeps blocked papers viewable
        and exportable."""
        ctx = _ctx()
        paper_md = "# Title\n\n[SOURCE-1]."
        proposal = _proposal(paper_md, source_map=[])
        original_paper = proposal.metadata["full_paper"]["paper_markdown"]
        _evaluate(stage, ctx, proposal)
        # The artifact is unchanged.
        assert proposal.metadata["full_paper"]["paper_markdown"] == original_paper
        # But the evaluation is blocked.
        assert proposal.metadata["paper_evaluation"]["status"] == "blocked"
