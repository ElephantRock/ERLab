# P1B Closeout — Ranking Evaluation, No Production Activation

> The frozen benchmark, governed semantic snapshot, and predeclared quality
> gate were applied without post-result tuning. No evaluated candidate
> policy demonstrated sufficient quality improvement for production
> activation. The legacy ranking policy therefore remains authoritative.

## 1. Status

```
P0          CLOSED
P1A         CLOSED
P1B         CLOSED at Gate 2 (evaluation complete; no policy activated)
P1          OPEN — quality objective unmet
P2          BLOCKED by P1
```

P1B closure here means the authorized evaluation phase completed correctly.
It does **not** mean ranking quality is solved, and it does **not** close P1
overall. It records a genuine negative result under the frozen contract.

## 2. Entry state and commit chain

```
entry    b95ec20  docs: freeze P1B ranking evaluation and activation contract
42449db  docs(p1b): record authorization for P1B.1-P1B.3 (decisions 1C/2C/3A/4B)
9d2b922  feat(p1b1): expand benchmark to 66 cases with blind-adjudication schema v2
8d48024  docs(p1b1): freeze Gate 1 deliverables for blind adjudication
13f24d3  feat(p1b1): protocol-compliant blind adjudication package v2 + rubric
777fcf7  feat(p1b1): close Gate 1 — blind adjudication reconciled, benchmark frozen
0dfcb60  feat(p1b2): immutable embedding snapshot format + integrity gates
3643631  feat(p1b2): governed embedding snapshot generation harness
e6f5ef7  feat(p1b2): generate governed embedding snapshot via qwen3-embedding-0.6b
c17d894  feat(p1b3): frozen policy evaluation — NO policy passes the gate
e7554a1  docs(p1b2): Gate 2 diagnostic analysis — recommends Branch D
```

## 3. What was completed

| phase | status |
|---|---|
| ranking infrastructure (P1A) | complete |
| benchmark expansion + blind adjudication (P1B.1) | complete |
| governed real-provider embedding snapshot (P1B.2) | complete |
| candidate-policy evaluation (P1B.3) | complete |
| quality improvement proved | **no** |
| production policy activated | **no** |

## 4. Authorization honored (decisions 1C / 2C / 3A / 4B)

- **1C — Cached real embeddings.** Snapshot generated once through
  `EffectiveEmbeddingConfiguration → run_capability_check (dual_probe
  PASSED) → embedding_capability_binding → VerifiedEmbeddingRuntime →
  embed_*_authorized`. Frozen, immutable, self-fingerprinting.
- **2C — Defer reranker conditionally.** Evaluated legacy → semantic-only
  → hybrid_rrf → weighted before considering any reranker. Hybrid RRF
  failed → "Hybrid RRF fails" branch → **no reranker was built** and none
  is authorized by this closeout.
- **3A — Blinded adjudication.** 66 cases / 270 judgments authored, blind
  second pass run (SHA-256-verified), 1 material disagreement adjudicated,
  benchmark frozen.
- **4B — Scope.** Executed P1B.1–P1B.3 only. P1B.4+ never started.

## 5. Frozen evaluation artifacts

```
benchmark version          discovery_ranking_v2+retrieval_ranking_v2
benchmark fingerprint      0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4
benchmark cases            66 (33 discovery + 33 retrieval)
selection splits           calibration + development (44 cases)
held_out                   22 cases (legacy baseline reported only)
embedding snapshot fp      2d8b26f709c03b6bbc7d5c4ab7ca65259a87e8f06ef80b3da0e9e50df69b38d2
snapshot provider          text-embedding-qwen3-embedding-0.6b (1024d, governed)
frozen hyperparameters     rrf_k=60, weighted=0.5/0.5, final_limit=20
frozen thresholds          ΔnDCG@10 ≥ 0.03, bootstrap LB > 0,
                           worst slice ≥ −0.05, replay 100%
```

## 6. Candidate-policy results (calibration + development, n=44)

Macro metrics and paired bootstrap 95% CI vs legacy baseline:

| policy | nDCG@10 | Δ vs legacy | bootstrap CI (Δ) | p(Δ>0) | verdict |
|---|---:|---:|---:|---:|:---:|
| legacy_lexical_top20_v1 (baseline) | 0.9495 | — | — | — | baseline |
| semantic_only_v1 | 0.9321 | −0.0174 | [−0.0410, +0.0048] | 0.064 | FAIL |
| hybrid_rrf_v1 | 0.9561 | **+0.0065** | [−0.0004, +0.0155] | 0.966 | FAIL |
| hybrid_weighted_v1 | 0.9394 | −0.0102 | [−0.0297, +0.0071] | 0.145 | FAIL |

