# Elephant Rock Research Platform — Comprehensive UX & User Journey Report

**Date:** 2026-05-01  
**Analyst:** AI Agent (Session 260501-ivory-wolf)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [User Personas](#2-user-personas)
3. [Onboarding Journey](#3-onboarding-journey)
4. [CLI User Experience](#4-cli-user-experience)
5. [Web UI User Experience](#5-web-ui-user-experience)
6. [API Developer Experience](#6-api-developer-experience)
7. [End-to-End User Journeys](#7-end-to-end-user-journeys)
8. [Interaction Design Patterns](#8-interaction-design-patterns)
9. [Error Handling & Recovery](#9-error-handling--recovery)
10. [Feedback Loops](#10-feedback-loops)
11. [Gaps, Frictions & Pain Points](#11-gaps-frictions--pain-points)
12. [Recommendations](#12-recommendations)

---

## 1. Executive Summary

The Elephant Rock Research Platform serves users through **three distinct interfaces**: a feature-rich CLI (`erock`), a React-based web UI, and a RESTful API. The platform's core value proposition is automating the entire academic research ideation pipeline — from literature discovery to exportable research proposals.

**Overall UX Assessment**: The platform provides a **powerful but complex** experience. The backend is extraordinarily capable (250+ config parameters, 30+ API endpoints, 12 CLI commands), but this power creates a significant **cognitive load** for new users. The onboarding path is unclear, the web UI is functional but sparse, and there are notable gaps between backend capabilities and frontend exposure.

| Interface | Maturity | Usability | Feature Parity |
|:---|:---|:---|:---|
| **CLI** | High | Good | Full backend access |
| **Web UI** | Medium | Adequate | ~40% of backend surfaced |
| **API** | High | Good | Full backend access |

---

## 2. User Personas

### Persona 1: "Dr. Researcher" (Primary)
- **Role**: Academic researcher or PhD student
- **Goal**: Generate novel research ideas in their domain
- **Technical skill**: Moderate (comfortable with command line, basic API usage)
- **Primary interface**: Web UI + CLI
- **Key need**: "Give me research ideas I can actually pursue"
- **Patience level**: Low — wants results in minutes, not hours of configuration

### Persona 2: "Alex the Engineer" (Secondary)
- **Role**: ML/AI engineer exploring research directions
- **Goal**: Rapidly explore multiple research domains
- **Technical skill**: High (API integration, scripting)
- **Primary interface**: API + CLI
- **Key need**: "Automate research exploration at scale"

### Persona 3: "Sam the Student" (Tertiary)
- **Role**: Graduate student looking for thesis topics
- **Goal**: Find interesting, feasible research problems
- **Technical skill**: Low-moderate
- **Primary interface**: Web UI exclusively
- **Key need**: "Help me understand what's novel and feasible"

---

## 3. Onboarding Journey

### 3.1 First Contact — What the User Sees

The README provides a minimal quick-start:

```bash
cp .env.example .env   # Add your API keys
pip install -e ".[dev]"
erock search "chain-of-thought reasoning"
erock generate --domain "AI/NLP" --rounds 2 --ideas 3
```

**Assessment**:
- ✅ **Strength**: Three commands to first value — concise and action-oriented
- ❌ **Gap**: No mention of starting the API server for web UI
- ❌ **Gap**: No mention of frontend setup (`cd frontend && npm install && npm run dev`)
- ❌ **Gap**: `.env.example` has 15+ config keys — overwhelming for first-time user
- ❌ **Gap**: No "getting started" guide, tutorial, or walkthrough
- ❌ **Gap**: No default API key — user must provide one immediately

### 3.2 Environment Setup Friction Points

**Required decisions before first use:**

| Step | Decision Required | Default | Friction |
|:---|:---|:---|:---|
| 1. Choose LLM provider | Which of 5 providers? | openai | 🔴 High — requires API key |
| 2. Get API key | OpenAI/Anthropic/Gemini signup | None | 🔴 High — external step |
| 3. Configure embeddings | Provider + model | openai/text-embedding-3-small | 🟡 Medium — reasonable default |
| 4. Database setup | SQLite URL | sqlite:///./data/elephant_rock.db | 🟢 Low — auto-creates |
| 5. Optional: Academic APIs | Semantic Scholar, OpenAlex keys | None | 🟢 Low — optional |

**The critical path requires an LLM API key**. Without it, the platform is unusable. The error when a key is missing is a `SystemExit` — abrupt and not user-friendly.

### 3.3 First-Run Experience

**CLI first run (`erock generate --domain "AI/NLP"`):**
```
Starting Pipeline
Domain: AI/NLP
Gaps: 5 | Rounds: 2 | Ideas/round: 3
Novelty: True | Feasibility: True | Export: markdown
```

**What the user experiences:**
1. A status spinner with stage names ("Stage 1/8: Literature Search (5s)")
2. A potentially **long wait** (5-15+ minutes depending on provider/load)
3. No indication of total expected time
4. No way to see intermediate results
5. Finally, idea panels appear with scores

**Assessment:**
- ✅ Rich Panel-based output is attractive
- ✅ Score guide appended at the bottom
- ❌ No progress percentage or ETA
- ❌ No way to explore results while pipeline is still running
- ❌ No notification when complete (for long-running tasks)
- ❌ Errors appear as raw Python tracebacks unless `--debug` is used

### 3.4 Web UI First Launch

**User navigates to `http://localhost:3000`:**
1. Sees the Dashboard page with empty state
2. Three stat cards show: "Total Runs: 0", "Total Ideas: 0", "System: Elephant Rock Research v0.1.0"
3. No analytics charts (no data)
4. Empty "Recent Runs" section with prompt: "No runs yet. Start your first pipeline!"
5. Empty "Recent Ideas" section with prompt: "No ideas generated yet."

**Assessment:**
- ✅ Clean empty states with call-to-action
- ✅ "New run" link takes user directly to pipeline configuration
- ❌ No onboarding tutorial or guided tour
- ❌ No explanation of what the platform does on the Dashboard
- ❌ No way to know the backend isn't running (just shows loading/empty states)
- ❌ Settings page requires knowing the API URL — not auto-detected

---

## 4. CLI User Experience

### 4.1 Command Inventory

| Command | Purpose | User Value |
|:---|:---|:---|
| `erock search "query"` | Search academic literature | 🔴 Immediate — but results require next step |
| `erock generate` | Run full pipeline | 🟢 Core value — generates complete proposals |
| `erock novelty-check "idea"` | Check idea novelty | 🟡 Useful for quick validation |
| `erock feasibility-score "idea"` | Score feasibility | 🟡 Useful for quick validation |
| `erock ingest file.pdf` | Ingest PDF | 🟢 Power user feature |
| `erock autonomous` | Autonomous cycles | 🟢 Advanced — great for power users |
| `erock ideas` | List stored ideas | 🟢 Review past results |
| `erock runs` | List pipeline runs | 🟡 Monitor history |
| `erock gaps` | List research gaps | 🟡 Explore knowledge frontier |
| `erock knowledge search "q"` | Search knowledge base | 🟡 Explore indexed papers |
| `erock status` | Platform status | 🟢 Debugging/config check |
| `erock config` | Display config | 🟢 Debugging |

### 4.2 CLI Output Quality

**Search results** — Tabular with columns: #, Title, Year, Citations, Source
- ✅ Clean table formatting via Rich
- ❌ No way to save/export results
- ❌ No pagination — all results shown at once

**Generate output** — Panel-based idea cards with scores
- ✅ Beautiful formatting with Rich Panels
- ✅ Score guide appended for interpretation
- ❌ Long titles truncated
- ❌ No way to open a specific idea for more detail from CLI
- ❌ Export path is printed but not made clickable

**Status/config commands:**
- ✅ Clean Panel-based display
- ✅ Key information visible at a glance

### 4.3 CLI Error Experience

The CLI wraps all errors with `_run_async()` which provides:
- `ImportError`: "Missing dependency" panel with install instructions
- `ConnectionError`: "Network error" panel with guidance
- Generic `Exception`: Error type + message panel
- `--debug` flag: Full traceback

**Assessment:**
- ✅ Good error categorization with contextual help
- ✅ `--debug` flag is well-designed
- ❌ No "did you mean?" or suggestion system
- ❌ API key errors show as raw `SystemExit` (bypasses the error handler)

---

## 5. Web UI User Experience

### 5.1 Navigation Architecture

```
┌──────────────────────────────────────────────────┐
│  Sidebar (collapsible, 56px/224px)               │
│  ┌──────────────────────────────────────────┐    │
│  │ 📊 Dashboard                            │    │
│  │ ▶ Pipeline                              │    │
│  │ 💡 Ideas                                │    │
│  │ 🔀 Gaps                                 │    │
│  │ 🔍 Knowledge                            │    │
│  │ ⚙ Settings                              │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  Main Content Area (scrollable)                   │
└──────────────────────────────────────────────────┘
```

**Assessment:**
- ✅ Clean, minimal sidebar with icons + labels
- ✅ Collapsible sidebar (hamburger toggle)
- ✅ Active state highlighting on current route
- ✅ Consistent page header pattern (title + description)
- ❌ No breadcrumbs for deep navigation
- ❌ No notification badge for running pipelines
- ❌ No search across the entire app
- ❌ No "back" navigation pattern on detail pages (except Idea Detail)

### 5.2 Page-by-Page Analysis

#### Dashboard (`/`)

**Content:**
- 3 stat cards: Total Runs, Total Ideas, System info
- Analytics section (lazy-loaded): Score Distribution bar chart, Run Status pie chart, Ideas by Domain pie chart
- Recent Runs list (5 latest)
- Recent Ideas list (5 latest)

**Strengths:**
- ✅ Lazy-loaded charts don't block initial render
- ✅ Charts use Recharts with professional styling
- ✅ Empty states have icons and actionable text
- ✅ "New run" and "View all" quick links

**Weaknesses:**
- ❌ Dashboard queries 200 ideas + 50 runs eagerly for charts (potential perf issue)
- ❌ No "Quick Start" card or onboarding for first-time users
- ❌ No real-time updates (no WebSocket/SSE for running pipeline status on dashboard)
- ❌ RunCard doesn't link to run detail page (no click handler for dashboard cards)
- ❌ System card just shows app name/version — low information density
- ❌ No cost/token usage overview on dashboard
- ❌ No "last pipeline run" status indicator

#### Pipeline Page (`/pipeline/new`)

**Content:**
- Tab selector: "Single Run" | "Autonomous Cycle"
- **Single Run form**: Domain, Max Gaps (1-50), Ideas Per Round (1-20), Search Queries
- **Autonomous form**: Domain, Max Runs (1-20)
- Progress view: 8-stage vertical stepper with SSE real-time updates

**Strengths:**
- ✅ Clean form layout with sensible defaults
- ✅ Real-time SSE progress tracking with stage status indicators
- ✅ Visual distinction between pending/running/completed stages
- ✅ Elapsed time shown per stage
- ✅ Connection status badge (Connecting.../Live/Complete)
- ✅ Error displayed in destructive-styled card
- ✅ Autonomous cycle option for power users

**Weaknesses:**
- ❌ **No generation_rounds field** in the UI form (backend supports it, but form hardcodes `ideas_per_round: 5`)
- ❌ **No toggle for novelty/feasibility/synthesis** — form always sends defaults (all true)
- ❌ **No export format selector** — always defaults to markdown
- ❌ **No search query builder** — just a comma-separated text input with no guidance
- ❌ No estimated cost/time before starting
- ❌ No cancel button visible during execution (must navigate away)
- ❌ **No results shown after completion** — user must navigate to Ideas page manually
- ❌ No "Run Again" or "New Configuration" button after completion
- ❌ The form disappears after starting — no way to start another run without refreshing
- ❌ Max Gaps range in form (1-50) doesn't match API validation (1-20)

#### Ideas Browser (`/ideas`)

**Content:**
- Domain filter text input
- Paginated grid (2-column) of IdeaCards
- Pagination controls (Previous/Next, page indicator)

**Strengths:**
- ✅ Clean card layout with click-through to detail
- ✅ ScoreBadge shows both novelty and feasibility at a glance
- ✅ Domain filter for quick narrowing
- ✅ Pagination with page count
- ✅ Empty state with contextual message

**Weaknesses:**
- ❌ **No sort options** (by score, by date, by novelty, etc.)
- ❌ **No min-score slider/filter** (backend supports `min_score` but UI doesn't expose it)
- ❌ **No overall score displayed** on IdeaCard — only novelty + feasibility
- ❌ No multi-select or batch operations
- ❌ No keyword search (only domain filter)
- ❌ Cards show truncated title with `line-clamp-2` — hard to distinguish similar ideas
- ❌ No indication of whether proposal exists for an idea

#### Idea Detail (`/ideas/:id`)

**Content:**
- Back navigation button
- Title + domain + score badges
- Export buttons (Markdown/LaTeX download)
- Refine button (re-runs novelty/feasibility)
- Problem Statement (Markdown rendered)
- Proposed Method (Markdown rendered)
- Expected Contributions (Markdown rendered)
- Tabbed section: Proposal | Novelty Report | Feasibility Report
- Feedback form (5-star rating + textarea)

**Strengths:**
- ✅ Most content-rich page — shows all idea information
- ✅ Markdown rendering with KaTeX math support and syntax highlighting
- ✅ Novelty report has visual score bars with color coding
- ✅ Feasibility report has score bars + risks + timeline badge
- ✅ Star-based feedback with hover effects
- ✅ Client-side file download (Markdown + LaTeX)
- ✅ Refine button re-evaluates the idea with current knowledge

**Weaknesses:**
- ❌ **No loading indicator during refinement** — just the button goes disabled with spinner
- ❌ **No confirmation before refinement** — it's irreversible and costs API tokens
- ❌ Score badges don't visually update after refinement (need query invalidation)
- ❌ **No "related ideas" or "similar proposals" section**
- ❌ **No link back to the source gap** that generated this idea
- ❌ **No link to the pipeline run** that produced it
- ❌ **No reference validation results shown** (backend computes but frontend doesn't display)
- ❌ Feedback notes field has character limit (2000) but no character counter
- ❌ No edit functionality — can't modify idea text
- ❌ No delete functionality
- ❌ Proposal sections tab content can be very long — no table of contents or navigation

#### Gaps Explorer (`/gaps`)

**Content:**
- List of GapCards sorted by confidence
- Each card: title, description, gap_type badge, potential_impact, confidence bar

**Strengths:**
- ✅ Clean card layout with confidence visualization
- ✅ Color-coded confidence bars (red → amber → green)
- ✅ Sorted by confidence by default
- ✅ Empty state with actionable prompt

**Weaknesses:**
- ❌ **No pagination** — loads all 50 gaps at once
- ❌ **No filtering by gap_type** (backend stores gap_type but no filter exposed)
- ❌ **No search/filter** — just a flat list
- ❌ **No click-through to gap detail** — no `/:id` route for gaps
- ❌ **No link to ideas generated from a gap**
- ❌ **No way to run pipeline targeting a specific gap**
- ❌ No way to dismiss/archive low-confidence gaps

#### Knowledge Search (`/knowledge`)

**Content:**
- Search input with form submission
- Result cards: text snippet, source badge, year badge, authors, relevance score

**Strengths:**
- ✅ Clean search interface with form submission pattern
- ✅ Relevance score with color-coded label (High/Medium/Low)
- ✅ Source and year metadata badges
- ✅ Error state and empty state with icons
- ✅ Text snippets truncated with `line-clamp-4`

**Weaknesses:**
- ❌ **No autocomplete or suggestions** — must type full query and submit
- ❌ **No search history** — every visit starts fresh
- ❌ **No advanced filters** (by year, by source, by author)
- ❌ **No way to see paper details** — just a snippet card
- ❌ **No way to ingest more papers** from the UI
- ❌ Search is fire-and-forget — no way to save/bookmark results
- ❌ No indication of knowledge base size or coverage

#### Settings (`/settings`)

**Content:**
- API Base URL input
- API Key input (password type)
- Theme toggle (Light/Dark)

**Strengths:**
- ✅ Simple and focused
- ✅ API key field is password-masked
- ✅ Dark mode support with CSS variables
- ✅ Settings persisted to localStorage

**Weaknesses:**
- ❌ **No "Test Connection" button** — user can't verify settings work
- ❌ **No feedback on save** — changes apply immediately with no confirmation
- ❌ **No API health check** — backend could be down and user wouldn't know
- ❌ Only 3 settings — many more could be useful (default domain, default provider, etc.)
- ❌ Theme is binary (light/dark) — no system preference detection

### 5.3 Missing Web UI Pages

These backend capabilities have **no frontend exposure**:

| Feature | Backend | Frontend |
|:---|:---|:---|
| Memory system | `/api/v1/memory/*` | ❌ No UI |
| Governance approvals | `/api/v1/governance/*` | ❌ No UI |
| Cost tracking | `/api/v1/costs/*` | ❌ No UI |
| Observability traces | `/api/v1/traces/*` | ❌ No UI |
| Session management | `/api/v1/pipeline/sessions/*` | ❌ No UI |
| Scheduler control | `/api/v1/pipeline/scheduler/*` | ❌ No UI |
| Pipeline resume | `POST /api/v1/pipeline/resume/{id}` | ❌ No UI |
| Idea filtering by min_score | `GET /ideas?min_score=X` | ❌ Not exposed |
| Pipeline run detail | `GET /pipeline/runs/detail/{id}` | ❌ No detail page |
| PDF ingestion | `POST` (CLI only) | ❌ No UI |
| Literature search | `erock search` (CLI only) | ❌ No UI |
| Knowledge base stats | `GET /knowledge/stats` | ❌ Not surfaced |

### 5.4 Visual Design

**Color System:**
- Primary: Blue (`hsl(221.2, 83.2%, 53.3%)`)
- Semantic colors: Green (success/high), Amber (moderate/warning), Red (error/low)
- Dark mode: Full CSS variable support
- Score badges: Contextual backgrounds (green/emerald/amber/red-100)

**Typography:**
- System font stack (`system-ui, -apple-system, sans-serif`)
- Clear hierarchy: 2xl bold titles, lg semibold section headers, sm body text

**Layout:**
- Sidebar + main content area
- Card-based layout throughout
- Grid system: `md:grid-cols-2` and `md:grid-cols-3` breakpoints

**Assessment:**
- ✅ Consistent design language using shadcn/ui primitives
- ✅ Professional color coding for scores and statuses
- ✅ Good use of loading skeletons
- ❌ No logo or branding beyond "Elephant Rock" text
- ❌ No illustrations or visual personality
- ❌ No animated transitions between pages
- ❌ No responsive mobile layout (sidebar + grid won't work on phones)

---

## 6. API Developer Experience

### 6.1 API Design Quality

**Strengths:**
- ✅ RESTful URL structure with versioning (`/api/v1/`)
- ✅ Consistent JSON request/response format
- ✅ Pydantic validation on all inputs with clear constraints
- ✅ API key authentication (optional, `X-API-Key` header)
- ✅ SSE endpoint for real-time progress
- ✅ Proper HTTP status codes (404, 503, 500)
- ✅ CORS enabled for cross-origin access

**Weaknesses:**
- ❌ No OpenAPI/Swagger UI documentation (FastAPI generates it but it's not promoted)
- ❌ No rate limit headers in responses
- ❌ SSE auth passes API key as query parameter (security concern — logged in URLs)
- ❌ No pagination metadata (total count returned but no `has_next` flag)
- ❌ No HATEOAS links in responses
- ❌ Pipeline run detail uses integer DB ID, but progress uses string run_id — confusing
- ❌ No webhook/callback for pipeline completion (only SSE polling)

### 6.2 API Error Experience

```json
// 404 Not Found
{"error": "Resource not found"}

// 401 Unauthorized
{"detail": "Invalid or missing API key"}

// 503 Service Unavailable
{"error": "ChromaDB not installed. Run: pip install chromadb"}
```

- ✅ Error messages are descriptive
- ✅ 503 errors include remediation hints
- ❌ Error response format is inconsistent (`error` vs `detail` field)
- ❌ No error codes or machine-readable error types
- ❌ No request ID for debugging

---

## 7. End-to-End User Journeys

### Journey 1: "First Research Idea" (New User — Web UI)

```
Step 1: Install & configure          Friction: 🔴 High
  ├── Clone repo
  ├── Copy .env.example → .env
  ├── Add OpenAI API key (must sign up)
  ├── pip install -e ".[dev]"
  ├── cd frontend && npm install
  ├── Start backend: uvicorn backend.api.app:app
  └── Start frontend: npm run dev

Step 2: Open browser                  Friction: 🟢 Low
  └── Navigate to http://localhost:3000

Step 3: Configure pipeline            Friction: 🟡 Medium
  ├── Click "Pipeline" in sidebar
  ├── Enter domain (e.g., "NLP")
  ├── Click "Start Pipeline"
  └── (No guidance on what to expect)

Step 4: Wait for completion            Friction: 🔴 High
  ├── Watch 8 stages progress (5-15 min)
  ├── No ETA shown
  ├── No intermediate results
  └── No cancel button visible

Step 5: Find results                   Friction: 🟡 Medium
  ├── Pipeline says "Complete"
  ├── No automatic navigation to results
  ├── Must click "Ideas" in sidebar
  └── Ideas appear with scores

Step 6: Explore an idea                Friction: 🟢 Low
  ├── Click on idea card
  ├── See full detail: problem, method, contributions
  ├── View novelty report with score bars
  ├── View feasibility report with timeline
  └── Read full proposal

Step 7: Provide feedback               Friction: 🟢 Low
  ├── Rate 1-5 stars
  ├── Add optional notes
  └── Submit

Step 8: Export                         Friction: 🟢 Low
  ├── Click "Markdown" or "LaTeX" button
  └── File downloads to browser

Total estimated friction: 🟡 Medium-High
Critical gap: Steps 1-2 have no guided setup wizard
Critical gap: Step 5 requires manual navigation
```

### Journey 2: "Quick Novelty Check" (Power User — CLI)

```
Step 1: Check novelty                  Friction: 🟢 Low
  $ erock novelty-check "Apply diffusion to theorem proving"
  
Step 2: Read report                    Friction: 🟢 Low
  ├── Overall score: 0.72
  ├── Method Novelty: 0.81
  ├── Problem Novelty: 0.65
  └── "High novelty — novel combination..."

Step 3: Check feasibility              Friction: 🟢 Low
  $ erock feasibility-score "Apply diffusion to theorem proving" \
      --method "Adapt DDPM for proof search" \
      --contributions "New theorem proving paradigm"

Total friction: 🟢 Low
This is the platform's best-designed journey.
```

### Journey 3: "Autonomous Research Cycle" (Advanced User)

```
Step 1: Start autonomous cycle         Friction: 🟡 Medium
  $ erock autonomous --domain "AI/NLP" --max-runs 5

Step 2: Wait (potentially hours)       Friction: 🔴 High
  ├── Multiple pipeline runs execute sequentially
  ├── No progress indication between runs
  ├── No way to check intermediate results
  └── No way to pause/resume

Step 3: Review results                 Friction: 🟡 Medium
  ├── CLI shows summary: "5 runs, 15 ideas"
  └── Must use `erock ideas` to explore

Critical gap: No real-time monitoring for autonomous cycles
Critical gap: No web UI for autonomous cycle management
```

### Journey 4: "Research Literature Exploration" (Graduate Student)

```
Step 1: Search literature              Friction: 🟢 Low
  $ erock search "transformer attention mechanisms"

Step 2: Browse results                 Friction: 🟡 Medium
  ├── Table shows 20-60 papers
  ├── Can see title, year, citations, source
  └── No way to save/favorite papers

Step 3: Ingest a paper                 Friction: 🟡 Medium
  $ erock ingest paper.pdf

Step 4: Search knowledge base          Friction: 🟢 Low
  $ erock knowledge search "attention mechanisms"

Critical gap: No way to go from "found a paper" to "generate ideas about it"
Critical gap: No web UI for literature search or ingestion
```

---

## 8. Interaction Design Patterns

### 8.1 Real-Time Feedback

**SSE Progress Tracking:**
```
Connecting... → Live → Stage updates → Complete
```
- ✅ Exponential backoff on SSE reconnection (max 5 retries)
- ✅ Heartbeat events prevent timeout
- ✅ Visual distinction between pending/running/completed stages
- ❌ No progress bar or percentage
- ❌ No estimated remaining time
- ❌ No notification sound or browser notification on completion

### 8.2 Data Loading States

**Pattern:** Skeleton loaders (rectangular pulsing placeholders)
- Used consistently across all pages
- ✅ Good: prevents layout shift
- ✅ Count matches expected content (3-6 skeletons)
- ❌ No error retry mechanism on failed queries

### 8.3 Empty States

All pages have empty state handling:
- Dashboard: "No runs yet. Start your first pipeline!"
- Ideas: "No ideas generated yet."
- Gaps: "No research gaps found. Run a pipeline to discover gaps."
- Knowledge: "No results found for 'query'."

**Assessment:**
- ✅ Empty states include actionable guidance
- ✅ Icons provide visual context (FlaskConical, Lightbulb, GitBranch, Database)
- ❌ No illustration or deeper explanation of what to do next

### 8.4 Loading Patterns

**TanStack Query Configuration:**
- `staleTime: 30_000` (30 seconds)
- `retry: 1` (single retry on failure)
- Query keys are well-structured: `["ideas", { limit: 20 }]`

**Assessment:**
- ✅ Sensible defaults for caching and retry
- ✅ Query invalidation after mutations (feedback, refinement)
- ❌ No optimistic updates (UI waits for server response)
- ❌ No background refetch indicator
- ❌ No infinite scroll for large datasets (uses pagination instead)

---

## 9. Error Handling & Recovery

### 9.1 Frontend Error Handling

**Global Error Boundary:**
```tsx
// Catches React render errors, shows:
// "Something went wrong" + [Reload] button
```

**API Error Handling:**
```tsx
// ApiError class with status + detail
// Thrown on non-OK responses
// Displayed via toast notifications (sonner)
```

**SSE Error Handling:**
```tsx
// Auto-reconnect with exponential backoff
// Max 5 retries, then shows error state
```

**Assessment:**
- ✅ Three-layer error handling (boundary + API + SSE)
- ✅ Toast notifications for mutation errors
- ❌ No error logging or reporting
- ❌ No "retry" button on failed queries (just auto-retry once)
- ❌ Error boundary doesn't preserve user state on reload
- ❌ SSE failure is silent after max retries — no user notification

### 9.2 Backend Error Handling

**API Error Hierarchy:**
- `APIError` (base) → `NotFoundError` (404) → `ServiceUnavailableError` (503)
- Generic handler catches all exceptions → 500

**Assessment:**
- ✅ Clean error hierarchy
- ✅ Structured logging with structlog
- ✅ Pipeline stage retry with exponential backoff
- ✅ Graceful degradation (non-critical subsystems warn but don't crash)
- ❌ Database errors surface as generic 500s
- ❌ No request correlation IDs
- ❌ Persistence failures are logged as warnings, not surfaced to user

### 9.3 Recovery Mechanisms

| Scenario | Recovery | User Visibility |
|:---|:---|:---|
| Pipeline stage fails | Auto-retry (3 attempts, exponential backoff) | ❌ Not shown to user |
| All retries exhausted | Checkpoint saved, pipeline halted | ❌ Just "completed" or "failed" badge |
| Backend restart during run | Resume from checkpoint via `POST /resume/{id}` | ❌ No UI for resume |
| SSE disconnect | Auto-reconnect (5 retries, exponential backoff) | ✅ Connection badge |
| API key invalid | 401 response | ✅ Error toast |
| Knowledge base empty | Returns empty results | ✅ Empty state |

---

## 10. Feedback Loops

### 10.1 Explicit Feedback

**Star Rating System:**
- 1-5 star rating with hover effects
- Optional notes (max 2000 chars)
- Stored in DB as `user_rating` + `user_notes`
- ✅ Simple and intuitive
- ❌ No guidance on what the rating means (quality? novelty? interest?)
- ❌ Rating is not used to improve future generations (no feedback loop to self-improve engine)

### 10.2 Implicit Feedback

**Refinement:**
- User clicks "Refine" → re-runs novelty/feasibility → updates scores
- ✅ Quick way to refresh stale evaluations
- ❌ No tracking of how often refinement changes scores
- ❌ No "was this refinement helpful?" prompt

### 10.3 Missing Feedback Loops

| Loop | Status | Impact |
|:---|:---|:---|
| User rating → idea ranking | ❌ Not connected | High — ratings don't affect idea ordering |
| User rating → generation params | ❌ Not connected | High — self-improve engine doesn't learn from feedback |
| Idea refinement → knowledge base | ❌ Not connected | Medium — refined scores don't update the KB |
| Export tracking | ❌ Not implemented | Low — no analytics on which ideas are exported |
| Time-on-page analytics | ❌ Not implemented | Medium — no engagement tracking |

---

## 11. Gaps, Frictions & Pain Points

### 🔴 Critical Pain Points

1. **No onboarding flow** — A new user must read the README, understand `.env` configuration, choose an LLM provider, obtain an API key, install Python + Node dependencies, and start two servers. This has **~10 steps before first value**.

2. **No results shown after pipeline completes** — The pipeline progress page shows "Complete" but doesn't link to or display the generated ideas. User must manually navigate to the Ideas page.

3. **Frontend-backend feature parity** — Only ~40% of backend capabilities are exposed in the web UI. Memory, governance, costs, traces, sessions, and scheduler have no UI at all.

4. **No run detail page** — The frontend lists runs but has no detail view. The backend provides a rich run detail endpoint that's unused.

5. **Pipeline form vs backend mismatch** — The form hardcodes defaults (ideas_per_round=5, max_gaps=10) and doesn't expose generation_rounds, export_format, or run_novelty/run_feasibility toggles that the backend supports.

### 🟡 Significant Frictions

6. **SSE auth via query parameter** — API key is passed in the URL for SSE connections, which means it appears in server logs and browser history.

7. **No search/filter in Gaps Explorer** — Just a flat sorted list with no way to find specific gaps.

8. **No gap → idea traceability** — Ideas reference source gaps but the UI doesn't show this relationship in either direction.

9. **Run cards on Dashboard don't link anywhere** — They display run info but aren't clickable.

10. **No dark mode system preference detection** — Must manually toggle in Settings.

11. **No loading state for knowledge search** — User must type query and press Enter; no typeahead or instant search.

12. **Cost invisible to users** — The platform tracks costs in detail but never shows them in the UI. No budget warnings.

13. **No notification system** — Long-running pipelines complete silently. No browser notification, no email, no webhook.

### 🟢 Minor Issues

14. **IdeaCard shows only 2 of 3 scores** — Overall score is not displayed on the card.

15. **Score guide only shown in CLI** — The web UI has score badges with labels but no explanation of what the scores mean.

16. **No delete/archive for ideas or runs** — Data accumulates indefinitely.

17. **Autonomous form has less guidance** — No explanation of what an autonomous cycle does beyond a one-line description.

18. **No character counter on feedback notes** — 2000 char limit with no visual feedback.

19. **No responsive design** — Sidebar + 2-3 column grid won't work on mobile devices.

20. **Export button only on Idea Detail** — No bulk export capability.

---

## 12. Recommendations

### 12.1 High Priority (Impact: User Activation)

| # | Recommendation | Effort |
|:--|:---|:---|
| 1 | **Add a setup wizard** on first launch that guides through provider selection, API key entry, and first pipeline run | Medium |
| 2 | **Show results inline** after pipeline completes — add a "View Results" button or auto-navigate to ideas filtered by run | Low |
| 3 | **Add a Run Detail page** showing stages completed, ideas generated, cost, and timeline | Medium |
| 4 | **Surface the pipeline form's hidden options** (generation rounds, export format, novelty/feasibility toggles) | Low |
| 5 | **Add a "Quick Start" card** to the empty Dashboard with a 3-step guide | Low |

### 12.2 Medium Priority (Impact: Retention & Power Use)

| # | Recommendation | Effort |
|:--|:---|:---|
| 6 | **Connect user ratings to idea ranking** — sort ideas by user_rating when present | Low |
| 7 | **Add Cost Dashboard** — surface cost tracking data from `/api/v1/costs/*` | Medium |
| 8 | **Add Memory Browser** — let users see what the agent remembers and delete incorrect memories | Medium |
| 9 | **Add Governance Queue** — pending approvals UI for human-in-the-loop operations | Medium |
| 10 | **Add gap ↔ idea traceability** — link gaps to ideas and vice versa | Medium |
| 11 | **Add sort/filter to Ideas Browser** — sort by score/date, filter by min_score | Low |
| 12 | **Add a cancel button** to the pipeline progress view | Low |
| 13 | **Add system dark mode detection** via `prefers-color-scheme` media query | Low |
| 14 | **Fix SSE auth** — use headers instead of query parameter for API key | Medium |

### 12.3 Lower Priority (Impact: Polish & Professionalism)

| # | Recommendation | Effort |
|:--|:---|:---|
| 15 | Add responsive layout for mobile/tablet | High |
| 16 | Add literature search UI (currently CLI-only) | Medium |
| 17 | Add PDF upload/ingest UI (currently CLI-only) | Medium |
| 18 | Add browser notifications for pipeline completion | Medium |
| 19 | Add bulk export (download all proposals as ZIP) | Medium |
| 20 | Add delete/archive for ideas, runs, gaps | Low |
| 21 | Add character counter to feedback textarea | Low |
| 22 | Add engagement analytics (which ideas are viewed, exported, rated) | High |
| 23 | Add "Test Connection" button to Settings | Low |
| 24 | Add search/filter to Gaps Explorer | Low |
| 25 | Consistent error response format (always use `error` or always use `detail`) | Low |

---

## 13. User Journey Heat Map

### Web UI — Feature Utilization by Journey Stage

```
Discovery          ████████████  Dashboard, Knowledge Search
Configuration      ██████████    Pipeline Form (limited options)
Execution          ████████████  SSE Progress (real-time)
Monitoring         ██████        (no cost/status/ETA)
Results Review     █████████████ Ideas Browser, Idea Detail
Analysis           ████████████  Novelty Report, Feasibility Report
Feedback           ████████      Star Rating, Notes
Export             ████████      Markdown/LaTeX Download
Iteration          ██            Refine Button (only per-idea)
Autonomous         ██████        Autonomous Form (basic)
Memory             ░░░░░░░░░░    (no UI)
Governance         ░░░░░░░░░░    (no UI)  
Cost Tracking      ░░░░░░░░░░    (no UI)
Sessions           ░░░░░░░░░░    (no UI)
```

### CLI — Feature Utilization

```
Literature Search  ████████████  Well-designed
Pipeline Run       ████████████  Core feature, good output
Quick Checks       ██████████    Novelty + Feasibility standalone
Data Exploration   ████████      Ideas, Runs, Gaps listing
Knowledge Search   ████████      Basic but functional
Configuration      ██████        Status + Config display
PDF Ingestion      ████          Single command
Autonomous Cycle   ██████        Summary-only output
```

---

## 14. Summary

The Elephant Rock Research Platform delivers **exceptional backend power** through a **serviceable but incomplete user experience**. The CLI is the most polished interface — it provides immediate value with clean, Rich-formatted output. The web UI covers the core journey (configure → run → view → feedback → export) but leaves significant capability uncovered.

**The platform's biggest UX challenge is the gap between its extraordinary backend sophistication and its relatively thin frontend.** The backend supports 250+ configuration parameters, a consciousness state machine, multi-agent negotiation, knowledge graph traversal, metacognitive self-improvement, and governance guardrails — but the frontend exposes only the basic pipeline → idea → feedback loop.

**Top 3 changes that would most improve the user experience:**

1. **Guided onboarding** — Reduce the 10-step setup to a 3-step wizard
2. **Post-pipeline result flow** — Automatically surface ideas after completion, with run detail context
3. **Feature parity for analytics** — Surface cost tracking, memory, and run history in the UI

The foundation is strong. The interaction patterns (SSE progress, star feedback, markdown rendering, score badges) are well-designed and consistent. With focused investment on closing the frontend-backend gap and reducing onboarding friction, this platform could deliver a truly exceptional research automation experience.
