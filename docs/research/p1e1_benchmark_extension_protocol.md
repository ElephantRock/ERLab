# P1E.1 — Benchmark Extension Protocol (FREEZE CANDIDATE)

```text
P1E.0                    CLOSED — Outcome M
P1E.1 protocol authoring AUTHORIZED
Commit 1 seal            PENDING pre-seal verification (this document)
Candidate construction   NOT AUTHORIZED
P1E.2 / P1E.3            BLOCKED
```

> **Mission.** Produce a new, versioned v3 candidate corpus that increases
> hard-negative coverage and metric sensitivity, preserving the frozen P1B v2
> corpus as an immutable historical baseline. P1E.1 constructs and seals the
> unblinded calibration/development extension and the blinded held-out package.
> Final held-out judgments belong to P1E.2.

This document freezes every value before any candidate construction. Once
sealed, the protocol SHA-256 and the split-manifest SHA-256 are immutable
inputs for every P1E.1 artifact.

## 1. Exact composition

```text
total v3 candidate cases              88
calibration cases                     33
development cases                     33
held-out cases                        22
cal+dev n after extension             66   (was 44; design lever for projected MDE)

v2-lineage cases                      44   (all 44 v2 cal+dev queries, extended)
  extended v2-lineage                 44
  unchanged v2-lineage                 0
  v2 held-out lineage in v3            0
fully-new cases                       44
  fully-new cal+dev                   22   (11 calibration + 11 development)
  fully-new held-out                  22
```

The 44 parent v2 cal+dev IDs are the frozen P1E.0 audited set. Allowlist
(sorted `audited_case_ids` from `data/evaluation/p1e_discrimination_audit.json`):

```text
parent_allowlist_sha256 = 4f6fdfa8bf44ba02f5fe6592ea9c1124fbde594c94e14475ece6ac3550db5e70
parent_allowlist_count  = 44
v2 held-out lineage     = 0
```

### 1.1 Fully-new case allocation table (44 rows, authoritative)

The table below is the authoritative allocation (the deterministic generation
rule is recorded in §1.2 for reproducibility only; the table itself governs).

`allocation_table_sha256 = ffb05ad3743c1b5fc6ca9cc5e7257f992166117dddd5ffffaa1fe0b1fb4b4edd`

