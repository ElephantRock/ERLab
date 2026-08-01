# Reproducibility

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
