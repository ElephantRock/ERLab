# P1B Gate 2 Diagnostic Analysis

## Branch recommendation: **D — close P1B without activation**

The evidence does **not** support Branch A (semantic signal suppressed by
RRF), Branch B (weak embedding), or Branch C (insufficient headroom). It
supports the conclusion that **no candidate policy earns production use on
this benchmark with this embedder, and the infrastructure to detect an
improvement is sound.**

The honest outcome is to retain the legacy lexical baseline, keep P1 open,
and document that no policy met the frozen production gate. Rationale per
section below.

Full machine-readable data: `docs/p1b_gate2/diagnostic_analysis.json`.

---

## Setup

- 44 selection cases (calibration + development); held_out (22) preserved
- frozen benchmark `0ffbfdb1…`; snapshot `2d8b26f7…` (qwen3-embedding-0.6b)
- frozen hyperparameters: rrf_k=60, weighted=0.5/0.5, final_limit=20

---

## Section 1 — Case-level deltas

Classification of hybrid_rrf vs legacy across 44 cases:

```
no_effective_change     34   (77%)
hybrid_marginal_win      5   (11%)
hybrid_clear_win         2   ( 5%)
hybrid_marginal_loss     2   ( 5%)
hybrid_material_loss     1   ( 2%)
```

77% of cases are unchanged by RRF; the wins and losses roughly cancel
(net +0.0065 macro). The two clear wins are on `neutral` slice cases
(`ml_disc_nt_001`, `bio_disc_nt_001`) where lexical ranking had a low
baseline (~0.81) — i.e., cases that were *not* designed as adversarial.

The one material loss is `exact_identifier` (`bio_disc_ei_001`), where RRF
mildly perturbs a near-perfect lexical ranking.

## Section 2 — Slice analysis (the central question)

```
slice                     sem Δ     rrf Δ     wt Δ      n
acronym_vs_expanded      +0.0355   +0.0355   +0.0000    4
semantic_paraphrase      +0.0002   +0.0062   +0.0062    4   ← intended-help slice
neutral                  +0.0269   +0.0228   +0.0585    4
source_rank_conflict    -0.0330   +0.0076   +0.0076    4
near_duplicate          -0.0038   +0.0042   +0.0015    4
method_vs_application   -0.0590   +0.0060   -0.0249    4
negated_findings        +0.0026   +0.0000   +0.0026    4
lexical_trap            +0.0000   +0.0000   +0.0000    4   ← intended-help slice
missing_abstract        -0.0078   +0.0000   -0.0078    4
review_vs_primary       -0.0568   -0.0035   -0.0532    4
exact_identifier        -0.0964   -0.0068   -0.1023    4   ← intended-stable slice (RRF holds)
```

**The semantic-ranking slices it was designed to help are already saturated:**
- `lexical_trap`: legacy 0.9164; semantic adds **+0.0000**. The traps are
  *trivially* avoided by lexical overlap (the trap candidates share one or
  two query tokens but are obviously off-topic once ranked by overlap
  because the relevant candidates share *more* tokens).
- `semantic_paraphrase`: legacy 0.9453; semantic adds **+0.0002**. The
  paraphrase candidates still share enough surface tokens with the query
  that lexical overlap already ranks them correctly.

**Where semantic-only actively helps:** `acronym_vs_expanded` (+0.0355)
and `neutral` (+0.0269) — neither of which is an adversarial slice designed
to expose lexical failure.

**Where semantic-only actively harms:** `exact_identifier` (−0.0964),
`method_vs_application` (−0.0590), `review_vs_primary` (−0.0568) —
precisely the slices where lexical overlap is the correct signal and the
embedder's cosine adds noise.

**RRF consistently rescues semantic-only's failures** (note rrf_d ≥ sem_d
on every harmful slice), which is why hybrid_rrf ends up net-positive but
tiny: it can only recover ground semantic lost, not add new value beyond
lexical.

## Section 3 — Surface + domain

