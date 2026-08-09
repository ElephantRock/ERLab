"""Regression tests for Stage 14 -> Stage 15 result semantics."""

from dataclasses import dataclass

from backend.pipeline.stages import PaperSynthesisStage


@dataclass
class MarkerStub:
    marker: str = "RESULT-1"
    metric_name: str = "balanced_accuracy"
    observed_value: float = 0.973
    role: str = "comparison"
    direction: str = "higher_is_better"
    experiment_result_id: int = 42


def test_short_marker_preserves_role_and_direction():
    rendered = PaperSynthesisStage._format_result_marker(MarkerStub())

    assert rendered == (
        "[RESULT-1] balanced_accuracy = 0.973 "
        "(role=comparison, direction=higher_is_better)"
    )


def test_long_marker_adds_provenance_without_changing_semantics():
    rendered = PaperSynthesisStage._format_result_marker(
        MarkerStub(),
        include_provenance=True,
    )

    assert "[RESULT-1] balanced_accuracy = 0.973" in rendered
    assert "role=comparison" in rendered
    assert "direction=higher_is_better" in rendered
    assert "source=metrics.json" in rendered
    assert "experiment_result_id=42" in rendered


def test_baseline_and_comparison_remain_distinct():
    model = MarkerStub(
        marker="RESULT-1",
        observed_value=0.973,
        role="comparison",
    )
    baseline = MarkerStub(
        marker="RESULT-2",
        observed_value=0.500,
        role="baseline",
    )

    model_text = PaperSynthesisStage._format_result_marker(model)
    baseline_text = PaperSynthesisStage._format_result_marker(baseline)

    assert "role=comparison" in model_text
    assert "role=baseline" in baseline_text
    assert "0.973" in model_text
    assert "0.5" in baseline_text


def test_empty_optional_semantics_do_not_emit_empty_metadata():
    marker = MarkerStub(role="", direction="", experiment_result_id=0)

    short = PaperSynthesisStage._format_result_marker(marker)
    long = PaperSynthesisStage._format_result_marker(
        marker,
        include_provenance=True,
    )

    assert short == "[RESULT-1] balanced_accuracy = 0.973"
    assert "role=" not in long
    assert "direction=" not in long
    assert "source=metrics.json" in long
    assert "experiment_result_id=0" in long
