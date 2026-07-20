# P1B.1 Gate 1 Closeout — Blind Adjudication Complete

## Status

```
P1B.1      CLOSED  — benchmark expanded, blind-adjudicated, frozen
P1B.2      AUTHORIZED — embedding snapshot generation may begin
P1B.3      AUTHORIZED after snapshot verification
P1B.4+     NOT YET AUTHORIZED
```

## Adjudication package integrity

- **Source**: `docs/p1b_gate1/adjudicated/blind_adjudication_package_adjudicated.json`
- **SHA-256** (computed): `d61641b0f205492603cc1ff9d42038a3c86d73c331e58674f7a5e099a5d8a5e0`
- **SHA-256** (reported by adjudicator): `d61641b0f205492603cc1ff9d42038a3c86d73c331e58674f7a5e099a5d8a5e0`
- **Match**: ✅ verified
- **Size**: 219950 bytes
- **Cases**: 66
- **Judgments**: 270 (matches provisional count exactly)
- **Specialist-review flags**: 0

## Reconciliation summary

Blind second-pass annotations reconciled against provisional (initial author)
judgments. Full report at `docs/p1b_gate1/adjudication/reconciliation_report.json`.

| Agreement class | Count | Rate | Definition |
|---|---:|---:|---|
| exact     | 179 | 0.663 | delta == 0 |
| minor     |  90 | 0.333 | abs(delta) == 1 |
| material  |   1 | 0.004 | abs(delta) >= 2 |
| unable    |   0 | 0.000 | specialist_review_needed |
| **total** | **270** | 1.000 | |

**Delta distribution** (blind − provisional): −2 → 1, −1 → 60, 0 → 179, +1 → 30.

### Agreement by surface
- discovery_ranking: 91 exact / 44 minor / 0 material (exact rate 0.674)
- retrieval_ranking: 88 exact / 46 minor / 1 material (exact rate 0.652)

### Agreement by domain
- machine_learning: 58 exact / 32 minor / 0 material (exact rate 0.644)
- biomedical: 56 exact / 33 minor / 1 material (exact rate 0.622)
- nlp: 65 exact / 25 minor / 0 material (exact rate 0.722)

### Agreement by slice (material rate)
All adversarial slices ≤ 4.2% material rate. The single material disagreement
is in `review_vs_primary`.

```
acronym_vs_expanded:    0/24 material
exact_identifier:       0/24 material
lexical_trap:           0/24 material
method_vs_application:  0/24 material
missing_abstract:       0/24 material
near_duplicate:         0/30 material
negated_findings:       0/24 material
neutral:                0/24 material
review_vs_primary:      1/24 material  ← adjudicated below
semantic_paraphrase:    0/24 material
source_rank_conflict:   0/24 material
```

## Material disagreement adjudication (1 total)

```
case_id      : bio_ret_rv_001
candidate_id : bior_rv_001_c
surface      : retrieval_ranking
domain       : biomedical
slice        : review_vs_primary
query        : "psilocybin depression clinical trial" (intent: evidence_support)
candidate    : "Psilocybin for Cancer-Related Anxiety (J Psychopharmacol)"
               "Double-blind trial reports anxiety reductions."
```

| Pass | Grade | Confidence | Rationale |
|---|:---:|:---:|---|
| provisional (author) | 3 | 0.90 | "primary psilocybin RCT" |
| blind (adjudicator)  | 1 | 0.87 | "Touches the topic but does not directly answer the requested empirical question, so evidence utility is marginal." |
| **adjudicated** | **1** | 0.87 | see below |

### Adjudication reasoning

The query is `"psilocybin depression clinical trial"` with `evidence_support`
intent. The candidate is a **psilocybin randomized trial** (so it is primary
evidence, not a review — consistent with the slice's design). However, the
candidate's **primary endpoint is cancer-related anxiety**, not depression.

The provisional grade of 3 was an error: it anchored on "psilocybin + RCT"
matching the `evidence_support` intent for primary evidence, and failed to
check that the **outcome** (anxiety) diverges from the **query-specified
outcome** (depression). For an evidence-support query, a trial of the right
intervention but a different endpoint is at most marginally useful.

The blind pass correctly downgraded to 1. **Adjudicated to blind grade 1.**
This is exactly the contamination-resistant catch the blind protocol was
designed to produce: my provisional reasoning had a systematic blind spot
(matching the intervention without checking the endpoint), and the
independent pass caught it.

## Frozen benchmark

- **Frozen fingerprint**: `0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4`
- **Provisional fingerprint** (for audit only, NOT for evaluation): `d9581928e2af1ff5aa49d3f84edef4c37ad86ee25ef479a6f1abed26c47cb22d`
- **Cases**: 66 (33 discovery + 33 retrieval) — unchanged from provisional
- **Splits**: frozen at 22 calibration / 22 development / 22 held_out — unchanged
- **Candidate pools**: unchanged (content hashes preserved)
- **Final grade distribution**: 139 grade-3 / 73 grade-2 / 40 grade-1 / 18 grade-0

The frozen view is the authoritative input for P1B.2 and P1B.3. It is produced
by `frozen_v2_cases()` in `backend/ranking/benchmark_v2_registry.py`, overlaid
from the generated `backend/ranking/benchmark_v2_frozen_adjudication.py`.

## Honest disclosures

1. **The benchmark is honestly described as** a *"controlled expert-reviewed
   benchmark, NOT population-level human relevance ground truth"* (per
   Decision 3). Both annotation passes were performed without external domain
   specialists; 0 specialist-review flags were raised, but the absence of flags
   reflects annotator confidence, not validated specialist review.

2. **Minor disagreement rate is 33.3%** (90/270). This is expected for
   grade-boundary cases on a 0–3 scale and does not indicate benchmark
   instability — all minor disagreements were resolved to the blind grade per
   the Decision 3 rule (trust the independent second pass when agreement is
   exact or minor).

3. **The single material disagreement exposed a systematic bias** in my
   provisional reasoning (matching intervention without checking endpoint).
   The blind protocol caught it. There may be analogous biases not caught by
   a single second pass; the closeout records this limitation honestly.

4. **No production policy has been selected.** No embedding snapshot exists
   yet. P1B.2 is now authorized to begin.

## Audit trail

```
backend/ranking/benchmark_v2_frozen_adjudication.py
  generated from the SHA-256-verified adjudication package
docs/p1b_gate1/adjudicated/blind_adjudication_package_adjudicated.json
  the returned, annotated package (SHA-256 d61641b0...)
docs/p1b_gate1/adjudication/reconciliation_report.json
  per-judgment reconciliation records + aggregate stats
docs/p1b_gate1/adjudication/material_disagreements.json
  the single material disagreement, isolated for review
backend/ranking/benchmark_v2_adjudication.py
  reconciliation harness (reproducible)
```