| v3_case_id | split | domain | slice | surface | lineage_type |
|---|---|---|---|---|---|
| v3_disc_lt_001 | calibration | machine_learning | lexical_trap | disc | fully_new |
| v3_ret_lt_001 | development | machine_learning | lexical_trap | ret | fully_new |
| v3_disc_lt_002 | calibration | biomedical | lexical_trap | disc | fully_new |
| v3_ret_lt_002 | development | biomedical | lexical_trap | ret | fully_new |
| v3_disc_lt_003 | calibration | nlp | lexical_trap | disc | fully_new |
| v3_ret_lt_003 | development | nlp | lexical_trap | ret | fully_new |
| v3_disc_sp_001 | calibration | biomedical | semantic_paraphrase | disc | fully_new |
| v3_ret_sp_001 | development | biomedical | semantic_paraphrase | ret | fully_new |
| v3_disc_sp_002 | calibration | nlp | semantic_paraphrase | disc | fully_new |
| v3_ret_sp_002 | development | nlp | semantic_paraphrase | ret | fully_new |
| v3_disc_mv_001 | calibration | machine_learning | method_vs_application | disc | fully_new |
| v3_ret_mv_001 | development | machine_learning | method_vs_application | ret | fully_new |
| v3_disc_mv_002 | calibration | nlp | method_vs_application | disc | fully_new |
| v3_ret_mv_002 | development | nlp | method_vs_application | ret | fully_new |
| v3_disc_rv_001 | calibration | machine_learning | review_vs_primary | disc | fully_new |
| v3_ret_rv_001 | development | machine_learning | review_vs_primary | ret | fully_new |
| v3_disc_rv_002 | calibration | biomedical | review_vs_primary | disc | fully_new |
| v3_ret_rv_002 | development | biomedical | review_vs_primary | ret | fully_new |
| v3_disc_ma_001 | calibration | biomedical | missing_abstract | disc | fully_new |
| v3_ret_ma_001 | development | biomedical | missing_abstract | ret | fully_new |
| v3_disc_ma_002 | calibration | nlp | missing_abstract | disc | fully_new |
| v3_ret_ma_002 | development | nlp | missing_abstract | ret | fully_new |
| v3_disc_nd_001 | held_out | machine_learning | near_duplicate | disc | fully_new |
| v3_ret_nd_001 | held_out | machine_learning | near_duplicate | ret | fully_new |
| v3_disc_nd_002 | held_out | biomedical | near_duplicate | disc | fully_new |
| v3_ret_nd_002 | held_out | biomedical | near_duplicate | ret | fully_new |
| v3_disc_sr_001 | held_out | nlp | source_rank_conflict | disc | fully_new |
| v3_ret_sr_001 | held_out | nlp | source_rank_conflict | ret | fully_new |
| v3_disc_sr_002 | held_out | machine_learning | source_rank_conflict | disc | fully_new |
| v3_ret_sr_002 | held_out | machine_learning | source_rank_conflict | ret | fully_new |
| v3_disc_ac_001 | held_out | biomedical | acronym_vs_expanded | disc | fully_new |
| v3_ret_ac_001 | held_out | biomedical | acronym_vs_expanded | ret | fully_new |
| v3_disc_ac_002 | held_out | nlp | acronym_vs_expanded | disc | fully_new |
| v3_ret_ac_002 | held_out | nlp | acronym_vs_expanded | ret | fully_new |
| v3_disc_nf_001 | held_out | machine_learning | negated_findings | disc | fully_new |
| v3_ret_nf_001 | held_out | machine_learning | negated_findings | ret | fully_new |
| v3_disc_nf_002 | held_out | biomedical | negated_findings | disc | fully_new |
| v3_ret_nf_002 | held_out | biomedical | negated_findings | ret | fully_new |
| v3_disc_ei_001 | held_out | nlp | exact_identifier | disc | fully_new |
| v3_ret_ei_001 | held_out | nlp | exact_identifier | ret | fully_new |
| v3_disc_ei_002 | held_out | machine_learning | exact_identifier | disc | fully_new |
| v3_ret_ei_002 | held_out | machine_learning | exact_identifier | ret | fully_new |
| v3_disc_nt_001 | held_out | biomedical | neutral | disc | fully_new |
| v3_ret_nt_001 | held_out | biomedical | neutral | ret | fully_new |

Aggregate checks: rows=44; new calibration=11; new development=11; new held_out=22;
duplicate v3 IDs=0; unknown domains/slices/splits=0; v2 held-out lineage=0.

Global counts: domain {machine_learning:14, biomedical:16, nlp:14} (max−min=2);
slice = 4 each across all 11 (max−min=0); surface {disc:22, ret:22}.

### 1.2 Deterministic generation rule (reproducibility only)

Iterate the 11 slices in fixed vocabulary order; for each slice pick a
2-domain pair rotated by `slice_index % 3` over `{(ml,bio),(bio,nlp),(ml,nlp)}`;
emit 4 cases per slice = `{disc,ret} × domain_pair`. Assign splits by walking
the 44 cases in generation order: the first 22 alternate
calibration/development (11 each); the remaining 22 are held_out. IDs are
numbered per (surface, slice) in generation order.

## 2. Balance tolerances (operational)

```text
domain balance   max(domain_count) - min(domain_count) <= 2   (global and per-split)
slice balance    global: max-min <= 1 (achieved 0); per-split: max-min <= 2
                  (held_out n=22 over 11 slices = 2 ideal; <=2 is the feasible rule)
surface balance  disc == ret (achieved 22/22 globally; balanced per construction)
```

Reported and tested aggregates: global domain, global slice, domain×split,
slice×split, domain×slice×split (max 2 per cell permitted).

## 3. Power projection (direct-array SDs, ddof=1)

Computed directly from the 44 sealed per-case nDCG@5 deltas in each required
comparison of `data/evaluation/p1e_policy_pairwise_comparison.json`.

