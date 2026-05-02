# Elephant Rock Research Platform — Comprehensive Study Report v3

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**Methodology:** Full codebase read — every source file, test file, configuration, and document  
**Scope:** 277 backend source files + 202 backend tests + 99 frontend source files + 63 frontend tests + 4 migrations + 3 CI workflows + root config  

---

## 1. Platform Overview

**Elephant Rock** is a multi-agent AI research ideation platform that autonomously discovers research gaps in academic literature, generates novel research ideas, evaluates them through multi-agent debate, and synthesizes publication-ready proposals. It is the most comprehensive implementation of the AIV Framework v5.1, having completed 47 batches across two roadmaps.

### 1.1 Scale Metrics

| Metric | Count |
|:---|:---|
| Backend source files (`.py`) | 277 |
| Backend test files | 202 |
| Frontend source files (`.tsx`/`.ts`) | 99 |
| Frontend test files | 63 |
| Alembic migrations | 4 |
| API endpoints | 76 |
| Pipeline subsystems | 32 |
| Frontend pages | 20 |
| Frontend components | 51 |
| LLM providers | 5 (OpenAI, Anthropic, Gemini, Ollama, LiteLLM) |
| Configuration parameters | 227 |
| Database models | 8 |
| Total backend LOC (source) | 36,976 |
| Total backend LOC (tests) | 23,555 |
| Total frontend LOC (source) | 9,328 |
| Total frontend LOC (tests) | 7,657 |
| **Grand total LOC** | **77,516** |
| Tests passing | 1,790 (1,480 backend + 310 frontend) |
| Git commits | 153+ |
| AIV batch directories | 41 (BATCH-07 → BATCH-47) |
| AIV documents archived | 200+ |

---

## 2. Architecture

### 2.1 Technology Stack

| Layer | Technology |
|:---|:---|
| Backend framework | FastAPI 0.110+ with Pydantic v2 |
| Database | SQLAlchemy 2.0 ORM + Alembic migrations (SQLite dev / PostgreSQL prod) |
| Vector store | ChromaDB 0.5+ |
| LLM routing | LiteLLM 1.40+ with 5 providers |
| Embeddings | OpenAI text-embedding-3-small (1536d) with Ollama fallback |
| Frontend | React 18 + TypeScript + Vite + TailwindCSS + shadcn/ui |
| Charts | Recharts |
| Markdown rendering | react-markdown + remark-math + rehype-katex + rehype-highlight |
| Testing | pytest (backend) + Vitest + jsdom (frontend) |
| Linting | Ruff (backend) + ESLint (frontend) |
| Type checking | mypy (backend) |
| CI/CD | GitHub Actions (3 workflows: CI, Nightly E2E, Docs) |
| Docs | MkDocs Material |

### 2.2 Backend Architecture

```
backend/
├── api/                          # FastAPI application layer
│   ├── app.py                    # Main app, middleware, error handling, route registration
│   ├── auth.py                   # JWT auth (BATCH-28) + API key verification
│   ├── errors.py                 # Unified error format: {error: {code, message, hint}}
│   ├── schemas.py                # Pydantic request/response schemas
│   └── routes/                   # 16 route modules (76 endpoints)
│       ├── auth.py               # POST /register, /login, GET /me, /users
│       ├── collaboration.py      # Comments + shared idea links (BATCH-34)
│       ├── costs.py              # 5 cost tracking endpoints
│       ├── exports.py            # Markdown/LaTeX/PDF export (BATCH-33)
│       ├── gaps.py               # 10 gap management endpoints (BATCH-38→46)
│       ├── governance.py         # Policy approval workflow (Phase 5)
│       ├── ideas.py              # CRUD + feedback
│       ├── knowledge.py          # Upload + search
│       ├── knowledge_graph.py    # 5 KG endpoints
│       ├── literature.py         # Semantic Scholar, arXiv, OpenAlex
│       ├── memory.py             # Tiered memory CRUD
│       ├── pipeline.py           # 25 pipeline management endpoints
│       ├── plugins.py            # Plugin registry
│       ├── search.py             # Global search (BATCH-47)
│       ├── status.py             # 3 status/health endpoints
│       └── traces.py             # 3 observability endpoints
├── cli/                          # Typer CLI with rich output
│   └── commands/                 # db, dev, research, setup subcommands
├── config.py                     # 227 configuration parameters via pydantic-settings
├── db/                           # Database layer
│   ├── database.py               # Engine, session factory, init_db()
│   ├── models.py                 # 8 SQLAlchemy models (User, Paper, Idea, Proposal, PipelineRun, Comment, SharedIdea, ResearchGapDB)
│   └── crud.py                   # 25+ CRUD functions with search, filter, pagination
├── logging_config.py             # structlog configuration
├── notifications/                # Webhook notifications (BATCH-32)
├── pipeline/                     # 32 subsystems (see §3)
├── plugins/                      # Plugin registry
└── providers/                    # LLM provider system (see §4)
```

### 2.3 Frontend Architecture

