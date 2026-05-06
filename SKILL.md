---
name: Elephant Rock Research Platform
version: 0.87.0-prealpha
description: |
  AI-powered research platform that automates literature discovery,
  identifies knowledge gaps, generates novel research ideas, scores
  novelty and feasibility, and synthesizes complete research proposals.
capabilities:
  - literature_search:
      sources: [arxiv, openalex, semantic_scholar, pubmed, crossref]
      multi_source: true
      deduplication: doi_and_title
      relevance_filter: embedding_cosine_similarity
  - gap_analysis:
      method: llm_cluster_analysis
      clustering: kmeans_with_auto_k
      min_gaps: 1
  - idea_generation:
      method: tree_search
      max_depth: 3
      branching: 4
      reflection: true
      max_iterations: 3
  - novelty_checking:
      method: embedding_similarity
      threshold: 0.85
  - feasibility_scoring:
      dimensions: [data_availability, method_complexity, computational_cost]
      scale: 0_to_1
  - proposal_synthesis:
      strategies: [fast_scan, deep_research, academic_proposal, literature_review]
      fast_scan_sections: 3
      deep_research_sections: 10+
  - evaluation:
      dimensions: [novelty, feasibility, completeness, rigor, clarity]
      scale: 0_to_1
  - knowledge_library:
      storage: sqlite
      dedup: sha256_title_hash
      types: [paper, gap, idea]
  - journal:
      formats: [notes_md, readme_md]
      scrub_sensitive: true
  - reflection:
      max_iterations: 3
      fail_open: true
  - soul:
      file: SOUL.md
      inject: system_prompt
constraints:
  - No API keys required for core functionality (graceful degradation)
  - All LLM calls respect provider rate limits
  - Embedding dimensions depend on provider (768 for Ollama nomic-embed-text)
  - Proposal length varies by strategy (fast: ~3K, deep: ~35K chars)
  - Pipeline requires at least 1 literature source to generate gaps
  - Knowledge library is per-domain SQLite — no cross-domain sharing
  - Journal entries scrub API keys and sensitive patterns
  - Reflection loop is fail-open — timeout returns original results
  - Relevance filter guarantees minimum 5 papers when available
integrations:
  llm_providers: [ollama, openai, anthropic, z.ai]
  embedding_providers: [ollama, openai]
  search_sources: [arxiv, openalex, semantic_scholar, pubmed, crossref]
  export_formats: [markdown, json, bibtex]
---

# Elephant Rock Research Platform

## Quick Start
```bash
# Start backend
cd backend && uvicorn backend.api.app:app --reload

# Start frontend
cd frontend && npm run dev
```

## Pipeline Stages (in order)
1. `literature_search` — Search across multiple academic sources
2. `ingestion` — Download and parse full-text papers
3. `gap_analysis` — Identify knowledge gaps via LLM cluster analysis
4. `idea_generation` — Generate novel ideas via tree search
5. `novelty_checking` — Score ideas against existing literature
6. `feasibility_scoring` — Evaluate practical implementability
7. `mechanical_metrics` — Compute objective quality metrics
8. `proposal_synthesis` — Generate complete research proposals
9. `export` — Output in multiple formats

## API Endpoints
- `POST /api/pipeline/runs` — Start a pipeline run
- `GET /api/pipeline/runs` — List all runs
- `GET /api/pipeline/runs/{id}` — Get run details
- `POST /api/search` — Search literature directly
- `GET /api/ideas` — List generated ideas
- `GET /api/gaps` — List identified gaps
