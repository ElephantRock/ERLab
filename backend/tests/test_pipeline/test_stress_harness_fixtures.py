"""Pure-function unit tests for the ground-truth stress harness.

These tests exercise the fixture builders and the invariant checkers with
SYNTHETIC papers — no live API calls, no cost. They verify the harness itself
is correct before any live money is spent.

What this file tests:
  - Fixtures carry the expected fields and the two ground-truth channels agree.
  - The reversed-attribution fixture puts the attack in the PROPOSAL, not the
    ground-truth channels (the corrected design from the decision).
  - Hard invariants pass on a clean synthetic paper.
  - Hard invariants fail on a substituted synthetic paper.
  - Diagnostics surface conflicting-term mentions without affecting pass rate.
  - The ablation fixtures correctly null out one channel each.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Load the harness module from scripts/ (not on the package path).
# Register in sys.modules BEFORE exec so @dataclass's module lookup succeeds.
_HARNESS_PATH = (
    Path(__file__).resolve().parents[3] / "scripts" / "stress_ground_truth.py"
)
_spec = importlib.util.spec_from_file_location("stress_ground_truth", _HARNESS_PATH)
stress = importlib.util.module_from_spec(_spec)
sys.modules["stress_ground_truth"] = stress
_spec.loader.exec_module(stress)


# ─── Fixture-shape tests ─────────────────────────────────────────────


class TestFixtureShape:
    def test_all_fixtures_have_required_fields(self):
        for builder in stress.ALL_FIXTURES:
            f = builder()
            for field in ("dimension", "level", "proposal_text", "expected"):
                assert field in f, f"{builder.__name__}: missing {field}"
            assert "gt_method" in f["expected"]
            assert "gt_dataset" in f["expected"]
            assert "conflicting_terms" in f["expected"]

    def test_ground_truth_channels_agree_when_both_present(self):
        """The corrected design requires experiment_context and result_markers
        carry the SAME attribution. They must not contradict each other."""
        import re as _re
        for builder in stress.ALL_FIXTURES:
            f = builder()
            ctx = f.get("experiment_context")
            markers = f.get("result_markers")
            if ctx and markers:
                # Every marker's numeric value + role must appear in the
                # experiment_context. The short-form marker carries
                # (role=..., direction=...) metadata; the long-form context
                # adds provenance (source=..., experiment_result_id=...).
                # Both must agree on value + role.
                for m in markers:
                    # Extract the numeric value (first number after the first '=')
                    num_match = _re.search(r"=\s*([-+]?\d+(?:\.\d+)?)", m)
                    if num_match:
                        num_str = num_match.group(1)
                        assert num_str in ctx, (
                            f"{builder.__name__}: marker value '{num_str}' "
                            f"not found in experiment_context — channels disagree"
                        )
                    # Extract role if present in the short-form marker
                    role_match = _re.search(r"role=(\w+)", m)
                    if role_match:
                        role_str = role_match.group(1)
                        assert f"role={role_str}" in ctx, (
                            f"{builder.__name__}: marker role '{role_str}' "
                            f"not found in experiment_context — channels disagree"
                        )

    def test_reversed_attribution_attack_is_in_proposal_not_channels(self):
        """Critical corrected-design check: the metric attack lives in the
        proposal narrative, NOT in the ground-truth channels."""
        f = stress.fixture_metric_reversed_attribution()
        # Channels must carry correct attribution (model=0.973, baseline=0.500)
        assert "0.973" in f["experiment_context"]
        assert "0.500" in f["experiment_context"]
        # The proposal must carry the REVERSED claim
        assert "0.973" in f["proposal_text"]
        assert "0.500" in f["proposal_text"]
        # Verify the proposal attributes 0.973 to the baseline (the attack)
        # and 0.500 to logistic regression. The channels do the opposite.
        assert "baseline achieves" in f["proposal_text"].lower()
        assert "0.973" in f["proposal_text"].lower()


# ─── Ablation tests ──────────────────────────────────────────────────


class TestAblation:
    def test_context_only_ablates_markers(self):
        f = stress.fixture_ablation_context_only()
        assert f["result_markers"] is None
        assert f["experiment_context"] is not None

    def test_markers_only_ablates_context(self):
        f = stress.fixture_ablation_markers_only()
        assert f["experiment_context"] is None
        assert f["result_markers"] is not None

    def test_full_ablation_keeps_both(self):
        f = stress.fixture_ablation_full()
        assert f["experiment_context"] is not None
        assert f["result_markers"] is not None


# ─── Hard-invariant checker tests (synthetic papers) ─────────────────


CLEAN_PAPER = """# Logistic Regression on the Iris Dataset