```
frontend/src/
├── App.tsx                       # 20 routes with JWT-protected shell
├── api/                          # 18 API client modules + types
│   ├── client.ts                 # Base fetch wrapper with error handling
│   ├── types.ts                  # 177 lines of TypeScript interfaces
│   └── [module].ts               # Per-domain API functions
├── components/                   # 51 components in 14 directories
│   ├── auth/                     # Role badge
│   ├── autonomous/               # Consciousness state + cycle progress
│   ├── charts/                   # 3 chart components (domain, status, score)
│   ├── costs/                    # 3 cost display components
│   ├── gaps/                     # GapCard, ClusterScatter, FeedbackForm
│   ├── governance/               # Approval card
│   ├── idea/                     # Comment thread + share dialog
│   ├── ideas/                    # 7 idea display components
│   ├── knowledge-graph/          # Graph canvas + entity detail + world model
│   ├── knowledge/                # Upload zone
│   ├── layout/                   # AppShell + Sidebar
│   ├── literature/               # Paper card
│   ├── markdown/                 # Markdown renderer
│   ├── memory/                   # Memory card + stats
│   ├── pipeline/                 # Run card + config form + stage progress
│   ├── traces/                   # Span detail + trace summary
│   └── ui/                       # 12 shadcn/ui primitives
├── contexts/                     # Auth context + settings context
├── hooks/                        # usePipelineProgress + useSSE
├── i18n/                         # i18next config with language switcher
├── lib/                          # Utilities, constants, score-utils
├── pages/                        # 20 page components
│   ├── dashboard.tsx             # Main dashboard
│   ├── pipeline-new.tsx          # Pipeline configuration wizard
│   ├── run-detail.tsx            # Run results view
│   ├── ideas-browser.tsx         # Paginated ideas grid
│   ├── idea-detail.tsx           # Single idea with feedback + comments
│   ├── gaps-explorer.tsx         # Gap search + filter + clusters tab
│   ├── gap-detail.tsx            # Truth values + feedback + related gaps
│   ├── knowledge-search.tsx      # Hybrid BM25 + semantic search
│   ├── knowledge-graph.tsx       # SVG knowledge graph
│   ├── settings.tsx              # All 227 config params
│   ├── costs.tsx                 # Cost tracking dashboard
│   ├── governance.tsx            # Governance policy view
│   ├── memory.tsx                # Memory browser with tiers
│   ├── traces.tsx                # Distributed traces view
│   ├── sessions.tsx              # Pipeline session management
│   ├── literature.tsx            # Literature search results
│   ├── autonomous.tsx            # Autonomous cycle controls
│   ├── plugins.tsx               # Plugin management
│   ├── login.tsx                 # JWT authentication
│   └── placeholder.tsx           # Placeholder for future pages
└── test/                         # Test setup + utilities
```

---

## 3. Pipeline Subsystem Deep Analysis (32 Subsystems)

### 3.1 Core Pipeline Flow

| Stage | Subsystem | LOC | Purpose |
|:---|:---|:---|:---|
| 1 | `literature/` | 571 | Search Semantic Scholar, arXiv, OpenAlex |
| 2 | `ingestion/` | 224 | PDF parsing (S1 parser), chunking |
| 3 | `gap_analysis/` | 364 | LLM-based gap identification + UMAP/HDBSCAN clustering |
| 4 | `generation/` | 3,649 | Multi-agent Ideator→Critic→Refiner with Borda Tournament |
| 5 | `novelty/` | 508 | Semantic novelty checking + citation-aware scoring |
| 6 | `feasibility/` | 480 | Feasibility scoring + causal DAG analysis + counterfactual |
| 7 | `synthesis/` | 410 | Proposal synthesis + reference validation |
| 8 | `export/` | 320 | Markdown, LaTeX, PDF export |

### 3.2 Intelligence Subsystems

| Subsystem | LOC | Purpose | Theoretical Basis |
|:---|:---|:---|:---|
| `knowledge/` | 4,004 | KG, truth calculus, graph RAG, BM25, embeddings | OpenNARS truth values, Hebbian consolidation |
| `memory/` | 1,216 | Tiered memory (working/episodic/semantic), consolidation | ACT-R inspired memory tiers |
| `self_improve/` | 1,104 | Pareto frontier evolution, lessons, A/B testing, ratchet | gepa-inspired evolutionary optimization |
| `autonomy/` | 918 | Consciousness state machine, curiosity, budget, scheduler | PUMA-inspired 5-state machine |
| `metacognitive/` | 252 | Strategy selection, plateau detection | Metacognitive monitoring |
| `negotiation/` | 508 | Multi-agent negotiation with consensus algorithms | Weighted voting consensus |
| `governance/` | 1,209 | Policy engine, approval workflow, guardrails, audit | Constitutional AI principles |

### 3.3 Infrastructure Subsystems

