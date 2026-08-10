"""Focused tests for role-aware stress-harness verdicts.

These tests exercise the harness's role-attribution and direction checks
against synthetic correct and incorrect papers. No live LLM calls.
"""

import importlib.util
import sys
from pathlib import Path

# Load the harness from scripts/ — parents[3] from backend/tests/test_pipeline/
HARNESS = Path(__file__).resolve().parents[3] / "scripts" / "stress_ground_truth.py"
spec = importlib.util.spec_from_file_location("stress_ground_truth", HARNESS)
stress = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["stress_ground_truth"] = stress
spec.loader.exec_module(stress)


def test_authoritative_channels_include_role_and_direction():
    context = stress._build_experiment_context()
    markers = stress._build_result_markers()

    assert "role=comparison" in context
    assert "role=baseline" in context
    assert "direction=higher_is_better" in context
    assert any("role=comparison" in m for m in markers)
    assert any("role=baseline" in m for m in markers)
    assert all("direction=higher_is_better" in m for m in markers)


def test_reversed_role_attribution_is_hard_failure():
    fixture = stress.fixture_metric_reversed_attribution()
    paper = """
# Logistic Regression on Iris

## Abstract
The majority-class baseline achieved balanced accuracy of 0.973 [RESULT-1],
while logistic regression achieved 0.500 [RESULT-2].
The baseline also achieved ROC-AUC of 0.998 [RESULT-3].

## Methodology
We evaluate logistic regression on the Iris dataset.
"""
    verdict = stress.check_hard_invariants(paper, fixture)

    assert verdict["checks"]["result_roles_preserved"] is False
    assert verdict["all_hard_pass"] is False


def test_correct_role_attribution_passes_role_check():
    fixture = stress.fixture_metric_reversed_attribution()
    paper = """
# Logistic Regression on Iris

## Abstract
Logistic regression achieved balanced accuracy of 0.973 [RESULT-1],
while the majority-class baseline achieved 0.500 [RESULT-2].
The logistic regression model achieved ROC-AUC of 0.998 [RESULT-3].

## Methodology
We evaluate logistic regression on the Iris dataset.
"""
    role_pass, failures = stress._check_result_role_attribution(paper, fixture)

    assert role_pass is True
    assert failures == []


def test_explicit_direction_reversal_is_hard_failure():
    fixture = stress.fixture_metric_reversed_attribution()
    paper = """
# Logistic Regression on Iris

## Abstract
Logistic regression achieved balanced accuracy of 0.973 [RESULT-1].
The majority-class baseline achieved 0.500 [RESULT-2].
Despite the lower score, the baseline at 0.500 outperforms the logistic
regression model at 0.973.
The logistic regression model achieved ROC-AUC of 0.998 [RESULT-3].

## Methodology
We evaluate logistic regression on the Iris dataset.
"""
    verdict = stress.check_hard_invariants(paper, fixture)

    assert verdict["checks"]["metric_direction_preserved"] is False
    assert verdict["all_hard_pass"] is False
