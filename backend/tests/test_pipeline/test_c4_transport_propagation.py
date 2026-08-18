"""Case-4 R2 regression: cloud-provider transport failures keep typed
identity through post-ideation fail-soft paths.

Adjudicated GENERIC_PRODUCT_DEFECT (2026-08-18), from the qualifying-run
specimen evidence/case4_qualifying_runfail_1 on the Case-4 evidence
branch: an exhausted z.ai quota raised GatewayTransportError, which the
fail-soft proposal/paper/evaluation machinery converted into fallback
artifacts (a 207-character stub paper, fallback review scores, GEval
parse fallbacks, and a non-promoting cold repair) while the orchestrator
finalized SUCCEEDED.

The correction re-raises GatewayTransportError at every proven catchall
so the EXISTING Q2 stage-loop terminalization converts it to
FAILED_EXECUTION (covered by
test_q2_failclosed.py::test_coordinator_terminalizes_transport_failure).
These tests prove the propagation layer: an injected GatewayTransportError
must escape each fail-soft path instead of becoming degraded output.
"""

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipeline.gateway.transport import GatewayTransportError


def _gte() -> GatewayTransportError:
    return GatewayTransportError(
        "test_task", "injected: usage limit reached for 5 hour"
    )


def _raising_provider(*, structured: bool = False) -> MagicMock:
    provider = MagicMock()
    if structured:
        provider.structured_output = AsyncMock(side_effect=_gte())
    else:
        provider.complete = AsyncMock(side_effect=_gte())
    return provider


def _idea() -> SimpleNamespace:
    return SimpleNamespace(
        title="Test idea",
        problem_statement="Problem",
        proposed_method="Method",
        expected_contributions="Contributions",
        novelty_rationale="Novelty",
        evaluation_approach="Eval",
        domain="machine learning",
        round_generated=1,
        score=0.7,
        supporting_papers=[],
    )


# ── Helper-layer propagation ────────────────────────────────────────────


class TestHelperLayerPropagation:
    def test_proposal_synthesizer_re_raises(self):
        from backend.pipeline.synthesis.proposal_synthesizer import (
            ProposalSynthesizer,
        )

        synth = ProposalSynthesizer(provider=_raising_provider())
        with pytest.raises(GatewayTransportError):
            asyncio.run(synth.synthesize(idea=_idea()))

    def test_governance_validator_re_raises(self):
        from backend.pipeline.governance.validator import OutputValidator

        validator = OutputValidator(
            provider=_raising_provider(structured=True)
        )
        with pytest.raises(GatewayTransportError):
            asyncio.run(validator.validate(
                "A sufficiently long proposal body with no structural"
                " violations so the LLM check path is exercised."
            ))

    def test_adversarial_reviewer_re_raises(self):
        from backend.pipeline.evaluation.adversarial_reviewer import (
            AdversarialReviewer,
        )

        reviewer = AdversarialReviewer(
            provider=_raising_provider(structured=True)
        )
        with pytest.raises(GatewayTransportError):
            asyncio.run(reviewer.review(proposal_text="proposal text"))

    def test_paper_synthesizer_re_raises(self):
        from backend.pipeline.synthesis.paper_synthesizer import (
            PaperSynthesizer,
            SynthesisSession,
        )

        synth = PaperSynthesizer(provider=_raising_provider())
        session = SynthesisSession(
            proposal_text="proposal text",
            source_papers=(),
            domain="machine learning",
        )
        with pytest.raises(GatewayTransportError):
            asyncio.run(synth.synthesize_session(session))

    def test_synthesis_service_re_raises(self):
        from backend.pipeline.synthesis.synthesis_service import (
            synthesize_paper,
        )

        with pytest.raises(GatewayTransportError):
            asyncio.run(synthesize_paper(
                provider=_raising_provider(),
                proposal_text="proposal text",
                source_papers=[],
                source_ids=[],
                domain="machine learning",
                proposal_id=1,
            ))


    def test_synthesis_service_specimen_sequence_re_raises(self):
        """The exact specimen path: monolithic call returns HTTP-200-empty
        (HB-02 None, untouched by design), the service falls back to
        section-wise, and the quota-exhausted transport error raised
        there must escape instead of producing a partial paper."""
        from backend.pipeline.synthesis.synthesis_service import (
            synthesize_paper,
        )

        provider = MagicMock()
        provider.complete = AsyncMock(
            side_effect=["", "1. Introduction", _gte()]
        )
        with pytest.raises(GatewayTransportError):
            asyncio.run(synthesize_paper(
                provider=provider,
                proposal_text="proposal text",
                source_papers=[],
                source_ids=[],
                domain="machine learning",
                proposal_id=1,
            ))

    def test_pipeline_evaluator_debate_re_raises(self):
        from backend.pipeline.evaluation.pipeline_evaluator import (
            PipelineEvaluator,
        )

        debate = MagicMock()
        debate.debate = AsyncMock(side_effect=_gte())
        evaluator = PipelineEvaluator.__new__(PipelineEvaluator)
        evaluator._geval_scorers = {}
        evaluator._deepeval_scorers = {}
        evaluator._quality_gate = None
        evaluator._debate = debate
        with pytest.raises(GatewayTransportError):
            asyncio.run(evaluator.evaluate_idea(
                idea=_idea(), target_id="idea-0"
            ))