| Subsystem | LOC | Purpose |
|:---|:---|:---|
| `evaluation/` | 1,444 | G-Eval, quality gate, ensemble review, scoring, caching |
| `compaction/` | 1,066 | Context window management, summarization, offloading |
| `tools/` | 1,397 | Tool registry, MCP integration, discovery, matching |
| `sandboxing/` | 786 | Docker/subprocess/WASM/noop sandbox backends |
| `observability/` | 266 | OTLP export, metrics collection, span lifecycle |
| `tracing/` | 371 | In-memory trace processing, span creation |
| `streaming/` | 186 | SSE event streaming with deduplication |
| `execution/` | 283 | Run state, checkpoints, heartbeat monitoring |
| `session/` | 256 | Session lifecycle management with budget tracking |
| `context/` | 285 | Cross-stage context persistence + layered prompts |
| `adaptation/` | 249 | Behavioral adaptation from feedback signals |
| `agents/` | 594 | Agent registry, message bus, DAG executor, dynamic factory |
| `skills/` | 661 | Skill registry, proposer/generator for self-improvement |
| `reasoning/` | 134 | Scratch space for intermediate reasoning |
| `plugins/` | 136 | Plugin loader with verification |

---

## 4. Provider System

### 4.1 Provider Architecture

```
providers/
├── base.py                    # LLMProvider abstract base (generate, generate_stream)
├── openai_provider.py         # OpenAI GPT-4o
├── anthropic_provider.py      # Anthropic Claude
├── gemini_provider.py         # Google Gemini
├── ollama_provider.py         # Local Ollama models
├── litellm_provider.py        # LiteLLM unified routing
├── provider_factory.py        # Provider registry with cost tracking
├── task_router.py             # Per-stage model routing
├── stage_wrapper.py           # Stage-specific provider wrapping
├── token_counter.py           # Token usage tracking
├── cache/                     # 3-tier caching: memory, semantic, base
├── resilience/                # Circuit breaker, retry, resilient provider
├── routing/                   # Cost router, latency tracker, budget manager
└── secrets/                   # Encrypted key vault with AES-GCM
```

### 4.2 Provider Features
- **5 LLM providers** with unified interface
- **Circuit breaker** with configurable failure threshold and cooldown
- **Exponential retry** with jitter
- **Semantic caching** via ChromaDB similarity search
- **Cost-aware routing** (cheapest/lowest-latency strategies)
- **Encrypted secret storage** with AES-GCM
- **Per-stage model routing** via TaskRouter
- **LiteLLM fallback** for unified resilience

---

## 5. Knowledge Architecture

### 5.1 OpenNARS Truth Calculus (`knowledge/truth.py`)

Every knowledge assertion carries a `TruthValue` with:
- **frequency**: P(proposition is true | evidence) — 0.0 to 1.0
- **confidence**: P(evidence is sufficient) — 0.0 to 0.99
- **evidence_count**: Number of observations
- **propagation_debt**: How stale downstream consumers are

Key operations:
- `revise(other)`: Weighted averaging of two TruthValues (OpenNARS revision rule)
- `decay(rate)`: Temporal truth decay
- `settle_debt()`: Mark propagation debt as resolved
- `from_observation(f)`: Create from single observation
- `expectation` property: frequency × confidence

### 5.2 Knowledge Graph (`knowledge/graph.py`)

Entity-centric graph with Hebbian-like edge consolidation:
- **Entity types**: Paper, Author, Method, Dataset, Concept, Metric
- **Relationship types**: Cites, Uses_Method, Extends, Contradicts, Proposes_Method, etc.
- **Features**: Content-hash dedup, entity resolution (Union-Find), adjacency index, version tracking
- **Truth revision**: Entities and relationships undergo OpenNARS revision on conflict
- **CONTRADICTS handling**: Automatic confidence reduction when contradictions detected
- **Persistence**: JSON with optional changeset versioning (.changes.jsonl)

### 5.3 Graph RAG (`knowledge/graph_rag_retriever.py`)

3-source retrieval combining:
1. **Vector search** (ChromaDB semantic similarity)
2. **BM25 search** (rank-bm25 keyword matching)
3. **Graph walks** (KG neighbor traversal with hop limits)

Fusion via weighted combination with configurable `graph_rag_weight`.

### 5.4 Additional Knowledge Subsystems

| File | Purpose |
|:---|:---|
| `activation.py` | Spreading activation pipeline (BaseLevelDecay, ContextSpreading) |
| `adjacency.py` | O(1) neighbor lookup index |
| `bm25_index.py` | BM25 full-text search with metadata |
| `change_detector.py` | World model change detection + goal re-evaluation |
| `community_detection.py` | Graph community detection for RAG |
| `contradiction.py` | LLM-based contradiction scanning |
| `embedding_providers.py` | Provider abstraction + Ollama fallback |
| `embedding_service.py` | Batch embedding with fallback |
| `entity_extractor.py` | LLM-based entity extraction |
| `faithfulness.py` | Faithfulness checking for gap claims |
| `graph_embeddings.py` | Graph embedding index for similarity search |
| `graph_walks.py` | Random walk + BFS graph traversal |
| `query_transform.py` | Multi-query decomposition |
| `reranker.py` | LLM + Cross-encoder reranking |
| `retrieval_quality.py` | Retrieval quality scoring + adaptive requery |
| `retriever.py` | Two-stage hybrid retriever (vector + BM25 + RRF) |
| `streams.py` | Reactive stream registry for change notifications |
| `vector_store.py` | ChromaDB vector store wrapper |
| `versioning.py` | Change tracking with content hashing |
| `world_model.py` | World model with activation pipeline |

---

## 6. Multi-Agent Generation System

### 6.1 Agent Topology

