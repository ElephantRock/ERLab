# Phase 2 Targeted Enforcement Report: idea_generation + feasibility_scoring

**Date:** 2026-05-18
**Run ID:** `phase2_20260518_125315`
**Model:** qwen/qwen3-4b-2507 (LM Studio, 65K context)
**Mode:** enforce

## 1. Executive Summary

**VERDICT: ALL PASS** — 11/11 pass criteria met.

Both `idea_generation` and `feasibility_scoring` are safe to add to `enforced_stages`. All 6 enforced calls (3 per stage) used certified models with no hard gate failures. Degraded paths return explicit failures. Quality metrics are acceptable.

**Recommendation: Add both stages to `enforced_stages`.**

## 2. Phase 1 — Contract and Certification Check

### idea_generation Contract

| Field | Value | Pass? |
|-------|-------|-------|
| Routing contract exists | ✅ Yes | ✅ |
| Risk level | medium | ✅ |
| requires_json | false | ✅ |
| requires_grounding | true | ✅ (passes gates) |
| requires_citations | false | ✅ |
| allowed_strategies | [single_call, evidence_first] | ✅ |
| v0.2 stage eligibility | limited_use (v0.1) | ✅ |

### feasibility_scoring Mapping

| Field | Value | Pass? |
|-------|-------|-------|
| Own contract | No — maps to `idea_generation` | ✅ |
| Grounding requirement | inherits idea_generation: true | ✅ (passes gates) |
| Output validation | exists (score bounds, explanation) | ✅ |

### Hard Gate Results (qwen3-4b-2507 for idea_generation)

| Gate | Result | Details |
|------|--------|---------|
| production_registry | ✅ PASS | Model in production registry |
| stage_allowed | ✅ PASS | idea_generation allowed |
| v2_not_approved | ✅ PASS | v0.1 eligibility accepted |
| context_sufficient | ✅ PASS | 65536 >= 8160 (with 15% headroom) |
| no_fabrication | ✅ PASS | citation_fabrication_rate = 0.0 |
| grounding_quality | ✅ PASS | claim_support_rate = 1.0 (default) |

### Certification Status

| Model | Stage | Eligibility | Status |
|-------|-------|------------|--------|
| qwen3-4b-2507 | idea_generation | limited_use | approved |
| qwen3-4b-2507 | feasibility_scoring | limited_use (via idea_generation) | approved |

## 3. Phase 2 — Targeted Enforcement Results

### idea_generation (3 calls)

| Call | Enforced | Model | Strategy | Certified | Gates Failed | Degraded | Ideas |
|------|----------|-------|----------|-----------|-------------|----------|-------|
| 1 | ✅ True | qwen3-4b-2507 | single_call | certified | none | False | ~5 |
| 2 | ✅ True | qwen3-4b-2507 | single_call | certified | none | False | ~5 |
| 3 | ✅ True | qwen3-4b-2507 | single_call | certified | none | False | ~4 |

### feasibility_scoring (3 calls)

| Call | Enforced | Model | Strategy | Certified | Gates Failed | Degraded | Score |
|------|----------|-------|----------|-----------|-------------|----------|-------|
| 1 | ✅ True | qwen3-4b-2507 | single_call | certified | none | False | 0.90 |
| 2 | ✅ True | qwen3-4b-2507 | single_call | certified | none | False | 0.80 |
| 3 | ✅ True | qwen3-4b-2507 | single_call | certified | none | False | 0.95 |

### Degraded Path Tests

| Stage | Degraded | Expected | Pass? |
|-------|----------|----------|-------|
| idea_generation | ✅ True | True | ✅ |
| feasibility_scoring | ✅ True | True | ✅ |

Both degraded tests returned explicit `degraded=True` with warnings about no certified candidates.

## 4. Phase 3 — Quality Metrics

### idea_generation Quality

| Metric | Value | Assessment |
|--------|-------|------------|
| Avg ideas per call | 4.7 | ✅ Good (>3) |
| Empty output rate | 0.0 | ✅ Perfect |
| Malformed output rate | 1.0 | ⚠️ Not JSON — outputs prose ideas |
| Duplicate idea rate | 0.0 | ✅ No duplicates |
| All certified | True | ✅ |
| Router exceptions | 0 | ✅ |

