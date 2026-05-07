# Run #76 — Hybrid Model Routing Results

**Date:** 2026-05-07  
**Config:** Local LM Studio (qwen3-4b) for thinking tasks, Cloud glm-5.1 for generation

---

## Model Routing Table

| Stage | Model | Location | Latency |
|:------|:------|:---------|:--------|
| Gap analysis | qwen/qwen3-4b-2507 | Local LM Studio | ~140ms/call |
| Feasibility scoring | qwen/qwen3-4b-2507 | Local LM Studio | ~140ms/call |
| Novelty checking | qwen/qwen3-4b-2507 | Local LM Studio | ~140ms/call |
| Faithfulness check | qwen/qwen3-4b-2507 | Local LM Studio | ~140ms/call |
| Idea generation | glm-5.1 (z.ai) | Cloud | ~5-15s/call |
| Proposal synthesis | glm-5.1 (z.ai) | Cloud | ~30-60s/call |
| Proposal deepening | glm-5.1 (z.ai) | Cloud | ~10-20s/call |
| Embeddings | nomic-embed-text (Ollama) | Local | ~100ms/batch |

---

## Run #76 Results

| Metric | Run #74 (Cloud only) | Run #76 (Hybrid) |
|:-------|:---------------------|:-----------------|
| **Duration** | 35.4 min | 35.7 min |
| **Gaps detected** | 7 | 7 |
| **Ideas** | 2 | 0 (JSON parse error) |
| **Quality score** | 0.80 | 0.35 |
| **Gap recall** | 50% | 12.5% |

---

## What Worked

1. **Gap analysis on local model** — qwen3-4b detected 7 gaps successfully via structured_output
2. **Routing works end-to-end** — thinking tasks hit LM Studio, generation tasks hit z.ai
3. **~140ms per thinking call** — vs ~5s on cloud = 35× faster for classification tasks
4. **No API cost** for gap analysis, feasibility, novelty checking

## What Needs Fixing

1. **Gap quality is lower** — local model detected gaps but with lower recall (12.5% vs 50%).
   The 4B model misses subtler research gaps that glm-5.1 catches.
   
2. **Idea generation JSON parse failure** — the cloud model's JSON output was 21K chars
   and had a syntax error at char 21710. This is a cloud model issue, not hybrid routing.
   The `_repair_json` couldn't recover.

3. **Ollama embeddings offline** — need to restart Ollama or switch embeddings to LM Studio.

## LM Studio Model Library Available

| Model | Size | Use Case | Status |
|:------|:-----|:---------|:-------|
| `qwen/qwen3-4b-2507` | 4B | Thinking tasks | ✅ Working, 140ms warm |
| `google/gemma-4-e4b` | 4B | Thinking (reasoning) | ✅ Working, 9s warm |
| `nvidia/nemotron-3-nano-4b` | 4B | Classification | ✅ Working, 40s cold |
| `qwen/qwen3.5-9b` | 9B | Better thinking | ❌ Failed to load |
| `qwen/qwen3-30b-a3b-2507` | 30B MoE | Best quality | ❌ Too slow (>120s) |
| `text-embedding-nomic-embed-text-v1.5` | — | Embeddings | ✅ 768-dim working |

## Next Steps

1. Switch embeddings from Ollama to LM Studio (`text-embedding-nomic-embed-text-v1.5`)
2. Consider using `google/gemma-4-e4b` for gap analysis (has reasoning capability)
3. Fix the JSON truncation issue for long structured outputs
4. Measure cloud API call reduction (expected ~40-50%)