The generation system uses a **TopologyDAG** (Directed Acyclic Graph) with 3 agent roles:

```
Ideator → Critic → Refiner
   ↑                  │
   └──── Borda ←──────┘
```

### 6.2 Ideator Agent (`generation/ideator_agent.py`)
- Generates raw research ideas from gaps + context papers
- Uses LLM with configurable temperature (evolved by PipelineEvolver)
- Supports Tree-of-Thought reasoning when enabled
- Tool calling integration (tool_calling.py)

### 6.3 Critic Agent (`generation/critic_agent.py`)
- Multi-strategy evaluation: STANDARD, ADVERSARIAL, META_REFLECTION, ENSEMBLE
- Data-driven strategy selection via StrategyTracker
- Produces structured critiques with strengths, weaknesses, suggestions

### 6.4 Refiner Agent (`generation/refiner_agent.py`)
- Refines ideas based on critiques
- Produces strengthened ResearchIdea objects with scores

### 6.5 Borda Tournament (`generation/borda.py`)
- **3-way blind comparison**: Incumbent (A) vs. Adversarial (B) vs. Synthesis (AB)
- **Positional bias elimination**: Labels shuffled for each judge
- **Convergence**: When incumbent wins k=2 consecutive rounds
- Based on autoreason (ICLR 2026 Oral) pattern

### 6.6 Impasse Detection (`generation/impasse.py`)
- Soar-style impasse detection: quality stall, loop detection, score degradation
- Resolution strategies: inject constraint, switch strategy, change perspective
- Hook dispatch for impasse events

### 6.7 Supporting Generation Files

| File | Purpose |
|:---|:---|
| `agent_handlers.py` | DAG node handler registration |
| `buffered_taxonomy.py` | Buffered taxonomy for gap→idea mapping |
| `context_isolator.py` | Per-gap context isolation for DAG execution |
| `dag_executor.py` | DAG-based parallel idea generation |
| `error_taxonomy.py` | Error classification for retry logic |
| `forest.py` | Forest-of-Thought multi-tree reasoning |
| `mechanical_checks.py` | Deterministic idea quality checks |
| `prompts/` | Prompt templates |
| `reasoning_graph.py` | Graph-of-thoughts reasoning |
| `strategies.py` | Strategy selection + convergence/plateau detection |
| `topology.py` | DAG topology definition (LOOP, PARALLEL, SEQUENTIAL nodes) |
| `tot_adapter.py` | Tree-of-Thought adapter |
| `verifier.py` | Reasoning verification for ideas |

---

## 7. Self-Improvement System

### 7.1 Pipeline Evolution (`self_improve/evolution.py`)
- **gepa-inspired** evolutionary optimization of pipeline parameters
- **7 evolvable parameters**: generation_rounds, ideas_per_round, ideator/critic/refiner temperatures, max_gaps, novelty_top_k
- **Pareto frontier** with multi-objective scoring (quality, novelty, diversity, efficiency)
- **Git snapshot** for rollback (autonovel pattern)
- **Constraint validation** gate before accepting evolved parameters

### 7.2 Fitness Scoring (`self_improve/fitness.py`)
- 4-dimension fitness: correctness, procedure_following, conciseness, length_penalty
- Composite score with configurable weights

### 7.3 Additional Self-Improve Components

| File | Purpose |
|:---|:---|
| `ab_test.py` | A/B testing harness for parameter comparison |
| `constraints.py` | Constraint validation (size, growth, sections) |
| `engine.py` | Evolution engine with decay rate |
| `feedback_history.py` | Feedback history tracking |
| `frontier.py` | Pareto frontier with FrontierPoint storage |
| `lessons.py` | LLM-based lesson extraction from pipeline runs |
| `ratchet.py` | Quality ratchet — never regress below best |

---

## 8. Consciousness State Machine (`autonomy/state_machine.py`)

5-state PUMA-inspired state machine:

```
IDLE ──idle_timeout──→ EXPLORING ──new_high_conf_gap──→ FOCUSED
  ↑                       │                              │
  │                       └──no_gaps_found──→ IDLE       │
  │                                                      ↓
  └──consolidation_complete── DREAMING ←── CONTEMPLATING
```

- **IDLE**: Waiting for triggers
- **EXPLORING**: Broad literature search via curiosity driver
- **FOCUSED**: Deep pipeline execution on identified gaps
- **CONTEMPLATING**: Result analysis and synthesis
- **DREAMING**: Memory consolidation and world model updates

### Curiosity Driver (`autonomy/curiosity.py`)
- LLM-powered exploration topic suggestion
- Tracks explored topics to avoid repetition

### Budget System (`autonomy/budget.py`)
- Token, cost, and time budgets with policy enforcement
- STOP (hard limit) and REPLAN (80% warning) policies

---

## 9. Database Schema

### 9.1 Models (8 total)

