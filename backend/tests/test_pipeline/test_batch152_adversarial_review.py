"""Tests for BATCH-152: Adversarial Review Stage.

15 tests total:
  TEST-152-01-01 through TEST-152-01-06 (TASK-01: AdversarialReviewer)
  TEST-152-02-01 through TEST-152-02-06 (TASK-02: AdversarialReviewStage + Registration)
  TEST-152-03-01 through TEST-152-03-03 (TASK-03: Provider Resolution + Preset Flags)

All tests use asyncio.run() directly (NOT @pytest.mark.asyncio).
The test file has -p no:asyncio in pytest.ini.
"""

import asyncio
import json
import sys
from dataclasses import fields
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_provider(
    provider_name: str = "mock_local",
    structured_result: dict | None = None,
    raise_error: bool = False,
):
    """Create a mock LLMProvider for testing."""
    provider = MagicMock()
    provider.provider_name = provider_name
    provider.default_model = "mock-model"

    if raise_error:
        provider.structured_output = AsyncMock(side_effect=RuntimeError("Provider unavailable"))
    elif structured_result:
        provider.structured_output = AsyncMock(return_value=structured_result)
    else:
        # Default: passing scores
        provider.structured_output = AsyncMock(return_value={
            "soundness": 8,
            "novelty": 7,
            "feasibility": 8,
            "clarity": 7,
            "soundness_justification": "Solid reasoning.",
            "novelty_justification": "Novel approach.",
            "feasibility_justification": "Feasible with current tools.",
            "clarity_justification": "Well-written.",
            "revision_notes": "",
        })

    return provider


def _make_research_proposal(title="Test Proposal", abstract="Test abstract"):
    """Create a minimal ResearchProposal-like object."""
    from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal
    return ResearchProposal(
        idea_id=0,
        title=title,
        abstract=abstract,
        introduction="This is a test introduction for the proposal.",
        proposed_method="We propose a novel method.",
    )


def _make_stage_context(proposals=None, all_papers=None):
    """Create a minimal StageContext."""
    from backend.pipeline.stages import StageContext
    from backend.pipeline.result import PipelineResult

    result = PipelineResult()
    if proposals:
        result.proposals = proposals
    return StageContext(
        result=result,
        all_papers=all_papers or [],
        domain="AI/NLP",
    )


# ===========================================================================
# TASK-01 TESTS: AdversarialReviewer class
# ===========================================================================


class TestAdversarialReviewScore:
    """TEST-152-01-01: AdversarialReviewScore dataclass has 12 fields."""

    def test_dataclass_has_12_fields(self):
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewScore

        all_fields = [f.name for f in fields(AdversarialReviewScore)]
        expected = [
            "soundness", "novelty", "feasibility", "clarity",
            "overall",
            "soundness_justification", "novelty_justification",
            "feasibility_justification", "clarity_justification",
            "revision_notes", "round", "model_used",
        ]
        assert len(all_fields) == 12, f"Expected 12 fields, got {len(all_fields)}: {all_fields}"
        for field_name in expected:
            assert field_name in all_fields, f"Missing field: {field_name}"

    def test_to_dict(self):
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewScore

        score = AdversarialReviewScore(
            soundness=8, novelty=7, feasibility=8, clarity=7,
            overall=7.5,
            soundness_justification="Good",
            novelty_justification="Novel",
            feasibility_justification="Feasible",
            clarity_justification="Clear",
            revision_notes=None,
            round=1,
            model_used="mock_provider",
        )
        d = score.to_dict()
        assert isinstance(d, dict)
        assert d["soundness"] == 8
        assert d["overall"] == 7.5
        assert d["model_used"] == "mock_provider"


