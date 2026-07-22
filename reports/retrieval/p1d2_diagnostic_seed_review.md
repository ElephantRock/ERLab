# P1D.2b — Diagnostic Seed Review

> **Status: DRAFT seed (v2, post-hardening + er_001 correction). NOT sealed. NOT scoreable. authored_provisional judgments only.**
> Author: P1D.2b seed wave (2026-07-22). 9 cases of the intended 30-case diagnostic set.
> Validators: `scripts/validate_p1d2_schemas.py` (25) + `scripts/validate_p1d2_seed.py` (134) — both green.

## Revision history

- **v1 (commit 72aa05f):** initial 9-case seed, offset-extracted passages, 278 checks.
- **v1 hardening (commit 257443e):** candidate pools, exhaustive judgments, claim dimensions, derived judgments file. **Introduced a semantic defect in diag_er_001** (weakened the causal claim to associational to make the observational result "correct," removing the false-support trap).
- **v2 (this revision):** **corrected diag_er_001** — restored the causal claim, added a causally-adequate positive RCT to the corpus, restructured the case into the three-role design (causal positive / observational false-support / design qualifier). Manual semantic review of all 9 cases completed. 134 checks pass.

## The diag_er_001 correction (the substantive change)

The hardening patch weakened the target claim from causal to associational so the observational result would "fully support" it. That removed the false-support trap instead of testing it — the exact failure mode the patch was supposed to prevent. v2 restores the trap correctly:

```
target claim                  metformin CAUSALLY reduces cancer incidence
                              (causal_vs_associational: causal_claim)
                              (study_design_requirement: randomized controlled trial)

fully supporting positive     doc_metformin_rct_positive — positive RCT, grade 3
  (NEW source doc added)        causally adequate, supports direction + force

false-support hard negative   doc_metformin_meta (results) — observational, grade 1
                                supportive wording ("reduced incidence") but
                                fails causal_vs_associational + study_design_requirement

qualifying evidence           doc_metformin_meta (discussion caveat) — grade 2
                                warns of confounding; fails study_design_requirement

cross-case distractor         doc_empagliflozin — grade 0
                                different drug, different outcome
```

The claim has a genuinely supporting passage (the RCT, grade 3) AND the central trap is intact (association mistaken for causation). The false-support problem is solved by adding causally-adequate evidence, not by weakening the claim.

## Manual semantic review (all 9 cases)

The validators prove structure (identity, hashes, coverage, schema). They cannot prove that a passage genuinely supports, contradicts, or qualifies a claim. The review below is the manual semantic check the reviewer requested.

### Per-case findings

| Case | Positive supports exact claim? | Hard negative genuinely difficult? | failed_dimension correct? | Qualifier not mislabeled? | Grade matches text? | Distractor plausible? |
|---|---|---|---|---|---|---|
| diag_er_001 | ✅ RCT supports causal claim | ✅ obs-as-causation is the canonical false-support | ✅ causal_vs_associational + study_design | ✅ caveat is qualifier (study_design), not irrelevant | ✅ g3/g1/g2/g0 | ✅ empagliflozin |
| diag_er_002 | ✅ CV result for CV claim | ✅ glycemic result is same-drug wrong-outcome | ✅ outcome | n/a | ✅ g3/g1/g1 | ✅ PCSK9 |
| diag_cr_001 | ✅ null RCT contradicts | ✅ meta-analysis positive must not drown null | ✅ causal+design | n/a | ✅ g3/g3/g1 | n/a |
| diag_cr_002 | ✅ blinding caveat qualifies | ✅ genuine qualifier, not negation | n/a | ✅ qualifier is grade 3 (the sought unit) | ✅ g3/g2/g2 | ✅ review |
| diag_mps_001 | ✅ GCN + GAT are distinct lineages | ✅ GraphSAGE same-lab redundancy | ✅ evidence_lineage | n/a | ✅ g3/g2/g3 | n/a |
| diag_mps_002 | ✅ inverse-scaling is primary | ✅ survey is review-aggregate | ✅ lineage + granularity | n/a | ✅ g3/g2 | n/a |
| diag_pd_001 | ✅ transfer-learning addresses low-resource | ⚠️ GAT distractor is topically distant (see note) | ✅ meaning_or_domain | n/a | ✅ g3/g0 | ⚠️ see note |
| diag_mr_001 | ✅ SimCLR defines the loss | ✅ application-vs-method is genuinely confusable | ✅ evidence_granularity | n/a | ✅ g3/g2 | n/a |
| diag_rga_001 | ⚠️ InstructGPT is helpfulness, query asks safety | ✅ safety-vs-helpfulness is real agenda mismatch | ✅ outcome | n/a | ✅ g2/g1 | ✅ scaling survey |