| Model | Table | Key Columns | Batch Origin |
|:---|:---|:---|:---|
| User | users | username, email, hashed_password, role | BATCH-28 |
| Paper | papers | source_id, title, abstract, authors, year, venue, doi, keywords | Initial |
| Idea | ideas | title, problem_statement, proposed_method, scores, user_rating, source_gap_ids, pipeline_run_id | BATCH-14 |
| Proposal | proposals | idea_id, content_md, content_latex, references_json, sections_json | Initial |
| PipelineRun | pipeline_runs | status, domain, config_json, session_id, current_stage, cluster_report_json | BATCH-22, 38 |
| Comment | comments | idea_id, author, content, parent_id | BATCH-34 |
| SharedIdea | shared_ideas | idea_id, token | BATCH-34 |
| ResearchGapDB | research_gaps | title, description, gap_type, confidence, truth_*, related_clusters, status, user_rating, user_notes, canonical_id, content_hash | BATCH-38, 41, 42 |

### 9.2 Migration Chain
```
001_initial (29607f14fd7f) → 002_gap_enrichment (38a2b1e7c4d5) → 003_gap_feedback → 004_gap_dedup
```

---

## 10. Configuration System (`backend/config.py`)

227 parameters organized into 30+ categories:

| Category | Example Parameters | Count |
|:---|:---|:---|
| LLM Providers | default_provider, *_api_key, *_model | 14 |
| Knowledge Base | chroma_dir, embedding_*, chunk_size, retrieval_mode | 12 |
| Pipeline | generation_rounds, ideas_per_round, novelty_top_k | 3 |
| Auth | auth_enabled, jwt_secret, jwt_expire_minutes | 4 |
| Memory | memory_enabled, tier, decay_rate, shared | 6 |
| Self-Improve | enabled, evolution_decay_rate, ab_testing | 4 |
| Autonomy | enabled, idle_timeout, max_autonomous_runs | 3 |
| Budget | max_tokens, max_cost_usd, max_seconds | 3 |
| Resilience | circuit_breaker_*, retry_* | 8 |
| Evaluation | framework_enabled, geval, quality_gate | 9 |
| Sandboxing | enabled, backend, timeout, docker_images | 7 |
| Observability | enabled, otlp_*, metrics | 7 |
| Caching | type, max_size, similarity_threshold, ttl | 5 |
| Cost Routing | enabled, strategy, per_provider_limits | 3 |
| Metacognitive | enabled, plateau_window, threshold | 3 |
| Governance | enabled, policy_path, approval_timeout | 3 |
| Graph RAG | enabled, walk_max_hops, weight | 5 |
| Tool Discovery | enabled, bm25_dir, trust_penalty | 5 |
| Negotiation | enabled, max_rounds, consensus_threshold | 7 |
| Session | enabled, data_dir, gc_* | 7 |
| Generation | tree_of_thought, counterfactual | 5 |
| Adaptation | enabled, feedback_window, min_improvement | 3 |
| Streaming | enabled, dedup_window | 2 |
| Webhooks | enabled, url, secret | 3 |
| Cross-stage | enabled, namespace, prompt_layers | 3 |
| Stage execution | max_retries, heartbeat_* | 7 |

All configurable via `EROCK_`-prefixed environment variables or `.env` file.

---

## 11. Frontend Detailed Analysis

### 11.1 Page Inventory (20 pages)

| Page | Route | LOC | Key Features |
|:---|:---|:---|:---|
| Dashboard | `/` | 213 | Run stats, domain chart, score distribution, quick actions |
| Pipeline New | `/pipeline/new` | 361 | Configuration wizard with all parameters |
| Run Detail | `/runs/:id` | 273 | Stage progress, ideas, proposals, exports |
| Ideas Browser | `/ideas` | 230 | Paginated grid, search, filter, sort |
| Idea Detail | `/ideas/:id` | 211 | Full idea view, feedback, comments, proposals |
| Gaps Explorer | `/gaps` | 274 | Search, filter, sort, clusters tab |
| Gap Detail | `/gaps/:id` | 217 | Truth values, cluster membership, feedback, related |
| Knowledge Search | `/knowledge` | 147 | Hybrid BM25 + semantic search |
| Knowledge Graph | `/knowledge-graph` | 184 | SVG graph visualization |
| Settings | `/settings` | 316 | All 227 config parameters |
| Costs | `/costs` | 163 | Cost breakdown, budget tracking |
| Governance | `/governance` | 108 | Policy status, approvals |
| Memory | `/memory` | 241 | Tiered memory browser |
| Traces | `/traces` | 194 | Distributed trace visualization |
| Sessions | `/sessions` | 191 | Session management |
| Literature | `/literature` | 94 | Search results display |
| Autonomous | `/autonomous` | 328 | Consciousness state, cycle control |
| Plugins | `/plugins` | 162 | Plugin management |
| Login | `/login` | 155 | JWT authentication |
| Placeholder | (unused) | 12 | Template for future pages |

### 11.2 Component Inventory (51 components)

**Data Display:** GapCard, IdeaCard, MemoryCard, PaperCard, RunCard, TraceSummary, ScoreBadge  
**Forms:** GapFeedbackForm, FeedbackForm, RunConfigForm, AutonomousForm, UploadZone  
**Visualization:** ClusterScatter (SVG), GraphCanvas (SVG), ScoreDistribution, DomainBreakdown, RunStatusChart, StageProgress, CycleProgress, ConsciousnessState  
**Layout:** AppShell, Sidebar  
**Auth:** RoleBadge  
**Idea:** CommentThread, ShareDialog, ExportButton, FeasibilityReportView, NoveltyReportView  
**Knowledge:** EntityDetail, WorldModelPanel  
**Cost:** BudgetBar, CostBreakdownTable, CostSummaryCard  
**Governance:** ApprovalCard  
**Export:** ExportDialog  
**i18n:** LanguageSwitcher  
**Markdown:** MarkdownRenderer  
**UI Primitives:** Badge, Button, Card, Dialog, Input, Progress, Select, Separator, Skeleton, Slider, Tabs  
**Error:** ErrorBoundary

