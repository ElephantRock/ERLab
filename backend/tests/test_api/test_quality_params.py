"""Tests for intent-based quality parameter mapping.

Verifies semantics: detailed > standard > concise, thorough > light, etc.
"""

import pytest

from backend.pipeline.quality.quality_params import (
    BASE_IDEATOR_TEMPERATURE,
    BASE_MIN_WORDS,
    BASE_NOVELTY_TOP_K,
    resolve_all,
    resolve_ideator_temperature,
    resolve_min_words,
    resolve_novelty_top_k,
)


class TestProposalDepthMapping:
    """Proposal depth controls section minimum word counts."""

    def test_standard_returns_base_values(self):
        """Standard depth returns base MIN_WORDS unchanged."""
        result = resolve_min_words("standard")
        assert result == BASE_MIN_WORDS

    def test_detailed_increases_minimums(self):
        """Detailed depth produces higher word counts than standard."""
        standard = resolve_min_words("standard")
        detailed = resolve_min_words("detailed")
        for section in BASE_MIN_WORDS:
            assert detailed[section] > standard[section], f"{section} should be higher"

    def test_concise_decreases_minimums(self):
        """Concise depth produces lower word counts than standard."""
        standard = resolve_min_words("standard")
        concise = resolve_min_words("concise")
        for section in BASE_MIN_WORDS:
            assert concise[section] < standard[section], f"{section} should be lower"

    def test_none_defaults_to_standard(self):
        """None depth returns base values (backward compat)."""
        result = resolve_min_words(None)
        assert result == BASE_MIN_WORDS

    def test_does_not_mutate_base(self):
        """Resolving min_words never mutates the immutable base."""
        original = dict(BASE_MIN_WORDS)
        resolve_min_words("detailed")
        resolve_min_words("concise")
        assert original == BASE_MIN_WORDS

    def test_concise_floors_at_50_words(self):
        """Concise never reduces below 50 words per section."""
        concise = resolve_min_words("concise")
        for section, words in concise.items():
            assert words >= 50, f"{section} floored at 50 words"


class TestNoveltyDepthMapping:
    """Novelty depth controls how many papers are checked."""

    def test_standard_returns_base(self):
        assert resolve_novelty_top_k("standard") == 20

    def test_thorough_is_larger_than_standard(self):
        assert resolve_novelty_top_k("thorough") > resolve_novelty_top_k("standard")
        assert resolve_novelty_top_k("thorough") == 50

    def test_light_is_smaller_than_standard(self):
        assert resolve_novelty_top_k("light") < resolve_novelty_top_k("standard")
        assert resolve_novelty_top_k("light") == 10

    def test_none_defaults_to_standard(self):
        assert resolve_novelty_top_k(None) == BASE_NOVELTY_TOP_K


class TestIdeaDiversityMapping:
    """Idea diversity controls ideator temperature."""

    def test_balanced_returns_base(self):
        assert resolve_ideator_temperature("balanced") == BASE_IDEATOR_TEMPERATURE

    def test_exploratory_is_warmer_than_balanced(self):
        assert resolve_ideator_temperature("exploratory") > resolve_ideator_temperature("balanced")
        assert resolve_ideator_temperature("exploratory") == pytest.approx(1.1)

    def test_focused_is_cooler_than_balanced(self):
        assert resolve_ideator_temperature("focused") < resolve_ideator_temperature("balanced")
        assert resolve_ideator_temperature("focused") == pytest.approx(0.3)

    def test_none_defaults_to_balanced(self):
        assert resolve_ideator_temperature(None) == BASE_IDEATOR_TEMPERATURE


class TestResolveAll:
    """resolve_all returns all effective settings in one dict."""

    def test_returns_all_keys(self):
        result = resolve_all("concise", "thorough", "exploratory")
        assert "proposal_depth" in result
        assert "effective_min_words" in result
        assert "novelty_depth" in result
        assert "effective_novelty_top_k" in result
        assert "idea_diversity" in result
        assert "effective_ideator_temperature" in result

    def test_none_inputs_default_to_standard(self):
        result = resolve_all(None, None, None)
        assert result["proposal_depth"] == "standard"
        assert result["novelty_depth"] == "standard"
        assert result["idea_diversity"] == "balanced"

    def test_detailed_uses_higher_min_words(self):
        standard_result = resolve_all("standard")
        detailed_result = resolve_all("detailed")
        # Method section should be notably different
        assert (
            detailed_result["effective_min_words"]["proposed_method"]
            > standard_result["effective_min_words"]["proposed_method"]
        )


