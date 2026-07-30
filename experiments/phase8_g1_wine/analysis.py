"""Phase 8 G1 — Wine Quality binary classification analysis.

Frozen checked-in analysis for spec phase8-g1-wine.

Comparison model: logistic regression (StandardScaler + LogisticRegression)
Baseline: majority-class predictor

Primary metric: balanced_accuracy (higher_better)
Secondary: accuracy (higher_better), roc_auc (higher_better)

Preprocessing (declared before observing results):
    - StandardScaler fit on training data only
    - No missing values in this dataset
    - No categorical features (all numeric)
    - Intercept: included (fit_intercept=True)
    - Regularization: L2, C=1.0 (sklearn default)
    - Solver: lbfgs, max_iter=1000
    - Split: stratified 80/20, seed=42, sklearn train_test_split

Outputs:
    metrics.json — declared metrics + metadata
    predictions.csv — test-set predictions
    results_table.csv — baseline vs comparison summary
    split_indices.csv — row indices for exact split reproduction
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def load_wine(csv_path: str):
    """Load the processed Wine Quality CSV."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    if len(rows) != 1599:
        print(f"ERROR: expected 1599 rows, got {len(rows)}", file=sys.stderr)
        sys.exit(1)
    feature_cols = [
        "fixed acidity", "volatile acidity", "citric acid", "residual sugar",
        "chlorides", "free sulfur dioxide", "total sulfur dioxide", "density",
        "pH", "sulphates", "alcohol",
    ]
    X = np.array([[float(r[c]) for c in feature_cols] for r in rows])
    y = np.array([1 if r["label"] == "good" else 0 for r in rows])
    return X, y


def main():
    parser = argparse.ArgumentParser(description="Wine Quality binary classification analysis")
    parser.add_argument("--input", required=True, help="Path to the processed Wine Quality CSV")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    X, y = load_wine(args.input)
    n_rows = len(y)

    # Stratified 80/20 split, seed=42
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )

    # Record split indices for exact reproduction
    all_indices = np.arange(n_rows)
    train_idx, test_idx = train_test_split(
        all_indices, test_size=0.2, random_state=42, stratify=y,
    )
    with open(output_dir / "split_indices.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["row_index", "split"])
        for i in train_idx:
            writer.writerow([int(i), "train"])
        for i in test_idx:
            writer.writerow([int(i), "test"])

    # Class counts in train and test
    train_good = int(y_train.sum())
    train_bad = int(len(y_train) - train_good)
    test_good = int(y_test.sum())
    test_bad = int(len(y_test) - test_good)

    # ── Baseline: majority-class predictor ──────────────────────────
    majority_class = 1 if train_good >= train_bad else 0
    baseline_preds = np.full(len(y_test), majority_class)
    baseline_accuracy_val = float(accuracy_score(y_test, baseline_preds))
    baseline_balanced_val = float(balanced_accuracy_score(y_test, baseline_preds))
    # ROC AUC for a constant predictor: 0.5
    baseline_roc_auc_val = 0.5

    # ── Comparison: logistic regression ─────────────────────────────
    # Preprocessing: StandardScaler fit on training data only
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(
        C=1.0, solver="lbfgs", max_iter=1000,
        random_state=42,
    )
    model.fit(X_train_scaled, y_train)
    model_preds = model.predict(X_test_scaled)
    model_proba = model.predict_proba(X_test_scaled)[:, 1]

    model_accuracy_val = float(accuracy_score(y_test, model_preds))
    model_balanced_val = float(balanced_accuracy_score(y_test, model_preds))
    model_roc_auc_val = float(roc_auc_score(y_test, model_proba))

    # ── Write metrics.json ──────────────────────────────────────────
    metrics = {
        "schema_version": "1",
        "experiment_spec_id": "phase8-g1-wine",
        "seed": 42,
        "sample_counts": {
            "train": int(len(y_train)),
            "test": int(len(y_test)),
        },
        "class_counts": {
            "train": {"good": train_good, "bad": train_bad},
            "test": {"good": test_good, "bad": test_bad},
        },
        "majority_class": "good" if majority_class == 1 else "bad",
        "metrics": {
            "baseline_balanced_accuracy": baseline_balanced_val,
            "baseline_accuracy": baseline_accuracy_val,
            "baseline_roc_auc": baseline_roc_auc_val,
            "model_balanced_accuracy": model_balanced_val,
            "model_accuracy": model_accuracy_val,
            "model_roc_auc": model_roc_auc_val,
        },
    }
    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # ── Write predictions.csv ───────────────────────────────────────
    with open(output_dir / "predictions.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["test_index", "true_label", "baseline_pred", "model_pred", "model_prob_good"])
        for i, (yt, bp, mp, pr) in enumerate(zip(y_test, baseline_preds, model_preds, model_proba)):
            writer.writerow([i, "good" if yt == 1 else "bad",
                             "good" if bp == 1 else "bad",
                             "good" if mp == 1 else "bad",
                             f"{pr:.6f}"])

    # ── Write results_table.csv ─────────────────────────────────────
    with open(output_dir / "results_table.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Method", "Balanced Accuracy", "Accuracy", "ROC AUC"])
        writer.writerow(["Majority-class baseline", f"{baseline_balanced_val:.6f}", f"{baseline_accuracy_val:.6f}", f"{baseline_roc_auc_val:.6f}"])
        writer.writerow(["Logistic regression", f"{model_balanced_val:.6f}", f"{model_accuracy_val:.6f}", f"{model_roc_auc_val:.6f}"])

    print(f"Analysis complete.")
    print(f"  baseline balanced_accuracy={baseline_balanced_val:.6f}")
    print(f"  model balanced_accuracy={model_balanced_val:.6f}")
    print(f"  model accuracy={model_accuracy_val:.6f}")
    print(f"  model roc_auc={model_roc_auc_val:.6f}")
    print(f"Artifacts written to {output_dir}/")


if __name__ == "__main__":
    main()
