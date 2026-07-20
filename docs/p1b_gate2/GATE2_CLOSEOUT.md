# P1B.3 Gate 2 Closeout — Policy Evaluation Results

## Status

```
P1B.3      COMPLETE — all candidate policies evaluated; NONE pass the frozen gate
GATE 2     PAUSED — design review required before any further action

No production policy activated. Legacy lexical baseline remains in production.
```

## Overall verdict

**NO POLICY PASSES the frozen quality gate.** Per Decision 2C, this fires the
"Hybrid RRF fails" branch:

> Stop after P1B.3 for design review. Do NOT automatically construct a small
> learned MLP… The P1 threshold must not be weakened merely to avoid
> implementing a reranker.

Per the contract stop condition #7 and §11, the legacy policy remains
explicitly active, **P1 stays OPEN, and thresholds are NOT weakened.**

## Frozen evaluation setup

- benchmark fingerprint: `0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4`
- snapshot fingerprint: `2d8b26f709c03b6bbc7d5c4ab7ca65259a87e8f06ef80b3da0e9e50df69b38d2`
- snapshot provider: `text-embedding-qwen3-embedding-0.6b` (1024d)
- selection splits: calibration + development (44 cases)
- held_out (22 cases): reported for legacy baseline ONLY (Decision 3)
- frozen hyperparameters: `rrf_k=60`, `weighted=0.5/0.5`, `final_limit=20`

## Macro metrics (calibration + development, n=44)

| policy | nDCG@5 | nDCG@10 | MRR@10 | P@5 | R@20 | time(s) |
|---|---:|---:|---:|---:|---:|---:|
| legacy_lexical_top20_v1 (baseline) | 0.9495 | 0.9495 | 1.0000 | 0.7591 | 1.0000 | 0.004 |
| semantic_only_v1            | 0.9321 | 0.9321 | 0.9886 | 0.7591 | 1.0000 | 0.025 |
| **hybrid_rrf_v1**           | **0.9561** | **0.9561** | 1.0000 | 0.7591 | 1.0000 | 0.027 |
| hybrid_weighted_v1          | 0.9394 | 0.9394 | 1.0000 | 0.7591 | 1.0000 | 0.026 |

## Paired bootstrap 95% CI vs legacy (nDCG@10, 10000 resamples, seed 20260721)

| policy | mean Δ | lower | upper | p(Δ>0) |
|---|---:|---:|---:|---:|
| semantic_only_v1   | −0.0174 | −0.0410 | +0.0048 | 0.0640 |
| **hybrid_rrf_v1**  | **+0.0065** | **−0.0004** | +0.0155 | **0.9656** |
| hybrid_weighted_v1 | −0.0102 | −0.0297 | +0.0071 | 0.1454 |

## Per-slice nDCG@10

```
slice                     legacy    semantic  hybrid_rrf  weighted
acronym_vs_expanded       0.9645    1.0000    1.0000      0.9645
exact_identifier          0.9415    0.8451    0.9347      0.8392   ← largest declines
lexical_trap              0.9164    0.9164    0.9164      0.9164
method_vs_application     0.9556    0.8966    0.9616      0.9307
missing_abstract          0.9902    0.9824    0.9902      0.9824
near_duplicate            0.9764    0.9726    0.9806      0.9779
negated_findings          0.9599    0.9625    0.9599      0.9625
neutral                   0.9104    0.9373    0.9332      0.9689
review_vs_primary         0.9774    0.9206    0.9739      0.9242
semantic_paraphrase       0.9453    0.9455    0.9515      0.9515
source_rank_conflict      0.9070    0.8740    0.9146      0.9146
```

## Gate verdict per policy

| policy | ΔnDCG@10 ≥0.03 | bootstrap LB >0 | R@20 Δ ≥−0.01 | worst slice Δ ≥−0.05 | replay 100% | **verdict** |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| semantic_only_v1   | ❌ −0.0174 | ❌ −0.0410 | ✅ | ❌ −0.0964 (exact_identifier) | ✅ | **FAIL** |
| hybrid_rrf_v1      | ❌ +0.0065 | ❌ −0.0004 | ✅ | ✅ −0.0068 | ✅ | **FAIL** |
| hybrid_weighted_v1 | ❌ −0.0102 | ❌ −0.0297 | ✅ | ❌ −0.1023 (exact_identifier) | ✅ | **FAIL** |

`hybrid_rrf_v1` is the closest to passing (every check except the +0.03
absolute improvement and the bootstrap LB > 0), but it does not clear either
threshold. Its point estimate is positive (+0.0065) and p(Δ>0)=0.966, but the
effect is too small to meet the frozen gate on this benchmark.

## Deterministic replay proof

All four policies produce bit-identical macro AND per-case metrics across two
independent runs against the same frozen snapshot + benchmark. The
"deterministic replay 100%" invariant is satisfied for every policy. This
confirms the snapshot + frozen-benchmark design makes ranking outputs exactly
reproducible (Decision 1C's frozen definition).

## Held-out posture (per Decision 3)

Held-out (22 cases) is reported **for the legacy baseline only**. Because no
candidate policy passed the gate, no candidate policy is evaluated on
held-out. This preserves the held-out freeze: held-out results are reported
only once, after a policy is selected.

```
held_out legacy_lexical_top20_v1 macro:
  see gate2_metrics_package.json -> held_out_legacy_baseline_only.macro
```

## Honest interpretation

1. **The benchmark is small (44 selection cases).** A +0.03 absolute nDCG@10
   improvement with a bootstrap lower bound strictly above zero is a high bar
   on 44 cases. The best policy (hybrid_rrf_v1) shows a real positive trend
   (p(Δ>0)=0.966) but the effect size is below the threshold and the CI
   includes zero. This is consistent with a genuinely small effect, not a
   measurement failure.

2. **The legacy lexical baseline is unusually strong on this benchmark.**
   Macro nDCG@10 of 0.9495 is high — the benchmark's lexical traps are
   well-handled by the keyword-overlap heuristic because the synthetic cases
   use distinctive keywords. A semantic policy only helps when lexical overlap
   fails to capture relevance, which is rare in this constructed benchmark.

3. **semantic_only and weighted fail the slice gate on `exact_identifier`.**
   Both degrade exact-identifier queries (e.g., "ResNet", "AlphaFold",
   "BERT") — where lexical overlap is a near-perfect signal and the
   embedder's cosine similarity adds noise. hybrid_rrf avoids this because
   RRF rank-fusion respects the lexical signal.

4. **The gate is NOT being weakened.** Per the contract and Decision 2C, the
   thresholds stay frozen. The honest outcome is that none of the four
   evaluated policies, on this benchmark with this embedder, clears the bar.

## Options for the design review (Decision 2C "Hybrid RRF fails" branch)

Per Decision 2C, the follow-on decision would evaluate (NOT auto-build):
- an existing production-capable cross-encoder
- an existing scoring-only model already present in ERLab
- an external reranker provider
- an LLM reranker
- or revised non-learned feature fusion

**Any reranker must receive its own frozen quality, latency, cost,
failure-policy, and reproducibility contract before being built.**

This is a decision for the human operator, not an automatic next step.
P1B.4+ remains NOT YET AUTHORIZED.

## Artifacts

```
docs/p1b_gate2/gate2_metrics_package.json   full metrics, CIs, verdicts
docs/p1b_gate2/GATE2_CLOSEOUT.md            this file
backend/ranking/p1b3_evaluation.py          evaluation harness (frozen)
```
