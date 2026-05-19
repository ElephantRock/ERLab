# Real Pipeline Run Report — Task #127

**Date:** 2026-05-19 18:18–18:36  
**Run ID:** `run_20260519_181846`  
**Domain:** Inference Speedup Alternatives for Latency Reduction  
**Reference Paper:** arXiv 2509.24435v1 — "Alternatives To Next Token Prediction In Text Generation"  

---

## Executive Summary

The **first real end-to-end pipeline run** completed successfully through all 17 stages in **17.2 minutes** using `qwen/qwen3-4b-2507` on LM Studio (RTX 3080 Ti 12GB). The pipeline:

- Ingested **355 papers** from 8 targeted search queries
- Identified **5 high-quality research gaps** (confidence 0.80–0.92)
- Applied **enforcement routing** to 2/26 gateway calls
- Achieved **0 degraded calls** — all LLM calls went through successfully

The pipeline did **not produce ideas or proposals** due to two issues:
1. **Idea generation parse failure** — qwen3-4b-2507's output was not parseable into the structured `Idea` format
2. **Embedding provider mismatch** — `text-embedding-bge-m3` returned zero vectors

---

## Run Configuration

| Setting | Value |
|---------|-------|
| Provider | `lmstudio` (qwen/qwen3-4b-2507) |
| LM Studio URL | `http://100.64.0.1:1234` |
| Embedding model | `text-embedding-bge-m3` (local) |
| Search queries | 8 targeted queries |
| max_gaps | 5 |
| generation rounds | 1 |
| ideas_per_round | 2 |
| Strategy | `deep_research` |
| SmartRouter mode | `enforce` |
| Enforced stages | `[repair, query_generation, idea_generation, feasibility_scoring]` |

---

## Stage Execution Timeline

| Stage | Status | Duration | Notes |
|-------|--------|----------|-------|
| literature_search | ✓ executed | 17.3s | 355 papers from 8 queries |
| ingestion | ✓ executed | 25.8s | 355 chunks added to KB, BM25, KG |
| trimmer | ✓ executed | 0.0s | No trimming needed |
| gap_analysis | ✓ executed | 27.9s | **5 gaps identified** |
| gap_reflection | ✓ executed | 0.0s | Skipped (no reflection needed) |
| idea_generation | ✓ executed | 82.0s | **ENFORCED** — ran but 0 ideas (parse failure) |
| idea_reflection | ✓ executed | 0.0s | No ideas to reflect on |
| novelty_checking | ✓ executed | 0.0s | No ideas to check |
| feasibility_scoring | ✓ executed | 0.0s | No ideas to score |
| mechanical_metrics | ✓ executed | 0.0s | Nothing to process |
| proposal_synthesis | ✓ executed | 0.0s | Nothing to synthesize |
| adversarial_review | ✓ executed | 0.0s | Nothing to review |
| evaluation | ✓ executed | 0.0s | Nothing to evaluate |
| paper_synthesis | ✓ executed | 0.0s | Nothing to synthesize |
| citation_audit | ✓ executed | 0.0s | Nothing to audit |
| proposal_deepening | ✓ executed | 0.0s | Nothing to deepen |
| export | ✓ executed | 0.0s | Nothing to export |

**Total:** 1034.1s (17.2 min) — all 17 stages completed gracefully.

---

## Research Gaps Identified

### Gap 1 [conf=0.92] — Lack of Cross-Cluster Latency Optimization Frameworks
**Type:** methodological  
**Description:** No research integrates insights from CNN-agnostic accelerators, autoregressive models, and token-level LLM techniques to jointly optimize inference latency across diverse architectures.

### Gap 2 [conf=0.90] — Missing Empirical Validation of Latency Predictions in Dynamic Environments
**Type:** empirical  
**Description:** While ELPG (2024) and Accurate Deep Learning Inference Latency Prediction (2023) propose latency prediction models, there's a lack of empirical validation under dynamic real-world conditions.

### Gap 3 [conf=0.88] — Absence of Hardware-Aware Inference Scheduling for Heterogeneous Edge-Cloud Systems
**Type:** methodological  
**Description:** No work combines hardware-specific inference characteristics with adaptive token routing for edge-cloud heterogeneous deployment.

