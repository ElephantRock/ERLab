# Elephant Rock Research Platform — Master Roadmap

**Version:** 1.0  
**Date:** 2026-05-01  
**Status:** Pre-Alpha (v0.1.0) → Production  

---

## How to Read This Document

This roadmap is organized into **6 phases**, each with **deliverables**, **task-level specifications** (files to create/modify, endpoints to build, components to add), **acceptance criteria**, and **dependencies**.

| Phase | Theme | Duration Estimate | Depends On |
|:---|:---|:---|:---|
| **0** | Foundation & Developer Experience | 2–3 weeks | Nothing |
| **1** | Core UX — The Golden Path | 3–4 weeks | Phase 0 |
| **2** | Feature Parity — Frontend Meets Backend | 4–6 weeks | Phase 1 |
| **3** | Intelligence & Autonomy UX | 3–4 weeks | Phase 2 |
| **4** | Production Hardening | 2–3 weeks | Phase 3 |
| **5** | Growth & Ecosystem | Ongoing | Phase 4 |

**Total estimated timeline: 14–20 weeks to production-ready v1.0**

---

## Current State Assessment

| Metric | Current | Target (v1.0) |
|:---|:---|:---|
| Backend source files | 262 | 262+ |
| Backend LOC | ~32,800 | ~35,000 |
| Frontend files | 59 | 90+ |
| Frontend LOC | ~3,100 | ~8,000 |
| Frontend test files | 9 | 25+ |
| API endpoints | 38 | 40+ |
| Frontend pages | 7 | 14+ |
| Frontend ↔ Backend parity | ~40% | ~90% |
| Coverage floor | 69% | 75% |
| Config parameters | 216 | 220+ |
| DB tables | 5 | 6–7 |
| Pipeline subpackages | 33 | 33 |
| Onboarding steps to first value | ~10 | 3 |

---

## PHASE 0: Foundation & Developer Experience

**Goal:** A new contributor or user can go from zero to first research idea in under 5 minutes.

### 0.1 Onboarding Wizard (CLI)

**Problem:** 10 steps before first value. User must read README, understand 18 env vars, choose a provider, get an API key, install deps, start servers.

**Deliverable:** `erock setup` interactive wizard.

```
Files to create/modify:
  backend/cli/commands/setup.py          ← New file (~200 lines)
  backend/cli/main.py                    ← Add `setup` command registration
```

**Wizard flow:**
1. Detect Python version (must be ≥3.11)
2. Ask: "Which LLM provider?" → OpenAI / Anthropic / Gemini / Ollama
3. If OpenAI/Anthropic/Gemini: prompt for API key, validate with a health check call
4. If Ollama: detect if running at localhost:11434
5. Write `.env` file with sensible defaults
6. Ask: "Run a test pipeline now?" → if yes, run `erock generate --domain "AI/NLP" --rounds 1 --ideas 1`
7. Print next-steps URL for web UI

**Acceptance Criteria:**
- [ ] `erock setup` creates a valid `.env` in under 2 minutes
- [ ] Invalid API keys are caught immediately with a helpful error
- [ ] After setup, `erock generate` works without additional configuration

### 0.2 One-Command Start (Web)

**Problem:** User must start backend and frontend separately, know two ports.

**Deliverable:** Single `erock dev` command.

```
Files to create/modify:
  backend/cli/commands/dev.py            ← New file (~120 lines)
  backend/cli/main.py                    ← Add `dev` command registration
```

**Behavior:**
1. Start `uvicorn backend.api.app:app` on port 8000
2. Start `npm run dev` in `frontend/` on port 3000
3. Print: "Backend: http://localhost:8000 | Frontend: http://localhost:3000"
4. Stream both logs to terminal with colored prefixes
5. Ctrl+C kills both

**Acceptance Criteria:**
- [ ] `erock dev` starts both servers
- [ ] Both processes are cleaned up on Ctrl+C
- [ ] Frontend proxy works without manual configuration

### 0.3 README Rewrite

**Problem:** Current README is 3 commands, no context, no mention of web UI.

```
Files to modify:
  README.md                              ← Complete rewrite
```

**Structure:**
1. One-paragraph "What is this?" with value proposition
2. 30-second quick start (after `erock setup`)
3. Architecture diagram (ASCII or link to image)
4. Interface guide (CLI / Web / API)
5. Configuration reference link
6. Contributing guide link

**Acceptance Criteria:**
- [ ] A new user can go from clone to first idea in under 5 minutes
- [ ] Web UI is mentioned and its start command is documented

### 0.4 API Documentation

**Problem:** FastAPI auto-generates OpenAPI docs but they're not promoted or enhanced.

```
Files to modify:
  backend/api/app.py                     ← Add descriptions to all routes
  backend/api/routes/*.py                ← Add response_examples to each endpoint
  docs/api-guide.md                      ← New file: human-readable API guide
```

**For each endpoint:**
- Add `summary` and `description` to route decorators
- Add `response_model` where missing
- Add example request/response in docstrings
- Document error responses

**Acceptance Criteria:**
- [ ] `/docs` (Swagger UI) shows complete, annotated API
- [ ] Every endpoint has a description, example, and error documentation
- [ ] A standalone `docs/api-guide.md` exists with curl examples

### 0.5 Error Message Audit

**Problem:** API key errors cause `SystemExit`. Error response format is inconsistent (`error` vs `detail`).