class TestPipelineRunRequestAccepts:
    """PipelineRunRequest schema accepts quality fields."""

    def test_accepts_quality_fields(self):
        from backend.api.schemas import PipelineRunRequest

        req = PipelineRunRequest(
            domain="test",
            proposal_depth="detailed",
            novelty_depth="thorough",
            idea_diversity="exploratory",
        )
        assert req.proposal_depth == "detailed"
        assert req.novelty_depth == "thorough"
        assert req.idea_diversity == "exploratory"

    def test_defaults_to_standard(self):
        from backend.api.schemas import PipelineRunRequest

        req = PipelineRunRequest()
        assert req.proposal_depth == "standard"
        assert req.novelty_depth == "standard"
        assert req.idea_diversity == "balanced"

    def test_rejects_invalid_depth(self):
        from pydantic import ValidationError

        from backend.api.schemas import PipelineRunRequest

        with pytest.raises(ValidationError):
            PipelineRunRequest(proposal_depth="invalid")

    def test_rejects_invalid_novelty(self):
        from pydantic import ValidationError

        from backend.api.schemas import PipelineRunRequest

        with pytest.raises(ValidationError):
            PipelineRunRequest(novelty_depth="exhaustive")

    def test_rejects_invalid_diversity(self):
        from pydantic import ValidationError

        from backend.api.schemas import PipelineRunRequest

        with pytest.raises(ValidationError):
            PipelineRunRequest(idea_diversity="wild")


class TestQualitySettingsVisibility:
    """Effective quality settings are resolvable and structured for run detail."""

    def test_resolve_all_provides_effective_values(self):
        """resolve_all returns a dict with effective_* keys for run detail."""
        result = resolve_all("detailed", "thorough", "exploratory")
        # Effective values present
        assert "effective_min_words" in result
        assert "effective_novelty_top_k" in result
        assert "effective_ideator_temperature" in result
        # Effective values match the semantic intent
        assert result["effective_novelty_top_k"] == 50
        assert result["effective_ideator_temperature"] == pytest.approx(1.1)

    def test_resolve_all_effective_min_words_are_concrete(self):
        """Effective min_words are concrete numbers, not multipliers."""
        result = resolve_all("concise")
        effective = result["effective_min_words"]
        for section, words in effective.items():
            assert isinstance(words, int)
            assert words >= 50, f"{section} floored at 50"

    def test_resolve_all_standard_matches_base(self):
        """Standard/balanced effective values match immutable base constants."""
        result = resolve_all(None, None, None)
        assert result["effective_min_words"] == BASE_MIN_WORDS
        assert result["effective_novelty_top_k"] == BASE_NOVELTY_TOP_K
        assert result["effective_ideator_temperature"] == BASE_IDEATOR_TEMPERATURE

    def test_quality_config_shape_for_run_detail(self):
        """The quality dict shape stored in config_json has the right structure."""
        quality = resolve_all("standard", "standard", "balanced")
        config_quality = {
            "proposal_depth": quality["proposal_depth"],
            "novelty_depth": quality["novelty_depth"],
            "idea_diversity": quality["idea_diversity"],
            "effective": {
                "min_words": quality["effective_min_words"],
                "novelty_top_k": quality["effective_novelty_top_k"],
                "ideator_temperature": quality["effective_ideator_temperature"],
            },
        }
        # Shape checks
        assert config_quality["proposal_depth"] == "standard"
        assert config_quality["effective"]["novelty_top_k"] == 20
        assert "abstract" in config_quality["effective"]["min_words"]
        assert isinstance(config_quality["effective"]["ideator_temperature"], float)