class TestScoreClamping:
    """TEST-152-01-02: Scores clamped to [1,10] range."""

    def test_scores_clamped_when_llm_returns_out_of_range(self):
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer

        mock_provider = _make_mock_provider(structured_result={
            "soundness": 15,
            "novelty": -3,
            "feasibility": 20,
            "clarity": 0,
            "soundness_justification": "test",
            "novelty_justification": "test",
            "feasibility_justification": "test",
            "clarity_justification": "test",
            "revision_notes": "",
        })

        reviewer = AdversarialReviewer(mock_provider)
        score = asyncio.run(reviewer.review("Test proposal", round_num=1))

        assert score.soundness == 10, f"Expected clamped to 10, got {score.soundness}"
        assert score.novelty == 1, f"Expected clamped to 1, got {score.novelty}"
        assert score.feasibility == 10, f"Expected clamped to 10, got {score.feasibility}"
        assert score.clarity == 1, f"Expected clamped to 1, got {score.clarity}"
        # overall should be mean of clamped scores: (10 + 1 + 10 + 1) / 4 = 5.5
        assert score.overall == 5.5


class TestRevisionNotesWhenBelowThreshold:
    """TEST-152-01-03: Revision notes populated when overall < 7."""

    def test_revision_notes_populated_when_overall_below_7(self):
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer

        mock_provider = _make_mock_provider(structured_result={
            "soundness": 3,
            "novelty": 3,
            "feasibility": 3,
            "clarity": 3,
            "soundness_justification": "Weak",
            "novelty_justification": "Not novel",
            "feasibility_justification": "Infeasible",
            "clarity_justification": "Unclear",
            "revision_notes": "The proposal lacks rigor. Improve the method section.",
        })

        reviewer = AdversarialReviewer(mock_provider)
        score = asyncio.run(reviewer.review("Test proposal", round_num=1))

        assert score.overall < 7.0
        assert score.revision_notes is not None
        assert len(score.revision_notes) > 0, "revision_notes should be non-empty"


class TestRevisionNotesWhenAboveThreshold:
    """TEST-152-01-04: Revision notes empty/None when overall >= 7."""

    def test_revision_notes_none_when_overall_above_7(self):
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer

        mock_provider = _make_mock_provider(structured_result={
            "soundness": 9,
            "novelty": 9,
            "feasibility": 9,
            "clarity": 9,
            "soundness_justification": "Excellent",
            "novelty_justification": "Very novel",
            "feasibility_justification": "Highly feasible",
            "clarity_justification": "Crystal clear",
            "revision_notes": "Some notes that should be ignored",
        })

        reviewer = AdversarialReviewer(mock_provider)
        score = asyncio.run(reviewer.review("Test proposal", round_num=1))

        assert score.overall >= 7.0
        assert score.revision_notes is None, f"Expected None, got: {score.revision_notes}"


class TestGracefulFallback:
    """TEST-152-01-05: Graceful fallback on LLM failure."""

    def test_fallback_on_llm_failure(self):
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer

        mock_provider = _make_mock_provider(raise_error=True)
        reviewer = AdversarialReviewer(mock_provider)
        score = asyncio.run(reviewer.review("Test proposal", round_num=1))

        assert score.soundness == 0
        assert score.novelty == 0
        assert score.feasibility == 0
        assert score.clarity == 0
        assert score.overall == 0.0
        assert score.model_used == "none"
        assert "Review skipped" in score.soundness_justification


class TestPromptContent:
    """TEST-152-01-06: Prompt instructs adversarial/critical role."""

    def test_prompt_contains_adversarial_keywords(self):
        from pathlib import Path

        prompt_path = Path(
            "C:/Next-Era/elephant-rock-platform/backend/pipeline/evaluation/prompts/adversarial_review.md"
        )
        content = prompt_path.read_text(encoding="utf-8").lower()

        assert "critical" in content, "Prompt must contain 'critical'"
        assert "weakness" in content, "Prompt must contain 'weakness'"
        assert "challenge" in content, "Prompt must contain 'challenge'"


# ===========================================================================
# TASK-02 TESTS: AdversarialReviewStage + Orchestrator Registration
# ===========================================================================


