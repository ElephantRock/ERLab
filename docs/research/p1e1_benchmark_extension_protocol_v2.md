# P1E.1 — Benchmark Extension Protocol, Revision 2 (calibration correction)

```text
status                          PROTOCOL REVISION (supersedes v1 threshold only)
supersedes                      docs/research/p1e1_benchmark_extension_protocol.md (v1, d2e16ae)
original protocol commit        d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a  (PRESERVED, not rewritten)
revision reason                 near-duplicate cosine threshold calibration defect
candidate sealing status        NOT YET SEALED (correction discovered before seal)
```

> This revision is a **calibration correction** to the v1 protocol. The v1
> protocol commit `d2e16ae` is preserved unchanged in history. Only the
> near-duplicate qualification threshold changes; all other frozen values
> (composition, allocation, targets, mining scorer identity, custody,
> canonicalization) remain as in v1. Downstream candidate artifacts generated
> against the v1 threshold are invalidated and must be regenerated.

## Calibration defect

The v1 protocol froze the validated-near-duplicate cosine threshold at `0.92`.
This value was an uncalibrated guess. Computing the exact cosines of the six
frozen v2 reference near-duplicate pairs under the **same frozen TEI mining
scorer** (gte-large-en-v1.5) shows 0.92 would reject 3 of the 6 reference
pairs the benchmark authors considered true near-duplicates.

## Exact v2 reference calibration (full precision, TEI gte-large)

```text
source corpus                  frozen P1B v2 (fingerprint 0ffbfdb1…)
scorer                         TEI gte-large-en-v1.5, rev 104333d6…, single-input, L2
pair transformation            candidate-candidate cosine over "{title}\n\n{abstract}"
```

| pair | cosine (full precision) |
|---|---|
| ml_disc_nd_001: ml_nd_001_b2 vs ml_nd_001_b | 0.8787074830960531 |
| bio_disc_nd_001: bio_nd_001_b2 vs bio_nd_001_b | 0.9390468054624912 |
| nlp_disc_nd_001: nlp_nd_001_b2 vs nlp_nd_001_b | 0.9354046440160263 |
| ml_ret_nd_001: mlr_nd_001_b2 vs mlr_nd_001_b | 0.9005590032978852 |
| bio_ret_nd_001: bior_nd_001_b2 vs bior_nd_001_b | 0.8616306621407969 |
| nlp_ret_nd_001: nlpr_nd_001_b2 vs nlpr_nd_001_b | 0.9411511056599775 |

```text
minimum   0.8616306621407969
median    0.9179818236569557
maximum   0.9411511056599775
```

## Corrected threshold (frozen)

```text
validated_constructed_near_duplicate qualification threshold
  old (v1)    0.92                         (defective — rejects 3/6 v2 references)
  new (v2)    0.861630662                  (exact v2 minimum, canonical 9-decimal ROUND_HALF_EVEN)

high-similarity near duplicate (REPORT-ONLY strict band, non-gating)
  cosine >= 0.92                           (retained as descriptive evidence)
```

The qualification threshold is set to the **exact minimum observed across the
six frozen v2 reference pairs**, recorded at canonical 9-decimal precision per
the protocol's ROUND_HALF_EVEN rule. It is not rounded down or substituted.

## What changes vs v1

- `validated_constructed_near_duplicate` cosine threshold: 0.92 → 0.861630662
- A new report-only classification `high_similarity_near_duplicate` (cosine ≥ 0.92) is added.
- The structural target `validated_constructed_near_duplicate_cases >= 12` is unchanged.
- **Allocation table corrected**: the v1 table (`ffb05ad3…`) was uneven
  (lexical_trap 6, neutral 2 across the 44 fully-new cases), violating the
  global slice-balance tolerance (max−min ≤ 1). The corrected allocation gives
  exactly 4 fully-new cases per slice (1 cal + 1 dev + 2 held per slice,
  domains rotated), achieving slice max−min = 0 and domain max−min = 1. The
  authoritative allocation-table SHA-256 (`93aa5e62…`) is computed from the
  as-built corpus's fully-new case rows (domain-abbreviated IDs), which is the
  single source of truth. Both defects (threshold + allocation) were
  discovered before any candidate sealing.
- All other frozen values (composition, projected-MDE table, mining scorer
  identity, custody contract, canonicalization, all other targets) are
  inherited unchanged from v1 (`d2e16ae`).

## Re-run requirements

```text
recompute protocol SHA-256                       yes (this document is the new protocol)
regenerate candidate package                     yes (if constructed under v1)
regenerate provenance                            yes
regenerate mining scores                         yes (already TEI-correct; re-emit to rebind to new protocol)
regenerate prejudgment diagnostics               yes (re-evaluate >=12 validated-case target)
invalidate v1-threshold downstream artifacts    yes
```

## Lineage

```text
original protocol v1   d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a  (preserved)
protocol v2 (this)     <sealed in this commit>
parent v2 cal+dev allowlist SHA-256   4f6fdfa8bf44ba02f5fe6592ea9c1124fbde594c94e14475ece6ac3550db5e70  (unchanged)
allocation-table SHA-256              93aa5e62cd89f2e704db918078a63dfa2f0930af21f3da3d98b5044fda9e2b87  (as-built corpus; corrected from v1 ffb05ad3…)
```

Every Commit-2 artifact records the protocol-v2 commit + SHA-256 as its
immutable input. Any change to this revision creates a new protocol version.
