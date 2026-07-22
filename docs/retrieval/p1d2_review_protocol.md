# P1D.2d — Independent Review Protocol

> **Status: DRAFT for reviewer onboarding. NOT sealed.**
> Author: P1D.2d-prep (2026-07-23). Two blinded reviewer packages are generated; actual review requires independent people or independently governed reviewers.

## Purpose

The 30-case diagnostic set has 81 provisional single-pass judgments by one author. Before any of these judgments can be used in policy evaluation (P1D.6), each judgment controlling a hard-gated metric must receive two independent reviews. This protocol defines how reviewers are blinded, what they see, what they must not see, and how disagreements are adjudicated.

## What reviewers see

Each reviewer package contains, per case:

```
case_id
task_family (and its definition)
query_or_claim
case_mode (positive_present | no_positive_expected)
candidate_pool (all units the system may return)
  → each unit shown as: neutral_id, passage_text, source_provenance (document/section/locator/hash)
claim_dimensions (for evidence_retrieval and contradiction_retrieval)
judgment rubric (the frozen P1B research_utility_0_to_3_v1 rubric)
risk definitions (what each risk means)
```

## What reviewers must NOT see

```
author's provisional relevance grades
author's rationales
other reviewer's decisions
candidate retrieval outputs (no policy names, scores, or rankings)
answer-revealing internal document labels (e.g. "doc_metformin_rct_positive")
```

Document and passage IDs are replaced with **neutral randomized identifiers** in the reviewer-facing packages. The mapping from neutral IDs to real IDs is held in the assignment manifest, not in the reviewer packages.

## Judgment rubric

The frozen P1B rubric (`research_utility_0_to_3_v1`):

| Grade | Anchor |
|---|---|
| **3** | Highly useful: directly on-topic, strong evidence, right type |
| **2** | Useful: relevant but with caveats (broader scope, adjacent method, secondary source, partial match) |
| **1** | Marginally relevant: touches the topic but not useful as primary evidence |
| **0** | Irrelevant: wrong meaning, wrong domain, or unrelated topic. Includes lexical traps and acronym collisions |

Sub-dimensions (0–3 each):
- **topical_relevance**: does the candidate address the same research question/intent?
- **evidence_utility**: would a researcher find this useful as evidence?
- **methodological_fit**: does the method/study type match what the query asks for?

For risk-bearing judgments (false_support, missed_contradiction, agenda_mismatch), reviewers must also make qualitative determinations:
- Does the passage **truly support** the claim? (not merely topically overlap)
- Does it **genuinely contradict or qualify**? (not merely discuss an adjacent finding)
- Does it address the **same research agenda**? (PICO alignment)
- Are two sources **distinct evidence lineages**?

## Blinding rules

```
reviewer A cannot see reviewer B's decisions before submission
reviewer B cannot see reviewer A's decisions before submission
neither reviewer sees the author's provisional grades or rationales
neither reviewer sees retrieval-policy outputs
case author cannot serve as either reviewer
policy developers cannot adjudicate
```

Reviewers submit independently. Only the adjudicator (if needed) sees both rationales.

## Assignment

All judgments controlling hard-gated metrics require two independent reviews:

```
false_support         → all such judgments
missed_contradiction  → all such judgments
agenda_mismatch       → all such judgments
missed_relevant_evidence → all such judgments
redundancy / lineage  → all such judgments
```

This covers every judgment in the 30-case diagnostic set (all 81, since every case exercises at least one hard-gated risk).

The assignment manifest records:
```
reviewer assignment per judgment
blinding attestations
submission hashes (when submitted)
review completion status
agreement status
adjudication requirements
```

## Adjudication

When reviewers disagree (different grade, or same grade but different qualitative determination):
1. The adjudicator reviews both rationales
2. The adjudicator records a final decision + rationale
3. The judgment's `review_status` becomes `adjudicated`

Adjudicators must not be policy developers and must not have authored any of the cases under review.

## State transitions

```
single_pass_provisional (author)
  → reviewer A submits + reviewer B submits
  → agreement_status = agreed
    → review_status = dual_reviewed, eligible_for_scoring = true
  OR agreement_status = disagreed_*
    → adjudicator resolves
    → review_status = adjudicated, eligible_for_scoring = true
```

Until both reviews are submitted and any disagreement is adjudicated, the judgment remains `eligible_for_scoring: false`.

## What this protocol does NOT authorize

- Running any retrieval policy against the judgments
- Using the judgments as activation evidence
- Changing the case design, query, or passage content
- Adding or removing cases from the pool