# ── Stage-layer propagation (specimen-proven per-proposal catches) ─────


def _stage_ctx(proposals: dict) -> SimpleNamespace:
    ctx = SimpleNamespace(
        result=SimpleNamespace(proposals=proposals),
        params={},
        provider_override=None,
    )
    ctx.result.experiments = {}
    ctx.result.experiment_runs = {}
    ctx.result.result_markers = {}
    ctx.all_papers = []
    return ctx


class TestStageLayerPropagation:
    def test_adversarial_review_stage_re_raises(self):
        from backend.pipeline.stages import AdversarialReviewStage

        stage = AdversarialReviewStage(
            reviewer=MagicMock(), synthesizer=MagicMock()
        )

        async def _boom(idx, proposal, ctx):
            raise _gte()

        stage._review_proposal = _boom
        ctx = _stage_ctx({0: SimpleNamespace(metadata=None)})
        with pytest.raises(GatewayTransportError):
            asyncio.run(stage.execute(ctx))

    def test_paper_synthesis_stage_re_raises(self):
        from backend.pipeline.stages import PaperSynthesisStage

        stage = PaperSynthesisStage.__new__(PaperSynthesisStage)
        stage._provider = MagicMock()
        stage._synthesizer = MagicMock()
        stage._context_window = 8192
        stage.PER_PROPOSAL_TIMEOUT = 30.0

        async def _boom(*args, **kwargs):
            raise _gte()

        stage._synthesize_paper_for_proposal = _boom
        ctx = _stage_ctx({0: SimpleNamespace(metadata=None)})
        with pytest.raises(GatewayTransportError):
            asyncio.run(stage.execute(ctx))


# ── Governed repair path ────────────────────────────────────────────────


class TestGovernedRepairPropagation:
    def test_auto_revise_paper_re_raises(self, monkeypatch):
        import backend.pipeline.evaluation.paper_remediator as pr

        @contextlib.contextmanager
        def _fake_session():
            session = MagicMock()
            session.execute = MagicMock(return_value=MagicMock(
                scalar_one_or_none=MagicMock(return_value=None)
            ))
            session.get = MagicMock(return_value=None)
            session.add = MagicMock()
            session.commit = MagicMock()
            yield session

        monkeypatch.setattr(pr, "get_session", _fake_session)

        async def _raising_synthesize(self, **kwargs):
            raise _gte()

        from backend.pipeline.synthesis.paper_synthesizer import (
            PaperSynthesizer,
        )
        monkeypatch.setattr(
            PaperSynthesizer, "synthesize", _raising_synthesize
        )

        spec = SimpleNamespace(
            research_question="rq",
            task_type="classification",
            target_name="target",
            analysis_method="method",
            baseline_method="baseline",
            comparison_method="comparison",
            primary_metric="metric",
            metric_directions={"metric": "lower"},
            dataset_name="dataset",
            split_method="split",
            dataset_raw_sha256="",
            random_seed=42,
        )
        with pytest.raises(GatewayTransportError):
            asyncio.run(pr.auto_revise_paper(
                proposal_id=1,
                experiment_result_id=1,
                original_paper_md="# Blocked paper",
                blocking_findings=["finding"],
                source_map=[],
                result_markers=[],
                spec=spec,
            ))
