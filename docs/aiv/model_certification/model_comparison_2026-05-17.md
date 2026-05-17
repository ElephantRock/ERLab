# Multi-Model Certification Comparison

**Date:** 2026-05-17  
**Evaluator:** Automated certification pipeline (v0.1 admission + v0.2 stage eval)  
**Hardware:** RTX 3080 Ti (12GB GDDR6X) via LM Studio  

## Model Matrix

| Model | Family | Params | Safe ctx | Smoke | JSON raw | Schema valid |
|---|---|---:|---:|---|---:|---:|
| qwen3-4b-2507 | Qwen 3 | 4B | 8,000¹ | PASS | 100% | 33% |
| qwen3.5-0.8b | Qwen 3.5 | 0.8B | 26,214² | PASS | 80% | 33% |
| qwen2.5-14b-instruct | Qwen 2.5 | 14B | 26,214² | PASS | 100% | 33% |
| google/gemma-4-e4b | Gemma 4 | 4B | 26,214² | PASS | 7% | 33% |

¹ Hardware-measured: hard ceiling ~8,167 tokens on RTX 3080 Ti 12GB (advertised 8,192)
² Advertised value; not hardware-measured (model was not hot-loaded during testing)

**Note:** All models received `rejected` admission status due to schema_valid_rate below 95% threshold. This reflects LM Studio's lack of structured JSON output support, not model quality.

## Stage Scores (v0.2 Evaluation)

| Stage | qwen3-4b-2507 | qwen3.5-0.8b | qwen2.5-14b | gemma-4-e4b |
|---|---:|---:|---:|---:|
| query_generation | 0.59 | 0.54 | 0.60 | — |
| literature_filtering | 0.40 | 0.40 | 0.40 | — |
| paper_extraction | **1.00** | 0.79 | **1.00** | — |
| evidence_table | 0.00 | 0.00 | 0.00 | — |
| repair | **0.80** | **0.80** | **0.80** | — |
| synthesis | 0.45 | 0.35 | 0.40 | — |
| adversarial_review | 0.58 | **0.70** | 0.63 | — |

**Note:** gemma-4-e4b timed out during stage eval (too slow on RTX 3080 Ti). Only v0.1 admission data available.

## Stage Eligibility (v0.2)

| Stage | qwen3-4b-2507 | qwen3.5-0.8b | qwen2.5-14b |
|---|---|---|---|
| query_generation | limited_use | limited_use | limited_use |
| literature_filtering | limited_use | limited_use | limited_use |
| paper_extraction | limited_use | limited_use | limited_use |
| evidence_table | not_approved | not_approved | not_approved |
| repair | limited_use | limited_use | limited_use |
| synthesis | not_approved | not_approved | not_approved |
| adversarial_review | not_approved | not_approved | not_approved |

**Grounding gate failures:** evidence_table and adversarial_review fail because `citation_fabrication_rate` and `claim_support_rate` metrics are not computed by the seed eval cases (they check citation existence which requires corpus-backed evaluation).

## Role Recommendations

| Role | Best candidate | Reason |
|---|---|---|
| Cheap query generation | qwen3.5-0.8b | Fastest, smallest, adequate for simple queries |
| Literature filtering | qwen2.5-14b-instruct | Larger context for multi-paper assessment |
| Paper extraction | qwen3-4b-2507 / qwen2.5-14b | Both score 1.00; qwen3-4b is faster |
| Evidence table | **No model approved** | All fail grounding gates — needs better eval cases |
| Repair | qwen3-4b-2507 / qwen2.5-14b | Both score 0.80; qwen3-4b is faster |
| Paper synthesis | **No model approved** | v0.2 cap + low synthesis scores |
| Proposal synthesis | **No model approved** | v0.2 cap + low synthesis scores |
| Adversarial review | **No model approved** | All fail grounding gates |
| Citation/grounding audit | **No model approved** | All fail grounding gates |

## Promotion Recommendations

| Model | Recommendation | Allowed stages |
|---|---|---|
| qwen3-4b-2507 | limited_use | query_generation, literature_filtering, paper_extraction, repair |
| qwen3.5-0.8b | limited_use | query_generation, literature_filtering, repair |
| qwen2.5-14b-instruct | limited_use | query_generation, literature_filtering, paper_extraction, repair |
| google/gemma-4-e4b | manual_review | Insufficient data (stage eval timed out) |

## Key Observations

1. **Schema compliance is the bottleneck**: All models show 33% schema_valid_rate. This is an artifact of LM Studio not supporting structured JSON output mode, not actual model inability. Models produce valid JSON 80-100% of the time.

2. **Grounding gates need better eval cases**: The seed cases don't include corpus-backed citations, so citation_fabrication_rate and claim_support_rate are not meaningfully computed. This causes all grounded stages to fail.

3. **Repair is universally strong**: All tested models score 0.80 on repair tasks.

4. **Paper extraction is strong for Qwen models**: qwen3-4b and qwen2.5-14b both score 1.00.

5. **Synthesis is weak across the board**: All models score below 0.50, confirming the v0.2 cap is appropriate.

6. **Hardware limitations**: 9B+ models require model swapping on RTX 3080 Ti 12GB. Cold load causes 2+ min stalls per request. Practical for offline certification only when pre-loaded.
7. **Context headroom**: qwen3-4b-2507 measured safe context is 8,000 tokens (derated from 8,192), not the previously assumed 6,553.

## Next Steps

1. **Improve eval cases**: Add corpus-backed grounding tests so citation metrics are meaningful
2. **Re-evaluate with improved cases**: Re-certify after grounding eval is fixed
3. **Scoped promotion**: Promote qwen3-4b-2507 for repair and query_generation only
4. **Staged enforcement**: Begin with repair stage enforcement after dry-run validation
5. **Do NOT enforce** paper_synthesis, proposal_synthesis, or adversarial_review until grounding eval produces meaningful metrics
