# Changelog

All notable changes to the Elephant Rock Research Platform are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — AIV Batch Execution
- **BATCH-38**: Gap data persistence & truth values — ResearchGapDB model gains truth_frequency (Float, default=0.5), truth_confidence (Float, default=0.5), truth_evidence_count (Integer, default=0), related_clusters (Text, nullable JSON array); PipelineRun gains cluster_report_json (Text, nullable); Alembic migration 002_gap_enrichment.py with batch mode; persist_gaps() writes truth columns and related_clusters; new persist_cluster_report() method; load_gaps() reconstructs ResearchGap with TruthValue and related_clusters for full roundtrip fidelity (HB-03); normalized _session() to get_session() across load_gaps/load_ideas/get_run_by_uuid; 8 tests (3 TASK-01 + 5 TASK-02)
- **BATCH-35**: MkDocs documentation site with GitHub Pages auto-deployment — mkdocs.yml (Material theme, navigation, search, dark/light mode), docs/index.md (landing page with feature list and quick start), docs/getting-started.md (installation, configuration, first run walkthrough), docs/api-reference.md (complete REST API reference copied from api-guide.md), docs/architecture.md (system overview, 9-stage pipeline, technology stack, data flow, database schema), docs/endpoints/ directory with 15 markdown files (ideas, gaps, pipeline, costs, memory, governance, traces, sessions, literature, knowledge, auth, collaboration, exports, plugins, knowledge-graph) each with request/response examples and parameter tables, .github/workflows/docs.yml (GitHub Pages deployment on docs/ push to main/master, MkDocs Material build, deploy-pages@v4), 8 tests (3+2+3)
- **BATCH-33**: PDF export, bulk export, plugin marketplace — backend/api/routes/exports.py (WeasyPrint HTML-to-PDF for single ideas, ZIP archive for bulk markdown/PDF export), backend/plugins/registry.py (thread-safe plugin registry with 4 built-in plugins), backend/api/routes/plugins.py (list + install), frontend/src/components/export/export-dialog.tsx (format select + download trigger), frontend/src/components/ui/dialog.tsx (reusable context-based Dialog), frontend/src/pages/plugins.tsx (search, install form, plugin cards), frontend/src/api/exports.ts (API functions for export + plugins), idea-detail.tsx ExportDialog integration, ideas-browser.tsx checkbox selection + bulk export, sidebar + router updates, 10 tests (4 backend + 4 frontend + 2 integration)
- **BATCH-34**: Comment threads, sharing, CLI enhancement — Comment + SharedIdea DB models (threaded replies via parent_id, unique share tokens), POST/GET /ideas/{id}/comments (add/list), POST /ideas/{id}/share (generate link), GET /shared/{token} (public read-only), comment-thread.tsx (threaded comment display + inline reply), share-dialog.tsx (generate + copy link), idea-detail.tsx 2-column layout with collaboration widgets, erock research open/proposal/export CLI commands (browser open, LLM proposal generation, markdown/JSON export), 12 tests (4 backend + 4 frontend + 4 CLI)
- **BATCH-32**: Dashboard lazy loading, gaps pagination, DB indexes, webhook notifications — React.lazy + Suspense for chart components (HB-01: renders under 3s with 1000+ ideas), server-side pagination for gaps explorer (offset + limit), 8 DB indexes on frequently queried columns (ideas.pipeline_run_id/domain/overall_score, pipeline_runs.status/session_id, research_gaps.pipeline_run_id/confidence), backend/notifications/ webhook module with HMAC-SHA256 signatures, webhook fired on pipeline completion/failure (non-blocking), 8 tests
- **BATCH-30**: PostgreSQL support + Docker Compose — database.py dual PostgreSQL/SQLite engine (HB-01: SQLite default), connection pooling (QueuePool with pre-ping) for PostgreSQL, multi-stage Dockerfile (builder + runtime, non-root user), docker-compose.yml (app + postgres + redis with health checks), .dockerignore, 8 tests
- **BATCH-29**: Alembic migration system — alembic.ini and env.py with SQLite batch mode (HB-01), initial auto-generated migration for all 6 model tables, `erock db upgrade/downgrade/history/current` CLI commands, `db-migrate` Makefile target, 8 tests
- **BATCH-28**: JWT authentication system — User model with hashed passwords (bcrypt), JWT token generation/validation (python-jose), login/register/me/users API endpoints, auth_enabled config flag (default: False for dev compatibility), login page with register mode, AuthContext with token persistence, ProtectedRoute wrapper, role badge component (admin/user), admin-only user management section in settings
- **BATCH-27**: Self-improvement evolution section in settings (READ-ONLY per HB-01), scheduler start/stop controls on autonomous page, GET /status/evolution endpoint, evolution status display
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
