"""Unit tests for proposal synthesis stage."""

import asyncio
from unittest.mock import MagicMock

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

    def test_limits_to_15(self):
        papers = [
            Paper(id=f"p{i}", source="test", title=f"Paper {i}", year=2024)
            for i in range(20)
        ]
        result = ProposalSynthesizer._format_literature(papers)
        assert result.count("\n") + 1 == 15


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
        provider.structured_output = MagicMock(side_effect=Exception("LLM down"))

        async def _fake_structured_output(*args, **kwargs):
            raise Exception("LLM down")

        provider.structured_output = _fake_structured_output

        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(synthesizer.synthesize(sample_ideas[0]))
        assert isinstance(proposal, ResearchProposal)
        assert proposal.sections.get("introduction") == "Synthesis failed. Manual writing required."

    def test_synthesize_with_supporting_papers(self, sample_ideas, sample_papers):
        provider = SchemaAwareFakeProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(
            synthesizer.synthesize(sample_ideas[0], supporting_papers=sample_papers)
        )
        assert isinstance(proposal, ResearchProposal)
        assert len(provider._call_log) == 1
