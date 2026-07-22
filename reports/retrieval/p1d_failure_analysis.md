# P1D.1 — Historical Failure Analysis

> **Status: DRAFT (revision P1D.1a) for user review. NOT frozen. No gate closed.**
> Author: P1D.1 wave (2026-07-22). Machine-readable twins: `p1d_historical_failure_analysis.jsonl`, `p1d_failure_distribution.json` (v1.1).
> Data source: frozen P1B benchmark (fingerprint `0ffbfdb1…`) + `docs/p1b_gate2/diagnostic_analysis.json` (frozen).
>
> **Revision P1D.1a corrects three defects from v1:** (1) saturation claim overstated — the gate is NOT arithmetically impossible; (2) held-out cases were counted as observed failures — they are now separated; (3) slice-based classifications were presented as causal diagnoses — they are now explicitly slice-informed intervention hypotheses. See "Changes from v1" at the end.

## Executive summary

The historical 66-case benchmark **cannot answer the full product-wide needs-led question** P1D sets out to ask, for two compounding reasons. It can still answer narrower paper-level questions.

1. **The benchmark is partially saturated.** The lexical baseline scores macro nDCG@10 = **0.9495** with recall@20 = 1.0 on the selection split, and is at ceiling on **22 of 44** selection cases (50%). The frozen +0.030 macro gate is **not arithmetically impossible** — the maximum possible gain is +0.0505 — but it is demanding: reaching +0.030 requires an average **+0.060 improvement across the 22 non-ceiling cases with zero regression on the 22 ceiling cases**. The gate has limited statistical power to detect improvements concentrated in a subset of workflows.
2. **Three of six product task families are weakly or minimally covered.** Evidence retrieval and contradiction retrieval operate at passage granularity the benchmark does not have; multi-paper synthesis requires a diversity metric the benchmark does not measure. The benchmark was designed around adversarial retrieval-failure *modes* (slices), not product *workflows* (task families).

**Consequence:** P1D.1, run on this benchmark, cannot close P1 on "retain lexical" (Decision A) — that would be a false negative born of a partially-saturated instrument with structural coverage gaps. It also cannot justify an embedding experiment. Its honest output is: *the full product-wide need question is undetermined on this evidence, and P1D.2 (fresh product-grounded cases) is load-bearing.*

This is **not** a re-litigation of the P1B negative result. P1B correctly found that no candidate policy passed the frozen gate. P1D.1 accepts that result and asks a different question: *was the gate even capable of revealing the full product need?* The answer is: only partially.

---

## 1. The saturation finding (corrected)

### 1.1 The frozen gate failed every candidate — but on what headroom?

P1B Gate 2 returned `NO POLICY PASSES` for all three candidate policies:

| Policy | macro nDCG@10 | Δ vs lexical | Verdict |
|---|---|---|---|
| `legacy_lexical_top20_v1` | **0.9495** | baseline | baseline |
| `semantic_only_v1` | 0.9321 | −0.0174 | FAIL |
| `hybrid_rrf_v1` | 0.9561 | +0.0066 | FAIL |
| `hybrid_weighted_v1` | 0.9394 | −0.0101 | FAIL |

The frozen gate requires **Δ nDCG@10 ≥ +0.030**. The best candidate (`hybrid_rrf`) achieved +0.0066 — roughly one-fifth of the threshold.

### 1.2 The correct arithmetic (v1 was wrong here)

v1 said the gate was "arithmetically impossible" / the benchmark was at "ceiling." **That was too strong.** The correct arithmetic:

```
baseline macro nDCG@10 (selection)         0.9495
maximum mathematically possible gain       +0.0505   (1.0000 − 0.9495)
frozen gate threshold                      +0.0300
→ gate is NOT arithmetically impossible

22 of 44 selection cases are at ceiling (lexical = 1.000)
→ those 22 contribute +0.00 to any macro gain
→ all improvement must come from the 22 non-ceiling cases

non-ceiling selection average (lexical)    0.899
average needed on non-ceiling for +0.030   0.959
required improvement on non-ceiling half   +0.060
```

**Correct wording:** *The benchmark is partially saturated and gives the frozen macro gate limited power to detect improvements concentrated in a subset of workflows. A +0.030 gain remains mathematically possible, but requires an average +0.060 improvement across the non-ceiling half without regression on the ceiling half.* That is demanding, and the 22 ceiling cases substantially dilute observable improvement, but it is feasible.

### 1.3 What this means for P1D.1 as a decision gate

The P1D plan sequences P1D.1 as a gate: *"Proceed to candidate testing only when the audit identifies a material need not satisfied by the current system."* On a partially-saturated benchmark with structural coverage gaps, that gate is unsafe in both directions:

- It could fire **false negative** ("lexical meets the need → Decision A → close P1") because the benchmark cannot reveal failures that don't exist *in the benchmark*, and three task families aren't measured at all.
- It could fire **false positive** ("no need → skip P1D.2") for the same reason.

