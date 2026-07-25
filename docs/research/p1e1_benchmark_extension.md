# P1E.1 — Benchmark Extension Diagnosis

```text
effective protocol v4      af2f131f2851ae1064750e54b29278d2ce8d3028
candidate_corpus_fingerprint 4da4e53d1969b4c14fdf86fd…
final_adjudicated_v3_fingerprint  pending_p1e2
```

## Composition

```text
  total_cases                    88
  calibration_cases              33
  development_cases              33
  held_out_cases                 22
  caldev_cases                   66
  v2_lineage_cases               44
  fully_new_cases                44
  candidate_records              576
  caldev_grade_records           444
```

## Adjudication breakdown

```text
  inherited v2 cal/dev records     180  (NOT freshly adjudicated)
  fresh injected records            132
  fresh fully-new records           132
  fresh judgments total             264
  v2 held-out inheritance           0
  grade mismatches vs frozen v2     0
```

> protocol v4 authorizes inheritance only for byte-identical v2 cal/dev records; the 180 inherited records are NOT described as freshly adjudicated

## Grade-dependent targets

```text
  grade distribution               {'0': 147, '1': 67, '2': 118, '3': 112}
  min grade-0 per case             2
  cases with >=2 grade-0           66/66
  cases with >=2 hard negatives    65/66
  unique-best cases                36/66
  misleading near-duplicate cases  36
  lexical-confuser cases           66
  all targets pass                 True
```

### P1E.0 comparison

```text
  raw grade-0 count        13 -> 147  (11.31x)
  per-case grade-0 rate    0.2955 -> 2.2273  (7.54x)
```

## Structural targets

```text
  candidate_count_in_6_to_8                True
  validated_near_duplicate_target_met      True
  lexical_trap_target_met                  True
  domain_balance_within_tolerance          True
  slice_balance_within_tolerance           True
  id_collisions_zero                       True
  preserved_content_unchanged              True
```

## Power projection

```text
  projected_mde (conservative)     0.02938
  design_projection                True
  measured_in_p1e1                 False
  planned_caldev_n                 66
  formula                          projected_mde = 2.801586 * SD / sqrt(n)
```

> This is a projected design value. No retrieval policy was evaluated in P1E.1. Actual paired-policy MDE belongs to P1E.3.

## Protocol history

```text
  v1: d2e16ae6b82a  initial freeze
  v2: 42ff0e661f2a  near-duplicate calibration and allocation correction
  v3: 679bc0052d08  historical held-out calibration-access disclosure
  v4: af2f131f2851  bounded authorization of inherited v2 cal/dev judgments
  historical held-out access: cases=2 texts=4 judgments=0
  admissible calibration: 4 cal/dev pairs, threshold=0.861630662
```

## Custody and blinding

```text
  blind held-out cases             22
  opaque identifiers               True
  reconciliation map committed     False
  construction copy deleted        True
  transfer status                  accepted
  held-out grades inspected        0
  final held-out adjudication      pending
```

> The custodian role resides within this governed environment. Any remaining independent-custody limitation is a P1E.2 prerequisite, not a P1E.1 failure.

## Completion status

```text
  p1e1_status                         closed
  candidate_layer_status              sealed
  caldev_adjudication_status          sealed
  heldout_package_status              prepared
  final_v3_fingerprint_status         pending_p1e2
  policy_evaluation_status            not_started
  production_retrieval_decision       not_made
```

## Conclusion

P1E.1 produced a larger and more discriminative retrieval benchmark. It materially increased negative and hard-negative coverage (grade-0 candidates: 13→147; per-case rate: 0.2955→2.2273). It did **not** compare retrieval policies and did **not** select a production retrieval architecture. P1E.2 is responsible for held-out adjudication. P1E.3 is responsible for the frozen retrieval-policy comparison. The projected MDE (0.02938) is a design value; actual MDE will be measured in P1E.3.

