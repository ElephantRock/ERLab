# P1E.0 — Benchmark Discrimination Audit (Diagnosis)

```text
P1E.0 diagnosis   OUTCOME M (mixed / inconclusive)
P1E.1             BLOCKED pending audit acceptance
P1                 OPEN
P2                 BLOCKED
```

> Generated exclusively from the three sealed Commit-2 artifacts. Every
> figure below traces to `data/evaluation/p1e_*.json`. The narrative does
> not introduce any number not present in those artifacts.

- manifest_sha256: `230fcfa75e80a879119fa0d33365a5760c0b6755c40f508d6882f4d2f5229253`
- protocol_sha256: `a1825d7add7ecdc9bf41ea5ce3c203181b76334345fbce6ffbf9228befd3aabf`
- diagnosis_rule_version: `p1e_diagnosis_v1`
- primary_statistical_seed: `20260721`
- benchmark_fingerprint: `0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4`
- audited cases: 44 cal+dev | excluded held-out: 22

## P1B parity guardrail

```text
tolerance        1e-12
pass             True
```

The five-run audit re-runs the P1B snapshot through the **original** evaluator and reproduces `gate2_metrics_package.json` within 1e-12 (lexical nDCG@5 = 0.9495, semantic = 0.9321, hybrid = 0.9561). This is the in-audit guardrail that the audit uses the frozen evaluator, not a reimplementation.

## Held-out isolation (all zero)

```text
held_out_case_objects_materialized               0
held_out_query_vectors_decoded                   0
held_out_only_candidate_vectors_decoded          0
held_out_ids_passed_to_evaluator                 0
held_out_records_emitted                         0
```

P1B filtered load: decoded 44 queries + 180 candidates; 112 held-out items skipped (never decoded). snapshot_fingerprint `2d8b26f709c03b6b…` matches frozen P1B.

TEI filtered load: decoded 44 queries + 180 candidates; 0 held-out decoded.

## §1 — Judgment and candidate-set structure

```text
total candidates in eval set          180
  grade 0 (nonrelevant)               13
  grade 1 (weakly relevant)           25
  grade >=2 (strongly relevant)       142
    of which grade 3                  90
cases with multiple grade-3           30/44
cases where every candidate relevant  31/44
cases with <2 nonrelevant             44/44
cases unique-best (max grade)         14/44
cases ambiguous-top (tie at max)      30/44
cases all-zero                        0/44
```

**Saturation signal.** Only 13 grade-0 candidates exist in the entire 44-case eval set; 31/44 cases have zero nonrelevant candidates; 44/44 have fewer than 2 genuine negatives; 30/44 have multiple equally-best grade-3 candidates. A benchmark cannot strongly measure top-result quality when nearly every candidate is relevant and the top is frequently tied.

## §2 — Metric ceiling, headroom, resolution

```text
observed headroom == 0                29/44
observed headroom <= 0.01             29/44
observed headroom <= 0.02             30/44
observed headroom > 0.05              8/44
```

**Saturation signal.** 29/44 cases have zero observed headroom — the best of the five runs already achieves the oracle. Only 8/44 cases have headroom above 0.05.

Empirical metric resolution (min nonzero macro movement from one adjacent differently-graded swap, /44):

```text
  ndcg_at_5        0.00012003
  ndcg_at_10       0.00012003
  mrr_at_10        None
  precision_at_5   None
  recall_at_20     None
  top1_optimal     0.02272727  (= 1/44; 14 eligible position-0 swaps across 14 uniquely-best cases)
  top1_optimal effective denominator   44 (all-zero excluded: 0)
```

## §3 — Policy separability (five-run matrix)

```text
run                  nDCG@5   MRR@10      P@5     R@20
lexical              0.9495   1.0000   0.7591   1.0000
p1b_semantic         0.9321   0.9886   0.7591   1.0000
tei_semantic         0.9480   1.0000   0.7591   1.0000
p1b_hybrid_rrf       0.9561   1.0000   0.7591   1.0000
tei_hybrid_rrf       0.9517   1.0000   0.7591   1.0000
```

All five runs cluster between 0.93 and 0.96 nDCG@5; MRR@10 is 1.0 for every run except p1b_semantic (0.9886); Recall@20 is 1.0 everywhere. The policies are barely separated at the macro level.

### Required pairwise comparisons

```text
comparison                      meanΔnDCG5  nontied  Kendall                 95% CI   perm p      MDE label
lexical_vs_p1b_semantic           -0.01741       20   0.5879 [-0.0410,+0.0048]   0.1474   0.0327 underpowered
lexical_vs_tei_semantic           -0.00153       21   0.5424 [-0.0225,+0.0195]   0.8924   0.0309 underpowered
p1b_semantic_vs_tei_semantic      +0.01588       19   0.5909 [-0.0013,+0.0346]   0.0891   0.0256 no_detected_difference
p1b_hybrid_rrf_vs_tei_hybrid_rrf    -0.00438       14   0.8015 [-0.0146,+0.0045]   0.4003   0.0138 no_detected_difference
```

