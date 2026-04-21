"""Tests for impasse detection and resolution."""

from backend.pipeline.generation.impasse import (
    ImpasseDetected,
    ImpasseDetector,
    ImpasseType,
)
from backend.pipeline.generation.models import Critique, ResearchIdea


class TestImpasseDetector:
    def _make_ideas(
        self, titles: list[str], scores: list[float] | None = None
    ) -> list[ResearchIdea]:
        ideas = []
        for i, title in enumerate(titles):
            ideas.append(
                ResearchIdea(
                    title=title,
                    problem_statement="",
                    proposed_method="",
                    expected_contributions="",
                    novelty_rationale="",
                    evaluation_approach="",
                    score=scores[i] if scores and i < len(scores) else 0.5,
                )
            )
        return ideas

    def _make_critiques(self, weaknesses: list[list[str]]) -> list[Critique]:
        return [Critique(idea_title=f"Idea {i}", weaknesses=w) for i, w in enumerate(weaknesses)]

    def test_detect_duplicate_ideas(self):
        detector = ImpasseDetector()
        prev = self._make_ideas(["transformer text classification"])
        curr = self._make_ideas(["transformer text classification"])

        result = detector.detect(curr, prev, [], [], [])
        assert result is not None
        assert result.impasse_type == ImpasseType.DUPLICATE_IDEAS

    def test_detect_identical_critiques(self):
        detector = ImpasseDetector()
        critiques = self._make_critiques([["lacks novelty", "poor evaluation methodology"]])
        history = [self._make_critiques([["lacks novelty", "poor evaluation methodology"]])]

        result = detector.detect([], [], critiques, history, [])
        assert result is not None
        assert result.impasse_type == ImpasseType.IDENTICAL_CRITIQUES

    def test_detect_score_plateau(self):
        detector = ImpasseDetector()
        scores = [0.6, 0.6, 0.6]  # No variation

        result = detector.detect([], [], [], [], scores)
        assert result is not None
        assert result.impasse_type == ImpasseType.SCORE_PLATEAU

    def test_no_impasse(self):
        detector = ImpasseDetector()
        prev = self._make_ideas(["Idea about topic A"])
        curr = self._make_ideas(["Idea about completely different topic B"])
        critiques = self._make_critiques([["novel concern about implementation"]])
        scores = [0.5, 0.7, 0.9]

        result = detector.detect(curr, prev, critiques, [], scores)
        assert result is None

    def test_resolve_duplicate_ideas(self):
        detector = ImpasseDetector()
        impasse = ImpasseDetected(
            impasse_type=ImpasseType.DUPLICATE_IDEAS,
            severity=0.8,
            evidence="test",
        )
        resolution = detector.resolve(impasse)
        assert resolution.action == "inject_constraint"
        assert "constraint" in resolution.params

    def test_resolve_identical_critiques(self):
        detector = ImpasseDetector()
        impasse = ImpasseDetected(
            impasse_type=ImpasseType.IDENTICAL_CRITIQUES,
            severity=0.7,
            evidence="test",
        )
        resolution = detector.resolve(impasse)
        assert resolution.action == "switch_strategy"
        assert resolution.params["strategy"] == "meta_reflection"

    def test_resolve_score_plateau(self):
        detector = ImpasseDetector()
        impasse = ImpasseDetected(
            impasse_type=ImpasseType.SCORE_PLATEAU,
            severity=0.6,
            evidence="test",
        )
        resolution = detector.resolve(impasse)
        assert resolution.action == "increase_temperature"
        assert resolution.params["delta"] == 0.1

    def test_empty_inputs(self):
        detector = ImpasseDetector()
        assert detector.detect([], [], [], [], []) is None