```
Files to modify:
  backend/providers/provider_factory.py  ← Replace SystemExit with friendly error
  backend/api/errors.py                  ← Standardize error format
  backend/api/app.py                     ← Unified error handler
```

**Changes:**
- `ProviderRegistry._validate_api_key`: raise `SystemExit` → raise `APIError(401, "API key required...")` with remediation hint
- All error responses use `{"error": {"code": "...", "message": "..."}}` format
- Error handler adds `request_id` header (UUID)

**Acceptance Criteria:**
- [ ] No `SystemExit` in user-facing code paths
- [ ] All error responses have consistent JSON structure
- [ ] Every error includes a remediation hint

### 0.6 Frontend Test Infrastructure

**Problem:** Only 9 frontend test files. Key pages and components have zero test coverage.

```
Files to create:
  frontend/src/pages/__tests__/dashboard.test.tsx
  frontend/src/pages/__tests__/pipeline-new.test.tsx
  frontend/src/pages/__tests__/ideas-browser.test.tsx
  frontend/src/pages/__tests__/idea-detail.test.tsx
  frontend/src/pages/__tests__/gaps-explorer.test.tsx
  frontend/src/pages/__tests__/knowledge-search.test.tsx
  frontend/src/pages/__tests__/settings.test.tsx
  frontend/src/components/charts/__tests__/score-distribution.test.tsx
  frontend/src/components/charts/__tests__/domain-breakdown.test.tsx
  frontend/src/components/charts/__tests__/run-status-chart.test.tsx
  frontend/src/components/markdown/__tests__/markdown-renderer.test.tsx
  frontend/src/components/gaps/__tests__/gap-card.test.tsx
```

**Each page test covers:**
- Renders without crashing
- Shows loading state
- Shows empty state
- Shows populated state (mocked API)
- Handles API errors

**Acceptance Criteria:**
- [ ] All 7 pages have test files
- [ ] `npm test` passes with ≥70% line coverage
- [ ] CI runs frontend tests

---

## PHASE 1: Core UX — The Golden Path

**Goal:** The primary journey (configure → run → see results → explore → feedback → export) is smooth, connected, and delightful.

### 1.1 Pipeline Results Flow

**Problem:** After pipeline completes, user sees "Complete" badge but no results. Must manually navigate to Ideas page.

```
Files to modify:
  frontend/src/pages/pipeline-new.tsx    ← Add post-completion results section
  frontend/src/api/pipeline.ts           ← Add getRunIdeas() call
  backend/api/routes/pipeline.py         ← Add /runs/{id}/ideas endpoint
```

**After pipeline completes:**
1. Show "Pipeline Complete" banner with summary stats (ideas found, gaps identified, time elapsed)
2. Show a list of generated ideas inline (using IdeaCard components)
3. Each idea card links to its detail page
4. Add "View All Ideas →" button linking to `/ideas`
5. Add "Run Another" button that resets the form

**New backend endpoint:**
```
GET /api/v1/pipeline/runs/{run_id}/ideas
→ { ideas: IdeaSummary[], total: int }
```

**Acceptance Criteria:**
- [ ] After pipeline completes, results appear on the same page within 2 seconds
- [ ] User can click through to any idea without leaving the pipeline page context
- [ ] "Run Another" resets the form state cleanly

### 1.2 Run Detail Page

**Problem:** Backend provides rich run detail (`GET /runs/detail/{id}`) but frontend has no page for it. Dashboard RunCards don't link anywhere.

```
Files to create:
  frontend/src/pages/run-detail.tsx      ← New page (~250 lines)
  frontend/src/api/pipeline.ts           ← getRunDetail() already exists
Files to modify:
  frontend/src/App.tsx                   ← Add /runs/:id route
  frontend/src/components/pipeline/run-card.tsx ← Add onClick navigation
  frontend/src/pages/dashboard.tsx       ← Make RunCards clickable
```

**Run Detail page shows:**
- Run metadata: ID, domain, status, timestamps, error message
- Configuration used (from `config_json`)
- Stages completed (from `stages_completed`) with timeline
- Ideas generated (list with scores)
- Cost summary (from cost tracker)
- "Resume" button if run failed (links to `/pipeline/resume/{id}`)
- "Delete" button (if user confirms)

**Acceptance Criteria:**
- [ ] Clicking a RunCard on Dashboard navigates to `/runs/:id`
- [ ] Run detail shows all metadata, stages, and ideas
- [ ] Failed runs show error message prominently
- [ ] Resume button appears only for failed/interrupted runs

### 1.3 Pipeline Form Completion

**Problem:** Frontend form hides critical backend options: `generation_rounds`, `export_format`, `run_novelty`/`run_feasibility`/`run_synthesis` toggles.

```
Files to modify:
  frontend/src/components/pipeline/run-config-form.tsx ← Add missing fields
  frontend/src/api/types.ts              ← Types already support these fields
```

**Fields to add:**
1. **Generation Rounds** — number input (1-10, default from settings)
2. **Export Format** — select dropdown (Markdown / LaTeX / None)
3. **Advanced Options** (collapsible section):
   - Toggle: Run Novelty Check (default: on)
   - Toggle: Run Feasibility Scoring (default: on)
   - Toggle: Run Proposal Synthesis (default: on)

**Also fix:** Max Gaps range in form (currently 1-50) must match API validation (1-20).

**Acceptance Criteria:**
- [ ] All backend pipeline options are exposed in the form
- [ ] Form validation matches API validation exactly
- [ ] Advanced options are collapsed by default to avoid overwhelming new users

