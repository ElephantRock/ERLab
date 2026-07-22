# P1D.2.0 — Annotation Protocol

> **Status: DRAFT (revision P1D.2a, post-review) for user review. NOT frozen. No gate closed.**
> Author: P1D.2a wave (2026-07-22). Schemas: `p1d2_case_schema.json` (v1), `p1d2_judgment_schema.json` (v1). Validator: `scripts/validate_p1d2_schemas.py` (25 assertions).
> Source contract: P1D.2 execution contract (pasted 2026-07-22), reviewed and amended.
>
> **Revision P1D.2a changes from the initial draft:** (1) two evidentiary layers replace the single "sealed" set — `sealed_product_proxy` (48 synthetic, may seal) and `real_project_holdout` (real-project-derived, binding P1E activation requirement); (2) the generic `sealed` benchmark_role is replaced by three distinct roles; (3) sealed-set isolation requires an access-controlled external location, not a branch in the same repo; (4) "provisional seal pending external review" is not a valid state — a benchmark is sealed or unsealed; (5) dual review applies to every judgment controlling a hard-gated metric, not only three risks; (6) richer origin enum and leakage-control fields added; (7) durable committed validator with fixtures.

## Purpose

This protocol defines how every P1D.2 case is authored, evidenced, judged, and reviewed across three evidentiary roles. It exists because P1D.1 established that the historical 66-case benchmark cannot answer the full product-wide needs-led question — three of six task families are weakly/minimally covered and two operate at passage granularity the benchmark lacks. P1D.2 builds the instrument that can.

The protocol is **binding on all case authors and reviewers** from the moment P1D.2a is frozen. No case enters any set except through this protocol.

## Scope guardrails (inherited from the P1D.0 freeze)

- **No model is evaluated during case authoring.** P1D.2 completion gate: `models evaluated during case authoring = 0`.
- **No candidate architecture is selected.** P1D.2 produces an evaluation instrument, not a retrieval decision.
- **Production retrieval is unchanged.** `legacy_lexical_top20_v1` remains authoritative.

---

## 1. Three evidentiary roles (reviewer Decision 1)

P1D.2 produces cases in three distinct roles. The generic term "sealed" is retired — it conflated two genuinely different evidentiary layers.

| Role | Count | Origin | Visibility | What it can establish |
|---|---|---|---|---|
| **diagnostic** | 30 | `synthetic_realistic` accepted | **visible** to implementation lane during development | failure modes, schema testing, bounded candidate selection. **Never** independent activation evidence. |
| **sealed_product_proxy** | 48 (8 per family) | `synthetic_realistic` accepted | **hidden** content; manifest-only in repo | independent adversarial validation. A candidate passing here may be described as *"validated on historical + synthetic product-proxy benchmarks"* — **not** *"validated on real ERLab workflows."* |
| **real_project_holdout** | TBD (≥1 per family + every hard gate) | `real_project_deidentified` or `real_project_unredacted_controlled` only | **hidden**; separately sealed | **binding P1E activation requirement.** No production activation without it. |

### 1.1 Why the split matters

A wholly synthetic 48-case set is a strong adversarial proxy but cannot honestly establish that ERLab works on actual ERLab research workflows. The `real_project_holdout` is the layer that can. It does not need to be authored now, but it becomes a **binding P1E activation requirement**: until it exists and a candidate passes it, no candidate may be described as validated on real workflows.

### 1.2 Origin precision (reviewer guard)

The schema enforces a richer origin enum to avoid collapsing invented and real-derived cases into one category:

```
synthetic_realistic                    invented
synthetic_derived_from_real_structure  abstracted from a real workflow's structure, not its content
real_project_deidentified              real content, identifiers removed
real_project_unredacted_controlled     real content, access-controlled
```

Each case carries `case_origin`, `origin_provenance` (auditable), and either `synthetic_scenario_id` or `real_project_id`. A `real_project_holdout` role with a `synthetic_*` origin fails schema validation.

---

## 2. Case contracts

Every case conforms to `p1d2_case_schema.json`. The required fields (from the execution contract, augmented with reviewer guards):

