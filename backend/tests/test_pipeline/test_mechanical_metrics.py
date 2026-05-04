"""Tests for MechanicalMetricsCalculator — BATCH-64 / TASK-01.

6 tests:
  1. test_reference_uniqueness
  2. test_gap_coverage
  3. test_citation_density
  4. test_method_specificity
  5. test_prior_art_distance
  6. test_compute_all_composite
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from backend.pipeline.evaluation.mechanical_metrics import (
    MechanicalMetricsCalculator,
    _clamp,
)

# ── Lightweight stubs ────────────────────────────────────────────────────────

@dataclass
class StubIdea:
    """Mimics IdeaCandidate fields used by the calculator."""
    proposed_method: str = ""
    supporting_papers: list[str] = field(default_factory=list)
    title: str = "stub idea"


@dataclass
class StubPaper:
    """Mimics Paper fields used by the calculator."""
    id: str = "p1"
    citation_count: int | None = None
    abstract: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class StubGap:
    """Mimics ResearchGap fields used by the calculator."""
    title: str = "gap"
    keywords: list[str] = field(default_factory=list)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def calc() -> MechanicalMetricsCalculator:
    return MechanicalMetricsCalculator()


# ── 1. reference_uniqueness ──────────────────────────────────────────────────

class TestReferenceUniqueness:
    def test_all_novel(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(supporting_papers=["A", "B", "C"])
        domain_papers = [StubPaper(id="X"), StubPaper(id="Y")]
        assert calc.reference_uniqueness(idea, domain_papers) == 1.0

    def test_none_novel(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(supporting_papers=["A", "B"])
        domain_papers = [StubPaper(id="A"), StubPaper(id="B")]
        assert calc.reference_uniqueness(idea, domain_papers) == 0.0

    def test_mixed(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(supporting_papers=["A", "B", "C", "D"])
        domain_papers = [StubPaper(id="A"), StubPaper(id="C")]
        # B and D are novel → 2/4 = 0.5
        assert calc.reference_uniqueness(idea, domain_papers) == pytest.approx(0.5)

    def test_empty_citations(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(supporting_papers=[])
        assert calc.reference_uniqueness(idea, []) == 0.0


# ── 2. gap_coverage ─────────────────────────────────────────────────────────

class TestGapCoverage:
    def test_all_gaps_covered(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(proposed_method="We use a transformer and attention mechanism.")
        gaps = [
            StubGap(keywords=["transformer"]),
            StubGap(keywords=["attention"]),
        ]
        assert calc.gap_coverage(idea, gaps) == 1.0

    def test_no_gaps_covered(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(proposed_method="We explore philosophical implications.")
        gaps = [
            StubGap(keywords=["transformer"]),
            StubGap(keywords=["attention"]),
        ]
        assert calc.gap_coverage(idea, gaps) == 0.0

    def test_partial_coverage(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(proposed_method="We propose a transformer-based method.")
        gaps = [
            StubGap(keywords=["transformer"]),
            StubGap(keywords=["reinforcement learning"]),
        ]
        assert calc.gap_coverage(idea, gaps) == pytest.approx(0.5)

    def test_no_gaps(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(proposed_method="Whatever")
        assert calc.gap_coverage(idea, []) == 0.0


# ── 3. citation_density ─────────────────────────────────────────────────────

class TestCitationDensity:
    def test_zero_citations(self, calc: MechanicalMetricsCalculator) -> None:
        papers = [StubPaper(citation_count=0), StubPaper(citation_count=0)]
        idea = StubIdea()
        assert calc.citation_density(idea, papers) == 0.0

    def test_high_density(self, calc: MechanicalMetricsCalculator) -> None:
        papers = [StubPaper(citation_count=1500), StubPaper(citation_count=500)]
        idea = StubIdea()
        # avg = 1000, normalised = 1000/1000 = 1.0
        assert calc.citation_density(idea, papers) == 1.0

    def test_moderate_density(self, calc: MechanicalMetricsCalculator) -> None:
        papers = [StubPaper(citation_count=300), StubPaper(citation_count=100)]
        idea = StubIdea()
        # avg = 200, normalised = 200/1000 = 0.2
        assert calc.citation_density(idea, papers) == pytest.approx(0.2)

    def test_none_citation_count_treated_as_zero(
        self, calc: MechanicalMetricsCalculator
    ) -> None:
        papers = [StubPaper(citation_count=None), StubPaper(citation_count=500)]
        idea = StubIdea()
        # avg = 250, normalised = 0.25
        assert calc.citation_density(idea, papers) == pytest.approx(0.25)

    def test_no_papers(self, calc: MechanicalMetricsCalculator) -> None:
        assert calc.citation_density(StubIdea(), []) == 0.0


# ── 4. method_specificity ───────────────────────────────────────────────────

class TestMethodSpecificity:
    def test_high_specificity(self, calc: MechanicalMetricsCalculator) -> None:
        method = (
            "1. We will implement a transformer-based model.\n"
            "2. We propose using a fine-tune approach.\n"
            "3. Specifically, our method employs contrastive learning.\n"
            "4. We will evaluate against a strong baseline.\n"
            "5. Our framework leverages pre-trained embeddings."
        )
        idea = StubIdea(proposed_method=method)
        score = calc.method_specificity(idea)
        assert 0.0 < score <= 1.0
        # At least several patterns should match → score > 0.3
        assert score > 0.3

    def test_low_specificity(self, calc: MechanicalMetricsCalculator) -> None:
        method = "This is a very vague idea about some topic."
        idea = StubIdea(proposed_method=method)
        assert calc.method_specificity(idea) == 0.0

    def test_empty_method(self, calc: MechanicalMetricsCalculator) -> None:
        idea = StubIdea(proposed_method="")
        assert calc.method_specificity(idea) == 0.0


# ── 5. prior_art_distance ───────────────────────────────────────────────────

class TestPriorArtDistance:
    def test_no_overlap_high_distance(
        self, calc: MechanicalMetricsCalculator
    ) -> None:
        idea = StubIdea(proposed_method="quantum entanglement molecular dynamics")
        papers = [
            StubPaper(abstract="classical mechanics newtonian physics velocity"),
        ]
        # Very different vocabularies → high distance
        dist = calc.prior_art_distance(idea, papers)
        assert dist > 0.7

    def test_high_overlap_low_distance(
        self, calc: MechanicalMetricsCalculator
    ) -> None:
        idea = StubIdea(
            proposed_method="We use transformer attention mechanism for NLP tasks"
        )
        papers = [
            StubPaper(
                abstract="transformer attention mechanism NLP tasks language model"
            ),
        ]
        dist = calc.prior_art_distance(idea, papers)
        # Large overlap → low distance
        assert dist < 0.5

    def test_no_papers_returns_max_distance(
        self, calc: MechanicalMetricsCalculator
    ) -> None:
        idea = StubIdea(proposed_method="some method")
        assert calc.prior_art_distance(idea, []) == 1.0

    def test_empty_abstracts_skip(
        self, calc: MechanicalMetricsCalculator
    ) -> None:
        idea = StubIdea(proposed_method="some method")
        papers = [StubPaper(abstract=None), StubPaper(abstract="")]
        # All empty abstracts → max_sim stays 0 → distance = 1.0
        assert calc.prior_art_distance(idea, papers) == 1.0


# ── 6. compute_all (composite) ──────────────────────────────────────────────

class TestComputeAllComposite:
    def test_all_metrics_returned_in_range(
        self, calc: MechanicalMetricsCalculator
    ) -> None:
        idea = StubIdea(
            proposed_method=(
                "1. We will implement a graph neural network.\n"
                "2. We propose using contrastive learning on molecular data.\n"
                "Our approach leverages attention-based pooling.\n"
                "We evaluate compared to a baseline GCN model.\n"
                "Specifically, our framework fine-tunes pre-trained representations."
            ),
            supporting_papers=["paper_a", "paper_b", "paper_c"],
        )
        gaps = [
            StubGap(keywords=["graph neural network"]),
            StubGap(keywords=["contrastive learning"]),
            StubGap(keywords=["something unrelated"]),
        ]
        supporting = [
            StubPaper(id="paper_a", citation_count=200),
            StubPaper(id="paper_b", citation_count=400),
            StubPaper(id="paper_c", citation_count=100),
        ]
        domain_papers = [StubPaper(id="paper_a")]
        closest = [
            StubPaper(
                id="closest1",
                abstract="graph neural network molecular property prediction",
            ),
        ]

        results = calc.compute_all(
            idea=idea,
            gaps=gaps,
            supporting_papers=supporting,
            all_domain_papers=domain_papers,
            closest_papers=closest,
        )

        expected_keys = {
            "reference_uniqueness",
            "gap_coverage",
            "citation_density",
            "method_specificity",
            "prior_art_distance",
        }
        assert set(results.keys()) == expected_keys

        for name, val in results.items():
            assert 0.0 <= val <= 1.0, f"{name} = {val} out of [0.0, 1.0]"

    def test_defaults_to_supporting_papers_when_closest_not_given(
        self, calc: MechanicalMetricsCalculator
    ) -> None:
        idea = StubIdea(
            proposed_method="novel quantum computing entanglement method",
            supporting_papers=["p1"],
        )
        supporting = [
            StubPaper(id="p1", citation_count=100, abstract="quantum entanglement computing"),
        ]
        results = calc.compute_all(
            idea=idea,
            gaps=[],
            supporting_papers=supporting,
            all_domain_papers=[],
        )
        # Should use supporting_papers for prior_art_distance
        assert "prior_art_distance" in results
        assert 0.0 <= results["prior_art_distance"] <= 1.0


# ── clamp helper ─────────────────────────────────────────────────────────────

class TestClamp:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (-1.0, 0.0),
            (0.0, 0.0),
            (0.5, 0.5),
            (1.0, 1.0),
            (2.5, 1.0),
        ],
    )
    def test_clamp(self, value: float, expected: float) -> None:
        assert _clamp(value) == expected