**Amendment applied:** P1D.1 is treated as a *characterization* step, not a decision gate. Its partial-saturation and coverage findings *justify* P1D.2; they do not terminate the program.

---

## 2. Observed behavior vs case-design attribution (corrected)

**v1 conflated two different things:** observed per-policy metrics (available for 44 selection cases only) and case-design priors (what each slice was built to exercise). v1 treated all 66 cases as if they had observed metrics and counted held-out cases as observed failures. **This was the most important technical defect.** P1D.1a separates them.

### 2.1 Observed distribution — selection split only (44 cases)

This is the only numerically defensible *observed* accounting:

| Observed status (selection, n=44) | Count |
|---|---|
| At ceiling (lexical nDCG@10 = 1.0, no observed failure) | 22 |
| Non-ceiling (lexical imperfect) | 22 |

For the 22 non-ceiling cases, the **observed fact** is that lexical is imperfect. The **cause** is not measured per-case in the gate2 diagnostic. The slice's `slice_expected_failure_mode` is a *design hypothesis* about what the slice was built to exercise — not a measured diagnosis of why this specific case failed.

### 2.2 The corrected embedding-relevance signal

Of the **22 observed non-ceiling selection cases**, **2** have `SEMANTIC_GENERALIZATION` as their slice design hypothesis (both are `semantic_paraphrase` cases: `nlp_disc_sp_001`, `ml_ret_sp_001`). That is **2/22 = 9.1%** observed.

**v1 reported "4/44 = 9.1%".** The percentage coincidentally matches because the held-out set mirrors the slice structure, but the 4/44 interpretation was invalid: 2 of those 4 cases are held-out with no observed metrics and cannot be counted as observed failures. The defensible observed figure is **2/22**.

### 2.3 Case-design distribution — all 66 cases (design priors, not measurements)

For completeness, the case-design attribution across all 66 cases by `slice_expected_failure_mode`. **This is what each slice was designed to exercise, not a measured cause of failure.** Held-out cases appear here by design; their observed behavior is unknown.

| Expected failure mode (design) | Cases (all 66) |
|---|---|
| `LEXICAL_PRECISION` | 12 |
| `AGENDA_MISMATCH` | 12 |
| `EVIDENCE_GRANULARITY` | 12 |
| `RANKING` | 12 |
| `SEMANTIC_GENERALIZATION` | 6 |
| `DIVERSITY` | 6 |
| `JUDGMENT_OR_BENCHMARK` | 6 |

The benchmark is evenly balanced across failure modes by design (6–12 cases each).

### 2.4 Softened embedding conclusion (v1 was too strong)

v1 said the other 91% of imperfect cases were "failures none of which a larger embedding addresses." **This was too strong.** A better embedding could affect ranking or agenda discrimination indirectly. The current evidence establishes only that the non-`SEMANTIC_GENERALIZATION` categories **do not, by themselves, establish an embedding-capacity deficit** — they do not rule out that an embedding could help indirectly.

**Correct reading:** the historical data does not isolate embedding capacity as the *dominant* bottleneck, but it does not exonerate embeddings either. This is meaningfully weaker than v1's claim and is the honest state of the evidence.

---

## 3. Task-family coverage of the existing benchmark

Using the slice→task-family mapping (`p1d_slice_to_task_family_map.json`), the 66 cases cover the six task families very unevenly:

| Task family | Primary-mapped cases | Coverage verdict |
|---|---|---|
| `paper_discovery` | 36 | well covered |
| `evidence_retrieval` | 24 | **weakly covered** (no passage granularity) |
| `research_gap_analysis` | 24 | moderately covered (no PICO cases) |
| `multi_paper_synthesis` | 12 | **weakly covered** (no diversity metric) |
| `method_retrieval` | 6 | moderately covered (direct proxy) |
| `contradiction_retrieval` | 6 | **minimally covered** (weakest of all) |

### 3.1 The structural gap

Three families — `evidence_retrieval`, `contradiction_retrieval`, and `multi_paper_synthesis` — are weakly or minimally covered. The reason is structural, not incidental:

