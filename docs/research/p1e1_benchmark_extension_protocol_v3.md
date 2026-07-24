# P1E.1 — Benchmark Extension Protocol, Revision 3 (custody-breach disclosure)

```text
status                          PROTOCOL REVISION (disclosure + identity canonicalization)
supersedes                      docs/research/p1e1_benchmark_extension_protocol_v2.md (42ff0e6)
preserved in history            d2e16ae (v1), 42ff0e6 (v2)
revision reason                 calibration custody-breach disclosure + canonical full-hash identity
candidate corpus                UNCHANGED (no candidate/query/order/grade/judgment changes)
```

> This revision discloses a historical custody breach in the near-duplicate
> threshold calibration and canonicalizes artifact protocol identity to full
> 40-character commit hashes. The candidate corpus is unchanged. The threshold
> (0.861630662) is unchanged because the minimum came from a calibration-split
> case, not a held-out case.

## Custody breach (P1E.1.2e)

The original near-duplicate calibration (performed during Commit-2 construction)
iterated `frozen_v2_cases()` to find declared near-duplicate pairs and computed
their candidate-candidate cosines. This materialized all 66 v2 case objects,
including the 22 held-out cases, and read held-out candidate *text* for 2 of
the 6 reference pairs. This breached the frozen P1E.1 custody rule requiring
zero held-out content inspection.

```text
historical invalid calibration (performed before this disclosure)
  held-out cases accessed               2   (ml_disc_nd_001, nlp_ret_nd_001)
  held-out reference pairs accessed     2
  held-out candidate texts accessed     4   (2 pairs × 2 candidates each)
  held-out judgments accessed           0   (judgments were never read)

final admissible calibration (cal/dev-only, recorded in construction provenance)
  cal/dev reference pairs               4
  held-out cases accessed               0
  held-out candidate texts accessed     0
  held-out judgments accessed           0
```

### Excluded held-out pairs

```text
ml_disc_nd_001   held_out   ml_nd_001_b  -> ml_nd_001_b2   cosine 0.8787074830960531
nlp_ret_nd_001   held_out   nlpr_nd_001_b -> nlpr_nd_001_b2 cosine 0.9411511056599775
```

Neither was the minimum. The minimum (0.861630662) came from `bio_ret_nd_001`
(calibration split). Excluding the held-out pairs does not change the threshold.

### Threshold validity (accepted)

The threshold 0.861630662 is accepted because it is derived exclusively from
the 4 cal/dev reference pairs and is identical to the threshold the breached
calibration produced. The breach is a custody violation, not a threshold error.
The bounded validity risk (the held-out pairs, had they been the minimum, would
have been inadmissible) is **accepted**: they were not the minimum, so the
threshold is unaffected.

## Canonical identity (P1E.1.2f-g)

All five candidate-layer artifacts must store the **full 40-character** protocol
commit hash and exact SHA-256 — no prefix matching. The effective protocol is
this v3 revision.

```text
v1 (preserved)   d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a
v2 (preserved)   42ff0e661f2acfa15ccefbd94f2770dcaa3f353d
v3 (effective)   <full hash sealed in this commit>
```

Every artifact's `protocol_commit` field must equal the v3 full hash exactly;
tests enforce `len(set) == 1` and exact equality, not prefix matching.

## What changes vs v2

- Custody-breach disclosure added (historical held-out access honestly recorded).
- Artifact identity canonicalized to full commit hashes with exact-equality tests.
- Threshold 0.861630662 unchanged; allocation 93aa5e62 unchanged; candidate
  corpus unchanged.

## v3 held-out isolation in the constructed corpus

The v3 corpus contains no v2 held-out lineage:

```text
v2 held-out parent references              0
v2 held-out preserved candidates          0
v2 held-out copied content hashes         0
v3 held-out judgments inspected           0
```

(The 44 v2-lineage cases are the 44 v2 cal+dev cases only; the 44 fully-new
cases are independent. No v2 held-out case_id or candidate appears in v3.)
