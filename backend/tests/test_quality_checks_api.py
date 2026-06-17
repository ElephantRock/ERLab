"""Tests for backend.api.quality_checks.compute_quality_checks."""

import pytest

from backend.api.quality_checks import compute_quality_checks


class TestComputeQualityChecks:
    """Tests for deterministic quality check computation on persisted sections."""

    def test_returns_none_for_none_input(self):
        assert compute_quality_checks(None) is None

    def test_returns_none_for_empty_dict(self):
        assert compute_quality_checks({}) is None

    def test_returns_none_for_non_dict_input(self):
        assert compute_quality_checks("not a dict") is None

    def test_all_sections_passing(self):
        """A well-formed proposal should have all sections pass."""
        sections = {
            "abstract": "word " * 160,
            "introduction": "Our contributions include novelty. " * 100,
            "related_work": "Some prior work [1] by Smith (2024). " * 50,
            "proposed_method": (
                "We define the loss function $$L = \\sum x^2$$ "
                "and optimize using Adam optimizer. "
                "We use $w$ as weights on GPU A100. "
            ) * 35,
            "expected_contributions": "contribution " * 200,
            "evaluation_plan": (
                "We compare against a baseline with ablation "
                "and a naive cross-domain retrieval without alignment "
                "using accuracy and F1 metric. "
            ) * 20,
            "timeline": "We need GPU A100 7B model compute. " * 20,
            "risk_mitigation": "risk " * 200,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        assert len(result) == len({r["section"] for r in result})
        passing = [r for r in result if r["passed"]]
        assert len(passing) == len(result), "All sections should pass"

    def test_short_section_fails_word_count(self):
        """A section below the word-count threshold should fail."""
        sections = {
            "abstract": "short",  # 1 word, min 150
        }
        result = compute_quality_checks(sections)
        assert result is not None
        abstract_check = next(r for r in result if r["section"] == "abstract")
        assert not abstract_check["meets_word_count"]
        assert not abstract_check["passed"]
        assert any("word count" in f for f in abstract_check["failures"])

    def test_missing_section_marked_not_present(self):
        """A section key absent from the dict should be marked not present."""
        sections = {"abstract": "word " * 160}
        result = compute_quality_checks(sections)
        assert result is not None
        intro_check = next(r for r in result if r["section"] == "introduction")
        assert not intro_check["present"]
        assert not intro_check["passed"]
        assert intro_check["word_count"] == 0

    def test_present_but_empty_string_is_not_present(self):
        """An empty or whitespace-only string counts as not present."""
        sections = {"abstract": "   "}
        result = compute_quality_checks(sections)
        assert result is not None
        abstract_check = next(r for r in result if r["section"] == "abstract")
        assert not abstract_check["present"]

    def test_pattern_check_failure_detected(self):
        """proposed_method without loss function should fail pattern check."""
        sections = {
            "proposed_method": "word " * 700,  # enough words but no patterns
        }
        result = compute_quality_checks(sections)
        assert result is not None
        method_check = next(r for r in result if r["section"] == "proposed_method")
        assert method_check["present"]
        assert method_check["meets_word_count"]
        assert not method_check["passed"]
        # Should have pattern failures
        assert len(method_check["failures"]) > 0
        assert any("missing" in f for f in method_check["failures"])

    def test_evaluation_plan_pattern_checks(self):
        """evaluation_plan should check for baselines, ablation, metrics."""
        sections = {
            "evaluation_plan": "We test with a baseline and ablation and metric. " * 15,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        eval_check = next(r for r in result if r["section"] == "evaluation_plan")
        # "baseline", "ablation", "metric" all present, but "naive cross-domain" may fail
        checks_by_name = {c["name"]: c["passed"] for c in eval_check["checks"]}
        assert checks_by_name.get("named baselines") is True
        assert checks_by_name.get("ablation experiments") is True

    def test_ignores_non_prose_keys(self):
        """ensemble_review, references, title should not be checked."""
        sections = {
            "title": "Test",
            "references": [{"raw": "[1] Test"}],
            "ensemble_review": {"overall_score": 0.8},
        }
        result = compute_quality_checks(sections)
        assert result is not None
        section_keys = {r["section"] for r in result}
        assert "ensemble_review" not in section_keys
        assert "references" not in section_keys
        assert "title" not in section_keys

    def test_each_result_has_required_fields(self):
        sections = {"abstract": "word " * 160}
        result = compute_quality_checks(sections)
        assert result is not None
        for r in result:
            assert "section" in r
            assert "label" in r
            assert "present" in r
            assert "word_count" in r
            assert "min_words" in r
            assert "meets_word_count" in r
            assert "checks" in r
            assert "passed" in r
            assert "failures" in r
            assert isinstance(r["failures"], list)
            assert isinstance(r["checks"], list)

    def test_label_is_human_readable(self):
        sections = {"proposed_method": "x"}
        result = compute_quality_checks(sections)
        assert result is not None
        method_check = next(r for r in result if r["section"] == "proposed_method")
        assert method_check["label"] == "Proposed Method"

    def test_list_section_word_count(self):
        """Word count should handle list values (e.g., references as dicts)."""
        sections = {
            "expected_contributions": [
                {"text": "one two three four five"},
                {"text": "six seven eight nine ten"},
            ] * 20,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        ec_check = next(r for r in result if r["section"] == "expected_contributions")
        assert ec_check["word_count"] > 0
        assert ec_check["present"]