```text
source artifact path    data/evaluation/p1e_policy_pairwise_comparison.json
source artifact SHA-256 29dde991d126d8605d0c6098bd7f07b3847cef67beefc255540e2fa0022b34d3
paired-value count      44 per comparison
SD convention           sample SD, ddof=1
median convention       arithmetic mean of the two middle ordered SDs (n=4)
formula                 projected_mde = 2.801586 * SD / sqrt(n)   (alpha 0.05, power 0.80)
exact planned cal/dev n 66   (sqrt = 8.12404)
```

| comparison | direct SD | projected MDE @ n=66 |
|---|---|---|
| lexical_vs_p1b_semantic | 0.07744 | 0.02671 |
| lexical_vs_tei_semantic | 0.07321 | 0.02525 |
| p1b_semantic_vs_tei_semantic | 0.06060 | 0.02090 |
| p1b_hybrid_rrf_vs_tei_hybrid_rrf | 0.03258 | 0.01124 |

Scenario summary:

| scenario | SD | projected MDE @ n=66 | passes ≤0.03 |
|---|---|---|---|
| min | 0.03258 | 0.01124 | yes |
| median | 0.06690 | 0.02307 | yes |
| max | 0.07744 | 0.02671 | yes |
| conservative (max×1.10) | 0.08518 | 0.02938 | yes |

**Chosen design guarantee: the conservative-upper scenario passes ≤0.03 at
cal/dev n=66.** This is a design projection only; actual MDE is measured in
P1E.3 after at least two frozen ranking configurations are evaluated. The
MDE-derived SD (`sd = MDE·√44/2.801586`) is retained only as a cross-check
and matches the direct-array SD to within 1e-6 on every comparison.

## 4. Targets (numerically frozen)

Grade-dependent targets are scoped to **adjudicated calibration+development
cases only**. Held-out validates structural targets only.

```text
candidate count per cal/dev case               6-8
candidate count per held-out case              6-8
min grade-0 per adjudicated cal/dev case       1
required % cal/dev with >=2 grade-0            80
required % cal/dev with >=2 primary hard neg   60
unique-best min % (cal/dev)                    50
ambiguous-top                                  report-only
weak-positive coverage                         report-only
constructed near-duplicate case minimum        12  (validated constructed; cal+dev+held-out; counts CASES)
adjudicated misleading near-duplicate minimum   8  (cal/dev CASES)
constructed lexical-trap case minimum          12  (cal+dev+held-out; counts CASES)
adjudicated grade-0 lexical-confuser minimum    8  (cal/dev CASES)
provenance completeness                        100
```

**Miss semantics:** a required target missed → P1E.1 does NOT close → the miss
is recorded in the extension identity → the frozen corpus is NOT edited →
retry requires a new candidate-corpus version. (No post-hoc candidate changes
within the same frozen construction.)

## 5. Hard-negative and confuser definitions

```text
primary hard negative (grade-dependent, unchanged from P1E.0):
  grade == 0
  AND ( lexical_overlap score OR semantic_mining score )
      >= minimum score among grade > 0 candidates in that case

declared_near_duplicate_pair (construction, pre-adjudication):
  candidate field mining_role = "constructed_near_duplicate"
  + near_duplicate_of = <parent candidate_id>
  sealed in the candidate package.

validated_constructed_near_duplicate (after mining scores sealed):
  a declared pair whose two candidates have DISTINCT content_hash
  AND frozen semantic_mining cosine >= 0.92.
  The structural quota (12) counts CASES containing >=1 validated pair.

adjudicated_misleading_near_duplicate (after cal/dev adjudication):
  a validated pair whose two candidates received DIFFERENT final grades.
  quota (8) counts cal/dev CASES.

constructed lexical trap (construction, pre-adjudication):
  a candidate with mining_role = "constructed_lexical_trap"
  whose frozen lexical_overlap score >= maximum lexical_overlap score of the
  FROZEN CONSTRUCTION ANCHORS in that case.
  anchor = query_generation_anchor_candidate_id (construction-only; carries NO
  grade/expected-grade; stored in mining provenance only; omitted from
  adjudication views). quota (12) counts CASES.

adjudicated grade-0 lexical confuser (grade-dependent):
  grade == 0 AND score >= minimum score among grade > 0 candidates.
  quota (8) counts cal/dev CASES.
```