- **Evidence retrieval** and **contradiction retrieval** operate at *passage* granularity. The benchmark operates at *title+abstract* granularity. The benchmark can tell you whether the right paper is in the result set; it **cannot** tell you whether the right *passage* is. These two families cannot be validated by the existing benchmark at all, only proxied.
- **Multi-paper synthesis** requires a *diversity* metric (are the results from distinct papers/labs/lineages?). The benchmark has only a *non-domination* proxy (near-duplicates don't crowd out rank 1). These are not the same property.

This is the second independent reason P1D.2 is load-bearing: **three of the six product task families cannot be evaluated against the existing benchmark**, regardless of saturation.

---

## 4. Decision implications (per P1D.7 decision rules)

| Decision | Triggered by | Triggered here? |
|---|---|---|
| **A** — lexical baseline already satisfies the need | Product gates pass, no material gap | **No — cannot conclude this.** The benchmark is partially saturated and 3 families are unmeasured. A "pass" here would be a false negative. |
| **B** — compact hybrid solves the need | BGE-M3 hybrid improves semantic recall, exact-term preserved, gates pass | Not yet testable — requires P1D.5 preflight + P1D.6 diagnostic. |
| **C** — existing 0.6B hybrid is sufficient | Existing hybrid comparable to BGE-M3 and meets gates | Not yet testable. |
| **D** — ranking is the problem | Relevant evidence in top 50 but misses top 5/10 | **Partially indicated (hypothesis, not measured).** Some non-ceiling cases have a RANKING design prior. Worth investigating, but on partially-saturated data the signal is weak. |
| **E** — evidence construction is the problem | Right papers, absent/fragmented passages | **Indicated but unmeasurable here.** Some non-ceiling cases have an EVIDENCE_GRANULARITY design prior. Confirms chunking/hierarchy is a live hypothesis, but the benchmark can't validate a fix. |
| **F** — structured agenda matching is needed | Dense systems mismatch PICO | **Partially indicated (hypothesis).** Some non-ceiling cases have an AGENDA_MISMATCH design prior. |
| **G** — compact models show a capacity-specific deficit | (six conditions) | **No.** Multiple conditions unmet. 4B is not eligible. |

### 4.1 The honest P1D.1 conclusion

The P1D.1 audit **does not establish a material embedding-capacity deficit** in the historical data — but, crucially, it does not exonerate embeddings either. It establishes:

1. A **partially saturated benchmark** with limited gate power (50% at ceiling; +0.030 needs +0.060 on the non-ceiling half).
2. A **coverage gap** in three of six task families that the benchmark was never designed to measure.
3. **Non-embedding failure-mode hypotheses** (ranking, agenda matching, evidence granularity) that appear in the case-design distribution, none of which has been measured as a *cause* — they are design priors.

None of these justify closing P1 on Decision A, and none justify jumping to a BGE-M3 candidate run. They **do** justify P1D.2: fresh, product-grounded cases at passage granularity for the three under-covered families, which is the only way to determine whether a real need exists that the historical benchmark was blind to.

---

## 5. What P1D.1 did NOT do (honest scope statement)

- It did **not** re-run any policy. All metrics are the frozen P1B Gate 2 numbers.
- It did **not** evaluate any new candidate. No model was loaded, embedded, or probed.
- It did **not** modify the benchmark, the snapshot, or any production code. All artifacts are additive.
- It did **not** touch the held-out split's candidate-policy metrics (held-out was reported for legacy-baseline-only per P1B Decision 3; candidate policies were never evaluated there and still are not).
- It did **not** freeze anything. Every artifact is `status: draft`.
- The case-design attribution is a **design prior grounded in slice intent**, not a measured cause. A future P1D.6 per-case causal classifier would need to establish, per case: whether the relevant item was absent from the candidate set, whether it was in top-50-but-below-cutoff, which specific mis-ranked candidate caused the loss, and whether the dense policy repaired or worsened it. The current schema separates `observed_failure_category` (null for non-ceiling cases, since cause isn't measured) from `slice_expected_failure_mode` (the design hypothesis) precisely to keep this honest.

## 6. Required follow-up

Per the P1D plan, the next wave is **P1D.2 — Build a product-grounded diagnostic set**. P1D.1's partial-saturation and coverage findings make this load-bearing rather than optional. Specifically, P1D.2 must produce:

- A **30-case diagnostic set** drawn from known failure modes, weighted toward the under-covered families.
- A **48-case sealed product-validation set** (8 per task family), at passage granularity for `evidence_retrieval` / `contradiction_retrieval` / `multi_paper_synthesis`.

Until P1D.2 produces cases that exercise the three under-covered families at the right granularity, the P1D.0 question — "does ERLab need a different retrieval system?" — remains genuinely open.

---

## Changes from v1 (P1D.1a correction log)

1. **Saturation wording corrected.** v1: "the benchmark is saturated / the gate is at ceiling / cannot answer." v1.1: "partially saturated; +0.030 is mathematically possible (max +0.0505) but demanding (+0.060 on non-ceiling half); cannot answer the *full product-wide* question but can answer narrower paper-level questions."
2. **Held-out accounting corrected.** v1: counted all 66 cases as observed, reported "4/44 = 9.1%". v1.1: separates observed (selection44, 2/22 = 9.1%) from case-design (all66). The 4/44 aggregate is retracted.
3. **Causal claims softened.** v1: classifications presented as "measured dominant causes"; embedding conclusion "none of which a larger embedding addresses." v1.1: explicitly slice-informed intervention *hypotheses*; conclusion "do not, by themselves, establish an embedding-capacity deficit" (does not exonerate embeddings).
4. **Schema hardened.** Each JSONL row now carries `classification_basis`, `candidate_policy_metrics_available`, `observed_baseline_status`, `observed_failure_category` (null for held-out), and `slice_expected_failure_mode`. Builder asserts fingerprint/count provenance and schema conformance.
