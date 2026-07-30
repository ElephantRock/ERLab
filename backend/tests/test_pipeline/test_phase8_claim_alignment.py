"""Phase 8 / 8R.6 — claim-level alignment regression tests.

8 fixtures using the reviewed papers and synthetic cases to prove the
claim-level alignment gate catches the defects the independent reviewer found.

Run: pytest backend/tests/test_pipeline/test_phase8_claim_alignment.py -v
"""

from __future__ import annotations

import pytest

from backend.pipeline.evaluation.claim_alignment import evaluate_claim_alignment


# ── Synthetic paper fixtures ─────────────────────────────────────────

IRIS_PAPER = """# Variational Quantum Linear Solver for Hydrodynamic Lubrication

## Abstract

The simulation of hydrodynamic lubrication is fundamental to efficient mechanical
systems. This paper presents a novel application of Variational Quantum Linear
Solvers (VQLS) to the sparse linear systems arising from the discretization of
the Reynolds equation. We demonstrate that hybrid quantum-classical algorithms
can serve as effective solvers for engineering physics problems.

## Proposed Method

We formulate the problem of hydrodynamic lubrication as a linear system and
solve it using a Variational Quantum Linear Solver (VQLS).

## Conclusion

We presented the first known application of a VQLS to hydrodynamic lubrication.
We demonstrate that hybrid quantum-classical algorithms can serve as effective
solvers. [RESULT-2] improvement over the baseline [RESULT-1].
"""

WINE_ALIGNED_PAPER = """# Logistic Regression for Wine Quality Binary Classification

## Abstract

This paper evaluates whether logistic regression with feature scaling outperforms
a majority-class baseline on the Wine Quality dataset for binary classification
(quality >= 6). Using balanced accuracy as the primary metric, we demonstrate
that logistic regression achieves 0.741 vs the baseline's 0.500.

## Proposed Method

We apply logistic regression with StandardScaler preprocessing to the Wine
Quality dataset. The majority-class baseline serves as the comparison.

## Conclusion

Logistic regression outperforms the majority-class baseline on balanced accuracy
for Wine Quality binary classification. [RESULT-5] improvement over [RESULT-2].
"""

WINE_MISALIGNED_PAPER = """# Adaptive Wavelet-Enhanced Graph Neural Network for Material Discovery

## Abstract

The rapid discovery of novel materials relies on spectral data analysis. This
paper proposes an Adaptive Wavelet-Enhanced Graph Neural Network (AWE-GNN) that
integrates a learnable wavelet transform. We demonstrate that our GNN
significantly outperforms conventional pipelines.

## Proposed Method

We formalize the problem as supervised learning on materials. Our AWE-GNN
architecture combines wavelet transforms with graph-based learning. Logistic
regression is used as a baseline comparison on wine quality data.

## Conclusion

We introduced the AWE-GNN architecture for spectral material discovery.
Our GNN significantly outperforms baselines. [RESULT-6] compared to [RESULT-3].
"""

CONCRETE_PINN_BACKGROUND_PAPER = """# Linear Regression for Concrete Compressive Strength Prediction

## Abstract

Predicting concrete compressive strength is important for construction safety.
While physics-informed neural networks (PINNs) have been explored as background
motivation, this paper evaluates ordinary linear regression with feature scaling
against a training-mean baseline on the Concrete Compressive Strength dataset.
We find that linear regression achieves lower RMSE (9.80) than the mean baseline
(16.05), demonstrating effective prediction.

## Proposed Method

We apply linear regression with StandardScaler to the Concrete Compressive
Strength dataset. PINNs are discussed as background motivation only; the
evaluated model is ordinary linear regression.

## Conclusion

Linear regression achieves lower RMSE than the mean baseline for concrete
strength prediction. [RESULT-5] demonstrates the improvement over [RESULT-2].
"""

CONCRETE_PINN_CENTERED_PAPER = """# Hybrid Quantum-Classical Graph Neural Network for Molecular Optimization

## Abstract

Molecular optimization presents challenges due to chemical space complexity.
This paper introduces a Hybrid Quantum-Classical Graph Neural Network (HQC-GNN)
that leverages Variational Quantum Circuits to model electron interactions.
We demonstrate that our quantum approach outperforms classical methods.

## Proposed Method

We combine classical GNNs with Variational Quantum Circuits. Linear regression
is used as a baseline comparison on concrete strength data.

## Conclusion

We presented the HQC-GNN for molecular optimization. Our quantum approach
outperforms classical methods. [RESULT-5] improvement over [RESULT-2].
"""