### 1.4 Ideas Browser Enhancement

**Problem:** No sort, no min-score filter (backend supports it), no overall score shown on cards, no keyword search.

```
Files to modify:
  frontend/src/pages/ideas-browser.tsx   ← Add sort/filter/search
  frontend/src/components/ideas/idea-card.tsx ← Show overall score
  frontend/src/api/ideas.ts              ← Add min_score param (already in types)
```

**Enhancements:**
1. **Sort dropdown**: By Score (desc), By Novelty (desc), By Feasibility (desc), By Date (desc)
2. **Min Score slider**: 0.0–1.0 range, shows only ideas above threshold
3. **Search input**: Full-text search across titles (new backend param needed)
4. **Overall score badge** on IdeaCard
5. **Proposal indicator**: small icon if proposal exists for an idea

**New backend param:**
```
GET /api/v1/ideas?search=keyword&sort_by=score&sort_order=desc
```

**Acceptance Criteria:**
- [ ] User can sort ideas by any score dimension
- [ ] Min score filter works in real-time
- [ ] IdeaCard shows all three scores (novelty, feasibility, overall)
- [ ] Ideas with proposals have a visual indicator

### 1.5 Gap ↔ Idea Traceability

**Problem:** Ideas reference source gaps but the UI doesn't show this relationship in either direction.

```
Files to modify:
  frontend/src/components/gaps/gap-card.tsx  ← Add "Generated Ideas" count
  frontend/src/pages/idea-detail.tsx     ← Show source gap(s)
  backend/api/routes/gaps.py             ← Add idea count per gap
  backend/api/routes/ideas.py            ← Include source_gap_ids in response
  backend/db/crud.py                     ← Add count_ideas_for_gap()
```

**GapCard enhancement:**
- Show "3 ideas generated" badge if ideas exist for this gap
- Click badge → navigates to Ideas filtered by that gap

**Idea Detail enhancement:**
- Show "Source Gaps" section with linked gap titles
- Each gap links to `/gaps` (or gap detail if we build one)

**Acceptance Criteria:**
- [ ] Gaps show how many ideas they spawned
- [ ] Ideas show which gaps they came from
- [ ] Both directions are navigable via clicks

### 1.6 Settings Enhancement

**Problem:** Settings page has only 3 fields. No "Test Connection" button. No health check.

```
Files to modify:
  frontend/src/pages/settings.tsx        ← Add connection test, more settings
  frontend/src/api/client.ts             ← Add testConnection() helper
  backend/api/routes/status.py           ← Add /health/detailed endpoint
```

**Enhancements:**
1. **"Test Connection" button** — calls `/health`, shows ✅ or ❌
2. **Connection status indicator** — green dot if backend is reachable
3. **Default Domain** setting — saves to localStorage
4. **Default Provider** display — shows what the backend is configured with
5. **Version display** — shows backend version

**New backend endpoint:**
```
GET /api/v1/status/detailed
→ { status, version, provider, embedding_model, db_status, chroma_status }
```

**Acceptance Criteria:**
- [ ] Settings page shows backend connection status at all times
- [ ] "Test Connection" gives immediate feedback
- [ ] Default domain is used in pipeline form pre-fill

### 1.7 Cancel Pipeline from UI

**Problem:** No cancel button visible during pipeline execution. Backend supports it (`DELETE /runs/{id}`).

```
Files to modify:
  frontend/src/pages/pipeline-new.tsx    ← Add cancel button
  frontend/src/api/pipeline.ts           ← cancelRun() already exists
```

**Add:**
- Red "Cancel Run" button in the progress card header
- Confirmation dialog: "Cancel this pipeline run?"
- On cancel: show "Cancelled" badge, display partial results if any

**Acceptance Criteria:**
- [ ] Cancel button appears during pipeline execution
- [ ] Confirmation dialog prevents accidental cancellation
- [ ] Cancelled runs show partial results

---

## PHASE 2: Feature Parity — Frontend Meets Backend

**Goal:** Every major backend capability has a frontend interface. The web UI is the primary interface, not the CLI.

### 2.1 Cost Dashboard

**Problem:** Backend tracks costs in detail (per provider, stage, model) but frontend shows nothing.

```
Files to create:
  frontend/src/pages/costs.tsx           ← New page (~200 lines)
  frontend/src/api/costs.ts              ← New API client
  frontend/src/components/charts/cost-over-time.tsx  ← New chart
  frontend/src/components/charts/cost-by-stage.tsx   ← New chart
Files to modify:
  frontend/src/App.tsx                   ← Add /costs route
  frontend/src/components/layout/sidebar.tsx ← Add nav item
  frontend/src/components/layout/sidebar.tsx ← Add "Costs" with DollarSign icon
```

**Cost Dashboard shows:**
- Total spend (today, this week, all time)
- Cost by provider (pie chart)
- Cost by stage (bar chart)
- Cost by model (table)
- Per-run cost breakdown
- Budget utilization bar (current spend vs configured limit)

**Acceptance Criteria:**
- [ ] User can see exactly how much each pipeline run costs
- [ ] Costs are broken down by provider, stage, and model
- [ ] Budget limits are visualized

### 2.2 Memory Browser

**Problem:** Backend has a full memory system (working/episodic/semantic) with recall, store, delete, stats — but frontend has zero memory UI.

