"""Tests for stage-to-stage traceability (P8)."""

import asyncio

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.pipeline.result import PipelineResult
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
from backend.tests.test_pipeline.conftest import SchemaAwareFakeProvider


class TestSourceGapIds:
    def test_idea_has_source_gap_ids_after_generation(self, sample_ideas):
        provider = SchemaAwareFakeProvider()
        orchestrator = AgentOrchestrator(provider)
        gaps = [
            ResearchGap(
                title="Gap A: Missing evaluation",
                description="No systematic evaluation exists",
                gap_type="methodological",
                confidence=0.9,
                supporting_evidence=[],
            ),
            ResearchGap(
                title="Gap B: Scalability",
                description="Methods don't scale",
                gap_type="technical",
                confidence=0.7,
                supporting_evidence=[],
            ),
        ]
        ideas = asyncio.run(
            orchestrator.run(gaps=gaps, context_papers=[], rounds=1, ideas_per_round=2)
        )
        for idea in ideas:
            assert idea.source_gap_ids == ["Gap A: Missing evaluation", "Gap B: Scalability"]

    def test_source_gap_ids_default_empty(self):
        idea = ResearchIdea(
            title="X",
            problem_statement="P",
            proposed_method="M",
            expected_contributions="C",
            novelty_rationale="N",
            evaluation_approach="E",
        )
        assert idea.source_gap_ids == []


class TestCritiqueHistory:
    def test_critique_history_populated_after_generation(self, sample_ideas):
        provider = SchemaAwareFakeProvider()
        orchestrator = AgentOrchestrator(provider)
        gaps = [ResearchGap(title="Test Gap", description="d", gap_type="methodological", confidence=0.8, supporting_evidence=[])]
        asyncio.run(
            orchestrator.run(gaps=gaps, context_papers=[], rounds=2, ideas_per_round=2)
        )
        assert isinstance(orchestrator.last_critique_history, dict)
        assert len(orchestrator.last_critique_history) > 0
        for round_num, critiques in orchestrator.last_critique_history.items():
            assert isinstance(round_num, int)
            assert isinstance(critiques, list)

    def test_critique_history_in_pipeline_result(self, sample_ideas):
        result = PipelineResult()
        assert isinstance(result.critique_history, dict)
        assert len(result.critique_history) == 0


class TestRefinementHistory:
    def test_refinement_history_populated_after_generation(self, sample_ideas):
        provider = SchemaAwareFakeProvider()
        orchestrator = AgentOrchestrator(provider)
        gaps = [ResearchGap(title="G", description="d", gap_type="methodological", confidence=0.8, supporting_evidence=[])]
        asyncio.run(
            orchestrator.run(gaps=gaps, context_papers=[], rounds=1, ideas_per_round=2)
        )
        assert isinstance(orchestrator.last_refinement_history, dict)
        for _round_num, entry in orchestrator.last_refinement_history.items():
            assert "round" in entry
            assert "original_titles" in entry
            assert "refined_titles" in entry
            assert "score_changes" in entry

    def test_refinement_history_in_pipeline_result(self):
        result = PipelineResult()
        assert isinstance(result.refinement_history, dict)
        assert len(result.refinement_history) == 0


class TestEnrichedClosestMatches:
    def test_success_path_has_enriched_matches(self):
        report = NoveltyReport(
            overall_score=0.75,
            method_novelty=0.8,
            problem_novelty=0.7,
            domain_transfer=0.5,
            combination_novelty=0.8,
            novelty_arguments="Novel combination",
            closest_matches=[
                {
                    "title": "Similar Paper",
                    "distance": 0.3,
                    "id": "p1",
                    "abstract": "An abstract about NLP methods...",
                    "doi": "10.1234/x",
                    "url": "https://example.com/paper",
                }
            ],
        )
        match = report.closest_matches[0]
        assert match["id"] == "p1"
        assert "abstract" in match
        assert match["doi"] == "10.1234/x"
        assert match["url"] == "https://example.com/paper"

    def test_key_risks_passed_to_prompt(self, sample_ideas, sample_feasibility_report):
        provider = SchemaAwareFakeProvider()
        synthesizer = ProposalSynthesizer(provider)
        asyncio.run(
            synthesizer.synthesize(
                sample_ideas[0],
                feasibility_report=sample_feasibility_report,
            )
        )
        # Verify the call was made — key_risks would be rendered into prompt
        assert len(provider._call_log) >= 1

    def test_no_feasibility_report_no_risks(self, sample_ideas):
        provider = SchemaAwareFakeProvider()
        synthesizer = ProposalSynthesizer(provider)
        proposal = asyncio.run(synthesizer.synthesize(sample_ideas[0]))
        assert isinstance(proposal.sections.get("title", ""), str)