# ── Regression tests ────────────────────────────────────────────────


class TestClaimAlignment:
    """8 regression fixtures for the claim-level alignment gate."""

    def test_01_iris_quantum_paper_blocked(self):
        """1. The Iris quantum-solver paper must be blocked."""
        result = evaluate_claim_alignment(
            IRIS_PAPER,
            spec_method="multinomial logistic regression vs majority-class baseline",
            spec_dataset="iris",
            spec_baseline="majority-class baseline",
        )
        assert not result.passed
        assert result.finding == "blocker"
        assert "quantum" in result.unexecuted_method_in_abstract

    def test_02_wine_misaligned_abstract_material(self):
        """2. The Wine multimodal-data abstract must produce at least material."""
        result = evaluate_claim_alignment(
            WINE_MISALIGNED_PAPER,
            spec_method="logistic regression (StandardScaler + L2) vs majority-class baseline",
            spec_dataset="wine_quality",
            spec_baseline="majority-class predictor",
            spec_comparison="logistic regression with StandardScaler",
        )
        assert not result.passed
        assert result.finding in ("blocker", "material_concern")

    def test_03_concrete_pinn_centered_material(self):
        """3. The Concrete PINN abstract must produce at least material."""
        result = evaluate_claim_alignment(
            CONCRETE_PINN_CENTERED_PAPER,
            spec_method="linear regression (StandardScaler + OLS) vs training-set mean baseline",
            spec_dataset="concrete_strength",
            spec_baseline="training-set mean predictor",
            spec_comparison="linear regression with StandardScaler",
        )
        assert not result.passed
        assert result.finding in ("blocker", "material_concern")

    def test_04_term_presence_insufficient(self):
        """4. Mentioning correct dataset and method somewhere is not enough."""
        # Wine paper mentions "logistic regression" and "wine quality" in the
        # method section but the abstract centers an unexecuted GNN method
        result = evaluate_claim_alignment(
            WINE_MISALIGNED_PAPER,
            spec_method="logistic regression (StandardScaler + L2) vs majority-class baseline",
            spec_dataset="wine_quality",
            spec_baseline="majority-class predictor",
            spec_comparison="logistic regression with StandardScaler",
        )
        # The method section mentions the correct terms, but the gate must still block
        assert not result.passed

    def test_05_pinn_as_background_passes(self):
        """5. An abstract explicitly saying PINNs are background may pass."""
        result = evaluate_claim_alignment(
            CONCRETE_PINN_BACKGROUND_PAPER,
            spec_method="linear regression (StandardScaler + OLS) vs training-set mean baseline",
            spec_dataset="concrete_strength",
            spec_baseline="training-set mean predictor",
            spec_comparison="linear regression with StandardScaler",
        )
        assert result.passed
        assert result.finding == "no_concern"

    def test_06_result_markers_dont_override_attribution(self):
        """6. Correct RESULT markers must not override incorrect method attribution."""
        # The Concrete PINN paper has correct RESULT markers but wrong attribution
        result = evaluate_claim_alignment(
            CONCRETE_PINN_CENTERED_PAPER,
            spec_method="linear regression (StandardScaler + OLS) vs training-set mean baseline",
            spec_dataset="concrete_strength",
            spec_baseline="training-set mean predictor",
            spec_comparison="linear regression with StandardScaler",
        )
        assert not result.passed  # blocked despite having correct markers

    def test_07_aligned_wine_paper_passes(self):
        """7. A fully aligned Wine paper must pass."""
        result = evaluate_claim_alignment(
            WINE_ALIGNED_PAPER,
            spec_method="logistic regression (StandardScaler + L2) vs majority-class baseline",
            spec_dataset="wine_quality",
            spec_baseline="majority-class predictor",
            spec_comparison="logistic regression with StandardScaler",
        )
        assert result.passed
        assert result.finding == "no_concern"

    def test_08_aligned_concrete_paper_passes(self):
        """8. A fully aligned Concrete paper must pass."""
        result = evaluate_claim_alignment(
            CONCRETE_PINN_BACKGROUND_PAPER,
            spec_method="linear regression (StandardScaler + OLS) vs training-set mean baseline",
            spec_dataset="concrete_strength",
            spec_baseline="training-set mean predictor",
            spec_comparison="linear regression with StandardScaler",
        )
        assert result.passed
        assert result.finding == "no_concern"