### 11.3 Frontend Infrastructure

| Module | Purpose |
|:---|:---|
| `api/client.ts` | Base fetch wrapper with error handling, retry, auth headers |
| `api/types.ts` | 177 lines of TypeScript interfaces mirroring backend models |
| `contexts/auth-context.tsx` | JWT auth state with login/logout/register |
| `contexts/settings-context.tsx` | Settings state management |
| `hooks/usePipelineProgress.ts` | Real-time pipeline progress tracking |
| `hooks/useSSE.ts` | Server-Sent Events hook for streaming |
| `i18n/config.ts` | i18next configuration |
| `lib/utils.ts` | shadcn/ui utility functions |
| `lib/constants.ts` | Frontend constants |
| `lib/score-utils.ts` | Score formatting and color utilities |

---

## 12. Testing Infrastructure

### 12.1 Backend Tests (202 files, 1,480 passing)

| Category | Files | Tests | Coverage |
|:---|:---|:---|:---|
| API | 22 | ~180 | All endpoints tested |
| Pipeline | 16 | ~120 | Stage-by-stage + integration |
| Generation | 12 | ~80 | Borda, impasse, DAG, strategies |
| Knowledge | 14 | ~100 | Graph, truth, retrieval, RAG |
| Memory | 8 | ~60 | Tiers, consolidation, dedup |
| Evaluation | 7 | ~50 | Quality gate, scoring, G-Eval |
| Governance | 4 | ~40 | Policy, validation, audit |
| Negotiation | 5 | ~40 | Consensus, protocol, sessions |
| Providers | 2 | ~30 | Provider validation, LiteLLM |
| DB | 7 | ~50 | CRUD, migrations, integration |
| Sandboxing | 5 | ~40 | Docker, subprocess, noop |
| Self-Improve | 6 | ~50 | Evolution, fitness, frontier |
| Session | 3 | ~30 | Manager, models, API |
| Streaming | 3 | ~25 | Events, callbacks, manager |
| Adaptation | 3 | ~20 | Feedback, strategy, manager |
| Autonomy | 4 | ~30 | Budget, state machine, dependency |
| Metacognitive | 4 | ~25 | Ledger, manager, plateau |
| Observability | 5 | ~30 | Metrics, spans, manager |
| Resilience | 1 | ~20 | Circuit breaker + retry |
| Routing | 5 | ~30 | Cost router, latency, strategy |
| Caching | 4 | ~25 | Memory, semantic, cached provider |
| MCP | 7 | ~40 | Adapter, client, transport |
| Tool Discovery | 5 | ~30 | Index, matcher, scoring |
| Graph RAG | 5 | ~30 | Community, embeddings, walks |
| Compaction | 8 | ~50 | Budget, summarizer, window |
| CLI | 6 | ~30 | Commands, progress |
| Benchmarks | 5 | ~15 | Activation, BM25, KG, memory, recall |
| Integration | 2 | ~10 | Cross-WP, Docker |
| Quality Benchmarks | 3 | ~10 | Bias, debate consistency, idea quality |

### 12.2 Frontend Tests (63 files, 310 passing)

| Category | Tests |
|:---|:---|
| Page tests | 27 files (every page has tests) |
| Component tests | 18 files |
| API client tests | 9 files |
| Hook tests | 1 file |
| Context tests | 1 file |
| Library tests | 3 files |
| i18n tests | 1 file |
| Batch-specific tests | 9 files (BATCH-13, 14, 16, 27, 32, 33, 39, 40, 41) |

### 12.3 CI/CD

