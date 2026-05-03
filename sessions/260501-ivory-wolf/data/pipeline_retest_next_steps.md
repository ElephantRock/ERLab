# Pipeline Retest Next Steps

## Status: **SUCCESS** (with 3 bugs fixed along the way)

The pipeline completed a full 8-stage run (literature search → export) in ~14 minutes using the z.ai Anthropic-compatible LLM endpoint.

## Remaining Issues

### 1. Semantic Scholar Rate Limiting (429)
- Semantic Scholar API returns 429 on most requests
- Only Arxiv reliably returns papers
- **Impact:** Limited literature coverage
- **Fix needed:** Add retry with backoff for Semantic Scholar, or configure an API key (EROCK_SEMANTIC_SCHOLAR_API_KEY)

### 2. OpenAlex Configuration Error
- OpenAlex source fails with `'NoneType' object has no attribute 'get'`
- Likely needs EROCK_OPENALEX_EMAIL configured
- **Impact:** Only 1 of 3 search sources working

### 3. Dummy Embedding Provider
- Currently using zero-vector embeddings ( DummyEmbeddingProvider)
- Semantic search via ChromaDB is non-functional
- **Impact:** Novelty checking and retrieval are degraded (but don't crash)
- **Fix needed:** Either configure a real embedding provider (OpenAI API key, Ollama, or z.ai embedding endpoint) or make the pipeline work without semantic search

### 4. DB `stages_completed` and `current_stage` Not Updated
- DB run record shows `current_stage: "initializing"` and `stages_completed: []` even when fully completed
- The checkpoint file correctly tracks stage progress
- **Root cause:** The orchestrator only updates DB status (running/completed/failed) but doesn't update `current_stage` or `stages_completed` during execution
- **Impact:** API responses show stale stage info; UI may not reflect progress correctly

### 5. Long Proposal Synthesis Duration
- proposal_synthesis stage took 8+ minutes (majority of total pipeline time)
- This is likely due to multiple LLM calls per idea + z.ai latency
- **Impact:** User wait time is high
- **Fix:** Consider parallel proposal generation, streaming responses, or caching

### 6. Environment Variable Override Confusion
- System env vars (EROCK_*) override .env file values
- This caused confusion when .env changes didn't take effect
- **Recommendation:** Document the precedence or use .env exclusively

## Recommendations

### Immediate (BATCH-57)
1. Fix the `stages_completed` DB update in the orchestrator so the API returns accurate progress
2. Add `EROCK_OPENALEX_EMAIL` to .env to enable OpenAlex search
3. Make the cost/model router aware of available providers (don't try to create OpenAI provider when key is absent)

### Short-term (BATCH-58)
1. Add retry with backoff for Semantic Scholar API (429 handling)
2. Investigate z.ai embedding support or set up Ollama for local embeddings
3. Parallelize proposal synthesis across ideas

### Medium-term
1. Add pipeline timeout configuration per stage
2. Implement proper stage progress callbacks that update the DB in real-time
3. Add WebSocket notifications for stage transitions (already partially implemented)