class TestStageRegistration:
    """TEST-152-02-01: Stage registered in _STAGE_ORDER."""

    def test_adversarial_review_in_stage_order(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator

        assert "adversarial_review" in PipelineOrchestrator._STAGE_ORDER, (
            "adversarial_review must appear in _STAGE_ORDER"
        )


class TestStagePosition:
    """TEST-152-02-02: Stage position after proposal_synthesis."""

    def test_adversarial_review_after_proposal_synthesis(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator

        stage_order = PipelineOrchestrator._STAGE_ORDER
        synth_idx = stage_order.index("proposal_synthesis")
        review_idx = stage_order.index("adversarial_review")
        assert review_idx > synth_idx, (
            f"adversarial_review (index {review_idx}) must come after "
            f"proposal_synthesis (index {synth_idx})"
        )


class TestReSynthesisTriggered:
    """TEST-152-02-03: Re-synthesis triggered on rejection."""

    def test_resynthesis_called_with_revision_notes(self):
        from backend.pipeline.evaluation.adversarial_reviewer import (
            AdversarialReviewScore,
            AdversarialReviewer,
        )
        from backend.pipeline.stages import AdversarialReviewStage

        # Mock reviewer that always rejects
        reviewer = MagicMock(spec=AdversarialReviewer)
        reviewer.review = AsyncMock(return_value=AdversarialReviewScore(
            soundness=4, novelty=4, feasibility=4, clarity=4,
            overall=4.0,
            soundness_justification="Weak",
            novelty_justification="Not novel",
            feasibility_justification="Infeasible",
            clarity_justification="Unclear",
            revision_notes="Please improve the method section.",
            round=1,
            model_used="mock_reviewer",
        ))

        # Mock synthesizer
        mock_proposal = _make_research_proposal()
        synthesizer = MagicMock()
        synthesizer.synthesize = AsyncMock(return_value=mock_proposal)

        stage = AdversarialReviewStage(
            reviewer=reviewer,
            synthesizer=synthesizer,
            generation_provider=_make_mock_provider("cloud"),
            thinking_provider=_make_mock_provider("local"),
        )

        proposal = _make_research_proposal()
        ctx = _make_stage_context(proposals={0: proposal})

        result = asyncio.run(stage.execute(ctx))
        assert result is True

        # Verify synthesizer was called for re-synthesis
        assert synthesizer.synthesize.called, "Synthesizer should have been called for re-synthesis"


class TestMaxRevisionRounds:
    """TEST-152-02-04: Max 2 revision rounds enforced."""

    def test_max_2_revision_rounds(self):
        from backend.pipeline.evaluation.adversarial_reviewer import (
            AdversarialReviewScore,
            AdversarialReviewer,
        )
        from backend.pipeline.stages import AdversarialReviewStage

        call_count = 0

        # Reviewer that always rejects
        async def _always_reject(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return AdversarialReviewScore(
                soundness=4, novelty=4, feasibility=4, clarity=4,
                overall=4.0,
                soundness_justification="Weak",
                novelty_justification="Not novel",
                feasibility_justification="Infeasible",
                clarity_justification="Unclear",
                revision_notes="Improve everything.",
                round=call_count,
                model_used="mock_reviewer",
            )

        reviewer = MagicMock(spec=AdversarialReviewer)
        reviewer.review = AsyncMock(side_effect=_always_reject)

        mock_proposal = _make_research_proposal()
        synthesizer = MagicMock()
        synthesizer.synthesize = AsyncMock(return_value=mock_proposal)

        stage = AdversarialReviewStage(
            reviewer=reviewer,
            synthesizer=synthesizer,
            generation_provider=_make_mock_provider("cloud"),
            thinking_provider=_make_mock_provider("local"),
        )

        proposal = _make_research_proposal()
        ctx = _make_stage_context(proposals={0: proposal})

        asyncio.run(stage.execute(ctx))

        # Should have 3 calls: initial + 2 revision rounds
        assert call_count == 3, f"Expected 3 review calls (1 initial + 2 revisions), got {call_count}"

        # Verify max_revisions_reached flag
        metadata = {}
        if hasattr(proposal, 'metadata') and proposal.metadata:
            if isinstance(proposal.metadata, str):
                metadata = json.loads(proposal.metadata)
            else:
                metadata = proposal.metadata

        review_data = metadata.get("adversarial_review", {})
        assert review_data.get("max_revisions_reached") is True, (
            "max_revisions_reached should be True after 2 failed revision rounds"
        )


class TestStrategyFlagControlsStage:
    """TEST-152-02-05: Strategy flag controls stage execution."""

    def test_stage_skipped_when_flag_disabled(self):
        """When adversarial_review stage is disabled in strategy, it's skipped."""
        from backend.pipeline.orchestrator import PipelineOrchestrator

        # Verify fast_scan has adversarial_review disabled
        from backend.pipeline.strategies import StrategyRegistry, register_presets
        registry = StrategyRegistry()
        register_presets(registry)
        fast_scan = registry.get("fast_scan")

        ar_config = fast_scan.stages.get("adversarial_review")
        assert ar_config is not None, "fast_scan must have adversarial_review in stages"
        assert ar_config.enabled is False, "fast_scan must disable adversarial_review"


class TestPresetsLoadWithoutError:
    """TEST-152-02-06: Regression test — all 4 presets load without error."""

    def test_all_presets_load(self):
        from backend.pipeline.strategies import StrategyRegistry, register_presets
        from backend.pipeline.strategies.models import PipelineStrategy

        registry = StrategyRegistry()
        register_presets(registry)

        for strategy_name in PipelineStrategy:
            config = registry.get(strategy_name.value)
            assert config is not None, f"Preset '{strategy_name.value}' failed to load"
            assert isinstance(config.stages, dict)
            assert len(config.stages) > 0, f"Preset '{strategy_name.value}' has no stages"


# ===========================================================================
# TASK-03 TESTS: Provider Resolution + Preset Flags
# ===========================================================================


class TestDeepResearchPresetFlag:
    """TEST-152-03-01: deep_research preset has adversarial_review=true."""

    def test_deep_research_has_adversarial_review_enabled(self):
        from backend.pipeline.strategies import StrategyRegistry, register_presets

        registry = StrategyRegistry()
        register_presets(registry)
        deep = registry.get("deep_research")

        ar_config = deep.stages.get("adversarial_review")
        assert ar_config is not None, "deep_research must have adversarial_review in stages"
        assert ar_config.enabled is True, "deep_research must enable adversarial_review"


class TestFastScanPresetFlag:
    """TEST-152-03-02: fast_scan preset has adversarial_review=false."""

    def test_fast_scan_has_adversarial_review_disabled(self):
        from backend.pipeline.strategies import StrategyRegistry, register_presets

        registry = StrategyRegistry()
        register_presets(registry)
        fast = registry.get("fast_scan")

        ar_config = fast.stages.get("adversarial_review")
        assert ar_config is not None, "fast_scan must have adversarial_review in stages"
        assert ar_config.enabled is False, "fast_scan must disable adversarial_review"


class TestDifferentProviders:
    """TEST-152-03-03: Different providers for synthesis vs review.

    When thinking provider == generation provider, stage skips with warning.
    """

    def test_stage_skips_when_providers_match(self):
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer
        from backend.pipeline.stages import AdversarialReviewStage

        same_provider = _make_mock_provider("same_provider")

        reviewer = MagicMock(spec=AdversarialReviewer)
        reviewer.review = AsyncMock()

        stage = AdversarialReviewStage(
            reviewer=reviewer,
            synthesizer=MagicMock(),
            generation_provider=same_provider,
            thinking_provider=same_provider,
        )

        proposal = _make_research_proposal()
        ctx = _make_stage_context(proposals={0: proposal})

        result = asyncio.run(stage.execute(ctx))
        assert result is True

        # Review should NOT have been called — providers are the same
        reviewer.review.assert_not_called()