Best candidate (hybrid_rrf_v1): point estimate positive, p(Δ>0)=0.966, but
Δ ≪ 0.03 threshold and bootstrap lower bound ≤ 0. Recall@20 unchanged
(cases have 4–5 candidates; nothing exceeds final_limit=20). Deterministic
replay 100% for all policies.

Per-slice, per-surface, per-domain, and the lexical-ceiling / embedding /
RRF-mechanics / judgment-sensitivity / statistical-power analyses are in
`docs/p1b_gate2/diagnostic_analysis.md`.

## 7. Why the gate failed (Branch D evidence)

The diagnostic established a genuine negative result, not a fixable failure:

```
benchmark validity        adequate   (43% of cases have genuine low-overlap
                                     relevant candidates; not saturated)
statistical power         adequate   (paired-t MDE 0.0081 ≪ 0.03 threshold)
embedding signal          credible   (ρ=0.514, monotonic by grade 0.50/0.64/
                                     0.67/0.72; traps distinguished 4/4;
                                     paraphrases retrieved 3/4)
                                     BUT thin separation (g3↔g2 = 0.05) cannot
                                     overcome lexical overlap's dynamic range
hybrid RRF gate           failed     (+0.0065 < 0.03; LB −0.0004 ≤ 0)
RRF suppression of signal not present (only 2/44 semantic-correction-blocked)
production activation     not earned
```

Branch A (semantic suppressed by RRF), Branch B (weak embedding), and
Branch C (insufficient headroom) were each evaluated and rejected by the
evidence. The legacy lexical baseline is unusually strong on this benchmark
because the synthetic cases use distinctive keywords.

## 8. Changes made during P1B (production / benchmark / threshold accounting)

```
production changes             0    (TrimmerStage unchanged; no policy activated)
threshold changes              0    (frozen thresholds never weakened)
benchmark changes after scoring 0  (no judgments/splits/cases modified after
                                    Gate 1 freeze)
embedding snapshot overwrites  0    (snapshot fingerprint 2d8b26f7… is the
                                    only approved version)
reranker built                 0
LLM reranker built             0
```

## 9. What is now in place (infrastructure for future re-evaluation)

```
backend/ranking/benchmark_v2_schema.py         v2 schema + rubric definition
backend/ranking/benchmark_v2_*_cases.py        66 frozen cases
backend/ranking/benchmark_v2_frozen_adjudication.py  frozen adjudicated grades
backend/ranking/embedding_snapshot.py          immutable snapshot format
backend/ranking/generate_embedding_snapshot.py governed snapshot harness
backend/ranking/p1b3_evaluation.py             frozen policy evaluation
backend/ranking/p1b_gate2_diagnostic.py        8-section diagnostic
docs/p1b_gate1/                                blind adjudication record
docs/p1b_snapshot/                             governed snapshot (regenerable)
docs/p1b_gate2/                                evaluation + diagnostic
```

121 ranking tests pass (44 pre-existing + 77 new across v2 integrity,
snapshot integrity, and P1B.3 evaluation).

## 10. Re-evaluation conditions

P1 should reopen only when there is new evidence capable of changing the
result. Examples (any one would justify a new versioned experiment):

```
a materially stronger governed embedding model
a production-capable cross-encoder or reranker (with its own frozen
    quality / latency / cost / failure-policy / reproducibility contract)
a new deterministic fusion hypothesis justified by diagnostics
a broader independently judged real-world benchmark
```

Any future evaluation **must create a new versioned experiment** (e.g.,
`discovery_ranking_v3+retrieval_ranking_v3`, a new embedding snapshot
version). It must **not** overwrite:

```
the current benchmark (discovery_ranking_v2+retrieval_ranking_v2)
the frozen judgments
the embedding snapshot (2d8b26f7…)
this negative result
```

The infrastructure above makes re-evaluation cheap: a new snapshot +
new policy module + a re-run of `p1b3_evaluation.py` against the new
version.

## 11. Resulting posture

```
legacy_lexical_top20_v1     remains production-authoritative
hybrid_rrf_v1               not activated (failed frozen gate)
reranker                    not built
TrimmerStage                unchanged
P1B                         CLOSED at Gate 2
P1                          OPEN — quality objective unmet
P2                          BLOCKED by P1
```

## 12. Honest summary

P1B succeeded as an *evaluation*: the frozen contract was applied
rigorously, the infrastructure is sound, and the result is trustworthy.
P1B did not succeed at *improving ranking quality*: no policy earned
production use. Both of these statements are true, and the closeout
records both without conflating them.
