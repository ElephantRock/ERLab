"""Tests for error taxonomy."""

import json
from pathlib import Path

import pytest

from backend.pipeline.generation.error_taxonomy import ErrorCategory, ErrorTaxonomy


class TestErrorCategory:
    def test_classify_methodological(self):
        taxonomy = ErrorTaxonomy()
        assert taxonomy.classify("The evaluation method is flawed") == ErrorCategory.METHODOLOGICAL
        assert (
            taxonomy.classify("Poor baseline choice and metric selection")
            == ErrorCategory.METHODOLOGICAL
        )

    def test_classify_novelty(self):
        taxonomy = ErrorTaxonomy()
        assert taxonomy.classify("This overlaps with prior work") == ErrorCategory.NOVELTY
        assert (
            taxonomy.classify("Not novel, similar to existing approaches") == ErrorCategory.NOVELTY
        )

    def test_classify_feasibility(self):
        taxonomy = ErrorTaxonomy()
        assert (
            taxonomy.classify("Not feasible with current compute resources")
            == ErrorCategory.FEASIBILITY
        )
        assert taxonomy.classify("Data availability is a concern") == ErrorCategory.FEASIBILITY

    def test_classify_scope(self):
        taxonomy = ErrorTaxonomy()
        assert taxonomy.classify("The scope is too broad") == ErrorCategory.SCOPE

    def test_classify_citation(self):
        taxonomy = ErrorTaxonomy()
        assert taxonomy.classify("Missing citation for related work") == ErrorCategory.CITATION

    def test_classify_unknown(self):
        taxonomy = ErrorTaxonomy()
        assert taxonomy.classify("Some random text with no keywords") is None


class TestErrorTaxonomy:
    def test_record_and_get_weights(self, tmp_path: Path):
        path = tmp_path / "errors.json"
        taxonomy = ErrorTaxonomy(persist_path=str(path))

        taxonomy.record(ErrorCategory.NOVELTY, "Overlaps with existing work")
        taxonomy.record(ErrorCategory.NOVELTY, "Not sufficiently novel")
        taxonomy.record(ErrorCategory.FEASIBILITY, "Too expensive")

        weights = taxonomy.get_weights()
        assert weights[ErrorCategory.NOVELTY] == pytest.approx(2 / 3)
        assert weights[ErrorCategory.FEASIBILITY] == pytest.approx(1 / 3)

    def test_persistence(self, tmp_path: Path):
        path = tmp_path / "errors.json"
        taxonomy1 = ErrorTaxonomy(persist_path=str(path))
        taxonomy1.record(ErrorCategory.METHODOLOGICAL, "Bad method")

        taxonomy2 = ErrorTaxonomy(persist_path=str(path))
        assert taxonomy2.get_weights()[ErrorCategory.METHODOLOGICAL] == 1.0

    def test_format_prompt_section_empty(self, tmp_path: Path):
        path = tmp_path / "errors.json"
        taxonomy = ErrorTaxonomy(persist_path=str(path))
        assert taxonomy.format_prompt_section() == ""

    def test_format_prompt_section_with_data(self, tmp_path: Path):
        path = tmp_path / "errors.json"
        taxonomy = ErrorTaxonomy(persist_path=str(path))
        taxonomy.record(ErrorCategory.NOVELTY, "Not novel")
        taxonomy.record(ErrorCategory.NOVELTY, "Overlap")
        taxonomy.record(ErrorCategory.SCOPE, "Too broad")

        text = taxonomy.format_prompt_section()
        assert "novelty" in text.lower()
        assert "scope" in text.lower()
        assert "67%" in text  # 2/3 = 67%

    def test_equal_weights_on_empty(self, tmp_path: Path):
        path = tmp_path / "errors.json"
        taxonomy = ErrorTaxonomy(persist_path=str(path))
        weights = taxonomy.get_weights()
        assert len(weights) == len(ErrorCategory)
        for w in weights.values():
            assert w == pytest.approx(1.0 / len(ErrorCategory))

    def test_max_descriptions_per_category(self, tmp_path: Path):
        path = tmp_path / "errors.json"
        taxonomy = ErrorTaxonomy(persist_path=str(path))
        for i in range(15):
            taxonomy.record(ErrorCategory.CITATION, f"Citation issue {i}")

        data = json.loads(path.read_text())
        assert len(data["descriptions"]["citation"]) == 10
