# Reproducibility

## Obtaining datasets

ERLab uses three public datasets that are **not included** in the repository
(the `data/` directory is gitignored). Download them separately:

```bash
# Iris (public domain)
# The raw CSV is included in scikit-learn or available from:
# https://archive.ics.uci.edu/dataset/53/iris

# Wine Quality (CC BY 4.0)
curl -sL "https://archive.ics.uci.edu/ml/machine-learning-databases/wine-quality/winequality-red.csv" \
  -o data/datasets/wine_quality/winequality-red-raw.csv
# Then run the preparation script:
python experiments/phase8_g1_wine/prepare.py \
  --raw data/datasets/wine_quality/winequality-red-raw.csv \
  --output data/datasets/wine_quality/wine_processed.csv

# Concrete Compressive Strength (CC BY 4.0)
# Download from: https://archive.ics.uci.edu/dataset/165/concrete+compressive+strength
# Convert the XLS to CSV and place at data/datasets/concrete_strength/concrete_raw.csv
```

The `dataset_meta.json` files in each dataset directory declare the expected
SHA-256 hash of the raw data. ERLab verifies these hashes at load time.

## Frozen experiment specifications

All empirical experiments use checked-in specifications that declare:

```
dataset (with SHA-256 hash)
split method and seed
analysis entrypoint (checked-in Python script)
declared metrics and directions
frozen tolerances
output artifacts
```

## Reproducing an experiment

```bash
# Run the Iris logistic regression
python experiments/phase5_pilot_v1/analysis.py \
  --input data/datasets/iris/iris_raw.csv \
  --output /tmp/repro_iris

# Run the Wine Quality random forest
python experiments/phase14_rf_wine/analysis.py \
  --input data/datasets/wine_quality/wine_processed.csv \
  --output /tmp/repro_rf
```

All experiments are deterministic (fixed seed, fixed split). Independent
reproductions produce diff=0.00000000 across all declared metrics.

## Evidence chain

```
experiment specification (frozen JSON)
→ checked-in analysis script (SHA-256 hashed)
→ deterministic execution (seed=42)
→ metrics.json (observed values)
→ artifacts (metrics, predictions, tables, feature_importance)
→ ExperimentManifest (reproducibility metadata)
→ RESULT markers (marker → metric → value → direction → role)
→ PaperRevision records (revision history)
→ Paper (paper_md + paper_meta_json)
```

Every step is persisted and hash-verifiable.

## Restart stability

All evidence survives backend restart:
- Experiment manifests unchanged
- RESULT-map hashes unchanged
- SOURCE-map hashes unchanged
- Paper hashes unchanged
- Revision history with parent linkage preserved

## Independent computational review

Phase 8+ papers were reviewed by GPT-5.3 (independent computational review,
not human peer review) with frozen evidence packages. All accepted papers
received NO CONCERN with no blocker.
