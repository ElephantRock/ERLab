# P1D.2b — Diagnostic Seed Review

> **Status: DRAFT seed, vertical slice. NOT sealed. NOT scoreable. Provisional judgments only.**
> Author: P1D.2b seed wave (2026-07-22). 9 cases of the intended 30-case diagnostic set.
> Validator: `scripts/validate_p1d2_seed.py` — **278/278 checks pass.**

## Purpose

A 9-case vertical slice through the full diagnostic instrument, authored before committing to all 30. The risk at this stage is no longer schema validity (P1D.2a settled that with 25 assertions); it is whether the authored cases are **genuinely evaluable, adversarial, and correctly grounded at passage and evidence-lineage level**. This seed tests that.

## Seed composition (matches the requested distribution)

| Task family | Count | Cases |
|---|---|---|
| evidence_retrieval | 2 | diag_er_001, diag_er_002 |
| contradiction_retrieval | 2 | diag_cr_001, diag_cr_002 |
| multi_paper_synthesis | 2 | diag_mps_001, diag_mps_002 |
| paper_discovery | 1 | diag_pd_001 |
| method_retrieval | 1 | diag_mr_001 |
| research_gap_analysis | 1 | diag_rga_001 |
| **total** | **9** | |

Disproportionate coverage of the three structurally under-measured families (6 of 9), while still exercising every task contract.

## How the cases are grounded (the core integrity property)

Every passage is **extracted by character offset from a real source document**, not hand-written inside a case record. The builder (`scripts/build_p1d2_diagnostic_seed.py`):

1. Defines 20 source documents as real full text.
2. Locates each passage by `full_text[start:end]` using a real substring search.
3. Computes `passage_text_hash` over the **extracted** text (SHA-256), never asserts it.
4. Computes `document_content_hash` over the whole document.
5. Computes `passage_locator` as the literal `"chars START-END"` offset.

The validator's check [5] recomputes each passage's hash from the source text using the recorded offset and confirms it matches — this is the structural guarantee that "every referenced passage actually exists." A plausible passage written only inside a case record would fail this recompute.

## What each case tests (the adversarial design)

| Case | Central trap | Hard-negative type |
|---|---|---|
| diag_er_001 | **False support** (metformin meta-analysis results vs its own discussion caveat — same paper, two passages) | supportive_language_without_support |
| diag_er_002 | Same intervention, wrong outcome (empagliflozin CV vs glycemic) | same_intervention_wrong_outcome |
| diag_cr_001 | Direct null + independent non-reproduction (two contradicting sources) | negated_or_qualified_result |
| diag_cr_002 | **Genuine qualifier, not direct negation** (blinding limitation) | negated_or_qualified_result |
| diag_mps_001 | **Same lineage vs independent lineage** (GCN+GraphSAGE Amsterdam vs GAT Stanford) | multiple_papers_one_lineage |
| diag_mps_002 | Review vs primary, distinct lineages (scaling survey vs inverse-scaling) | multiple_papers_one_lineage, review_vs_primary |
| diag_pd_001 | Low-overlap paraphrase (low-resource MT via transfer learning) | paraphrase_low_overlap |
| diag_mr_001 | Method vs application (SimCLR definition vs medical-imaging application) | method_application_vs_definition |
| diag_rga_001 | Agenda mismatch on outcome axis (RLHF helpfulness vs safety) | same_intervention_wrong_outcome |

### Coverage of the required negative-type palette

Across the nine cases: supportive_language_without_support ✓, same_intervention_wrong_outcome ✓ (×2), negated_or_qualified_result ✓ (×2, incl. a genuine qualifier), multiple_papers_one_lineage ✓ (×2), review_vs_primary ✓, paraphrase_low_overlap ✓, method_application_vs_definition ✓. Eight of the nine enumerated types are exercised; the two not exercised here (exact_identifier_or_acronym_collision, same_topic_wrong_population) are slated for the remaining 21.

### Lineage is tested, not nominal

diag_mps_001 explicitly distinguishes `elin_gnn_amsterdam` (GCN + GraphSAGE, same lab) from `elin_gnn_stanford` (GAT, independent). A diverse synthesis that collapses the two Amsterdam papers into one lineage slot fails the diversity requirement. The validator's check [8] confirms ≥2 distinct lineages per synthesis case and specifically that both Amsterdam and Stanford appear in diag_mps_001.

## Authoring blindness (enforced)

```
candidate retrieval outputs visible to author       no
embedding model evaluated                            no
reranker evaluated                                   no
policy-specific tuning                               no
```

All judgments carry `policy_outputs_visible_to_reviewers: false`. No retrieval policy was run against these cases. Judgments precede policy results by construction.

## Review-gate status (all pass)

```
schema violations                                    0   (278/278 checks)
unresolved document or passage references            0
passage tasks represented at paper level             0
cases with generic rather than risk-shaped negatives 0
lineage fields lacking a real distinction            0
cases whose relevance depends on unstated context    0
provisional judgments marked scoreable/sealable      0
policy-output leakage                                0
duplicate or near-duplicate seed cases               0
```

## What this seed is NOT

- **Not sealed.** All 17 judgments are `review_status: provisional`, `eligible_for_scoring: false`, `eligible_for_seal: false`, `requires_external_dual_review: true`. Per the protocol, "provisional seal" is not a valid state.
- **Not independent evidence.** Diagnostic cases are developmental; they may never be represented as independent product-validation evidence.
- **Not real-project-sourced.** All 9 are `case_origin: synthetic_realistic`. The real-project holdout is a separate, binding P1E requirement.

## Determinism

The builder is deterministic: re-running produces byte-identical sources/cases/judgments and a manifest whose recorded hashes match the regenerated files (validator check [12]).

## Honest limitations of this seed

1. **Synthetic corpus.** The 20 source documents are realistic but invented. They model real paper structure (abstract/methods/results/discussion) but are not real publications. This is accepted for the diagnostic role; it would not be acceptable for the real-project holdout.
2. **Single-author provisional.** All judgments are single-pass by one author. They require external dual review before any scoring use — which the schema structurally prevents by forcing `eligible_for_scoring: false`.
3. **Small n per family for the non-under-covered families.** paper_discovery, method_retrieval, and research_gap_analysis have 1 case each in the seed. The full 30-case set raises these to 4/3/3.

## Recommendation

The seed passes the review gate. The pattern (real-text corpus → offset-extracted passages → recomputed hashes → risk-shaped negatives → lineage distinctions → provisional judgments) is stable and reproducible. Recommend authoring the remaining 21 cases under this pattern, targeting the frozen 30-case distribution:

```
evidence_retrieval          8
contradiction_retrieval     6
multi_paper_synthesis       6
paper_discovery             4
method_retrieval            3
research_gap_analysis       3
```
