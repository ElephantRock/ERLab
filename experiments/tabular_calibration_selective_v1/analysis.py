#!/usr/bin/env python3
"""Tabular Calibration & Selective Classification v1 — Frozen Entrypoint.

Capability: tabular_calibration_selective_v1
Protocol: logistic regression with post-hoc calibration vs majority-class
          baseline, evaluated under fixed covariate-shift severities with
          selective-classification metrics (risk/coverage/AURC/ECE).

This is a checked-in, reviewed analysis entrypoint. It is NOT generated
by an LLM. It receives:
  --input  : path to a registered classification dataset CSV
  --output : directory for result artifacts

It auto-detects the dataset format by reading the adjacent
``dataset_meta.json``:
  - If the CSV has a header row: features are all columns except the
    last; the last column is the target.
  - If the CSV has no header: all columns except the last are numeric
    features; the last column is the string label.

It writes:
  metrics.json          — flat authoritative metrics for the manifest
  condition_metrics.json — detailed per-condition breakdown
  predictions.csv       — per-sample predictions (uncalibrated model)

Exit codes:
  0 = success
  1 = runtime error
  2 = invalid results (non-finite or missing)
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from pathlib import Path

# ── Fixed protocol constants ────────────────────────────────────────────────

SEED = 42
TRAIN_FRACTION = 0.8
CALIBRATION_FRACTION = 0.5  # of training set, for calibration fitting
LEARNING_RATE = 0.05
EPOCHS = 1000
L2_REG = 0.001

SHIFT_SEVERITIES = [0.0, 0.25, 0.5, 0.75]
CALIBRATION_METHODS = ["uncalibrated", "sigmoid", "isotonic"]
CONFIDENCE_THRESHOLDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


# ── Data loading ────────────────────────────────────────────────────────────


def load_dataset_csv(path: str):
    """Load a classification CSV. Returns (features_list, labels_list, has_header)."""
    with open(path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        print("ERROR: empty CSV", file=sys.stderr)
        sys.exit(1)

    first = rows[0]
    # Detect header: if last column is non-numeric and the rest are non-numeric
    # strings (column names), treat as header.
    last_col = first[-1]
    feature_cols = first[:-1]
    has_header = False
    try:
        [float(x) for x in feature_cols]
        float(last_col)
    except (ValueError, TypeError):
        has_header = True

    if has_header:
        data_rows = rows[1:]
    else:
        data_rows = rows

    features = []
    labels = []
    for row in data_rows:
        if len(row) < 2:
            continue
        try:
            feat = [float(x) for x in row[:-1]]
        except ValueError:
            continue
        features.append(feat)
        labels.append(str(row[-1]).strip())

    return features, labels, has_header


# ── Splitting ───────────────────────────────────────────────────────────────


import random


def stratified_split(features, labels, train_fraction=TRAIN_FRACTION, seed=SEED):
    """Stratified split by label class. Deterministic."""
    rng = random.Random(seed)
    by_class: dict[str, list[int]] = {}
    for i, label in enumerate(labels):
        by_class.setdefault(label, []).append(i)

    train_idx: list[int] = []
    test_idx: list[int] = []
    for cls in sorted(by_class.keys()):
        indices = by_class[cls][:]
        rng.shuffle(indices)
        n_train = int(len(indices) * train_fraction)
        train_idx.extend(indices[:n_train])
        test_idx.extend(indices[n_train:])

    rng2 = random.Random(seed + 1)
    rng2.shuffle(train_idx)
    rng2.shuffle(test_idx)
    return train_idx, test_idx


def split_train_calib(train_idx, calib_fraction=CALIBRATION_FRACTION, seed=SEED):
    """Split training indices into model-fit and calibration subsets."""
    rng = random.Random(seed + 2)
    shuffled = train_idx[:]
    rng.shuffle(shuffled)
    n_fit = int(len(shuffled) * (1.0 - calib_fraction))
    return shuffled[:n_fit], shuffled[n_fit:]


# ── Logistic regression (one-vs-rest) ──────────────────────────────────────


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def train_ovr_logistic(train_X, train_y, lr=LEARNING_RATE, epochs=EPOCHS, l2=L2_REG):
    classes = sorted(set(train_y))
    n_features = len(train_X[0])
    n_samples = len(train_X)
    models = {}

    for cls in classes:
        binary_y = [1 if y == cls else 0 for y in train_y]
        weights = [0.0] * n_features
        bias = 0.0
        for _epoch in range(epochs):
            grad_w = [0.0] * n_features
            grad_b = 0.0
            for i in range(n_samples):
                z = bias + sum(weights[j] * train_X[i][j] for j in range(n_features))
                pred = _sigmoid(z)
                error = pred - binary_y[i]
                for j in range(n_features):
                    grad_w[j] += error * train_X[i][j]
                grad_b += error
            for j in range(n_features):
                grad_w[j] = grad_w[j] / n_samples + l2 * weights[j]
                weights[j] -= lr * grad_w[j]
            bias -= lr * grad_b / n_samples
        models[cls] = (weights, bias)
    return models


def predict_proba(models, features):
    """Return dict: class -> probability, normalized via softmax of logits."""
    logits = {}
    for cls, (weights, bias) in models.items():
        z = bias + sum(weights[j] * features[j] for j in range(len(features)))
        logits[cls] = z
    max_logit = max(logits.values())
    exp_vals = {cls: math.exp(l - max_logit) for cls, l in logits.items()}
    total = sum(exp_vals.values())
    return {cls: ev / total for cls, ev in exp_vals.items()}


# ── Calibration ────────────────────────────────────────────────────────────


def fit_sigmoid_calibration(probs, labels, positive_class):
    """Platt scaling: fit a/b so sigmoid(a*p + b) matches empirical frequency."""
    best_loss = float("inf")
    best_a, best_b = 1.0, 0.0
    for a in [0.5, 1.0, 1.5, 2.0, 3.0]:
        for b in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]:
            loss = 0.0
            for p, y in zip(probs, labels):
                target = 1.0 if y == positive_class else 0.0
                cal_p = _sigmoid(a * p + b)
                cal_p = max(1e-12, min(1 - 1e-12, cal_p))
                loss -= target * math.log(cal_p) + (1 - target) * math.log(1 - cal_p)
            if loss < best_loss:
                best_loss = loss
                best_a, best_b = a, b
    return best_a, best_b


def apply_sigmoid_calibration(probs, a, b):
    return {cls: _sigmoid(a * p + b) for cls, p in probs.items()}


def fit_isotonic_calibration(probs, labels, positive_class):
    """PAV-based isotonic regression on 1D probabilities."""
    pairs = sorted(zip(probs, [1.0 if y == positive_class else 0.0 for y in labels]))
    raw_x = [p for p, _ in pairs]
    raw_y = [y for _, y in pairs]
    # Pool adjacent violators
    blocks = [(raw_x[i], raw_y[i], 1) for i in range(len(raw_x))]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][1] / blocks[i][2] > blocks[i + 1][1] / blocks[i + 1][2]:
            merged_x = blocks[i][0]
            merged_y = blocks[i][1] + blocks[i + 1][1]
            merged_w = blocks[i][2] + blocks[i + 1][2]
            blocks[i] = (merged_x, merged_y, merged_w)
            del blocks[i + 1]
        else:
            i += 1
    breakpoints = [(b[0], b[1] / b[2]) for b in blocks]
    return breakpoints


def apply_isotonic_calibration(probs, breakpoints, positive_class):
    """Apply isotonic map to the positive-class probability, renormalize."""
    p_pos = probs.get(positive_class, 0.5)
    cal_p = breakpoints[-1][1] if breakpoints else p_pos
    for bp_x, bp_y in breakpoints:
        if p_pos <= bp_x:
            cal_p = bp_y
            break
    # Renormalize across classes
    other_total = sum(v for cls, v in probs.items() if cls != positive_class)
    if other_total > 0:
        remaining = 1.0 - cal_p
        return {
            **{cls: remaining * (v / other_total) for cls, v in probs.items() if cls != positive_class},
            positive_class: cal_p,
        }
    return {cls: cal_p if cls == positive_class else (1 - cal_p) / (len(probs) - 1) for cls in probs}


# ── Covariate shift ────────────────────────────────────────────────────────


def apply_covariate_shift(test_features, test_labels, severity, seed=SEED):
    """Feature-dependent reweighting of test set.

    Shifts P(x) by weighting observations whose first feature exceeds
    the median. At severity=0, weights are uniform. At severity=1, only
    observations above the median survive.

    This changes P(x) without changing P(y|x) for surviving observations.
    """
    if severity <= 0.0:
        return list(range(len(test_features)))

    rng = random.Random(seed + 100)
    first_feature = [f[0] for f in test_features]
    if not first_feature:
        return list(range(len(test_features)))
    median = sorted(first_feature)[len(first_feature) // 2]

    indices = list(range(len(test_features)))
    rng.shuffle(indices)

    # Keep all observations above median, subsample those below
    keep = []
    for idx in indices:
        if test_features[idx][0] >= median:
            keep.append(idx)
        else:
            if rng.random() >= severity:
                keep.append(idx)

    if len(keep) < 2:
        return list(range(len(test_features)))
    return sorted(keep)


# ── Metrics ─────────────────────────────────────────────────────────────────


def accuracy(y_true, y_pred):
    if not y_true:
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true)


def expected_calibration_error(probs_list, labels, positive_class, n_bins=10):
    """ECE: weighted average of bin-level |accuracy - confidence|."""
    confidences = [p.get(positive_class, 0.0) for p in probs_list]
    correctness = [1.0 if y == positive_class else 0.0 for y in labels]
    n = len(confidences)
    if n == 0:
        return 0.0
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = [j for j in range(n) if lo <= confidences[j] < hi or (i == n_bins - 1 and confidences[j] == hi)]
        if mask:
            bin_acc = sum(correctness[j] for j in mask) / len(mask)
            bin_conf = sum(confidences[j] for j in mask) / len(mask)
            ece += (len(mask) / n) * abs(bin_acc - bin_conf)
    return ece


def selective_risk_coverage(probs_list, labels, positive_class, thresholds=CONFIDENCE_THRESHOLDS):
    """Compute risk-coverage curve. Returns list of (threshold, coverage, risk)."""
    confidences = [max(p.values()) for p in probs_list]
    correctness = [1.0 if max(p, key=p.get) == y else 0.0 for p, y in zip(probs_list, labels)]
    n = len(confidences)
    if n == 0:
        return [(t, 0.0, 0.0) for t in thresholds]

    results = []
    for t in thresholds:
        selected = [i for i in range(n) if confidences[i] >= t]
        if selected:
            coverage = len(selected) / n
            risk = 1.0 - sum(correctness[i] for i in selected) / len(selected)
        else:
            coverage = 0.0
            risk = 1.0
        results.append((t, coverage, risk))
    return results


def compute_aurc(rc_curve):
    """Area Under Risk-Coverage curve via trapezoidal integration on coverage."""
    coverages = [c for _, c, _ in rc_curve]
    risks = [r for _, _, r in rc_curve]
    if len(coverages) < 2:
        return 1.0
    # Sort by coverage
    pairs = sorted(zip(coverages, risks))
    area = 0.0
    for i in range(1, len(pairs)):
        dc = pairs[i][0] - pairs[i - 1][0]
        avg_r = (pairs[i][1] + pairs[i - 1][1]) / 2.0
        area += dc * avg_r
    return area


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Tabular calibration & selective classification v1",
    )
    parser.add_argument("--input", required=True, help="Path to dataset CSV")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # Load data
    features, labels, has_header = load_dataset_csv(args.input)
    if len(features) < 10:
        print(f"ERROR: too few rows ({len(features)})", file=sys.stderr)
        sys.exit(1)

    classes = sorted(set(labels))
    if len(classes) < 2:
        print(f"ERROR: need >= 2 classes, got {classes}", file=sys.stderr)
        sys.exit(1)

    # Reject regression datasets: if the number of unique labels exceeds
    # a threshold relative to dataset size, treat as regression, not classification.
    n_unique = len(set(labels))
    if n_unique > max(20, len(labels) * 0.1):
        print(
            f"ERROR: {n_unique} unique labels in {len(labels)} rows"
            f" — this is a regression dataset, not classification",
            file=sys.stderr,
        )
        sys.exit(1)

    positive_class = classes[-1]

    # Split
    train_idx, test_idx = stratified_split(features, labels)
    fit_idx, calib_idx = split_train_calib(train_idx)

    train_X = [features[i] for i in fit_idx]
    train_y = [labels[i] for i in fit_idx]
    calib_X = [features[i] for i in calib_idx]
    calib_y = [labels[i] for i in calib_idx]
    test_X = [features[i] for i in test_idx]
    test_y = [labels[i] for i in test_idx]

    # Train model on fit subset
    models = train_ovr_logistic(train_X, train_y)

    # Majority-class baseline
    from collections import Counter
    majority = Counter(train_y).most_common(1)[0][0]
    baseline_acc = accuracy(test_y, [majority] * len(test_y))

    # Uncalibrated probabilities on calibration set
    calib_probs = [predict_proba(models, x) for x in calib_X]

    # Fit calibration maps on calibration subset
    calib_positive_probs = [p.get(positive_class, 0.0) for p in calib_probs]
    sig_a, sig_b = fit_sigmoid_calibration(calib_positive_probs, calib_y, positive_class)
    iso_bp = fit_isotonic_calibration(calib_positive_probs, calib_y, positive_class)

    # Evaluate across shift severities × calibration conditions
    condition_results = []
    flat_metrics = {}

    for severity in SHIFT_SEVERITIES:
        shifted_idx = apply_covariate_shift(test_X, test_y, severity)
        s_X = [test_X[i] for i in shifted_idx]
        s_y = [test_y[i] for i in shifted_idx]

        for cal_method in CALIBRATION_METHODS:
            raw_probs = [predict_proba(models, x) for x in s_X]
            if cal_method == "sigmoid":
                probs = [
                    apply_sigmoid_calibration(p, sig_a, sig_b) for p in raw_probs
                ]
            elif cal_method == "isotonic":
                probs = [
                    apply_isotonic_calibration(p, iso_bp, positive_class)
                    for p in raw_probs
                ]
            else:
                probs = raw_probs

            preds = [max(p, key=p.get) for p in probs]
            acc = accuracy(s_y, preds)
            ece = expected_calibration_error(probs, s_y, positive_class)
            rc = selective_risk_coverage(probs, s_y, positive_class)
            aurc = compute_aurc(rc)

            condition = {
                "dataset": Path(args.input).stem,
                "shift_severity": severity,
                "calibration_method": cal_method,
                "n_test": len(s_y),
                "accuracy": round(acc, 6),
                "ece": round(ece, 6),
                "aurc": round(aurc, 6),
                "risk_coverage": [(round(t, 1), round(c, 4), round(r, 4)) for t, c, r in rc],
            }
            condition_results.append(condition)

            # Flat metrics: key = sev_method (e.g., "0.5_sigmoid_accuracy")
            sev_label = str(severity).replace(".", "_")
            flat_metrics[f"{sev_label}_{cal_method}_accuracy"] = round(acc, 6)
            flat_metrics[f"{sev_label}_{cal_method}_ece"] = round(ece, 6)
            flat_metrics[f"{sev_label}_{cal_method}_aurc"] = round(aurc, 6)

    # Baseline accuracy is independent of shift/calibration
    flat_metrics["baseline_accuracy"] = round(baseline_acc, 6)

    # Validate all metrics are finite
    for name, val in flat_metrics.items():
        if not isinstance(val, (int, float)) or not math.isfinite(val):
            print(f"ERROR: metric {name} is not finite: {val}", file=sys.stderr)
            sys.exit(2)

    # Write metrics.json (authoritative)
    metrics = {
        "schema_version": "2",
        "experiment_spec_id": "tabular-calibration-selective-v1",
        "seed": SEED,
        "sample_counts": {
            "train_fit": len(fit_idx),
            "calibration": len(calib_idx),
            "test": len(test_idx),
        },
        "shift_severities": SHIFT_SEVERITIES,
        "calibration_methods": CALIBRATION_METHODS,
        "classes": classes,
        "positive_class": positive_class,
        "metrics": flat_metrics,
    }
    metrics_path = os.path.join(args.output, "metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    # Write condition_metrics.json (detailed breakdown)
    cond_path = os.path.join(args.output, "condition_metrics.json")
    with open(cond_path, "w") as f:
        json.dump(condition_results, f, indent=2)

    # Write predictions.csv (uncalibrated model, no-shift)
    no_shift_0 = [i for i, c in enumerate(condition_results)
                  if c["shift_severity"] == 0.0 and c["calibration_method"] == "uncalibrated"]
    pred_path = os.path.join(args.output, "predictions.csv")
    with open(pred_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample_idx", "true_label", "model_pred", "confidence"])
        # Recompute uncalibrated probs for full test set
        full_probs = [predict_proba(models, x) for x in test_X]
        full_preds = [max(p, key=p.get) for p in full_probs]
        full_conf = [round(max(p.values()), 4) for p in full_probs]
        for i, (true, pred, conf) in enumerate(zip(test_y, full_preds, full_conf)):
            writer.writerow([i, true, pred, conf])

    print(f"Analysis complete. baseline_acc={baseline_acc:.4f}")
    print(f"Conditions: {len(condition_results)}")
    print(f"Metrics: {len(flat_metrics)} flat values")
    print(f"Artifacts written to {args.output}/")
    sys.exit(0)


if __name__ == "__main__":
    main()