**Power signal.** No pairwise comparison detects a statistically significant difference (every 95% CI includes 0; every permutation p >= 0.05). The two lexical-vs-semantic comparisons are `underpowered` (MDE ~0.031–0.033 exceeds a plausible effect of interest), and the two semantic-vs-semantic / hybrid-vs-hybrid comparisons are `no_detected_difference`. Kendall τ across comparisons is 0.54–0.80 — rankings differ substantially case-by-case, but the differences do not move the metric past the noise floor.

## §4 — Hard-negative coverage (PRIMARY grade-0)

```text
total primary grade-0 hard negatives   5
cases with >=1 near-miss negative      5/44
```

**Saturation signal.** Only 5 primary grade-0 hard negatives exist across all 44 cases, concentrated in 5 cases. The benchmark has almost no genuine negatives to confuse a ranker (consistent with §1: only 13 grade-0 candidates total). Hard-negative coverage is far too thin to exercise a reranking architecture.

## §5 — Error recurrence (observable evidence patterns)

```text
class                                posture         count distinct_cases
lexical_aliasing                     classified          4 4
generic_research_language_overlap    hypothesis         10 n/a
entity_mismatch                      not_inferable    None n/a
method_vs_domain_confusion           classified          0 n/a
task_vs_evidence_mismatch            not_inferable    None n/a
long_document_dilution               hypothesis          0 n/a
near_duplicate_candidates            classified          4 4
missing_query_context                not_inferable    None n/a
```

**Architecture signal (qualified).** Two *classified* recurring error patterns are directly schema-supported: `lexical_aliasing` (4 distinct cases — a grade-0 candidate with lexical overlap ≥ a grade-3 candidate's, ranked above it by lexical) and `near_duplicate_candidates` (4 distinct cases via the `near_duplicate_of` schema field). Two *hypothesis* patterns are suggested but not causally established: `generic_research_language_overlap` (10 cases) and `long_document_dilution` (0 cases). Three classes are `not_inferable` from observable scores. This is genuine but thin architectural evidence: the patterns recur, but the benchmark lacks the negatives and power to turn them into a measurable ranking signal.

## §7 — S/A/M diagnosis

Every criterion's boolean result and measured value:

```text
S_R1_headroom_le_0.01                      pass=True
S_R2_top1_optimal_all_runs                 pass=True
S_R3_few_hard_negatives                    pass=True
S_R4_no_detected_difference_all_pairwise   pass=False
S_R5_largest_delta_power                   pass=True
A1_headroom_gt_0.05                        pass=False
A2_many_hard_negatives                     pass=False
A3_recurring_error_classes                 pass=True
A4_detected_effect                         pass=False
```

```text
S_complete                              False
A_complete                              False
no_architecture_criterion_materially_met False
precedence                              S-complete&A-incomplete->S; A-complete&S-incomplete->A; both->M; neither->M

OUTCOME                                 M
```

### Why M (mixed / inconclusive)

**Saturation evidence present (S partially supported):**

- R1 passes: 66% of cases have observed headroom ≤ 0.01 (29/44 are exactly 0).

- R2 passes: top1_optimal = 1.0 under every one of the five runs on ≥60% of non-all-zero cases.

- R3 passes: 100% of cases have <2 primary grade-0 hard negatives.

- R5 passes: the largest-delta comparison is power-limited.

- **But R4 fails:** the lexical-vs-semantic pairwise comparisons are `underpowered`, not `no_detected_difference` — so saturation is not cleanly established. And `no_architecture_criterion_materially_met` is False because A3 passes.


**Architecture evidence present (A partially supported):**

- A3 passes: 2 recurring *classified* error classes (lexical_aliasing, near_duplicate_candidates), each in ≥2 distinct cal+dev cases.

- **But A1 fails** (only 8/44 = 18% have headroom > 0.05, below 40%), **A2 fails** (only 5 grade-0 hard negatives total), and **A4 fails** (no comparison has both adequate power and a detected effect).


**Resolution.** Neither S nor A is complete under the frozen precedence, so the outcome is **M**. The benchmark is neither purely saturation-dominant (there are recurring architectural error patterns) nor architecture-dominant (there is no detectable ranking signal and almost no headroom or negatives). It is a benchmark with strong ceiling effects AND a few genuine, recurring failure modes that it lacks the power and negative coverage to resolve.

```text
recommended next action (per protocol §10.3 for outcome M):
  authorize a bounded P1E.1 benchmark extension followed by P1E.3
```