```
surface                  legacy   sem Δ    rrf Δ     wt Δ
discovery_ranking        0.9591  -0.0254  +0.0007   -0.0171   (n=22)
retrieval_ranking        0.9399  -0.0094  +0.0124   -0.0032   (n=22)

domain
machine_learning         0.9665  -0.0205  -0.0008   -0.0104   (n=15)
biomedical               0.9166  -0.0278  +0.0084   -0.0240   (n=14)
nlp                      0.9632  -0.0046  +0.0122   +0.0031   (n=15)
```

No aggregate improvement hides degradation on another surface: hybrid_rrf
is approximately flat on both discovery (+0.0007) and retrieval (+0.0124).
Biomedical has the lowest legacy baseline (0.9166) and the largest RRF
gain (+0.0084) — but it's still well below threshold.

## Section 4 — Lexical-baseline ceiling

```
perfect legacy nDCG@10 (>= 0.999):       22/44  (50%)
trivially separable (g≥2 overlaps > g≤1): 12/44  (27%)
genuine low-overlap relevant (g≥2, o<0.3): 19/44  (43%)
verdict: moderate_headroom
```

**Mixed signal.** 50% of cases are already perfectly ranked by lexical
overlap, and 27% are trivially separable (every relevant candidate has
strictly higher overlap than every irrelevant one). These cases cannot
demonstrate a semantic gain. However, 43% of cases have at least one
genuinely low-overlap relevant candidate (overlap < 0.3) — so the benchmark
isn't *entirely* saturated. There is headroom in principle, but the
embedding isn't capturing it (see Section 5).

This is **not** a Branch C trigger: the benchmark has enough low-overlap
cases that a genuinely better semantic policy *could* show a 0.03 gain; it
just didn't.

## Section 5 — Embedding snapshot analysis

```
overall similarity ↔ grade rank correlation:  0.514
mean cosine by grade:
    grade 0:  0.4953
    grade 1:  0.6446
    grade 2:  0.6733
    grade 3:  0.7210
lexical_trap cases where embedding distinguishes the trap:  4/4
semantic_paraphrase cases where top-sim candidate is grade-3:  3/4
```

**The embedding is monotonic in relevance** (0.50 → 0.64 → 0.67 → 0.72 by
grade) with a credible rank correlation of 0.514. It correctly
distinguishes lexical traps (4/4) and retrieves paraphrases (3/4).

**This is the decisive negative finding for Branch A.** The embedding
signal exists and is correctly ordered — but the *absolute separation*
between grade 3 (0.72) and grade 2 (0.67) is only **0.05**, and between
grade 2 (0.67) and grade 1 (0.64) only **0.03**. On cases where the
lexical ranking is already near-perfect, this thin separation is dominated
by lexical overlap's much larger dynamic range. RRF correctly prefers the
lexical signal in those cases (Section 6), so it's not *suppressing* a
useful semantic signal — there is no useful semantic signal to suppress.

This is also **not** Branch B (weak embedding): the embedding is weakly
but genuinely informative; it's just not informative *enough* relative to
lexical on this benchmark.

## Section 6 — RRF mechanics

```
semantic correction blocked by RRF:           2/44
lexical dominance (lex#1 == rrf#1 != sem#1): 14/44
```

Only **2 cases** show "semantic-only wins but RRF does not capture the
gain" — both are non-adversarial (`neutral` and `negated_findings`). On
both, the semantic-only gain comes from reordering within already-relevant
candidates, not from surfacing a missed relevant one.

In 14 cases RRF ranks the lexical #1 candidate first (differing from
semantic's #1) — and this is *correct* behavior, because in those cases
the lexical #1 is the grade-3 candidate and the semantic #1 is a grade-2
noise candidate. RRF is doing its job: respecting the stronger signal.

**Branch A is not supported.** There is no systematic suppression of a
useful semantic correction by RRF. The semantic signal that exists is
either (a) already captured by lexical overlap, or (b) too thin to
overcome lexical's dynamic range.

## Section 7 — Judgment sensitivity

