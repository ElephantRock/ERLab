"""Tests for plateau detection with qualified-item ratio."""

from backend.pipeline.generation.models import Critique
from backend.pipeline.generation.strategies import check_plateau


def _critique(suggestions: list[str]) -> Critique:
    return Critique(
        idea_title="Test",
        weaknesses=["weakness"],
        strengths=["strength"],
        suggestions=suggestions,
        overall_assessment="ok",
        score=0.7,
    )


class TestCheckPlateau:
    def test_no_critiques(self):
        result = check_plateau([])
        assert not result.converged
        assert "no_critiques" in result.reason

    def test_no_suggestions_converges(self):
        c = _critique([])
        result = check_plateau([c])
        assert result.converged

    def test_all_specific_stays_active(self):
        c = _critique(["Add a baseline comparison", "Include error bars", "Test on 3 datasets"])
        result = check_plateau([c])
        assert not result.converged

    def test_majority_hedged_converges(self):
        c = _critique(
            [
                "You might consider adding a baseline",
                "Perhaps the method could be clarified",
                "It would be nice to include more experiments",
                "Add error bars",
            ]
        )
        result = check_plateau([c])
        assert result.converged
        assert "plateau" in result.reason

    def test_half_hedged_at_threshold(self):
        c = _critique(["Consider adding X", "Add error bars"])
        result = check_plateau([c], qualification_threshold=0.5)
        assert result.converged  # 1/2 = 50% = at threshold

    def test_custom_threshold(self):
        c = _critique(["Consider X", "Maybe Y", "Add Z"])
        result = check_plateau([c], qualification_threshold=0.9)
        assert not result.converged  # 2/3 = 67%, below 90%
