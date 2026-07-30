"""Phase 8 G2 — Concrete Compressive Strength regression analysis.

Frozen checked-in analysis for spec phase8-g2-concrete.

Comparison model: linear regression (StandardScaler + LinearRegression)
Baseline: training-set mean predictor

Primary metric: model_rmse (lower_better)
Secondary: model_mae (lower_better), model_r2 (higher_better)
Baseline metrics: baseline_rmse (lower_better), baseline_mae (lower_better)
Derived: rmse_reduction = baseline_rmse - model_rmse (higher_better)

Preprocessing (declared before observing results):
    - StandardScaler fit on training data only
    - No missing values in this dataset
    - No categorical features (all numeric)
    - Intercept: included (fit_intercept=True)
    - Regularization: none (ordinary least squares)
    - Split: 80/20, seed=42, sklearn train_test_split (no stratification for regression)

Outputs:
    metrics.json — declared metrics + metadata
    predictions.csv — test-set predictions
    results_table.csv — baseline vs comparison summary
    split_indices.csv — row indices for exact split reproduction
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def main():
    parser = argparse.ArgumentParser(description="Concrete Strength regression analysis")
    parser.add_argument("--input", required=True, help="Path to the Concrete Strength CSV")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input)
    if len(df) != 1030:
        print(f"ERROR: expected 1030 rows, got {len(df)}", file=sys.stderr)
        sys.exit(1)

    # Target is the last column
    target_col = df.columns[-1]
    feature_cols = list(df.columns[:-1])
    X = df[feature_cols].values.astype(float)
    y = df[target_col].values.astype(float)

    # 80/20 split, seed=42 (no stratification for regression)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42,
    )

    # Record split indices for exact reproduction
    all_indices = np.arange(len(df))
    train_idx, test_idx = train_test_split(
        all_indices, test_size=0.2, random_state=42,
    )
    with open(output_dir / "split_indices.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["row_index", "split"])
        for i in train_idx:
            writer.writerow([int(i), "train"])
        for i in test_idx:
            writer.writerow([int(i), "test"])

    # ── Baseline: training-set mean predictor ───────────────────────
    train_mean = float(np.mean(y_train))
    baseline_preds = np.full(len(y_test), train_mean)
    baseline_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_preds)))
    baseline_mae = float(mean_absolute_error(y_test, baseline_preds))

    # ── Comparison: linear regression ───────────────────────────────
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LinearRegression(fit_intercept=True)
    model.fit(X_train_scaled, y_train)
    model_preds = model.predict(X_test_scaled)

    model_rmse = float(np.sqrt(mean_squared_error(y_test, model_preds)))
    model_mae = float(mean_absolute_error(y_test, model_preds))
    model_r2 = float(r2_score(y_test, model_preds))

    # Derived: rmse_reduction (lower_better → reduction is positive = good)
    rmse_reduction = baseline_rmse - model_rmse

    # ── Write metrics.json ──────────────────────────────────────────
    metrics = {
        "schema_version": "1",
        "experiment_spec_id": "phase8-g2-concrete",
        "seed": 42,
        "sample_counts": {
            "train": int(len(y_train)),
            "test": int(len(y_test)),
        },
        "target": "Concrete compressive strength (MPa)",
        "metrics": {
            "baseline_rmse": baseline_rmse,
            "baseline_mae": baseline_mae,
            "model_rmse": model_rmse,
            "model_mae": model_mae,
            "model_r2": model_r2,
            "rmse_reduction": rmse_reduction,
        },
    }
    with open(output_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # ── Write predictions.csv ───────────────────────────────────────
    with open(output_dir / "predictions.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["test_index", "true_strength", "baseline_pred", "model_pred"])
        for i, (yt, bp, mp) in enumerate(zip(y_test, baseline_preds, model_preds)):
            writer.writerow([i, f"{yt:.4f}", f"{bp:.4f}", f"{mp:.4f}"])

    # ── Write results_table.csv ─────────────────────────────────────
    with open(output_dir / "results_table.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Method", "RMSE", "MAE", "R²"])
        writer.writerow(["Mean baseline", f"{baseline_rmse:.4f}", f"{baseline_mae:.4f}", "N/A"])
        writer.writerow(["Linear regression", f"{model_rmse:.4f}", f"{model_mae:.4f}", f"{model_r2:.4f}"])

    print(f"Analysis complete.")
    print(f"  baseline rmse={baseline_rmse:.4f}")
    print(f"  model rmse={model_rmse:.4f}")
    print(f"  model mae={model_mae:.4f}")
    print(f"  model r2={model_r2:.6f}")
    print(f"  rmse_reduction={rmse_reduction:.4f}")
    print(f"Artifacts written to {output_dir}/")


if __name__ == "__main__":
    main()