```
Files to create:
  frontend/src/pages/memory.tsx          ← New page (~300 lines)
  frontend/src/api/memory.ts             ← New API client
  frontend/src/components/memory/memory-card.tsx    ← New component
  frontend/src/components/memory/memory-stats.tsx   ← New component
Files to modify:
  frontend/src/App.tsx                   ← Add /memory route
  frontend/src/components/layout/sidebar.tsx ← Add "Memory" with Brain icon
```

**Memory Browser shows:**
- Memory statistics (total, by type)
- Searchable list of memories (filter by type: episodic/semantic/working)
- Each memory card: content preview, type badge, confidence score, creation date
- Delete button per memory (with confirmation)
- "Recall" search: query the memory system and see results

**Acceptance Criteria:**
- [ ] User can browse all stored memories
- [ ] User can search memories by text query
- [ ] User can delete individual memories
- [ ] Memory statistics are visible at a glance

### 2.3 Governance Queue

**Problem:** Backend has a full governance system with pending approvals, approve/deny API — but no UI.

```
Files to create:
  frontend/src/pages/governance.tsx      ← New page (~200 lines)
  frontend/src/api/governance.ts         ← New API client
  frontend/src/components/governance/approval-card.tsx ← New component
Files to modify:
  frontend/src/App.tsx                   ← Add /governance route
  frontend/src/components/layout/sidebar.tsx ← Add "Governance" with Shield icon
```

**Governance page shows:**
- Pending approvals list
- Each approval card: stage name, reason, rule name, timestamp
- Approve button (green) → calls `POST /governance/{id}/approve`
- Deny button (red) → opens amendment textarea → calls `POST /governance/{id}/deny`
- Empty state: "No pending approvals. Governance is running smoothly."

**Acceptance Criteria:**
- [ ] Pending governance decisions are visible
- [ ] User can approve or deny with one click
- [ ] Deny allows an optional amendment message

### 2.4 Observability / Traces Viewer

**Problem:** Backend has tracing with spans, metrics, latency percentiles — but no UI.

```
Files to create:
  frontend/src/pages/traces.tsx          ← New page (~250 lines)
  frontend/src/api/traces.ts             ← New API client
  frontend/src/components/traces/trace-detail.tsx ← New component
  frontend/src/components/charts/latency-chart.tsx ← New chart
Files to modify:
  frontend/src/App.tsx                   ← Add /traces route
  frontend/src/components/layout/sidebar.tsx ← Add "Traces" with Activity icon
```

**Traces page shows:**
- Trace summary (total traces, avg latency, error rate)
- Metrics chart (latency percentiles over time)
- Recent traces list (trace_id, run_id, stages, duration)
- Click trace → span detail view (per-stage timing, errors)

**Acceptance Criteria:**
- [ ] User can see pipeline performance at a glance
- [ ] Per-trace span breakdown is viewable
- [ ] Error traces are highlighted

### 2.5 Session Management UI

**Problem:** Backend has full session lifecycle (create, activate, pause, resume, end, budget tracking) — but no UI.

```
Files to create:
  frontend/src/pages/sessions.tsx        ← New page (~250 lines)
  frontend/src/api/sessions.ts           ← New API client
  frontend/src/components/session/session-card.tsx ← New component
Files to modify:
  frontend/src/App.tsx                   ← Add /sessions route
  frontend/src/components/layout/sidebar.tsx ← Add "Sessions" with Layers icon
  frontend/src/components/pipeline/run-config-form.tsx ← Add session selector
```

**Sessions page shows:**
- Active sessions list with state badges
- Each session card: name, state, run count, tokens used, cost, budget remaining
- Actions: Activate, Pause, Resume, End
- Create new session form
- Budget bar per session

**Pipeline form integration:**
- Session dropdown in pipeline form (if sessions enabled)
- Pipeline runs are tracked under the selected session

**Acceptance Criteria:**
- [ ] User can create and manage sessions from the UI
- [ ] Pipeline form allows selecting an active session
- [ ] Budget consumption is visible per session

### 2.6 Literature Search UI

**Problem:** Literature search is CLI-only. This is a core feature with no web access.

```
Files to create:
  frontend/src/pages/literature.tsx      ← New page (~300 lines)
  frontend/src/api/literature.ts         ← New API client
  frontend/src/components/literature/paper-card.tsx ← New component
Files to modify:
  frontend/src/App.tsx                   ← Add /literature route
  frontend/src/components/layout/sidebar.tsx ← Add "Literature" with BookOpen icon
  backend/api/routes/literature.py       ← New route file
  backend/api/app.py                     ← Register literature router
```

**New backend endpoint:**
```
GET /api/v1/literature/search?q=...&sources=semantic_scholar,arxiv&limit=20
→ { papers: PaperSummary[], total: int }
```

**Literature page shows:**
- Search bar with source selection (checkboxes: Semantic Scholar, arXiv, OpenAlex)
- Year range filter
- Results grid: paper cards with title, authors, year, citations, abstract preview, source badge
- Click paper → detail view (full abstract, authors, URLs)
- "Ingest" button per paper (adds to knowledge base)

**Acceptance Criteria:**
- [ ] User can search academic literature from the web UI
- [ ] Results show key metadata (citations, year, source)
- [ ] Papers can be ingested into the knowledge base with one click

### 2.7 PDF Upload / Ingestion UI

**Problem:** PDF ingestion is CLI-only.

