"""Phase 14 — Random Forest analysis on Wine Quality.

Frozen checked-in analysis for spec phase14-rf-wine.

Comparison model: random forest (n_estimators=100, max_depth=10, min_samples_leaf=2, class_weight=balanced)
Baseline: majority-class predictor

Primary metric: balanced_accuracy (higher_better)
Secondary: accuracy, ROC-AUC
Additional artifact: feature_importance.csv

Preprocessing (declared before observing results):
    - No feature scaling (tree-based model)
    - No missing values
    - No categorical features
    - Split: stratified 80/20, seed=42, sklearn train_test_split

Outputs:
    metrics.json — declared metrics + metadata
    predictions.csv — test-set predictions
    results_table.csv — baseline vs comparison summary
    split_indices.csv — row indices for exact split reproduction
    feature_importance.csv — feature name, importance value (sorted descending)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split


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
    return X, y, feature_cols


def main():
    parser = argparse.ArgumentParser(description="Random Forest Wine Quality classification analysis")
    parser.add_argument("--input", required=True, help="Path to the processed Wine Quality CSV")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    X, y, feature_cols = load_wine(args.input)
    n_rows = len(y)

    # Stratified 80/20 split, seed=42
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y,
    )

    # Record split indices
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

    train_good = int(y_train.sum())
    train_bad = int(len(y_train) - train_good)

    # ── Baseline: majority-class predictor ──────────────────────────
    majority_class = 1 if train_good >= train_bad else 0
    baseline_preds = np.full(len(y_test), majority_class)
    baseline_accuracy_val = float(accuracy_score(y_test, baseline_preds))
    baseline_balanced_val = float(balanced_accuracy_score(y_test, baseline_preds))
    baseline_roc_auc_val = 0.5

    # ── Comparison: random forest ───────────────────────────────────
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)
    model_preds = model.predict(X_test)
    model_proba = model.predict_proba(X_test)[:, 1]

    model_accuracy_val = float(accuracy_score(y_test, model_preds))
    model_balanced_val = float(balanced_accuracy_score(y_test, model_preds))
    model_roc_auc_val = float(roc_auc_score(y_test, model_proba))

    # Feature importance
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    top_feature = feature_cols[sorted_idx[0]]
    top_importance = float(importances[sorted_idx[0]])

    # Write feature_importance.csv
    with open(output_dir / "feature_importance.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["feature", "importance"])
        for idx in sorted_idx:
            writer.writerow([feature_cols[idx], f"{importances[idx]:.6f}"])

    # ── Write metrics.json ──────────────────────────────────────────
    metrics = {
        "schema_version": "1",
        "experiment_spec_id": "phase14-rf-wine",
        "seed": 42,
        "sample_counts": {
            "train": int(len(y_train)),
            "test": int(len(y_test)),
        },
        "class_counts": {
            "train": {"good": train_good, "bad": train_bad},
        },
        "majority_class": "good" if majority_class == 1 else "bad",
        "model_family": "random_forest",
        "hyperparameters": {
            "n_estimators": 100,
            "max_depth": 10,
            "min_samples_leaf": 2,
            "class_weight": "balanced",
        },
        "top_feature": top_feature,
        "metrics": {
            "baseline_balanced_accuracy": baseline_balanced_val,
            "baseline_accuracy": baseline_accuracy_val,
            "model_balanced_accuracy": model_balanced_val,
            "model_accuracy": model_accuracy_val,
            "model_roc_auc": model_roc_auc_val,
            "top_feature_importance": top_importance,
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
        writer.writerow(["Random forest", f"{model_balanced_val:.6f}", f"{model_accuracy_val:.6f}", f"{model_roc_auc_val:.6f}"])

    print(f"Analysis complete.")
    print(f"  baseline balanced_accuracy={baseline_balanced_val:.6f}")
    print(f"  model balanced_accuracy={model_balanced_val:.6f}")
    print(f"  model accuracy={model_accuracy_val:.6f}")
    print(f"  model roc_auc={model_roc_auc_val:.6f}")
    print(f"  top feature: {top_feature} (importance={top_importance:.6f})")
    print(f"Artifacts written to {output_dir}/")


if __name__ == "__main__":
    main()
