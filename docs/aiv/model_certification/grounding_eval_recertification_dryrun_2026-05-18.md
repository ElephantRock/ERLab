# Grounding Eval Recertification & SmartRouter Dry-Run Report

**Date:** 2026-05-18
**Run IDs:** certification `qwen/qwen3-4b-2507-20260518-063406`, dry-run `dry_run_20260518_093614`

## 1. Summary

Replaced weak/non-corpus seed grounding eval cases with corpus-backed cases that distinguish citation existence from claim support. Created 10 new corpus-backed eval cases across 4 stages. Updated GroundingScorer with dual-path (corpus-backed + heuristic) computation. Ran v0.2 certification and SmartRouter dry-run.

## 2. Corpus-Backed Case Audit Table

| Case ID | Stage | Has corpus | Has source IDs | Has claim support labels | Has negative controls | Status |
|---------|-------|:---:|:---:|:---:|:---:|--------|
| evidence_table-001 | evidence_table | ❌ | ❌ | ❌ | ❌ | Legacy (heuristic) |
| evidence_table-002 | evidence_table | ✅ | ✅ P1-P3 | ✅ 5 labels | ✅ fabricated, wrong_cite, unsupported | **NEW** |
| evidence_table-003 | evidence_table | ✅ | ✅ P1-P3 | ✅ 6 labels | ✅ contradicted, fabricated, wrong_cite | **NEW** |
| evidence_table-004 | evidence_table | ✅ | ✅ P1-P3 | ✅ 6 labels | ✅ contradicted (×2), unsupported (×2) | **NEW** |
| adversarial_review-001 | adversarial_review | ❌ | ❌ | ❌ | ✅ planted errors | Legacy (heuristic) |
| adversarial_review-002 | adversarial_review | ✅ | ✅ P1-P2 | ✅ 6 defects | ✅ overclaim, wrong_cite, unsupported | **NEW** |
| adversarial_review-003 | adversarial_review | ✅ | ✅ P1-P3 | ✅ 6 defects | ✅ overclaim, wrong_cite, missing_control | **NEW** |
| adversarial_review-004 | adversarial_review | ✅ | ✅ P1-P2 | ✅ 6 defects | ✅ contradiction, overclaim, unsupported | **NEW** |
| paper_synthesis-001 | paper_synthesis | ✅ | ✅ S1-S3 | ✅ | ✅ fabricated forbidden | **NEW** |
| paper_synthesis-002 | paper_synthesis | ✅ | ✅ S1-S3 | ✅ | ✅ overclaim check, fabricated | **NEW** |
| proposal_synthesis-001 | proposal_synthesis | ✅ | ✅ S1-S3 | ✅ | ✅ hypothesis check, overclaim, fabricated | **NEW** |
| proposal_synthesis-002 | proposal_synthesis | ✅ | ✅ S1-S3 | ✅ | ✅ overclaim, hypothesis, fabricated | **NEW** |

## 3. GroundingScorer Test Results

**25/25 tests passing** in `test_grounding_scorer.py`.

Key invariants validated:
- ✅ citation_precision and claim_support_rate are independent
- ✅ Fabricated citations (PX, P99) detected → citation_fabrication_rate > 0
- ✅ Wrong citations lower claim_support_rate even when citation_precision is high
- ✅ Contradicted claims detected → contradiction_handling_score affected
- ✅ Unsupported claims raise unsupported_claim_rate
- ✅ All rates in [0, 1] range
- ✅ Support + unsupported ≤ 1.0

## 4. v0.2 Certification Results (qwen3-4b-2507)

| Stage | Eligibility | Score | Grounding Gate | Key Grounding Metrics |
|-------|------------|-------|----------------|----------------------|
| adversarial_review | **not_approved** | 0.602 | FAILED | fab=0.522, unsup=0.862, support=0.013 |
| evidence_table | **not_approved** | 0.00 | FAILED | fab=0.268, unsup=0.341, support=0.350 |
| literature_filtering | limited_use | 0.40 | N/A | — |
| paper_extraction | limited_use | 1.00 | N/A | — |
| paper_synthesis | **limited_use** (cap) | 0.00 | N/A | — |
| proposal_synthesis | **not_approved** | 0.00 | FAILED | — |
| query_generation | limited_use | 0.59 | N/A | — |
| repair | limited_use | 0.80 | N/A | — |

**Structured schema valid rate: 100%** (prompted: 33%, structured: 100%)
**Overall status: approved_for_production** (for non-grounded stages)

### Hard Gate Failures