```
Files to create:
  frontend/src/components/knowledge/upload-zone.tsx ← New component
Files to modify:
  frontend/src/pages/knowledge-search.tsx ← Add upload section
  backend/api/routes/knowledge.py        ← Add POST /ingest endpoint
```

**Knowledge page enhancement:**
- "Upload PDF" drop zone at the top
- Drag-and-drop or click-to-browse
- Progress indicator during ingestion
- Success/error toast

**New backend endpoint:**
```
POST /api/v1/knowledge/ingest
→ multipart/form-data with PDF file
→ { paper_id, chunks_added, status }
```

**Acceptance Criteria:**
- [ ] User can upload a PDF via drag-and-drop
- [ ] Uploaded papers appear in knowledge search results within 30 seconds
- [ ] Upload errors are shown with clear messages

### 2.8 Knowledge Base Stats Enhancement

**Problem:** `/knowledge/stats` returns only 3 fields. Frontend doesn't call it.

```
Files to modify:
  backend/api/routes/knowledge.py        ← Enrich /stats response
  frontend/src/pages/knowledge-search.tsx ← Show stats banner
```

**Enriched stats:**
```json
{
  "document_count": 245,
  "collection": "papers",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "sources": {"arxiv": 120, "semantic_scholar": 80, "openalex": 45},
  "last_updated": "2026-05-01T12:00:00Z"
}
```

**UI:** Stats banner at top of Knowledge page: "245 documents indexed from 3 sources"

**Acceptance Criteria:**
- [ ] Knowledge page shows document count and source breakdown
- [ ] Stats update after ingestion

---

## PHASE 3: Intelligence & Autonomy UX

**Goal:** The platform's most advanced capabilities (self-improvement, autonomous cycles, knowledge graph, scheduler) are visible, controllable, and understandable from the UI.

### 3.1 Knowledge Graph Explorer

**Problem:** The knowledge graph is one of the most powerful subsystems but has zero visual representation.

```
Files to create:
  frontend/src/pages/knowledge-graph.tsx  ← New page (~350 lines)
  frontend/src/api/knowledge-graph.ts    ← New API client
  frontend/src/components/knowledge-graph/graph-canvas.tsx ← D3/force-directed
  frontend/src/components/knowledge-graph/entity-detail.tsx ← New component
  backend/api/routes/knowledge.py        ← Add graph endpoints
```

**New backend endpoints:**
```
GET /api/v1/knowledge/graph/stats        → entity/relationship counts, type breakdown
GET /api/v1/knowledge/graph/entities?type=PAPER&limit=50 → entity list
GET /api/v1/knowledge/graph/entity/{id}  → entity detail + relationships
GET /api/v1/knowledge/graph/subgraph?center={id}&depth=2 → neighborhood
```

**Knowledge Graph page shows:**
- Stats bar: entity count, relationship count, type distribution
- Interactive force-directed graph (D3.js or react-force-graph)
- Click entity → detail panel (properties, truth value, relationships)
- Filter by entity type (paper, concept, method, dataset)
- Search entities by name

**Acceptance Criteria:**
- [ ] User can see the knowledge graph as a visual network
- [ ] Clicking a node shows its properties and relationships
- [ ] Graph can be filtered by entity type

### 3.2 Autonomous Cycle Dashboard

**Problem:** Autonomous cycles run as a black box. No monitoring, no progress, no control.

```
Files to create:
  frontend/src/pages/autonomous.tsx      ← New page (~300 lines)
  frontend/src/api/autonomous.ts         ← New API client
  backend/api/routes/pipeline.py         ← Enhance autonomous endpoint
Files to modify:
  frontend/src/components/layout/sidebar.tsx ← Add "Autonomous" with Bot icon
  frontend/src/components/pipeline/autonomous-form.tsx ← Move to standalone page
```

**Autonomous Dashboard shows:**
- Current cycle status (idle / running / completed)
- Cycle configuration (domain, max runs)
- Run-by-run progress (which run, which state in the consciousness machine)
- Total ideas generated across all runs
- Start / Stop / Pause controls
- Cycle history table (past cycles with summaries)

**New backend endpoints:**
```
GET /api/v1/pipeline/autonomous/status   → current cycle state
POST /api/v1/pipeline/autonomous/stop    → stop current cycle
GET /api/v1/pipeline/autonomous/history  → past cycles
```

**Acceptance Criteria:**
- [ ] User can start, monitor, and stop autonomous cycles from the UI
- [ ] Consciousness state machine transitions are visible
- [ ] Historical cycles are browsable

### 3.3 Scheduler UI

**Problem:** Backend has scheduler start/stop/status endpoints — but no UI.

```
Files to modify:
  frontend/src/pages/autonomous.tsx      ← Add scheduler section
  frontend/src/api/pipeline.ts           ← Add scheduler API calls
```

**Scheduler section on Autonomous page:**
- "Schedule automated runs" toggle
- Interval selector (hourly / daily / weekly)
- Domain selector
- Start / Stop buttons
- Next scheduled run countdown
- Run history (last 10 scheduled runs)

**Acceptance Criteria:**
- [ ] User can configure and control the scheduler from the UI
- [ ] Next run time is displayed
- [ ] Scheduler can be stopped cleanly

### 3.4 Self-Improvement Dashboard

**Problem:** The evolutionary engine and lesson extraction run silently. Users can't see what the platform has learned.

```
Files to create:
  frontend/src/components/settings/self-improve-section.tsx ← New component
Files to modify:
  frontend/src/pages/settings.tsx        ← Add self-improvement section
  backend/api/routes/status.py           ← Add evolution stats endpoint
```

