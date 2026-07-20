# P1 Ranking Surface Audit

## Summary

Three independent ranking surfaces control research-quality outcomes:

### 1. TrimmerStage (dominant quality lever)
- **File**: `backend/pipeline/dag/trimmer.py:38-132`
- **Problem**: Ranks entire corpus using 12-line keyword-overlap heuristic, truncates to `[:20]`
- **Configured reranker**: NEVER WIRED (`_orchestrator.py:682` — no `reranker=` kwarg)
- **Impact**: Every downstream stage (gap analysis, ideation, synthesis) only sees 20 papers in keyword-overlap order

### 2. SearchService (source-priority deduplication)
- **File**: `backend/pipeline/literature/search_service.py`
- **Problem**: Deduplicates by source priority (S2 > PubMed > OpenAlex > CrossRef > arXiv), not relevance
- **RelevanceFilter**: INACTIVE in production (no embedding provider passed at `service_registry.py:50`)
- **PubMed/CrossRef**: Emit constant `relevance_score=1.0` — no ranking signal

### 3. TwoStageRetriever (proper hybrid, but scores transient)
- **File**: `backend/pipeline/knowledge/retriever.py:42-234`
- **Flow**: Parallel BM25 + semantic → RRF fusion → optional reranker → `[:n_results]`
- **Problem**: Scores never persisted. `RetrievalResult.score` discarded after each call.

## Discovery ranking surface
- SearchService → dedup → TrimmerStage → corpus admission
- Primary ranking defect: keyword-overlap heuristic + `[:20]`

## Retrieval ranking surface
- TwoStageRetriever → BM25 + semantic → RRF → reranker → top_k
- Primary ranking defect: scores transient, no durable evidence

## Score columns persisted
- `run_papers.relevance_score` — nullable, not populated by production path
- `paper_discoveries.source_rank` — source-native rank only
- `vector_retrieval_results.rank` — governed vector retrieval rank (P0.3.6)

## Ranking settings (P0.5 field IDs)
- `retrieval_mode` (hybrid), `reranker_enabled` (True), `reranker_type` (cross_encoder)
- `rrf_k` (60), `novelty_top_k` (20)
- NOT configurable: trim_top_k (hardcoded 20 in pipeline.yaml), limit_per_source (hardcoded 20)

## Frozen P1 scope

Primary: TrimmerStage replacement (discovery ranking)
Secondary: TwoStageRetriever durable evidence (retrieval ranking)