## 6. Mining scorer identity (frozen by value)

```text
scorer 1 — lexical_overlap:
  source path             backend/ranking/policies.py
  source-file SHA-256     0db56255e0653088fd965e9520d0011303c2884fadc362a517b7f8ebe075c010
  pre-freeze parent commit c1fa5541a5efa9a57a2c6bc10ab3d0832ac29fa3
  qualified name          backend.ranking.policies._keyword_overlap
  formula                 |query_words ∩ text_words| / |query_words|
  tokenization            re.findall(r"\w+", text.lower())
  tie                     candidate_id asc

scorer 2 — semantic_mining (candidate-mining diagnostic ONLY; NOT a P1E.3 policy):
  model                   Alibaba-NLP/gte-large-en-v1.5
  revision                104333d6af6f97649377c2afbde10a7704870c7b
  runtime                 TEI 1.9.3, sha 06670157fb6c1523482219bdb2d1660277d38088
  image digest            sha256:ad950d30878eceb72aaf32024d26fa2b1d04a75304fa0b4776b49aa1941fea07
  pooling                 cls ; dtype float32 ; dimension 1024 ; L2-normalized
  max input tokens        512 ; request shape single input
  truncation              FORBIDDEN; over-limit input fails
  empty field rule        treat empty title/abstract as "" (join still "{title}\n\n{abstract}")
  text transform          operate on sealed canonical candidate text (NFC, LF); no extra normalization
  query transform         "query: {text}" ; candidate transform "{title}\n\n{abstract}"
  score                   cosine = dot (L2-normalized) ; full float precision
  nonfinite behavior      any nonfinite score -> hard fail (no silent substitution)
  tie                     candidate_id asc
  snapshot file           docs/p1b_snapshot/snapshot_tei_gte_large_en_v15.json
  snapshot file SHA-256   cdcf12626b1a402fb758f14c51896ab6... (full hash in artifact)
  classification          candidate-mining diagnostics only; NOT a P1E.3 ranking evaluation
```

Sequence (frozen): candidate package sealed → mining scores generated and
sealed → NO candidate changes permitted → adjudication view generated
WITHOUT diagnostic labels or scores → cal/dev grading performed → grades
joined to frozen diagnostic scores for validation.

## 7. Canonical serialization (exact rules)

```text
Unicode normalization     NFC
encoding                  UTF-8
newline normalization     CRLF/CR -> LF
trailing newline          exactly one
leading/trailing spaces   stripped
internal whitespace       preserved
JSON keys                 lexicographically sorted (map-like records only)
JSON separators           compact (",", ":")
numbers                   finite floats only; negative zero -> 0.000000000
quantization              0.000000001 ; rounding ROUND_HALF_EVEN
notation                  plain decimal; exponent notation prohibited
locale dependence         prohibited
NaN/Infinity              forbidden
list ordering             DECLARED canonical case order (preserved, NOT sorted)
                          DECLARED candidate order within case (preserved, NOT sorted)
hash                      SHA-256
```

One shared canonicalizer module is imported by every producer and verifier;
parallel canonicalizers are prohibited.

## 8. Blind custody (one method, fully concrete)

```text
method                   randomly-generated sealed reconciliation map under separate custody
opaque IDs               secrets.token_hex(16) -> 32-char lowercase hex (128 bits entropy)
generator                Python secrets module (CSPRNG); version pinned at seal time
collision handling       regenerate on collision, verified against issued set
blind package            data/evaluation/p1e1_blind_heldout_package.json (committed; opaque IDs + content only)
reconciliation map       NOT committed to adjudicator-visible repo
external location class  out-of-repository secure store (path in custody receipt only)
custodian role           P1E.2 Reconciliation Custodian
custody receipt          data/evaluation/p1e1_reconciliation_map_custody_receipt.json
P1E.2 retrieval          custodian presents receipt; map loaded for reconciliation only; never to adjudicator
adjudicator access       prohibited
regeneration             blind package + map immutable once sealed; regen requires a new version + new receipt
cal/dev adjudication view also omits mining scores, constructed-confuser labels, mining rationales
```

### 8.1 Custody receipt fields (binds package to map)