**Self-Improvement section shows:**
- Evolution status: enabled/disabled toggle
- Current parameters (temperatures, top_k, rounds)
- Evolution history: parameter changes over time (sparkline chart)
- Lessons learned: last 10 extracted lessons as a list
- Fitness score trend: composite score over last N runs
- "Reset to defaults" button

**New backend endpoint:**
```
GET /api/v1/status/evolution
→ { enabled, current_params, fitness_history, recent_lessons, generation_count }
```

**Acceptance Criteria:**
- [ ] User can see what parameters the system has evolved
- [ ] Fitness trend is visible
- [ ] Recent lessons are displayed

### 3.5 World Model Viewer

**Problem:** The world model tracks the research landscape over time — invisible to users.

```
Files to create:
  frontend/src/components/knowledge-graph/world-model-panel.tsx ← New component
Files to modify:
  frontend/src/pages/knowledge-graph.tsx  ← Add world model section
  backend/api/routes/knowledge.py        ← Add world model endpoint
```

**World Model section shows:**
- Topic trends (most explored topics over time)
- Gap closure rate (how many gaps have been addressed)
- Idea generation rate over time
- Knowledge graph growth chart
- "Hot topics" — areas getting the most attention

**New backend endpoint:**
```
GET /api/v1/knowledge/world-model
→ { topics, gap_closure_rate, idea_trends, graph_growth }
```

**Acceptance Criteria:**
- [ ] User can see what the platform knows about the research landscape
- [ ] Trends are visible over time

---

## PHASE 4: Production Hardening

**Goal:** The platform is reliable, performant, secure, and deployable.

### 4.1 Authentication & Authorization

**Problem:** API key auth is binary (valid/invalid). No user concept, no roles, no sessions.

```
Files to create:
  backend/api/routes/auth.py             ← New: login, register, token endpoints
  backend/db/models.py                   ← Add User table
  backend/api/deps.py                    ← New: dependency injection for current_user
  backend/db/alembic/                    ← Migration framework
Files to modify:
  backend/api/auth.py                    ← JWT-based auth
  backend/api/app.py                     ← Register auth routes
```

**Implementation:**
- User model: email, password_hash, role (admin/user), api_key
- JWT token auth for API
- Login page on frontend
- Role-based access (admin can see costs, traces; user can see their own data)

**Acceptance Criteria:**
- [ ] Users must authenticate to use the API
- [ ] JWT tokens expire and can be refreshed
- [ ] Each user sees only their own data

### 4.2 Database Migration

**Problem:** Using SQLite with no migration tool. Alembic is a dependency but not configured.

```
Files to create:
  alembic.ini                            ← Alembic configuration
  backend/db/alembic/env.py              ← Migration environment
  backend/db/alembic/versions/           ← Migration directory
Files to modify:
  backend/db/database.py                 ← Use Alembic for schema management
```

**Tasks:**
- Initialize Alembic with current schema
- Create initial migration
- Add `erock db upgrade` / `erock db downgrade` CLI commands
- Document migration workflow

**Acceptance Criteria:**
- [ ] `alembic upgrade head` creates all tables
- [ ] Schema changes go through migrations, not direct DDL
- [ ] Database can be reset to a clean state

### 4.3 Database Upgrade: PostgreSQL Support

**Problem:** SQLite won't handle concurrent users in production.

```
Files to modify:
  backend/db/database.py                 ← Support PostgreSQL connection string
  backend/config.py                      ← Document PostgreSQL URL format
  pyproject.toml                         ← Add psycopg2-binary optional dep
  docker-compose.yml                     ← New: PostgreSQL + app containers
```

**Docker Compose:**
```yaml
services:
  db:
    image: postgres:16
  backend:
    build: .
    depends_on: [db]
  frontend:
    build: ./frontend
    depends_on: [backend]
```

**Acceptance Criteria:**
- [ ] Platform works with both SQLite (dev) and PostgreSQL (prod)
- [ ] Docker Compose starts the full stack
- [ ] Connection string is configurable via env var

### 4.4 SSE Auth Fix

**Problem:** API key is passed as a query parameter for SSE connections — appears in logs and browser history.

```
Files to modify:
  frontend/src/api/client.ts             ← Remove api_key from URL
  backend/api/routes/pipeline.py         ← Accept API key via header in SSE
  backend/api/auth.py                    ← Support query-param auth as fallback only
```

**Solution:** Use the `Authorization: Bearer <token>` header for EventSource by using a custom `fetch`-based SSE client instead of native `EventSource`.

**Acceptance Criteria:**
- [ ] API keys never appear in URLs
- [ ] SSE connections authenticate via headers

### 4.5 Responsive Design

**Problem:** Sidebar + multi-column grid doesn't work on mobile/tablet.

```
Files to modify:
  frontend/src/components/layout/app-shell.tsx ← Mobile drawer nav
  frontend/src/components/layout/sidebar.tsx ← Mobile: bottom nav bar
  frontend/src/pages/dashboard.tsx       ← Single-column on mobile
  frontend/src/pages/ideas-browser.tsx   ← Single-column on mobile
  frontend/src/components/pipeline/run-config-form.tsx ← Stack on mobile
  frontend/tailwind.config.js            ← Ensure responsive breakpoints
```

