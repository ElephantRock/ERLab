"""Tests for constraint validation on evolved artifacts."""

import json

from backend.pipeline.self_improve.constraints import (
    ConstraintConfig,
    ConstraintValidator,
)


class TestConstraintValidator:
    def setup_method(self):
        self.config = ConstraintConfig(
            max_size=100,
            max_growth_pct=0.3,
            allow_empty=False,
            min_sections=2,
        )
        self.validator = ConstraintValidator(self.config)

    def test_all_pass_for_valid_text(self):
        baseline = json.dumps({"a": 1, "b": 2, "c": 3, "d": 4})
        text = json.dumps({"a": 1, "b": 2, "c": 3, "d": 5})  # same length, different value
        assert self.validator.all_passed(text, baseline)

    def test_reject_empty(self):
        results = self.validator.validate("", '{"a":1}')
        non_empty = [r for r in results if r.constraint_name == "non_empty"]
        assert len(non_empty) == 1
        assert not non_empty[0].passed

    def test_allow_empty_when_configured(self):
        v = ConstraintValidator(ConstraintConfig(allow_empty=True, min_sections=0))
        results = v.validate("", "")
        assert all(r.passed for r in results)

    def test_reject_oversized(self):
        text = "x" * 200
        results = self.validator.validate(text, "")
        size = [r for r in results if r.constraint_name == "size_limit"]
        assert len(size) == 1
        assert not size[0].passed

    def test_reject_excessive_growth(self):
        baseline = "short"
        text = "x" * 50  # 10x growth = 900%
        results = self.validator.validate(text, baseline)
        growth = [r for r in results if r.constraint_name == "growth_limit"]
        assert len(growth) == 1
        assert not growth[0].passed

    def test_allow_moderate_growth(self):
        baseline = "x" * 100
        text = "x" * 120  # 20% growth, under 30% limit
        results = self.validator.validate(text, baseline)
        growth = [r for r in results if r.constraint_name == "growth_limit"]
        assert len(growth) == 1
        assert growth[0].passed

    def test_reject_insufficient_structure_json(self):
        text = json.dumps({"only_one": "key"})
        results = self.validator.validate(text, text)
        struct = [r for r in results if r.constraint_name == "structure"]
        assert len(struct) == 1
        assert not struct[0].passed

    def test_accept_sufficient_structure_json(self):
        text = json.dumps({"a": 1, "b": 2, "c": 3})
        results = self.validator.validate(text, text)
        struct = [r for r in results if r.constraint_name == "structure"]
        assert len(struct) == 1
        assert struct[0].passed

    def test_no_baseline_growth_passes(self):
        text = "some content here"
        results = self.validator.validate(text, "")
        growth = [r for r in results if r.constraint_name == "growth_limit"]
        assert growth[0].passed