```text
receipt_schema                    p1e1_reconciliation_custody_receipt_v1
blind_package_sha256              <sealed at construction>
reconciliation_map_sha256         <sealed at construction>
mapping_entry_count              <number of opaque-id mappings>
opaque_id_algorithm               secrets.token_hex(16), 128-bit
generator_implementation_version  <Python secrets, pinned at seal>
custodian_role                    P1E.2 Reconciliation Custodian
created_at                        RFC 3339 UTC
authorized_retrieval_procedure    P1E.2 custodian-presented reconciliation only
```

## 9. Artifact inventory (frozen)

```text
data/evaluation/p1e1_candidate_package.json
data/evaluation/p1e1_candidate_provenance.json
data/evaluation/p1e1_candidate_mining_scores.json     (load-bearing; sealed before adjudication; no grades)
data/evaluation/p1e1_prejudgment_diagnostics.json
data/evaluation/p1e1_caldev_adjudication.json
data/evaluation/p1e1_split_manifest.json
data/evaluation/p1e1_blind_heldout_package.json
data/evaluation/p1e1_reconciliation_map_custody_receipt.json   (hash + custodian only; map NOT in repo)
data/evaluation/p1e1_benchmark_extension.json
```

Commit 3 adjudication pins and verifies ALL of: `candidate_corpus_fingerprint`,
`candidate_package_sha256`, `candidate_provenance_sha256`,
`candidate_mining_scores_sha256`, `split_manifest_sha256` — before loading any
grade record. The adjudication loader fails on any query/candidate/order/
add-remove/lineage/provenance/split change.

## 10. Construction discipline (frozen)

```text
frozen P1B v2 cases changed                        0
frozen P1B v2 judgments changed                    0
P1E.0 artifacts regenerated                        0
existing held-out labels inspected                 0
new held-out labels exposed during development     0
ranking-policy tuning on new held-out data         0
candidate-layer fields bearing grades/relevance    0   (recursive exclusion)
post-hoc candidate changes after a target miss     0
```

Candidate generation and judgment are separated. Models/lexical systems may
mine candidates but may not determine final relevance grades. Every grade
carries a rubric-anchored rationale (`research_utility_0_to_3_v1`).

## 11. Identity semantics

```text
candidate_corpus_fingerprint   ordered case IDs + ordered candidate IDs + normalized
                                query/candidate content hashes + lineage + candidate order + version
split_manifest_sha256          canonical case->split mapping
candidate_provenance_sha256    mining provenance + constructed-confuser declarations
candidate_mining_scores_sha256 frozen diagnostic scores (no grades)
caldev_adjudication_sha256     candidate IDs + grades + rationales + adjudicator metadata (cal/dev only)
blind_heldout_package_sha256   exact distributed blind bytes
provisional_benchmark_identity deterministic digest over the preceding component identities
final_adjudicated_v3_fingerprint = pending_p1e2
```

P1E.2 may add the independently reconciled held-out-adjudication identity to
produce `final_adjudicated_v3_fingerprint`; it must not replace or mutate the
P1E.1 provisional identity.

## 12. Closeout mode

```text
ERLAB_REQUIRE_P1E1_ARTIFACTS=1  -> hard-fail with a list of missing artifacts:
  protocol, candidate package, split manifest, candidate provenance,
  candidate mining scores, prejudgment diagnostics, cal/dev adjudication,
  blind held-out package, reconciliation-map custody receipt, extension identity.
Also fails when any required structural or cal/dev target is unmet.
```

P1E.1 does not depend on embedding snapshots.

## 13. Completion gate

```text
P1B historical corpus unchanged                  proven
v3 candidate corpus identity sealed (provisional) proven
candidate package frozen before grading (enforced) proven
candidate provenance complete                    proven
structural targets met                           proven
cal+dev grade-dependent targets met (or miss recorded, no post-hoc fix) proven
near-duplicate + lexical-confuser adjudicated targets met  proven
cal/dev labels available                         yes
held-out package blinded (opaque IDs, separate map) yes
held-out labels inspected                        0
projected_mde reported (not achieved)            yes
tests green (closeout 0 skips)                   yes
working tree                                     clean
```