### 2.1 Case-level (selection)

| Field | Notes |
|---|---|
| `case_id` | Globally unique across all three roles. Pattern-enforced prefix. |
| `benchmark_role` | `diagnostic` / `sealed_product_proxy` / `real_project_holdout`. |
| `task_family` | One of six frozen families. |
| `query_or_claim` | Verbatim; downstream code must not paraphrase. |
| `retrieved_unit` | `passage` required for evidence_retrieval and contradiction_retrieval. |
| `positive_passage_ids`, `contradicting_or_qualifying_passages`, `hard_topical_negatives`, `false_support_negatives`, `agenda_mismatch_negatives` | Evidence arrays per the contract. |
| `relevance_judgments` | Conform to `p1d2_judgment_schema.json`. |
| `risk_labels`, `hard_negative_types` | Drive the risk-coverage audit. |
| `case_origin`, `origin_provenance`, `deidentification_status`, `real_project_id`/`synthetic_scenario_id` | Reviewer origin guards. |
| `case_author_id`, `reviewer_a_id`, `reviewer_b_id`, `adjudicator_id` | Independence governance (pseudonymous). |
| `leakage_group_id`, `document_family_id`, `query_semantic_fingerprint`, `positive_unit_fingerprint` | Leakage control beyond exact string equality. |

### 2.2 Passage-level provenance (reviewer guard — expanded)

Every passage carries:

| Field | Why |
|---|---|
| `document_id`, `document_version` | Source identity. |
| `section_id` | Which section. |
| `passage_id`, `passage_locator` | Exact locator (start/end offsets). |
| `passage_text_hash`, `document_content_hash` | Drift detection at passage and document level. |
| `source_access_or_license_basis` | How ERLab may use the source. |
| `evidence_lineage_id` | **Required for multi-paper-synthesis diversity.** Distinct papers are not necessarily distinct lineages (same lab, dataset, trial family). |

**A case must not be labeled solely at paper level when the product task requires a passage.** The schema enforces this (P1D.1 coverage gap fix).

---

## 3. Hard negatives — the defining quality bar

Every diagnostic case must have **at least one difficult negative designed to expose a concrete product risk**, not generic topical irrelevance. The schema requires `hard_negative_types` (minItems 1) from a closed enum of risk-shaped types. A case whose only negative is "a paper on a different topic" fails review.

---

## 4. Diagnostic vs sealed — the separation rule (reviewer Decision 2)

| Set | Visibility | Permitted use |
|---|---|---|
| **diagnostic (30)** | visible | failure attribution, debugging, bounded configuration selection, architecture comparison |
| **sealed_product_proxy (48)** | hidden content / manifest-only in repo | independent activation evidence (within the "product-proxy, not real-workflow" caveat) |
| **real_project_holdout** | hidden; separately sealed | binding P1E activation requirement |

### 4.1 Isolation requires an access-controlled external location

A normal branch in the same repository is **not isolation** — anyone with repository access can inspect it. Approved controlled locations, in preference order:

1. Separate private evaluation repository with evaluator-only membership
2. Access-controlled object storage with versioning and evaluator-only access
3. Encrypted archive in durable storage, with the key withheld from the implementation lane

A local-only path is acceptable **during authoring** but is not an acceptable **final sealed location** (lacks durable availability and access governance).

### 4.2 Public manifest contents (reviewer-specified)

The public manifest (`p1e_sealed_manifest.json` / real-project equivalent) contains:

```
artifact hashes, schema versions, case and task counts, risk-coverage counts,
source-corpus fingerprint, seal date, storage locator or opaque artifact ID,
access-policy identifier, seal custodian
```

It must **not** expose: queries, claims, positive/negative passage identities, judgments, or document titles when titles leak the answer.

### 4.3 Verification command

A verification command receives access to the controlled package and confirms its hashes against the public manifest **without copying its contents into the development repository**. (To be specified when the controlled location is established at P1D.2c.)

---

## 5. Independent review and adjudication (reviewer Decision 3)