1. **adversarial_review**: `citation_fabrication_rate=0.522 > 0.00` → fabricates citations in adversarial contexts
2. **adversarial_review**: `unsupported_claim_rate=0.862 > 0.20` → fails to identify unsupported claims
3. **evidence_table**: `citation_fabrication_rate=0.268 > 0.00` → generates non-corpus citations
4. **evidence_table**: `unsupported_claim_rate=0.341 > 0.20` → too many unsupported claims
5. **proposal_synthesis**: Grounding hard gate failed

## 5. Stage Eligibility v0.2 Comparison

| Stage | Before (v0.1) | After (v0.2) | Change |
|-------|--------------|--------------|--------|
| adversarial_review | not_approved | **not_approved** | Confirmed by grounding metrics |
| evidence_table | not_approved | **not_approved** | Confirmed by grounding metrics |
| paper_synthesis | not_approved | **limited_use** (cap) | v0.2 cap applies |
| proposal_synthesis | not_approved | **not_approved** | Confirmed by grounding metrics |
| repair | approved | **limited_use** | Downgraded by threshold misses |
| query_generation | approved | **limited_use** | Downgraded by threshold misses |

Key change: **Grounding metrics are now meaningful.** Previously, grounding gates were blocked because eval cases lacked corpus-backed citations. Now the scorer produces real citation_fabrication_rate, claim_support_rate, and unsupported_claim_rate.

## 6. SmartRouter Dry-Run Results

**Run:** `dry_run_20260518_093614`
**Elapsed:** 913.9 seconds
**Pass criteria:** 10/10 PASS

| Criterion | Result |
|-----------|--------|
| no_execution_changes | ✅ True |
| every_stage_gets_decision | ✅ True |
| no_router_exceptions | ✅ True |
| paper_synthesis_not_single_call | ✅ True |
| citation_audit_closed_set | ✅ True |
| review_avoids_same_model | ✅ True |
| context_gates_use_strategy | ✅ True |
| not_approved_gated | ✅ True |
| missing_candidates_no_crash | ✅ True |
| logs_complete | ✅ True |

### Routing Decisions by Stage

| Stage | Calls | Strategy |
|-------|-------|----------|
| adversarial_review | 52 | compressed_review_packet |
| proposal_synthesis | 37 | single_call |
| ingestion | 24 | — |
| feasibility_scoring | 20 | — |
| paper_synthesis | 16 | section_wise |
| proposal_deepening | 2 | — |
| idea_generation | 1 | — |

### Structured Output Results
- Paper synthesis: 14/14 sections **structured OK** (100%)
- Prose fallbacks: 0
- Strategy shifts: proposal_synthesis → single_call, paper_synthesis → section_wise

## 7. Hard-Gate Rejections and Reasons

All hard-gate rejections are from grounding metrics:

1. **evidence_table** — Citation fabrication detected (0.268). Model generates citations not in corpus.
2. **evidence_table** — Unsupported claim rate too high (0.341 > 0.20). Model doesn't distinguish supported from unsupported claims.
3. **adversarial_review** — Citation fabrication detected (0.522). More than half citations in adversarial context are fabricated.
4. **adversarial_review** — Unsupported claim rate too high (0.862 > 0.20). Model fails to identify unsupported claims.

## 8. Enforcement Recommendation

### Safe to enforce (low-risk stages):
- ✅ **repair** — limited_use, 0.80 score, no grounding requirements
- ✅ **query_generation** — limited_use, 0.59 score, no grounding requirements
- ✅ **literature_search** helper calls — no grounding requirements

### NOT safe to enforce (grounding gate failures):
- ❌ **evidence_table** — citation_fabrication_rate=0.268
- ❌ **citation_audit** — depends on evidence_table grounding
- ❌ **adversarial_review** — citation_fabrication_rate=0.522, unsupported_claim_rate=0.862
- ❌ **paper_synthesis** — v0.2 cap at limited_use
- ❌ **proposal_synthesis** — v0.2 cap at limited_use

### Pre-conditions for evidence_table/citation_audit enforcement:
1. citation_fabrication_rate == 0.00 (currently 0.268)
2. claim_support_rate passes threshold (currently 0.35)
3. unsupported_claim_rate ≤ 0.20 (currently 0.341)
4. Second certified model available for cross-model review

## 9. Next Steps

1. **Try larger model** (qwen2.5-14b-instruct or qwen3.5-27b) for grounded stages — may achieve lower fabrication rate
2. **Add structured output to grounding eval** — force `response_format json_schema` for eval cases to reduce fabrication
3. **Multi-model 65K dry-run** with at least 2 certified models
4. **Enable enforcement** for repair, query_generation, literature_search
5. **Refresh Anthropic API key** for cloud/local hybrid routing
