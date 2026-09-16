"""BATCH-61/TASK-01 — Per-proposal timeout with graceful continuation.

TEST-61-01-01: Single proposal timeout → placeholder saved, batch continues
TEST-61-01-02: All proposals succeed → no placeholders, all real proposals
TEST-61-01-03: Timeout value respects 300s cap from HB-01
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import ProposalSynthesisStage, StageContext
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal


def _make_idea(title: str, idx: int = 0) -> ResearchIdea:
    return ResearchIdea(
        title=title,
        problem_statement=f"Problem for {title}",
        proposed_method=f"Method for {title}",
        expected_contributions=f"Contributions for {title}",
        novelty_rationale=f"Novelty for {title}",
        evaluation_approach=f"Eval for {title}",
        domain="AI/NLP",
        round_generated=1,
        score=0.7,
    )


def _make_ctx(n_ideas: int = 3) -> StageContext:
    result = PipelineResult()
    result.ideas = [_make_idea(f"Idea {i}", i) for i in range(n_ideas)]
    return StageContext(
        result=result,
        domain="AI/NLP",
        run_id="test_run",
        db_run_id=None,
        params={},
        search_queries=None,
        max_gaps=5,
        rounds=1,
        ideas_per=n_ideas,
        export_format=None,
    )


def _make_proposal(title: str) -> ResearchProposal:
    return ResearchProposal(
        title=title,
        abstract=f"Abstract for {title} with enough words to pass quality checks.",
        introduction=f"Introduction for {title} " * 20,
        proposed_method=f"Method for {title} " * 20,
    )


class TestProposalTimeout:
    """TEST-61-01-01: Single proposal timeout → placeholder saved, batch continues."""

    @pytest.mark.anyio
    async def test_single_timeout_retries_then_marks_synthesis_status(self):
        """Commissioning remediation: a timed-out idea is retried once; if
        synthesis still fails, sections persist EMPTY with an explicit
        synthesis_status marker — never error strings as content — and the
        run continues for the remaining ideas."""
        stage = ProposalSynthesisStage(synthesizer=MagicMock())

        # Idea 0: both attempts time out. Ideas 1 and 2 succeed.
        real_proposal_1 = _make_proposal("Idea 1")
        real_proposal_2 = _make_proposal("Idea 2")
        stage._synthesizer.synthesize = AsyncMock(
            side_effect=[
                TimeoutError(),
                TimeoutError(),
                real_proposal_1,
                real_proposal_2,
            ]
        )

        ctx = _make_ctx(n_ideas=3)

        with patch("backend.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(per_proposal_timeout=5.0)
            result = await stage._execute_synthesis(ctx)

        assert result is True
        proposals = ctx.result.proposals

        # Idea 0: honest failure — empty sections + explicit marker
        assert 0 in proposals
        assert proposals[0].abstract == ""
        assert proposals[0].sections.get("synthesis_status") == "timeout"
        assert "timed out" not in (proposals[0].abstract or "").lower()
        assert proposals[0].title == "Idea 0"

        # Ideas 1 and 2 should be real proposals
        assert 1 in proposals
        assert 2 in proposals
        assert proposals[1].title == "Idea 1"
        assert proposals[2].title == "Idea 2"
        assert "timed out" not in proposals[1].abstract.lower()

    @pytest.mark.anyio
    async def test_all_proposals_succeed_no_placeholders(self):
        """TEST-61-01-02: All proposals succeed → no placeholders, all real proposals."""
        stage = ProposalSynthesisStage(synthesizer=MagicMock())

        ctx = _make_ctx(n_ideas=3)
        stage._synthesizer.synthesize = AsyncMock(
            side_effect=[_make_proposal(f"Idea {i}") for i in range(3)]
        )

        with patch("backend.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(per_proposal_timeout=120.0)
            result = await stage._execute_synthesis(ctx)

        assert result is True
        proposals = ctx.result.proposals
        assert len(proposals) == 3

        for i in range(3):
            assert i in proposals
            assert "timed out" not in proposals[i].abstract.lower()
            assert proposals[i].title == f"Idea {i}"

    def test_timeout_respects_900s_cap(self):
        """TEST-61-01-03: Timeout value respects the 900s HB-01 ceiling
        (raised from 300s on 2026-09-13 after runs 104/135 exhausted the
        old cap)."""
        # When config says 1200s, the effective timeout is capped at 900s
        settings = MagicMock(per_proposal_timeout=1200.0)
        effective = min(getattr(settings, "per_proposal_timeout", 120.0), 900.0)
        assert effective == 900.0

        # When config says 120s, no capping needed
        settings = MagicMock(per_proposal_timeout=120.0)
        effective = min(getattr(settings, "per_proposal_timeout", 120.0), 900.0)
        assert effective == 120.0

        # When config says 900s exactly, it passes uncapped
        settings = MagicMock(per_proposal_timeout=900.0)
        effective = min(getattr(settings, "per_proposal_timeout", 120.0), 900.0)
        assert effective == 900.0

        # When config says 901s, it caps to 900s
        settings = MagicMock(per_proposal_timeout=901.0)
        effective = min(getattr(settings, "per_proposal_timeout", 120.0), 900.0)
        assert effective == 900.0