| Workflow | Trigger | Steps |
|:---|:---|:---|
| CI | Push/PR to main/develop/master | lint → format check → test with coverage → typecheck → upload |
| Nightly E2E | Cron (3AM UTC) + manual | Install → run slow/integration tests → upload coverage |
| Docs | Push to main (docs/**) | Build MkDocs → deploy to GitHub Pages |

---

## 13. Theoretical Foundations

The platform implements or draws from **10+ theoretical frameworks**:

| Foundation | Implementation | Location |
|:---|:---|:---|
| **OpenNARS Truth Calculus** | TruthValue with frequency/confidence/revision | `knowledge/truth.py` |
| **Hebbian Learning** | Edge weight reinforcement in Knowledge Graph | `knowledge/graph.py` |
| **Borda Tournament** | 3-way blind comparison for convergence | `generation/borda.py` |
| **PUMA State Machine** | 5-state consciousness for autonomy | `autonomy/state_machine.py` |
| **gepa Evolution** | Pareto frontier parameter optimization | `self_improve/evolution.py` |
| **ACT-R Memory** | Working/episodic/semantic tier system | `memory/tiers.py` |
| **Soar Impasse Detection** | Quality stall/loop/degradation detection | `generation/impasse.py` |
| **Autoreason Convergence** | Positional bias elimination in judging | `generation/borda.py` |
| **Constitutional AI** | Governance policy + approval workflow | `governance/` |
| **Spreading Activation** | Context-based activation in Knowledge Graph | `knowledge/activation.py` |
| **Reciprocal Rank Fusion** | Hybrid BM25 + vector search fusion | `knowledge/retriever.py` |
| **Quality Ratchet** | Never-regress-below-best guarantee | `self_improve/ratchet.py` |

---

## 14. API Endpoint Inventory (76 endpoints)

### Pipeline (25 endpoints)
- POST `/api/v1/pipeline/run` — Start pipeline
- POST `/api/v1/pipeline/run-async` — Async pipeline
- GET `/api/v1/pipeline/runs` — List runs
- GET `/api/v1/pipeline/runs/{id}` — Get run
- DELETE `/api/v1/pipeline/runs/{id}` — Delete run
- GET `/api/v1/pipeline/runs/{id}/ideas` — Run's ideas
- GET `/api/v1/pipeline/runs/{id}/proposals` — Run's proposals
- POST `/api/v1/pipeline/resume/{run_id}` — Resume interrupted run
- POST `/api/v1/pipeline/autonomous/start` — Start autonomous cycle
- POST `/api/v1/pipeline/autonomous/stop` — Stop autonomous cycle
- GET `/api/v1/pipeline/autonomous/status` — Get autonomous status
- GET `/api/v1/pipeline/scheduler/status` — Scheduler status
- POST `/api/v1/pipeline/scheduler/start` — Start scheduler
- POST `/api/v1/pipeline/scheduler/stop` — Stop scheduler
- GET `/api/v1/pipeline/stages` — List pipeline stages
- GET `/api/v1/pipeline/stages/{name}` — Stage details
- POST `/api/v1/pipeline/sessions` — Create session
- GET `/api/v1/pipeline/sessions/{id}` — Get session
- GET `/api/v1/pipeline/sessions/{id}/runs` — Session's runs
- POST `/api/v1/pipeline/evolve` — Trigger evolution
- GET `/api/v1/pipeline/evolve/history` — Evolution history
- POST `/api/v1/pipeline/evolve/rollback` — Rollback evolution
- GET `/api/v1/pipeline/evolve/frontier` — Pareto frontier
- POST `/api/v1/pipeline/hooks/{event}` — Fire hook
- GET `/api/v1/pipeline/export-template` — Export template

### Gaps (10 endpoints)
- GET `/api/v1/gaps/` — List gaps (search, filter, sort)
- GET `/api/v1/gaps/stats` — Gap analytics
- GET `/api/v1/gaps/export` — CSV/JSON export
- GET `/api/v1/gaps/clusters` — Cluster report
- GET `/api/v1/gaps/canonical` — Deduplicated gaps
- GET `/api/v1/gaps/{id}` — Gap detail
- GET `/api/v1/gaps/{id}/papers` — Gap source papers
- GET `/api/v1/gaps/{id}/related` — Related gaps
- POST `/api/v1/gaps/{id}/feedback` — Submit feedback (1-5 stars)
- PATCH `/api/v1/gaps/{id}/status` — Update lifecycle status

### Ideas (4 endpoints)
- GET `/api/v1/ideas/` — List ideas
- GET `/api/v1/ideas/{id}` — Idea detail
- POST `/api/v1/ideas/{id}/feedback` — Submit feedback
- POST `/api/v1/ideas/{id}/rate` — Rate idea

### Knowledge (3 endpoints)
- GET `/api/v1/knowledge/search` — Hybrid search
- POST `/api/v1/knowledge/upload` — Upload documents
- POST `/api/v1/knowledge/index` — Re-index

### Knowledge Graph (5 endpoints)
- GET `/api/v1/knowledge-graph/stats` — Graph statistics
- GET `/api/v1/knowledge-graph/entities` — List entities
- GET `/api/v1/knowledge-graph/entities/{id}` — Entity detail
- GET `/api/v1/knowledge-graph/relationships` — List relationships
- GET `/api/v1/knowledge-graph/neighbors/{id}` — Entity neighbors

### Auth (4 endpoints)
- POST `/api/v1/auth/register` — Register user
- POST `/api/v1/auth/login` — Login
- GET `/api/v1/auth/me` — Current user
- GET `/api/v1/auth/users` — List users

### Collaboration (4 endpoints)
- POST `/api/v1/ideas/{id}/comments` — Add comment
- GET `/api/v1/ideas/{id}/comments` — List comments
- POST `/api/v1/ideas/{id}/share` — Create share link
- GET `/api/v1/shared/{token}` — View shared idea (public)

### Costs (5 endpoints)
- GET costs summary, by-stage, by-provider, by-model, trends

### Exports (2 endpoints)
- POST `/api/v1/export/proposal/{id}` — Export proposal
- POST `/api/v1/export/batch` — Batch export

### Governance (3 endpoints)
- GET policies, POST approve, POST reject

### Literature (3 endpoints)
- GET search, GET sources, POST import

### Memory (3 endpoints)
- GET memories, GET stats, DELETE memory

### Search (1 endpoint)
- GET `/api/v1/search/` — Global search across ideas, gaps, papers, runs

### Status (3 endpoints)
- GET `/api/v1/status/` — System status
- GET `/api/v1/status/detailed` — Detailed status
- GET `/api/v1/status/providers` — Provider status

### Traces (3 endpoints)
- GET traces, GET trace detail, GET spans

### Plugins (2 endpoints)
- GET list plugins, POST toggle plugin

### Health (1 endpoint)
- GET `/health` — Health check

---

## 15. Data Flow: Full Pipeline Run

```
User → POST /pipeline/run
  │
  ├─ PipelineOrchestrator.__init__()
  │   ├─ Init 32 subsystems (22 subsystem factories)
  │   ├─ Build 8 stages
  │   └─ Register builtin tools
  │
  ├─ Run budget validation
  ├─ Create DB run record
  ├─ Start MCP servers
  ├─ Dispatch pipeline.start hook
  │
  ├─ Stage 1: LiteratureSearchStage
  │   └─ SearchService → Semantic Scholar + arXiv + OpenAlex
  │
  ├─ Stage 2: IngestionStage
  │   ├─ PDFService → chunking
  │   ├─ VectorStore → ChromaDB indexing
  │   ├─ BM25Index → keyword indexing
  │   └─ KnowledgeGraph → entity creation
  │
  ├─ Stage 3: GapAnalysisStage
  │   ├─ GapAnalyzer → LLM gap identification
  │   ├─ ClusterService → UMAP + HDBSCAN clustering
  │   ├─ FaithfulnessChecker → claim verification
  │   └─ GoalManager → goal creation from gaps
  │
  ├─ Stage 4: IdeaGenerationStage
  │   ├─ DAGExecutor → parallel agent execution
  │   │   ├─ IdeatorAgent → raw idea generation
  │   │   ├─ CriticAgent → multi-strategy evaluation
  │   │   ├─ RefinerAgent → idea refinement
  │   │   └─ BordaTournament → convergence detection
  │   ├─ ImpasseDetector → Soar-style stall detection
  │   └─ ReasoningVerifier → idea reasoning verification
  │
  ├─ Stage 5: NoveltyCheckingStage
  │   └─ NoveltyChecker → semantic + citation + embedding novelty
  │
  ├─ Stage 6: FeasibilityScoringStage
  │   ├─ FeasibilityScorer → LLM feasibility
  │   └─ Counterfactual analysis → refutation tests
  │
  ├─ Stage 7: ProposalSynthesisStage
  │   ├─ ProposalSynthesizer → full proposal generation
  │   ├─ OutputValidator → governance validation
  │   ├─ GovernanceAuditLog → audit trail
  │   └─ ReferenceValidator → reference verification
  │
  ├─ Stage 8: ExportStage
  │   └─ ExportService → Markdown/LaTeX/PDF export
  │
  ├─ Post-pipeline:
  │   ├─ PipelineEvaluator → unified evaluation
  │   ├─ PipelineEvolver → parameter evolution
  │   ├─ LessonExtractor → lesson extraction → memory
  │   ├─ WorldModel → update + change detection
  │   └─ MemoryService → background extraction
  │
  └─ Mark run completed, persist costs
```

---

## 16. Observations and Strengths

### 16.1 Architectural Strengths

1. **Deep theoretical grounding** — 12+ academic frameworks implemented in code, not just referenced
2. **Comprehensive test coverage** — 1,790 tests with 69% coverage threshold
3. **Clean separation of concerns** — 32 pipeline subsystems with clear boundaries
4. **Feature-flag driven** — Every subsystem gated by config, enabling incremental adoption
5. **Resilient provider system** — Circuit breaker, retry, caching, cost routing
6. **OpenNARS truth calculus** — First implementation in a research ideation platform
7. **Borda Tournament convergence** — Rigorous convergence guarantees for multi-agent debate
8. **Durable execution** — Checkpoint + resume with heartbeat monitoring
9. **Complete frontend** — 20 pages, 51 components, full API client coverage
10. **AIV Framework compliance** — 47 batches with full document trail

### 16.2 Scale Assessment

- **77,516 total LOC** across backend + frontend + tests
- **277 backend source files** — the most comprehensive research ideation platform codebase examined
- **76 API endpoints** — full CRUD for every entity plus analytics, export, and search
- **227 configuration parameters** — every subsystem is configurable
- **8 database models** with 4 migrations in a clean chain
- **5 LLM providers** with unified abstraction
- **32 pipeline subsystems** — more than most production ML platforms

---

## 17. Known Limitations

1. **E2E smoke test requires live API key** — 1 test failure out of 1,791
2. **SQLite for development** — PostgreSQL migration path exists but not default
3. **No Docker Compose** — Production deployment configuration not yet created
4. **No accessibility audit** — WCAG 2.1 AA compliance not verified
5. **No performance benchmarks** — Dashboard render time not measured at scale
6. **i18n infrastructure present but incomplete** — Only English locale fully populated
7. **No plugin SDK documentation** — Plugin API exists but lacks public documentation

---

*Report — AIV Framework v5.1 — Lead Agent — 2026-05-02*