```
low-confidence judgments (<0.75 confidence):  see JSON
baseline mean Δ (rrf − legacy):              +0.0065
max single-judgment case Δ shift:            0.0917  (one case)
max implied mean Δ shift:                    0.0021
gap to 0.03 threshold:                       0.0235
verdict under max perturbation:              stable
```

Even the most aggressive single-judgment ±1 perturbation could shift the
macro mean by at most 0.0021 — far below the 0.0235 gap to the 0.03
threshold. **The Gate 2 verdict is robust to plausible judgment
disagreement.** This is not a measurement artifact.

## Section 8 — Statistical power

```
n cases:                                    44
mean paired Δ (rrf − legacy):               +0.0065
sd paired Δ:                                0.0274
minimum detectable effect (paired t, 95%):  0.0081
frozen threshold:                           0.0300
MDE exceeds threshold:                      false
interpretation:                             adequately_powered
```

**The benchmark is adequately powered** to detect the 0.03 threshold (MDE
0.0081 ≪ 0.03). The observed +0.0065 is within the MDE — meaning the true
effect, if any, is smaller than 0.03. This is genuine equivalence at the
threshold scale, **not** a power failure.

The bootstrap 95% CI on the observed Δ is [−0.0004, +0.0155], which lies
entirely below the 0.03 threshold. Even the upper bound is half the
threshold.

---

## Branch assessment

| Branch | Required evidence | Present? |
|---|---|:---:|
| **A** — semantic signal exists, RRF suppresses it | semantic-only wins important slices; RRF loses those gains; credible embedding correlation | ❌ semantic-only doesn't win adversarial slices; RRF doesn't suppress (only 2 cases) |
| **B** — semantic signal is weak | semantic-only fails paraphrase; low embedding correlation; traps remain highly similar | ❌ embedding correlation is 0.514 (credible); traps distinguished 4/4 |
| **C** — benchmark insufficient headroom | most cases perfect; few lexical/semantic disagreements; MDE > threshold | ❌ 43% have low-overlap relevant; MDE 0.0081 < threshold |
| **D** — adequate benchmark, no policy signal | sufficient lexical difficulty; adequate power; no meaningful improvement | ✅ all three hold |

## Recommendation

**Branch D.** Close P1B Gate 2 without production activation. Retain the
explicit legacy lexical baseline. Keep P1 open. Document that no candidate
policy earned production use on this benchmark with this embedder.

This is not a failure of infrastructure: the benchmark is well-constructed
(43% genuine low-overlap cases), adequately powered (MDE 0.0081), the
embedding is genuinely informative (ρ=0.514, monotonic by grade), and the
evaluation machinery is sound (100% deterministic replay, robust to
judgment perturbation). It is a genuine negative result: on this benchmark
with qwen3-embedding-0.6b, **semantic ranking does not add value beyond
the lexical baseline at the +0.03 threshold.**

The infrastructure is now in place to re-run this evaluation cheaply if a
future condition changes — a stronger embedder, a benchmark expansion
(under a new frozen version, preserving the original), or a true
cross-encoder reranker with its own contract. None of those is justified
by the current evidence.

## Prohibited during this diagnostic (and observed)

```
change relevance judgments                NOT done
change split assignments                  NOT done
regenerate embeddings                     NOT done
change the RRF constant                   NOT done
tune weights                              NOT done
add benchmark cases                       NOT done
lower acceptance thresholds               NOT done
activate hybrid RRF                       NOT done
start TrimmerStage migration              NOT done
build an LLM reranker                     NOT done
```

## Artifacts

```
docs/p1b_gate2/diagnostic_analysis.json   full per-case + per-section data
docs/p1b_gate2/diagnostic_analysis.md     this file
docs/p1b_gate2/gate2_metrics_package.json frozen evaluation metrics + verdicts
docs/p1b_gate2/GATE2_CLOSEOUT.md          Gate 2 closeout (verdict summary)
backend/ranking/p1b_gate2_diagnostic.py   diagnostic harness (reproducible)
```