**Mobile adaptations:**
- Sidebar becomes a bottom navigation bar on screens < 768px
- 2-column grids become single-column
- Forms stack vertically
- Cards become full-width

**Acceptance Criteria:**
- [ ] All pages are usable on 375px width (iPhone SE)
- [ ] Navigation works via bottom bar on mobile
- [ ] No horizontal scrolling on any page

### 4.6 Performance Optimization

**Problem:** Dashboard fetches 200 ideas + 50 runs eagerly for charts. No pagination on gaps.

```
Files to modify:
  frontend/src/pages/dashboard.tsx       ← Lazy-load chart data
  frontend/src/pages/gaps-explorer.tsx   ← Add pagination
  backend/api/routes/gaps.py             ← Add pagination params
  backend/api/routes/ideas.py            ← Optimize query for dashboard
```

**Optimizations:**
- Dashboard charts: fetch in background after initial render, show "Loading analytics..."
- Gaps: 20-per-page pagination (matching Ideas browser)
- Ideas: add database index on `(domain, overall_score)` for faster filtering
- Add query count logging in debug mode

**Acceptance Criteria:**
- [ ] Dashboard renders in under 1 second with empty data
- [ ] Dashboard renders in under 3 seconds with 1000+ ideas
- [ ] Gaps page has working pagination

### 4.7 Monitoring & Alerting

**Problem:** No production monitoring. Pipeline failures are silent.

```
Files to create:
  backend/pipeline/notifications/        ← New module
  backend/pipeline/notifications/webhook.py   ← Webhook notifications
  backend/pipeline/notifications/email.py     ← Email notifications (optional)
Files to modify:
  backend/pipeline/orchestrator.py       ← Add notification hooks
  backend/config.py                      ← Add notification config
```

**Notification events:**
- Pipeline completed (with summary)
- Pipeline failed (with error)
- Autonomous cycle completed (with total results)
- Budget threshold exceeded (50%, 80%, 100%)
- Governance approval needed

**Channels:**
- Webhook (generic HTTP POST)
- Browser notification (via frontend)
- Email (optional, via SMTP)

**Acceptance Criteria:**
- [ ] User receives a webhook when a pipeline completes
- [ ] Budget alerts fire at 50%, 80%, 100%
- [ ] Browser notifications work when the tab is in background

---

## PHASE 5: Growth & Ecosystem

**Goal:** The platform is extensible, documented, and ready for a community.

### 5.1 Plugin Marketplace

**Problem:** Plugin system exists but has no marketplace or UI.

```
Files to create:
  frontend/src/pages/plugins.tsx         ← New page
  backend/api/routes/plugins.py          ← New route
  docs/plugin-guide.md                   ← Plugin development guide
```

**Plugin page:**
- Installed plugins list
- Available plugins (from registry)
- Install / Uninstall buttons
- Plugin configuration forms

### 5.2 Export Enhancements

**Problem:** Only Markdown and LaTeX export. No bulk export. No PDF.

```
Files to modify:
  backend/pipeline/export/export_service.py ← Add PDF export via WeasyPrint
  frontend/src/pages/ideas-browser.tsx   ← Add bulk export
  frontend/src/components/ideas/export-button.tsx ← Add PDF option
```

**New capabilities:**
- PDF export (already have WeasyPrint dependency)
- Bulk export: select multiple ideas → download ZIP of proposals
- Export to Notion/Obsidian format

### 5.3 Collaboration Features

**Problem:** Single-user system. No sharing, no comments, no teams.

```
Files to create:
  backend/api/routes/collaboration.py    ← New: sharing, comments
  backend/db/models.py                   ← Add Comment, SharedIdea tables
  frontend/src/components/ideas/comments.tsx ← Comment thread
```

**Features:**
- Share idea via link (public or team-only)
- Comment thread on each idea
- Team workspace (group of users sharing runs/ideas)

### 5.4 CLI Enhancement

**Problem:** CLI doesn't show proposal content. No `erock open` command.

```
Files to modify:
  backend/cli/main.py                    ← Enhance generate output
Files to create:
  backend/cli/commands/open.py           ← New: open idea in browser
```

**New commands:**
- `erock open <idea_id>` — open idea in default browser
- `erock proposal <idea_id>` — print full proposal to terminal
- `erock export <idea_id> --format pdf` — export single idea

### 5.5 Documentation Site

**Problem:** No user-facing documentation beyond README.

```
Files to create:
  docs/                                  ← Documentation structure
  docs/getting-started.md
  docs/cli-reference.md
  docs/api-reference.md
  docs/configuration.md
  docs/architecture.md
  docs/contributing.md
  docs/deployment.md
  docs/changelog.md
```

**Documentation site:**
- MkDocs or Docusaurus
- Auto-deployed via GitHub Pages
- API reference synced with FastAPI OpenAPI schema

### 5.6 Internationalization (i18n)

**Problem:** English only.

```
Files to modify:
  frontend/                              ← Add react-i18next
  backend/api/                           ← Accept-Language header support
```

**Phase 5 scope:** Add i18n infrastructure. Actual translations are ongoing.

---

## Dependency Graph