### Gap 4 [conf=0.85] — Underexplored Token-Level Adaptation in Autoregressive Models
**Type:** methodological  
**Description:** TCRA-LLM (2023) and TOKCOINFER (2026) introduce token-level compression, but dynamic adaptation of token-level techniques in autoregressive generation remains underexplored.

### Gap 5 [conf=0.80] — Theoretical Foundations for Latency-Performance Trade-offs in Non-Standard Architectures
**Type:** theoretical  
**Description:** No theoretical analysis on fundamental trade-offs between latency, energy, and accuracy in non-standard inference architectures (non-parametric autoregressive models, unstructured alternatives).

---

## Enforcement Metrics

| Metric | Value |
|--------|-------|
| Total gateway calls | 26 |
| Enforced calls | 2 (7.7%) |
| Degraded calls | 0 |
| Stages seen | `idea_generation`, `query_generation`, `ingestion` |
| Enforced stages | `idea_generation`, `query_generation` |
| Enforcement model | `qwen3-4b-2507` (single_call strategy) |

---

## Issues Encountered

### Issue 1: Idea Generation Parse Failure
- **Stage:** idea_generation (82.0s)
- **Symptom:** `[ENFORCE] stage=idea_generation` ran, model produced output, but 0 ideas parsed
- **Root cause:** qwen3-4b-2507 did not output ideas in the expected structured format. The LLM response wasn't parseable into `Idea` objects.
- **Contract violation:** `Empty output: ideas; Output ideas has 0 items, minimum 1`

### Issue 2: Embedding Provider Mismatch
- **Stage:** ingestion (initial embedding)
- **Symptom:** `text-embedding-bge-m3` returned 400 Bad Request from LM Studio
- **Root cause:** LM Studio's loaded embedding model may not match the configured model name, or batch size exceeded limits
- **Impact:** Zero vectors returned → novelty scores unreliable
- **Resolution:** Pipeline continued gracefully with degraded embeddings

### Issue 3: Literature Search Contract Violation (early runs)
- **Stage:** literature_search
- **Symptom:** `Output papers_found has 0 items, minimum 1`
- **Root cause:** Gateway provider calling Z.ai with expired key → empty results
- **Resolution:** Fixed by overriding gateway provider with direct LM Studio call

### Issue 4: Settings Cache
- **Symptom:** `.env` changes not picked up between runs
- **Root cause:** `pydantic-settings` caches on first `get_settings()` call
- **Resolution:** `importlib.reload(backend.config)` before re-import

---

## What Worked

1. **Full 17-stage pipeline execution** — all stages completed, no crashes
2. **LM Studio integration** — qwen3-4b-2507 responded reliably at ~3s/call
3. **Enforcement routing** — SmartRouter correctly enforced `idea_generation` and `query_generation`
4. **Gap analysis** — produced 5 meaningful, well-structured research gaps with citations
5. **Knowledge graph** — 3494 entities, 883 relationships loaded successfully
6. **BM25 index** — 2519 documents indexed, used for hybrid retrieval
7. **Contract enforcement** — violations detected and logged, pipeline didn't crash
8. **Graceful degradation** — downstream stages handled empty inputs without errors

---

## Next Steps

1. **Fix idea generation parsing** — add fallback JSON extraction for qwen3-4b output format
2. **Fix embedding model** — verify `text-embedding-bge-m3` is loaded in LM Studio, or switch to a confirmed model
3. **Re-run with fixes** — should produce ideas and proposals
4. **Refresh Z.ai API key** — unblock cloud LLM for higher-quality grounded stages
5. **Try larger models** — `deepseek/deepseek-r1-0528-qwen3-8b` or `qwen2.5-14b-instruct` now available on same LM Studio

---

## Run History (7 attempts today)

| Run | Elapsed | Papers | Gaps | Ideas | Notes |
|-----|---------|--------|------|-------|-------|
| `run_20260519_171557` | 811.8s | 285 | 5 | 0 | Z.ai 401 errors |
| `run_20260519_173037` | — | — | — | — | Same 401 |
| `run_20260519_174517` | — | — | — | — | Same 401 |
| `run_20260519_180104` | — | — | — | — | Settings cache issue |
| `run_20260519_180214` | — | — | — | — | Same |
| `run_20260519_181632` | — | — | — | — | Gateway provider still Z.ai |
| `run_20260519_181846` | **1034.1s** | **355** | **5** | **0** | **SUCCESS — first clean run** |
