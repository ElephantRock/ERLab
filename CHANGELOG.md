# Changelog

All notable changes to the Elephant Rock Research Platform are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — AIV Batch Execution
- **BATCH-26**: Autonomous cycle dashboard — POST /autonomous/stop (HB-01: requires cycle_id confirmation), GET /autonomous/history with cycle statuses, CycleProgress and ConsciousnessStateBadge components, full dashboard page with start form, stop confirmation dialog, history list, consciousness state display, sidebar Cpu icon nav item
- **BATCH-25**: Knowledge graph explorer — 4 API endpoints (stats, entities, entity detail, subgraph traversal), SVG-based graph canvas with colored nodes and edges, entity detail panel with truth values and relationships, type filter and search, sidebar BrainCircuit icon nav item (HB-01: client-side SVG, HB-02: 100 entity limit)
- **BATCH-24**: PDF upload via drag-and-drop — POST /knowledge/ingest endpoint with PDF magic-bytes validation (HB-01), enriched GET /knowledge/stats with total_documents/total_chunks, frontend upload zone component with drag-and-drop, stats banner on knowledge page
- **BATCH-23**: Literature search page — multi-source academic search (Semantic Scholar, arXiv, OpenAlex), paper cards with title/authors/abstract/year, ingest into knowledge base with confirmation (HB-01)
- **BATCH-22**: Session grouping for pipeline runs — backend `session_id` filter on GET /runs, GET /runs/sessions endpoint, frontend Sessions page with grouped run cards, optional session_id input in pipeline form
- **BATCH-20**: Governance Queue — pending approvals page with approve/deny actions, optional amendment on denial, real-time list refresh
- **BATCH-19**: Memory Browser — search, filter by type, delete with confirmation, memory statistics
- **BATCH-18**: Cost Dashboard — full page with cost summary, breakdown tables, budget utilization bar
- **BATCH-16**: Navigation infrastructure — sidebar items and placeholder routes for Phase 2 pages
- **BATCH-14**: Ideas browser — sortable, filterable, searchable; gap↔idea bidirectional traceability with `source_gap_ids` column
- **BATCH-13**: Pipeline form completion — all backend options exposed; settings enhanced with connectivity check, version display, default domain
- **BATCH-12**: Pipeline results flow — inline results after completion, run detail page at `/runs/:id`, clickable dashboard RunCards, `GET /runs/{id}/ideas` endpoint

## [0.1.0] - 2026-05-01

### Added — AIV Batch Execution
- **BATCH-07**: `erock setup` interactive CLI wizard — provider selection, API key validation, `.env` generation, optional test pipeline run (#19db311)

### Added — Work Packages (WP-01 through WP-16)
- **WP-16**: Session lifecycle with policy condition evaluator
- **WP-15**: Multi-agent negotiation with structured debate protocol
- **WP-14**: Dynamic tool discovery with embedding-based search and hybrid RRF
- **WP-13**: Graph-augmented retrieval with three-source RRF fusion
- **WP-12**: Memory consolidation — LLM dual-pass decisions, embedding dedup, periodic scheduler
- **WP-11**: Streaming enhancement — typed events, stream manager with dedup, stage callbacks
- **WP-10**: Behavioral adaptation — feedback collector, plateau-aware strategy, post-run manager
- **WP-09**: Context management — model-aware window tracking, fraction triggers, filesystem offload
- **WP-08**: MCP integration — multi-transport client, YAML server registry, tool adapter
- **WP-07**: Metacognitive strategy — progress ledger, plateau detection, strategy adaptation
- **WP-06**: Cost-optimized routing — strategy-based provider selection with budgets
- **WP-05**: Semantic caching — exact-match and embedding-based similarity cache
- **WP-04**: Observability pipeline — multi-processor tracing, metrics, OTLP export
- **WP-03**: Sandboxing — pluggable execution isolation backends
- **WP-02**: Evaluation framework — unified scoring, GEval, quality gates
- **WP-01**: Provider resilience — circuit breakers, retry, encrypted secrets

### Added — Initial Platform
- 9-stage AI/NLP research idea generation pipeline
- Multi-agent architecture (Ideator/Critic/Refiner)
- Knowledge graph with truth values
- 5 LLM provider implementations (OpenAI, Anthropic, Gemini, Ollama, Mock)
- FastAPI backend with 38 API endpoints
- React/TypeScript frontend with 7 pages
- CLI with 12 commands
- 1,303 backend tests, 56 frontend tests