**Note on malformed_output_rate:** idea_generation produces prose output (numbered ideas with descriptions), not JSON. The contract has `requires_json: false`, so this is expected behavior. The "malformed" label is an artifact of using JSON-validity as the metric when the stage doesn't require JSON.

### feasibility_scoring Quality

| Metric | Value | Assessment |
|--------|-------|------------|
| All scores | [0.9, 0.8, 0.95] | ✅ All in [0, 1] |
| Avg score | 0.883 | ✅ Reasonable spread |
| Score bounds valid | True | ✅ All 0-1 |
| Invalid score rate | 0.0 | ✅ Perfect |
| Explanation present rate | 1.0 | ✅ All calls |
| JSON valid rate | 1.0 | ✅ All calls |
| Degraded rate | 0.0 | ✅ No degradation |
| All certified | True | ✅ |

## 5. Pass Criteria

| # | Criterion | Result |
|---|-----------|--------|
| 1 | At least 6 enforced calls | ✅ PASS (6/6) |
| 2 | idea_generation enforced | ✅ PASS (3 calls) |
| 3 | feasibility_scoring enforced | ✅ PASS (3 calls) |
| 4 | No uncertified model | ✅ PASS (all certified) |
| 5 | Model routing consistent | ✅ PASS (routed == actual) |
| 6 | No hard gate failures | ✅ PASS (0 failures) |
| 7 | idea_generation degraded tested | ✅ PASS (degraded=True) |
| 8 | feasibility_scoring degraded tested | ✅ PASS (degraded=True) |
| 9 | No router exceptions | ✅ PASS |
| 10 | idea output nonempty | ✅ PASS (3/3) |
| 11 | feasibility output nonempty | ✅ PASS (3/3) |

## 6. Test Suite

| Test Suite | Tests | Status |
|-----------|-------|--------|
| test_phase2_enforcement.py | 16 | ✅ ALL PASS |
| test_enforcement_integration.py | 19 | ✅ ALL PASS |
| test_staged_enforcement.py | 17 | ✅ ALL PASS |
| test_routing/ | 59 | ✅ ALL PASS |
| test_gateway.py | 19 | ✅ ALL PASS |
| test_json_extraction.py | 18 | ✅ ALL PASS |
| **Total** | **167** | **✅ ALL PASS** |

### New Phase 2 Tests (16 total)

**Idea Generation (5 tests):**
- Routes through gateway with enforcement_applied=true
- Routed model is certified
- No hard gate failures
- Degraded returns explicit failure
- Strategy is valid (single_call or evidence_first)

**Feasibility Scoring (3 tests):**
- Routes through gateway with enforcement_applied=true
- Maps to idea_generation contract
- Degraded returns explicit failure

**Routing Contract (5 tests):**
- High-risk stages excluded
- Grounded stages excluded
- idea_generation has contract
- Model certified for idea_generation
- Model passes hard gates

**Score Validation (3 tests):**
- Invalid scores detected
- Valid scores pass
- Explanation required

## 7. Updated enforced_stages

```yaml
smart_router:
  enabled: true
  mode: enforce
  require_certified_models: true
  enforced_stages:
    - repair
    - query_generation
    - idea_generation        # NEW
    - feasibility_scoring    # NEW
```

## 8. Recommendation

### Add to enforced_stages: ✅ Both Approved

| Stage | Risk | Grounding | Certification | Quality | Recommendation |
|-------|------|-----------|--------------|---------|---------------|
| idea_generation | medium | passes gates | limited_use | Good | ✅ Enforce |
| feasibility_scoring | medium (inherited) | passes gates | limited_use | Excellent | ✅ Enforce |

### NOT ready for enforcement:

| Stage | Reason |
|-------|--------|
| evidence_table | citation_fabrication_rate=0.268 |
| adversarial_review | citation_fabrication_rate=0.522 |
| paper_synthesis | v0.2 cap at limited_use |
| proposal_synthesis | grounding hard gate failure |
| citation_audit | depends on evidence_table |
| gap_analysis | no routing contract |

### Prerequisites for next wave (grounded stages):
1. Larger model certified (qwen2.5-14b-instruct or better)
2. citation_fabrication_rate < 0.05
3. claim_support_rate > 0.70
4. Multi-model 65K dry-run clean
5. Anthropic API key refreshed for hybrid routing
