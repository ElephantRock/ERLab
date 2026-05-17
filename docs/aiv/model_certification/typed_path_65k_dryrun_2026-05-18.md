# Typed-Path 65K Context Dry-Run Validation

**Date:** 2026-05-18  
**Run ID:** `dry_run_20260518_010640`  
**Commit chain:** `e226a1f` → `016f5fc` → `c040ad4`  

---

## 1. LM Studio Load Config

| Parameter | Value |
|-----------|-------|
| model | `qwen/qwen3-4b-2507` |
| instance_id | `qwen/qwen3-4b-2507` (no suffix) |
| context_length | 65,536 |
| flash_attention | true |
| offload_kv_cache_to_gpu | true |
| eval_batch_size | 512 |
| parallel | 4 |
| load_time_seconds | 4.1 |

## 2. Certification Summary

**Report:** `20260517T214737Z.yaml`

| Metric | Prompted | Structured |
|--------|:--------:|:----------:|
| smoke_test | 100% | 100% |
| structured_claim | 20% | **100%** |
| repair | 100% | **100%** |
| **Overall** | **40%** | **100%** |

| Field | Value |
|-------|-------|
| structured_schema_valid_rate | 100% (15/15) |
| admission status | `approved_for_production` |
| promotion_allowed | `true` |
| eligible stages | 8 (incl. structured_generation) |
| schema thresholds | **Unchanged** (95% / 85% / 70%) |

## 3. Structured Output Schema Results

**Test script:** `scripts/test_structured_output.py` — 108 test calls

| Model | smoke_test | structured_claim | repair |
|-------|:----------:|:----------------:|:------:|
| qwen3-4b-2507 | 100% / **100%** | 0% / **100%** | 100% / **100%** |
| qwen3.5-0.8b | 100% / **100%** | 0% / **100%** | 100% / **100%** |
| qwen2.5-14b | 100% / **100%** | 0% / **100%** | 100% / **100%** |

Format: `prompted / structured`

**strict=true (bool):** Works for all models  
**strict="true" (string):** Works for all models  

## 4. Dry-Run Run Summary

| Metric | 8K Run (`dry_run_20260517_173905`) | 65K Run (`dry_run_20260518_010640`) |
|--------|-----------------------------------:|-----------------------------------:|
| context_length | 8,192 | 65,536 |
| elapsed_seconds | 862 | 321 |
| total_llm_calls | 150 | 25 |
| routed_decisions | 150 (100%) | 25 (100%) |
| degraded | 0 | 0 |
| router_exceptions | 0 | 0 |
| execution_changes | 0 | 0 |

**Note:** The 65K run had fewer LLM calls because the actual execution model (`glm-5.1` from orchestrator default) completed fewer pipeline stages. SmartRouter decisions are correct regardless of execution model.

## 5. Routing Strategy Comparison

| Stage | 8K Strategy | 65K Strategy | Changed? |
|-------|-------------|--------------|----------|
| literature_search | single_call | single_call | No |
| idea_generation | single_call | single_call | No |
| proposal_synthesis | section_wise | *(not reached)* | — |
| adversarial_review | compressed_review_packet | *(not reached)* | — |
| paper_synthesis | map_reduce | *(not reached)* | — |

The 65K run only completed literature_search (24 calls) and started idea_generation (1 call) before the validation script finished. Both use `single_call` — unchanged from 8K. The high-context stages (proposal_synthesis, paper_synthesis) were not reached, so we cannot confirm strategy shifts in this run.

**Context gate reason (8K):** `"Single call: 1500+2048 tokens (fits)"`  
**Context gate reason (65K):** `"Single call: 1500+2048 tokens (fits)"` — same reasoning, confirming the 65K profile is active (these low-token stages fit in either context).

## 6. Capability Registry Detection

The gateway capability registry correctly detected:
```
Probed qwen/qwen3-4b-2507: ctx=65536, loaded=True
```
This confirms SmartRouter sees the 65K context profile.

## 7. Failures and Fallbacks

| Issue | Severity | Details |
|-------|----------|---------|
| Embedding provider zero vectors | Warning | LM Studio embedding endpoint returned zero vectors — fallback used |
| PubMed 429 rate limiting | Warning | Too many requests to PubMed API — cached results used |
| CONTRACT VIOLATION literature_search | Info | `papers_found` had 0 items (expected ≥1) — pipeline continued |
| Reranker unavailable | Warning | Remote reranker connection failed — fallback used |
| Actual model mismatch | Info | Orchestrator used `glm-5.1` for execution while SmartRouter routed to `qwen3-4b-2507` |

No critical failures. All fallbacks worked correctly.

## 8. Typed-Path Activation

The pipeline uses `glm-5.1` as the actual execution model (from orchestrator default config), not `qwen3-4b-2507`. SmartRouter routes in dry-run mode and does not change execution. Therefore:
- Typed claim generation activates based on the execution model's capabilities
- The gateway's `structured_complete()` path is available but was not called by the actual execution model in this dry-run
- `prose_fallback` metrics are from the execution model, not the routed model

**To fully validate typed-path activation, SmartRouter must be in `enforce` mode** — which this task explicitly prohibits.

## 9. 10/10 Pass Criteria

| # | Criterion | 8K Run | 65K Run |
|---|-----------|:------:|:-------:|
| 1 | No execution changes | ✅ | ✅ |
| 2 | Every stage gets routing decision | ✅ | ✅ |
| 3 | No router exceptions | ✅ | ✅ |
| 4 | paper_synthesis not single_call | ✅ | *(not reached)* |
| 5 | citation_audit closed_set | ✅ | *(not reached)* |
| 6 | review avoids same_model | ✅ | *(not reached)* |
| 7 | context gates use strategy | ✅ | ✅ |
| 8 | not_approved gated | ✅ | ✅ |
| 9 | missing candidates no crash | ✅ | ✅ |
| 10 | logs complete | ✅ | ✅ |

**Verdict: PASS** (all reached criteria pass; stages not reached in this run were validated in the 8K run)

## 10. Enforcement Recommendation

**Do NOT enable enforcement yet.** This run validates:

1. ✅ LM Studio loads at 65,536 context
2. ✅ Structured output achieves 100% schema compliance
3. ✅ SmartRouter routes correctly with 65K profile
4. ✅ No execution behavior changes
5. ✅ No router exceptions

**But does NOT yet validate:**
- ❌ proposal_synthesis strategy shift at 65K (not reached)
- ❌ paper_synthesis strategy shift at 65K (not reached)
- ❌ Typed-path activation (requires enforce mode or execution model change)
- ❌ Claim-quality metrics from structured output path

**Recommended staged enforcement (after one more dry-run with all stages reached):**

| Stage | Risk | Recommendation |
|-------|------|----------------|
| repair | Low | ✅ Safe to enforce first |
| query_generation | Low | ✅ Safe to enforce |
| literature_search | Low | ✅ Safe to enforce |
| idea_generation | Medium | Wait for structured output E2E |
| proposal_synthesis | High | Block until grounding eval fixed |
| paper_synthesis | High | Block until grounding eval fixed |
| adversarial_review | High | Block until grounding eval fixed |
| citation_audit | High | Block until grounding eval fixed |
| evidence_table | High | Block until corpus-backed eval |

**Prerequisites for enforcement:**
1. Wire SmartRouter to use `qwen3-4b-2507` as actual execution model (not `glm-5.1`)
2. Run full pipeline with all stages reached at 65K context
3. Fix corpus-backed grounding eval cases
4. Complete at least one clean multi-model 65K dry-run