### 5.1 No "provisional seal"

A benchmark is either **sealed** with its required review complete, or it remains an **unsealed authoring package**. The phrase "provisional seal pending external review" is not a valid state and must not be used. The schema enforces this: a `provisional` judgment has `eligible_for_seal: false` structurally, not merely by convention.

### 5.2 Review state machine

```
single_pass_provisional
  → review_status = provisional
  → requires_external_dual_review = true
  → eligible_for_scoring = false
  → eligible_for_seal = false
→ independent reviewer A
→ independent reviewer B
→ agreement or adjudication
→ eligible_for_seal = true
```

The schema makes these implications **structural, not documentary** — the validator's assertions [6] prove a provisional judgment cannot become scoreable or sealable.

### 5.3 Expanded dual-review scope

Dual review applies to **every judgment that controls a hard-gated metric**, not only the three originally named risks:

```
false_support                (globally non-compensable — strictest scrutiny)
missed_contradiction         (strictest scrutiny)
agenda_mismatch              (strictest scrutiny)
missed_relevant_evidence
redundancy / evidence-lineage diversity
```

The strictest scrutiny still applies to false support, contradiction, and agenda alignment.

### 5.4 Independence rules (schema-enforced where structural, documented otherwise)

```
case author cannot serve as both reviewers
reviewers cannot inspect retrieval-policy outputs
reviewers cannot inspect one another's decisions before submission
adjudicator must see both rationales
policy developers cannot adjudicate sealed cases
```

`reviewers_blinded_to_each_other` and `policy_outputs_visible_to_reviewers` are schema fields; the others are governance documented in `independence_exception` when relaxed.

---

## 6. Risk coverage audit (P1D.2.5)

The sealed_product_proxy set must exercise the frozen integrity framework from `p1d_task_risk_matrix.json`:

```
false-support traps, missed-contradiction opportunities, agenda mismatches,
low-overlap relevant evidence, exact-term requirements,
method/application distinctions, evidence-granularity distinctions,
source and lineage redundancy
```

P1D.2.5 produces a task-by-risk coverage matrix. **No critical product risk depends on a single case** — every hard-gated or globally-non-compensable cell has ≥2 cases.

---

## 7. Freeze inventory

```
docs/retrieval/p1d2_annotation_protocol.md       (this file)
docs/retrieval/p1d2_case_schema.json
docs/retrieval/p1d2_judgment_schema.json
scripts/validate_p1d2_schemas.py                 (durable validator, 25 assertions)

docs/retrieval/p1d2_diagnostic_cases.jsonl       (visible)
docs/retrieval/p1d2_diagnostic_judgments.jsonl   (visible)
docs/retrieval/p1d2_diagnostic_manifest.json

<controlled location>/p1e_product_proxy_cases.jsonl       (hidden content)
<controlled location>/p1e_product_proxy_judgments.jsonl   (hidden content)

docs/retrieval/p1e_sealed_manifest.json           (visible: counts + hashes + custodian)
docs/retrieval/p1d2_task_risk_coverage.json
docs/retrieval/p1d2_adjudication_report.json
docs/retrieval/p1d2_leakage_audit.json
docs/retrieval/p1d2_freeze_record.json
```

---

## 8. Execution limits (carried forward honestly)

Three limits from the initial P1D.2a, now with the reviewer's resolutions:

1. **Case content source** — `synthetic_realistic` accepted for diagnostic and sealed_product_proxy. The real_project_holdout is a **separate, binding P1E requirement** and is not authored in P1D.2. A synthetic set is never described as real-workflow-validated.
2. **Sealed-set isolation** — requires an access-controlled external location (§4.1), not a branch. P1D.2c is blocked until a controlled location and seal custodian are recorded.
3. **Dual-review independence** — provisional authoring is accepted for case construction, not as a sealed judgment state. P1D.2 cannot seal until dual review + adjudication complete (P1D.2d).

These limits block **P1D.2 final seal** (P1D.2c needs the controlled location; P1D.2d needs independent reviewers). They do not block P1D.2b (diagnostic authoring, provisional).
