"""Phase 8 G1 — Wine Quality dataset preparation.

Transforms the UCI Wine Quality (red) dataset into a binary classification
target for the frozen G1 experiment specification.

Transformation:
    quality >= 6 → label "good" (positive)
    quality <  6 → label "bad" (negative)

This binary label is a Phase 8 transformation, NOT an original UCI target.

Usage:
    python experiments/phase8_g1_wine/prepare.py \
        --raw data/datasets/wine_quality/winequality-red-raw.csv \
        --output data/datasets/wine_quality/wine_processed.csv

Outputs:
    - The processed CSV with all 11 features + binary label column
    - Prints raw and processed SHA-256 hashes
    - Prints class counts (before and after — they are the same since
      every source row is preserved)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Prepare Wine Quality binary classification dataset")
    parser.add_argument("--raw", required=True, help="Path to the raw UCI Wine Quality red CSV")
    parser.add_argument("--output", required=True, help="Path to write the processed CSV")
    args = parser.parse_args()

    raw_path = Path(args.raw)
    output_path = Path(args.output)

    if not raw_path.exists():
        print(f"ERROR: raw file not found: {raw_path}", file=sys.stderr)
        sys.exit(1)

    # Read the raw semicolon-delimited CSV
    with open(raw_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    if len(rows) != 1599:
        print(f"ERROR: expected 1599 rows, got {len(rows)}", file=sys.stderr)
        sys.exit(1)

    # Count original quality distribution
    quality_counts = {}
    for r in rows:
        q = int(r["quality"])
        quality_counts[q] = quality_counts.get(q, 0) + 1

    # Binarize: quality >= 6 → "good", quality < 6 → "bad"
    good_count = sum(1 for r in rows if int(r["quality"]) >= 6)
    bad_count = sum(1 for r in rows if int(r["quality"]) < 6)

    feature_cols = [
        "fixed acidity", "volatile acidity", "citric acid", "residual sugar",
        "chlorides", "free sulfur dioxide", "total sulfur dioxide", "density",
        "pH", "sulphates", "alcohol",
    ]

    # Write processed CSV: 11 features + label column
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(feature_cols + ["label"])
        for r in rows:
            label = "good" if int(r["quality"]) >= 6 else "bad"
            writer.writerow([r[col] for col in feature_cols] + [label])

    # Compute and print hashes
    raw_hash = compute_sha256(raw_path)
    processed_hash = compute_sha256(output_path)

    print(f"Raw rows: {len(rows)}")
    print(f"Raw SHA-256: {raw_hash}")
    print(f"Processed SHA-256: {processed_hash}")
    print(f"Original quality distribution: {dict(sorted(quality_counts.items()))}")
    print(f"Binary label counts: good={good_count}, bad={bad_count}")
    print(f"Processed file: {output_path}")


if __name__ == "__main__":
    main()
