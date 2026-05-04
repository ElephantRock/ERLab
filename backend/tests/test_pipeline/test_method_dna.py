"""Tests for MethodDNA extraction — BATCH-65/TASK-01.

TEST-65-01-01: extract returns MethodDNA with populated fields
TEST-65-01-02: Handles ideas with empty fields (returns "unknown" placeholders)
TEST-65-01-03: Keywords extracted from method text
"""

import pytest

from backend.pipeline.generation.method_dna import MethodDNA, MethodDNAExtractor
from backend.pipeline.generation.models import IdeaCandidate


@pytest.fixture
def extractor() -> MethodDNAExtractor:
    return MethodDNAExtractor()


@pytest.fixture
def rich_idea() -> IdeaCandidate:
    return IdeaCandidate(
        title="Reinforcement Learning for Healthcare Scheduling",
        problem_statement="Hospital scheduling is suboptimal.",
        proposed_method=(
            "We propose a reinforcement learning approach that models patient "
            "scheduling as a Markov decision process. The agent learns optimal "
            "scheduling policies through interaction with a simulated hospital "
            "environment using proximal policy optimization."
        ),
        expected_contributions="Improved scheduling efficiency.",
        novelty_rationale="RL has not been applied to hospital scheduling.",
        evaluation_approach="Compare against heuristic baselines on simulated data.",
    )


# ── TEST-65-01-01 ────────────────────────────────────────────────────────


class TestExtractDNAPopulatedFields:
    """TEST-65-01-01: extract returns MethodDNA with populated fields."""

    def test_returns_method_dna_instance(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        assert isinstance(dna, MethodDNA)

    def test_core_technique_populated(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        assert dna.core_technique
        assert dna.core_technique != "unknown"
        assert "reinforcement learning" in dna.core_technique.lower()

    def test_domain_populated(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        assert dna.domain
        assert dna.domain != "general"
        assert dna.domain == "healthcare"

    def test_evaluation_approach_populated(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        assert dna.evaluation_approach
        assert "baselines" in dna.evaluation_approach.lower()

    def test_method_keywords_non_empty(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        assert len(dna.method_keywords) > 0

    def test_to_dict(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        d = dna.to_dict()
        assert set(d) == {
            "core_technique",
            "domain",
            "evaluation_approach",
            "method_keywords",
        }

    def test_extract_batch(self, extractor, rich_idea):
        ideas = [rich_idea, rich_idea]
        results = extractor.extract_batch(ideas)
        assert len(results) == 2
        assert all(isinstance(d, MethodDNA) for d in results)


# ── TEST-65-01-02 ────────────────────────────────────────────────────────


class TestEmptyFieldHandling:
    """TEST-65-01-02: Handles ideas with empty fields gracefully."""

    def test_empty_method_gives_unknown_technique(self, extractor):
        idea = IdeaCandidate(
            title="Empty idea",
            problem_statement="",
            proposed_method="",
        )
        dna = extractor.extract(idea)
        assert dna.core_technique == "unknown"

    def test_empty_evaluation_gives_unknown(self, extractor):
        idea = IdeaCandidate(
            title="Idea with no eval",
            problem_statement="Some problem",
            proposed_method="Some method.",
            evaluation_approach="",
        )
        dna = extractor.extract(idea)
        assert dna.evaluation_approach == "unknown"

    def test_all_empty_fields(self, extractor):
        idea = IdeaCandidate(
            title="",
            problem_statement="",
            proposed_method="",
            evaluation_approach="",
        )
        dna = extractor.extract(idea)
        assert dna.core_technique == "unknown"
        assert dna.evaluation_approach == "unknown"
        assert dna.domain == "general"
        assert dna.method_keywords == []

    def test_whitespace_only_fields(self, extractor):
        idea = IdeaCandidate(
            title="   ",
            problem_statement="   ",
            proposed_method="   ",
            evaluation_approach="   ",
        )
        dna = extractor.extract(idea)
        assert dna.core_technique == "unknown"
        assert dna.evaluation_approach == "unknown"


# ── TEST-65-01-03 ────────────────────────────────────────────────────────


class TestKeywordExtraction:
    """TEST-65-01-03: Keywords extracted from method text."""

    def test_keywords_from_method(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        # High-frequency content words should appear
        assert "scheduling" in dna.method_keywords
        assert "reinforcement" in dna.method_keywords

    def test_stopwords_excluded(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        stopwords = {"the", "a", "is", "that", "with", "for", "and"}
        for sw in stopwords:
            assert sw not in dna.method_keywords

    def test_keywords_limited(self, extractor, rich_idea):
        dna = extractor.extract(rich_idea)
        assert len(dna.method_keywords) <= 10

    def test_nlp_domain_detection(self, extractor):
        idea = IdeaCandidate(
            title="Language Model for Text Summarization",
            problem_statement="Summarization is hard.",
            proposed_method="We use a transformer-based language model for text summarization.",
        )
        dna = extractor.extract(idea)
        assert dna.domain == "NLP"
        assert "summarization" in dna.method_keywords

    def test_keywords_from_title_and_method(self, extractor):
        idea = IdeaCandidate(
            title="Causal Inference in Finance",
            problem_statement="Understanding causality.",
            proposed_method="We apply causal inference to portfolio risk management.",
        )
        dna = extractor.extract(idea)
        # Keywords should come from both title and method
        assert "causal" in dna.method_keywords
        assert "inference" in dna.method_keywords