```
Phase 0: Foundation
  ├── 0.1 Onboarding Wizard
  ├── 0.2 One-Command Start
  ├── 0.3 README Rewrite
  ├── 0.4 API Documentation
  ├── 0.5 Error Message Audit
  └── 0.6 Frontend Test Infrastructure
        │
Phase 1: Core UX (depends on Phase 0)
  ├── 1.1 Pipeline Results Flow
  ├── 1.2 Run Detail Page
  ├── 1.3 Pipeline Form Completion
  ├── 1.4 Ideas Browser Enhancement
  ├── 1.5 Gap ↔ Idea Traceability
  ├── 1.6 Settings Enhancement
  └── 1.7 Cancel Pipeline from UI
        │
Phase 2: Feature Parity (depends on Phase 1)
  ├── 2.1 Cost Dashboard
  ├── 2.2 Memory Browser
  ├── 2.3 Governance Queue
  ├── 2.4 Observability / Traces Viewer
  ├── 2.5 Session Management UI
  ├── 2.6 Literature Search UI
  ├── 2.7 PDF Upload / Ingestion UI
  └── 2.8 Knowledge Base Stats
        │
Phase 3: Intelligence & Autonomy UX (depends on Phase 2)
  ├── 3.1 Knowledge Graph Explorer
  ├── 3.2 Autonomous Cycle Dashboard
  ├── 3.3 Scheduler UI
  ├── 3.4 Self-Improvement Dashboard
  └── 3.5 World Model Viewer
        │
Phase 4: Production Hardening (depends on Phase 3)
  ├── 4.1 Authentication & Authorization
  ├── 4.2 Database Migration
  ├── 4.3 PostgreSQL Support
  ├── 4.4 SSE Auth Fix
  ├── 4.5 Responsive Design
  ├── 4.6 Performance Optimization
  └── 4.7 Monitoring & Alerting
        │
Phase 5: Growth & Ecosystem (depends on Phase 4)
  ├── 5.1 Plugin Marketplace
  ├── 5.2 Export Enhancements
  ├── 5.3 Collaboration Features
  ├── 5.4 CLI Enhancement
  ├── 5.5 Documentation Site
  └── 5.6 Internationalization
```

---

## Priority Matrix

| Priority | Items | Rationale |
|:---|:---|:---|
| **P0 — Ship Blockers** | 0.1, 0.2, 0.3, 1.1, 1.2, 1.3 | Users can't get started or see results |
| **P1 — Core Value** | 1.4, 1.5, 1.6, 1.7, 2.6, 2.7 | Core journey must be complete |
| **P2 — Power Features** | 2.1, 2.2, 2.3, 2.4, 2.5, 2.8 | Backend capabilities must be visible |
| **P3 — Intelligence** | 3.1, 3.2, 3.3, 3.4, 3.5 | Differentiating features |
| **P4 — Production** | 4.1–4.7 | Required for multi-user deployment |
| **P5 — Growth** | 5.1–5.6 | Required for community adoption |

---

## New Frontend Files Summary

| Phase | New Files | New Pages | Modified Files |
|:---|:---|:---|:---|
| **0** | 15 test files | 0 | 4 |
| **1** | 1 page, 1 API client | 1 (run-detail) | 7 |
| **2** | 7 pages, 5 API clients, 8 components | 7 | 5 |
| **3** | 4 components, 1 API client | 2 (knowledge-graph, autonomous) | 5 |
| **4** | 3 components | 0 | 12 |
| **5** | 8+ docs, 2 components | 1 (plugins) | 6 |
| **Total** | **~50 new files** | **~11 new pages** | **~39 modified files** |

---

## New Backend Endpoints Summary

| Phase | New Endpoints |
|:---|:---|
| **1** | `GET /runs/{id}/ideas`, `GET /status/detailed` |
| **2** | `GET /literature/search`, `POST /knowledge/ingest`, `GET /knowledge/graph/stats`, `GET /knowledge/graph/entities`, `GET /knowledge/graph/entity/{id}`, `GET /knowledge/graph/subgraph`, `GET /status/evolution`, `GET /knowledge/world-model` |
| **3** | `GET /autonomous/status`, `POST /autonomous/stop`, `GET /autonomous/history` |
| **4** | `POST /auth/login`, `POST /auth/register`, `GET /auth/me` |
| **5** | `GET /plugins`, `POST /plugins/install/{id}`, `DELETE /plugins/{id}` |
| **Total** | **~18 new endpoints** |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|:---|:---|:---|:---|
| Knowledge graph visualization is too slow with 10K+ entities | Medium | High | Implement clustering/zooming, limit initial render to 100 entities |
| PostgreSQL migration breaks SQLite compatibility | Low | High | Test both DBs in CI, maintain dual compatibility |
| SSE auth refactor breaks existing connections | Medium | Medium | Gradual rollout, keep query-param auth as fallback |
| Responsive design requires component rewrites | Medium | Medium | Use Tailwind responsive utilities, no component rewrites |
| Feature parity increases frontend bundle size | Low | Medium | Lazy-load pages, code splitting (already started with chart lazy-loading) |

---

## Success Metrics

| Metric | Current (v0.1.0) | Target (v1.0) |
|:---|:---|:---|
| Time to first idea | ~30 min | < 5 min |
| Frontend-backend parity | 40% | 90% |
| Frontend pages | 7 | 14+ |
| Frontend test coverage | ~30% | 70%+ |
| API endpoints documented | 0% | 100% |
| Mobile usable | No | Yes |
| Concurrent users supported | 1 (SQLite) | 50+ (PostgreSQL) |
| Error messages with remediation | ~50% | 100% |
| Post-pipeline result flow | Manual navigation | Auto-displayed |
| Average pipeline run visibility | Stage names only | Stage + cost + ETA + progress |