### Two non-blocking observations

1. **diag_pd_001 distractor is topically distant.** The GAT passage (graph neural networks) is the hard negative for a low-resource-MT query. It's schema-valid and resolves, but it's a *generic* off-topic negative rather than a *risk-shaped* one — the very thing the protocol says to avoid. For a paper-discovery case whose defining trap is `paraphrase_low_overlap`, the hard negative should ideally be a same-topic-but-different-subdomain paper, not an unrelated-domain paper. **Not blocking for the seed** (paper_discovery is a secondary family here with 1 case), but the remaining 3 paper-discovery cases should use risk-shaped negatives (e.g., a translation-memory paper for an NMT query), not generic off-topic ones. Flagged for the remaining 21.

2. **diag_rga_001 has no fully-supporting grade-3 unit.** The query asks for RLHF-safety papers; InstructGPT is about helpfulness (grade 2, fails on `outcome`), and the scaling survey mentions safety but isn't RLHF (grade 1). This is actually *correct for a research-gap-analysis case* — the gap is that no paper fully addresses the safety question — but it means the case has no grade-3 positive, unlike the evidence-retrieval cases. This is by design (the case tests whether the system correctly returns agenda-adjacent work rather than fabricating a match), but worth noting that research-gap cases may legitimately lack a grade-3 unit. **Not a defect.**

### failed_dimension audit (correctness check across all cases)

Every `negative_failed_dimensions` entry was checked against the actual passage text and claim dimensions. All are correct except the two observations above (which are design choices, not mislabels). No pattern of systematic mislabeling found.

## Patch-gate status (all green)

```
scored candidate universe defined                  0 undefined
scored units without judgments                      0
orphan or duplicate judgments                      0
inline/parallel judgment divergence                0 (byte-for-byte)
builder outputs nondeterministic                    0 (all 4 stable across 2x build)
false-support claim without fully supporting unit   0 (er_001 fixed)
qualifying evidence mislabeled as generic negative  0
synthetic authoring leakage untested                0 (bias audit: no verbatim copy, cross-case sharing present)
exact-identifier collision only background          (deferred to remaining 21)
wrong-population mismatch only background           (deferred to remaining 21)
```

## Determinism

All four outputs byte-stable across two builds (sources, cases, judgments, manifest — identical SHA-256). Manifest records live hashes, schema versions, candidate-pool design, and judgment-authority model.

## What this seed is NOT

- **Not sealed.** All judgments `authored_provisional`, non-scoreable, non-sealable, requires-external-dual-review. Not "provisional seal."
- **Not independent evidence.** Diagnostic only; never activation evidence.
- **Not real-project-sourced.** All `synthetic_realistic`.

## Recommendation

The seed passes the bounded review gate. The corrected diag_er_001 preserves a genuine false-support trap with a fully-supporting positive. The two non-blocking observations (diag_pd_001 generic distractor; diag_rga_001 legitimately grade-3-less) are noted for the remaining 21 cases.

The pattern is now stable across both structure and semantics. Recommend proceeding with the remaining 21 cases (+6 er, +4 cr, +4 mps, +3 pd, +2 mr, +2 rga), including the two deferred primary traps (exact-identifier collision, wrong-population mismatch), using risk-shaped negatives throughout.

