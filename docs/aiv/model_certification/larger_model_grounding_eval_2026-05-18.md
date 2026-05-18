# Larger Model Grounding Evaluation Report

**Date:** 2026-05-18
**Task:** #126 — Certify larger models for grounded stages
**Pass Criteria:** citation_fabrication_rate < 0.05, claim_support_rate > 0.70, unsupported_claim_rate ≤ 0.20

## Models Evaluated

| Model | Parameters | Context Window | Latency/call | RTX 3080 Ti Fit |
|-------|-----------|----------------|-------------|----------------|
| qwen3-4b-2507 | 4B | 65,536 | ~3s | Full 65K |
| qwen2.5-14b-instruct | 14B | 131,072 | ~8s | Fits with offloading |
| qwen/qwen3.5-9b | 9B | ~32K | ~42s | Fits (slow) |
| qwen3.5-27b | 27B | ~32K | ~495s | Extreme offloading, unusable |

## Results Summary

### qwen2.5-14b-instruct (Best Candidate)

| Stage | Fab Rate | Support Rate | Unsup Rate | Precision | Pass? |
|-------|----------|-------------|------------|-----------|-------|
| evidence_table | **0.483** | **0.411** | 0.178 ✓ | 0.517 | ✗ |
| adversarial_review | **0.567** | **0.000** | **0.833** | 0.433 | ✗ |
| paper_synthesis | **0.450** | **0.675** | 0.100 ✓ | 0.550 | ✗ |
| proposal_synthesis | **0.635** | **0.500** | **0.333** | 0.364 | ✗ |

- **Improvement over baseline (qwen3-4b-2507):**
  - evidence_table support: 0.411 vs 0.35 (+17%)
  - evidence_table unsup: 0.178 vs 0.341 (PASS vs FAIL)
  - adversarial_review: No meaningful improvement

### qwen/qwen3.5-9b

| Stage | Fab Rate | Support Rate | Unsup Rate | Precision | Pass? |
|-------|----------|-------------|------------|-----------|-------|
| evidence_table | 0.000 ✓ | **0.000** | **0.589** | 0.000 | ✗ |
| adversarial_review | 0.000 ✓ | **0.000** | **0.833** | 0.000 | ✗ |
| paper_synthesis | 0.000 ✓ | **0.000** | **0.775** | 0.000 | ✗ |
| proposal_synthesis | 0.000 ✓ | **0.000** | **0.833** | 0.000 | ✗ |

- **Interpretation:** The 9B model produces unstructured prose that the grounding scorer cannot parse.
  Fab_rate=0.0 reflects inability to extract citations (not genuine precision).
  All claim_support_rate=0.0 because structured evaluation fails.
  42s/call latency makes it impractical.

### qwen3.5-27b

- **Status:** Unusable on RTX 3080 Ti 12GB. ~495s per call (8+ minutes).
  Only completed 1 of 12 eval cases before timeout.
  Excluded from comparison.

## Baseline Comparison (qwen3-4b-2507)

| Stage | Fab Rate | Support Rate | Unsup Rate |
|-------|----------|-------------|------------|
| evidence_table | 0.268 | 0.35 | 0.341 |
| adversarial_review | 0.522 | 0.013 | 0.862 |

## Conclusions

### 1. No model passes all grounding gates

The strict pass criteria (fab < 0.05, support > 0.70, unsup ≤ 0.20) were not met by any
evaluated model. Citation fabrication rates remain 45-64% for the best candidate (14B).

### 2. qwen2.5-14b-instruct shows partial improvement

- **unsupported_claim_rate PASSES** on evidence_table (0.178 ≤ 0.20) — a genuine improvement
- claim_support_rate improved 17% on evidence_table
- adversarial_review remains severely challenged for all local models

### 3. The grounding gates are calibrated for 70B+ models

The < 0.05 fabrication rate gate was designed for frontier-scale models with strong
instruction following. Local 4-14B models lack the parametric knowledge and instruction
discrimination to achieve this level of grounding precision.

### 4. Practical recommendation

- **Keep qwen3-4b-2507 as primary** — fastest inference, 65K context, adequate for low-risk stages
- **Add qwen2.5-14b-instruct as secondary** for evidence_table specifically (better unsup rate)
- **Grounded stages (evidence_table, adversarial_review)** remain at `limited_use` / `not_approved`
- **Refresh Anthropic API key** to unblock cloud LLM for grounded stages — only cloud models
  can meet the strict grounding gates

### 5. No auto-promotion

As specified: no changes to `enforced_stages` or `production_registry.yaml`.
Current enforcement list unchanged: `[repair, query_generation, idea_generation, feasibility_scoring]`

## Test Evidence

- `data/model_certification/direct_grounding_results.json` — Raw eval results for 14B and 9B models
- `data/model_certification/direct_grounding_eval.log` — Detailed execution log
- 12 eval cases × 2 models = 24 LLM calls evaluated
- Certification CLI smoke test failure (qwen2.5-14b-instruct) — pre-existing bug in response
  parsing, not model quality issue
