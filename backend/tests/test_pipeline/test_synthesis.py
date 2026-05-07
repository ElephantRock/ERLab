"""Unit tests for proposal synthesis stage."""

import asyncio
import json
from unittest.mock import MagicMock

from backend.pipeline.evaluation.ensemble_review import (
    EnsembleReviewResult,
    PerspectiveReview,
)
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.synthesis.proposal_synthesizer import (
    ProposalSynthesizer,
    ResearchProposal,
)
from backend.tests.test_pipeline.conftest import SchemaAwareFakeProvider


class TestResearchProposalToMarkdown:
    def test_renders_sections_as_headers(self):
        proposal = ResearchProposal(
            title="Test Title",
            abstract="Test Abstract",
            introduction="Intro text",
            proposed_method="Method text",
        )
        md = proposal.to_markdown()
        assert "## Title" in md
        assert "Test Title" in md
        assert "## Abstract" in md
        assert "Test Abstract" in md
        assert "## Introduction" in md

    def test_renders_references_as_bullets(self):
        proposal = ResearchProposal(
            title="X",
            references=["ref1", "ref2"],
        )
        md = proposal.to_markdown()
        assert "## References" in md
        assert "- ref1" in md
        assert "- ref2" in md

    def test_minimal_proposal(self):
        proposal = ResearchProposal(title="Only Title")
        md = proposal.to_markdown()
        assert "## Title" in md
        assert "Only Title" in md


class TestFormatLiterature:
    def test_formats_papers(self):
        papers = [
            Paper(
                id="p1",
                source="test",
                title="Test Paper",
                authors=[Author(name="Smith")],
                year=2024,
                venue="ACL",
            )
        ]
        result = ProposalSynthesizer._format_literature(papers)
        assert "Smith" in result
        assert "2024" in result
        assert "Test Paper" in result

    def test_empty_papers(self):
        result = ProposalSynthesizer._format_literature([])
        assert result == "No specific supporting papers provided."

    def test_limits_to_30(self):
        papers = [
            Paper(id=f"p{i}", source="test", title=f"Paper {i}", year=2024)
            for i in range(40)
        ]
        result = ProposalSynthesizer._format_literature(papers)
        assert result.count("\n") + 1 == 30
        # Also verify [SOURCE-X] indexing
        assert "[SOURCE-30]" in result
        assert "[SOURCE-31]" not in result


class TestProposalSynthesizer:
    def test_synthesize_happy_path(self, sample_ideas):
        provider = SchemaAwareFakeProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(synthesizer.synthesize(sample_ideas[0]))
        assert isinstance(proposal, ResearchProposal)
        assert proposal.title
        assert proposal.abstract

    def test_synthesize_with_reports(
        self, sample_ideas, sample_novelty_report, sample_feasibility_report
    ):
        provider = SchemaAwareFakeProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(
            synthesizer.synthesize(
                sample_ideas[0],
                novelty_report=sample_novelty_report,
                feasibility_report=sample_feasibility_report,
            )
        )
        assert isinstance(proposal, ResearchProposal)
        assert proposal.title

    def test_synthesize_llm_failure(self, sample_ideas):
        provider = SchemaAwareFakeProvider()

        async def _fake_complete(*args, **kwargs):
            raise Exception("LLM down")

        provider.complete = _fake_complete

        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(synthesizer.synthesize(sample_ideas[0]))
        assert isinstance(proposal, ResearchProposal)
        # All sections are empty strings when everything fails
        assert proposal.sections.get("introduction", "") == ""

    def test_synthesize_with_supporting_papers(self, sample_ideas, sample_papers):
        provider = SchemaAwareFakeProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(
            synthesizer.synthesize(sample_ideas[0], supporting_papers=sample_papers)
        )
        assert isinstance(proposal, ResearchProposal)
        # At least one complete() call was made
        assert len(provider._call_log) >= 1
        assert provider._call_log[0]["method"] == "complete"


class TestEnsembleReviewSerialization:
    """BATCH-75/TASK-03: EnsembleReviewResult must be stored as dict, not Pydantic model."""

    @staticmethod
    def _make_reviewer(return_value):
        """Create a mock ensemble reviewer whose review() returns *return_value*."""
        reviewer = MagicMock()

        async def _review(proposal, idea=None):
            return return_value

        reviewer.review = _review
        return reviewer

    @staticmethod
    def _sample_review_result() -> EnsembleReviewResult:
        return EnsembleReviewResult(
            overall_score=0.78,
            methodology=PerspectiveReview(
                perspective="methodology", score=0.8, strengths=["Rigorous design"]
            ),
            novelty=PerspectiveReview(
                perspective="novelty", score=0.75, weaknesses=["Incremental"]
            ),
            clarity=PerspectiveReview(
                perspective="clarity", score=0.8, suggestions=["Add diagram"]
            ),
            consensus_strengths=["Strong evaluation plan"],
            critical_weaknesses=["Limited datasets"],
            actionable_suggestions=["Add ablation study"],
            summary="Solid proposal with minor gaps in evaluation breadth.",
        )

    # TEST-75-03-01
    def test_ensemble_review_is_dict(self, sample_ideas):
        """proposal.sections['ensemble_review'] is a dict after synthesis."""
        provider = SchemaAwareFakeProvider()
        reviewer = self._make_reviewer(self._sample_review_result())
        synthesizer = ProposalSynthesizer(provider, ensemble_reviewer=reviewer)

        proposal = asyncio.run(synthesizer.synthesize(sample_ideas[0]))

        assert isinstance(proposal.sections["ensemble_review"], dict)

    # TEST-75-03-02
    def test_ensemble_review_contains_expected_fields(self, sample_ideas):
        """Dict contains all EnsembleReviewResult fields (overall_score, summary, etc.)."""
        provider = SchemaAwareFakeProvider()
        reviewer = self._make_reviewer(self._sample_review_result())
        synthesizer = ProposalSynthesizer(provider, ensemble_reviewer=reviewer)

        proposal = asyncio.run(synthesizer.synthesize(sample_ideas[0]))
        review = proposal.sections["ensemble_review"]

        assert "overall_score" in review
        assert "summary" in review
        assert "methodology" in review
        assert "novelty" in review
        assert "clarity" in review
        assert "consensus_strengths" in review
        assert "critical_weaknesses" in review
        assert "actionable_suggestions" in review
        assert review["overall_score"] == 0.78

    # TEST-75-03-03
    def test_json_dumps_succeeds_on_all_sections(self, sample_ideas):
        """json.dumps(proposal.sections) succeeds without custom encoder."""
        provider = SchemaAwareFakeProvider()
        reviewer = self._make_reviewer(self._sample_review_result())
        synthesizer = ProposalSynthesizer(provider, ensemble_reviewer=reviewer)

        proposal = asyncio.run(synthesizer.synthesize(sample_ideas[0]))

        # Must not raise TypeError
        serialized = json.dumps(proposal.sections)
        assert isinstance(serialized, str)
        assert "ensemble_review" in serialized

    # TEST-75-03-04
    def test_handles_reviewer_returning_none(self, sample_ideas):
        """proposal.sections gracefully handles ensemble_reviewer returning None."""
        provider = SchemaAwareFakeProvider()
        reviewer = self._make_reviewer(None)
        synthesizer = ProposalSynthesizer(provider, ensemble_reviewer=reviewer)

        proposal = asyncio.run(synthesizer.synthesize(sample_ideas[0]))

        # Should not contain ensemble_review key when reviewer returns None
        assert "ensemble_review" not in proposal.sections