## Abstract
We apply logistic regression to the Iris dataset. The model achieves
balanced_accuracy = 0.973 [RESULT-1] balanced_accuracy = 0.973, the baseline
manages 0.500 [RESULT-2] balanced_accuracy = 0.500.

## Introduction
Iris is a classic dataset for logistic regression.

## Methodology
We use [RESULT-3] ROC-AUC = 0.998 with sklearn LogisticRegression.

## Related Work
Quantum methods have been proposed elsewhere.
"""

SUBSTITUTED_PAPER = """# Variational Quantum Linear Solver

## Abstract
We propose a quantum solver. The model achieves
[RESULT-1] balanced_accuracy = 0.973.

## Introduction
Quantum circuits are interesting.
"""

EMPTY_PAPER = ""


class TestHardInvariants:
    def test_clean_paper_passes(self):
        f = stress.fixture_method_absurd()
        v = stress.check_hard_invariants(CLEAN_PAPER, f)
        assert v["all_hard_pass"] is True, v["checks"]

    def test_substituted_paper_fails_method_identity(self):
        f = stress.fixture_method_absurd()
        v = stress.check_hard_invariants(SUBSTITUTED_PAPER, f)
        # "logistic regression" should NOT be in the substituted paper's identity
        assert v["all_hard_pass"] is False
        assert v["checks"]["gt_method_in_identity"] is False

    def test_empty_paper_fails(self):
        f = stress.fixture_method_absurd()
        v = stress.check_hard_invariants(EMPTY_PAPER, f)
        assert v["all_hard_pass"] is False

    def test_missing_marker_fails(self):
        f = stress.fixture_method_absurd()
        paper_missing_marker = CLEAN_PAPER.replace("[RESULT-2]", "[RESULT-9]")
        v = stress.check_hard_invariants(paper_missing_marker, f)
        assert v["checks"]["all_markers_present"] is False

    def test_identity_region_excludes_related_work(self):
        """The Related Work section is NOT part of the identity region.
        A conflicting term in Related Work must not fail the hard
        gt_method_in_identity check."""
        region = stress._title_abstract_methodology(CLEAN_PAPER)
        assert "logistic regression" in region
        # "quantum" only appears in Related Work, which is excluded
        assert "quantum" not in region


# ─── Diagnostic tests ────────────────────────────────────────────────


class TestDiagnostics:
    def test_conflicting_term_in_related_work_produces_alert_not_failure(self):
        """The core corrected-design property: a conflicting-term mention
        is a DIAGNOSTIC, not a hard failure."""
        f = stress.fixture_method_absurd()
        v = stress.check_hard_invariants(CLEAN_PAPER, f)
        d = stress.check_diagnostics(CLEAN_PAPER, f)
        # "quantum" is in the paper (Related Work) — should alert
        alert_terms = [a.get("term") for a in d["alerts"]
                       if a.get("type") == "conflicting_term_mentioned"]
        assert "quantum" in alert_terms
        # But the hard verdict should still PASS (identity region is clean)
        assert v["all_hard_pass"] is True

    def test_no_alerts_when_no_conflicting_terms(self):
        f = stress.fixture_metric_correct()  # conflicting_terms is empty
        d = stress.check_diagnostics(CLEAN_PAPER, f)
        term_alerts = [a for a in d["alerts"]
                       if a.get("type") == "conflicting_term_mentioned"]
        assert len(term_alerts) == 0

    def test_marker_attribution_context_recorded(self):
        f = stress.fixture_metric_correct()
        d = stress.check_diagnostics(CLEAN_PAPER, f)
        attr_alerts = [a for a in d["alerts"]
                       if a.get("type") == "marker_attribution_context"]
        # Should have at least one alert per marker found in the paper
        assert len(attr_alerts) >= 1
        # Each should carry the sentence and role words for adjudication
        for a in attr_alerts:
            assert "sentence" in a
            assert "role_words_nearby" in a


# ─── Spend account tests ─────────────────────────────────────────────


class TestSpendAccount:
    def test_can_spend_under_ceiling(self):
        acct = stress.SpendAccount(ceiling_usd=1.0)
        assert acct.can_spend(0.5) is True

    def test_cannot_spend_over_ceiling(self):
        acct = stress.SpendAccount(ceiling_usd=1.0)
        acct.spent_usd = 0.8
        assert acct.can_spend(0.3) is False

    def test_record_accumulates(self):
        acct = stress.SpendAccount(ceiling_usd=10.0)
        # 1M output tokens = $0.60
        acct.record(input_tokens=0, output_tokens=1_000_000)
        assert abs(acct.spent_usd - 0.60) < 1e-9
        assert acct.calls == 1
        acct.record(input_tokens=1_000_000, output_tokens=0)
        # $0.60 + $0.15
        assert abs(acct.spent_usd - 0.75) < 1e-9
        assert acct.calls == 2
