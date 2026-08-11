"""Phase A tests: Eval Case Format."""


import pytest

from backend.pipeline.model_certification.eval_case import (
    GoldAnswer,
    StageEvalCase,
    load_suite,
)


def _make_case(**overrides):
    defaults = dict(
        case_id="test-001",
        stage="query_generation",
        prompt_template="Generate research queries about {topic}",
        difficulty="medium",
    )
    defaults.update(overrides)
    return StageEvalCase(**defaults)


class TestEvalCase:
    def test_eval_case_yaml_roundtrip(self):
        case = _make_case(
            gold=GoldAnswer(expected_keys=["machine learning", "NLP"]),
        )
        yaml_str = case.to_yaml()
        loaded = StageEvalCase.from_yaml(yaml_str)
        assert loaded.case_id == case.case_id
        assert loaded.stage == case.stage
        assert loaded.difficulty == case.difficulty

    def test_eval_case_rejects_missing_gold_when_grounding_required(self):
        case = _make_case(
            requires_grounding=True,
            gold=None,
            gold_path=None,
        )
        errors = case.validate()
        assert any("Gold answer required" in e for e in errors)

    def test_eval_case_validates_required_fields(self):
        case = StageEvalCase(case_id="", stage="", prompt_template="")
        errors = case.validate()
        assert len(errors) >= 3  # case_id, stage, prompt_template

    def test_eval_case_difficulty_must_be_easy_medium_hard(self):
        with pytest.raises(ValueError, match="difficulty"):
            StageEvalCase(
                case_id="x", stage="x", prompt_template="x",
                difficulty="impossible",
            )

    def test_load_suite_returns_cases_for_stage(self, tmp_path):
        stage_dir = tmp_path / "query_generation"
        stage_dir.mkdir()
        case = _make_case()
        case.to_yaml_file(stage_dir / "001.yaml")
        loaded = load_suite("query_generation", tmp_path)
        assert len(loaded) == 1
        assert loaded[0].stage == "query_generation"

    def test_load_suite_ignores_other_stages(self, tmp_path):
        qg_dir = tmp_path / "query_generation"
        qg_dir.mkdir()
        _make_case().to_yaml_file(qg_dir / "001.yaml")
        lf_dir = tmp_path / "literature_filtering"
        lf_dir.mkdir()
        _make_case(stage="literature_filtering", case_id="lf-001").to_yaml_file(lf_dir / "001.yaml")

        loaded = load_suite("query_generation", tmp_path)
        assert all(c.stage == "query_generation" for c in loaded)

    def test_gold_answer_yaml_roundtrip(self):
        gold = GoldAnswer(
            expected_keys=["topic1", "topic2"],
            expected_fields={"field": "value"},
            planted_errors=[{"type": "overclaim", "indicator": "proves"}],
        )
        case = _make_case(gold=gold)
        yaml_str = case.to_yaml()
        loaded = StageEvalCase.from_yaml(yaml_str)
        assert loaded.gold is not None
        assert loaded.gold.expected_keys == ["topic1", "topic2"]

    def test_case_id_format_consistent(self):
        case = _make_case(case_id="query_generation-001")
        assert "query_generation" in case.case_id
        assert "-" in case.case_id
