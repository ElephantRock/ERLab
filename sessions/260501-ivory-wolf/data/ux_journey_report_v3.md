# Elephant Rock Research Platform — Comprehensive UX & User Journey Report v3

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**Methodology:** Read every frontend source file — 99 `.tsx`/`.ts` files + 63 test files  
**Scope:** 20 pages, 51 components, 18 API modules, 2 contexts, 2 hooks, 5 lib modules, complete type system  

---

## 1. Executive Summary

The Elephant Rock frontend is a **React 18 + TypeScript single-page application** with 20 pages, 51 components, and 76 API endpoints. It provides a complete research lifecycle interface — from JWT authentication through pipeline configuration, real-time progress monitoring, idea/gap exploration, knowledge graph navigation, autonomous cycle control, cost tracking, and multi-format export.

**Key UX characteristics:**
- **Progressive disclosure**: Advanced options hidden behind collapsible panels
- **Real-time feedback**: SSE-powered pipeline progress with auto-reconnect
- **Defensive design**: Confirmation dialogs for destructive actions, error boundaries, loading skeletons
- **Responsive layout**: Desktop sidebar + mobile bottom nav, collapsible sidebar
- **Dark mode**: System-level theme switching with persistence
- **Internationalization**: i18next with English locale, language switcher component ready

---

## 2. Application Shell & Navigation

### 2.1 Entry Point (`main.tsx`)

The app boots through a layered provider stack:

```
ReactDOM.createRoot
  └── React.StrictMode
      └── QueryClientProvider (React Query, 30s staleTime, 1 retry)
          └── SettingsProvider (theme, API URL, API key)
              └── AuthProvider (JWT token, user state)
                  └── BrowserRouter
                      └── ErrorBoundary (catches all render errors)
                          └── App (route definitions)
                          └── Toaster (sonner, bottom-right)
```

**UX implications:**
- Settings (API URL, theme) persist across sessions via localStorage
- JWT token auto-restored on page reload via `getMe()` call
- All uncaught render errors caught by ErrorBoundary
- Sonner toasts provide non-intrusive feedback

### 2.2 Route Structure (`App.tsx`)

Two-layer route architecture:

**Layer 1 — Public routes (no auth):**
- `/login` → LoginPage

**Layer 2 — Protected routes** (behind `ProtectedRoute`):
```
/ → Dashboard
/pipeline/new → PipelineNewPage
/runs/:id → RunDetailPage
/ideas → IdeasBrowserPage
/ideas/:id → IdeaDetailPage
/gaps → GapsExplorerPage
/gaps/:id → GapDetailPage
/knowledge → KnowledgeSearchPage
/knowledge-graph → KnowledgeGraphPage
/settings → SettingsPage
/costs → CostsPage
/memory → MemoryBrowserPage
/governance → GovernancePage
/traces → TracesPage
/sessions → SessionsPage
/literature → LiteraturePage
/autonomous → AutonomousPage
/plugins → PluginsPage
```

**Auth flow:** When `auth_enabled=False` (default dev mode), `ProtectedRoute` always renders children. When enabled, unauthenticated users see a loading spinner, then redirect to `/login`.

### 2.3 Navigation Shell (`AppShell` + `Sidebar`)

**Desktop layout:**
- Collapsible sidebar (256px → 64px) with toggle button
- 15 navigation items with lucide icons
- Active item highlighted with `bg-primary/10 text-primary`
- Collapsed mode shows only icons

**Mobile layout:**
- Bottom navigation bar with 5 items (Dashboard, Pipeline, Ideas, Autonomous, Settings)
- Hidden on desktop via CSS media queries

**Navigation items:**

| Icon | Label | Route | Mobile |
|:---|:---|:---|:---|
| LayoutDashboard | Dashboard | `/` | ✅ |
| Play | Pipeline | `/pipeline/new` | ✅ |
| Lightbulb | Ideas | `/ideas` | ✅ |
| GitBranch | Gaps | `/gaps` | |
| Search | Knowledge | `/knowledge` | |
| Settings | Settings | `/settings` | ✅ |
| DollarSign | Costs | `/costs` | |
| Brain | Memory | `/memory` | |
| Shield | Governance | `/governance` | |
| Activity | Traces | `/traces` | |
| Layers | Sessions | `/sessions` | |
| BookMarked | Literature | `/literature` | |
| BrainCircuit | Graph | `/knowledge-graph` | |
| Cpu | Autonomous | `/autonomous` | ✅ |
| Puzzle | Plugins | `/plugins` | |

---

## 3. Authentication Journey

### 3.1 Login Page (`login.tsx`, 155 LOC)

**User Flow:**
1. User arrives at `/login` — sees centered Card with "Sign In" title
2. Enters **username** and **password** in labeled inputs
3. Clicks "Sign In" button (disabled while submitting, shows "Please wait...")
4. On success: redirected to Dashboard (`/`, replace)
5. On failure: red error text appears below form

**Registration toggle:**
- "Don't have an account? **Register**" link switches to registration mode
- Registration adds an **email** field (type=email)
- "Already have an account? **Sign In**" switches back
- Error state clears on mode switch

**Test IDs:** `auth-form`, `username-input`, `password-input`, `email-input`, `auth-submit`, `auth-error`, `switch-to-register`, `switch-to-login`

### 3.2 Auth Context (`auth-context.tsx`)

**Token management:**
- JWT stored in `localStorage` under `erock_jwt_token`
- `window.fetch` monkey-patched globally to add `Authorization: Bearer <token>` header to all `/api/v1/` requests
- Session restored on mount via `getMe()` call
- Invalid/expired tokens auto-cleared

**User state:**
- `user: AuthUser | null` — null until login
- `loading: boolean` — true during session restore
- `login(username, password)` — calls API, stores token + user
- `register(username, email, password)` — creates account + auto-login
- `logout()` — clears token + user state

---

## 4. Primary User Journeys

### Journey 1: First Pipeline Run

```
Dashboard → Pipeline New → Configure → Watch Progress → View Results
```

**Step 1: Dashboard** (`dashboard.tsx`, 213 LOC)
- Landing page after login
- **3 stat cards**: Total Runs, Total Ideas, System (version)
- **3 charts** (lazy-loaded, shown only when data exists):
  - Score Distribution (bar chart)
  - Run Status (pie chart)
  - Ideas by Domain (bar chart)
- **2 lists**: Recent Runs (clickable → run detail), Recent Ideas (clickable → idea detail)
- "New run" and "View all" navigation links
- Empty states with icons and helpful messages ("No runs yet. Start your first pipeline!")

**Step 2: Pipeline Configuration** (`pipeline-new.tsx`, 361 LOC)

Configuration options via `RunConfigForm`:
- **Session ID** (optional) — group runs together
- **Tab: Single Run vs. Autonomous Cycle**
- **Domain** (text, max 200 chars, default "AI/NLP")
- **Max Gaps** (number, 1-20, default 5)
- **Ideas Per Round** (number, 1-20, default 5)
- **Generation Rounds** (number, 1-10, default 2)
- **Export Format** (select: Markdown / LaTeX)
- **Search Queries** (comma-separated text)
- **Advanced Options** (collapsible):
  - Toggle: Run Novelty Check (default: on)
  - Toggle: Run Feasibility Scoring (default: on)
  - Toggle: Run Proposal Synthesis (default: on)
- **Start Pipeline** button (shows spinner while loading)

**Step 3: Real-Time Progress** (SSE via `usePipelineProgress`)
- 8-stage progress bar with icons:
  1. 🔍 Literature Search
  2. 📄 PDF Ingestion
  3. 🌿 Gap Analysis
  4. 💡 Idea Generation
  5. 🛡️ Novelty Checking
  6. 📊 Feasibility Scoring
  7. ✏️ Proposal Synthesis
  8. 📥 Export
- Live badge: "Connecting..." → "Live" (blue) → "Complete" (green)
- **Cancel Run** button with confirmation dialog (destructive action protection)
- SSE auto-reconnects up to 5 times with exponential backoff

**Step 4: Results Display**
- Success card with ✅ icon and idea count
- Clickable idea cards with title, domain, score badge
- "View All Ideas" and "Run Another" buttons

### Journey 2: Exploring Research Ideas

```
Ideas Browser → Search/Filter → Select → Idea Detail → Feedback/Export/Share
```

**Ideas Browser** (`ideas-browser.tsx`, 230 LOC)

**Controls:**
- Search input with magnifying glass icon
- Sort dropdown: Newest First, Overall Score, Novelty Score, Feasibility Score
- Min Score slider (0-1, step 0.1)
- Domain filter text input
- Pagination (20 per page)

**Grid layout:** 2-column card grid on desktop

**Idea Card** (`idea-card.tsx`, 48 LOC):
- Title (line-clamped to 1 line)
- Domain + score badges
- Clickable → idea detail

**Multi-select for bulk export:**
- Checkbox overlay on each card (top-right corner)
- "Export N Ideas" button appears when items selected
- "Clear selection" button

**Idea Detail** (`idea-detail.tsx`, 211 LOC)

**Layout sections:**
1. **Header**: Back button, title, domain, score badges (novelty, feasibility, overall)
2. **Action buttons**: Export (PDF/Markdown), Refine (re-runs LLM)
3. **Problem Statement** — rendered as Markdown
4. **Proposed Method** — rendered as Markdown
5. **Expected Contributions** — rendered as Markdown
6. **Source Research Gaps** — list of gap titles with amber dots
7. **Tabbed content** (Proposal / Novelty Report / Feasibility Report)
8. **Feedback Form** (star rating 1-5 + notes textarea + submit)
9. **Comment Thread** (nested replies, author name, Enter to send)
10. **Share Dialog** (generate link → copy to clipboard)

### Journey 3: Research Gap Exploration

```
Gaps Explorer → Search/Filter → Gap Detail → Feedback → Navigate to Ideas
```

**Gaps Explorer** (`gaps-explorer.tsx`, 274 LOC)

**Two tabs:**
- **Gaps tab**: Search, filter, sort list
- **Clusters tab**: SVG scatter plot visualization

**Gap filters:**
- Search input (title + description)
- Gap Type dropdown: All, Methodological, Empirical, Theoretical, Cross-domain
- Min Confidence slider (0-1)
- Sort: Confidence, Date, Type
- Reset filters button

**Gap Card** (`gap-card.tsx`, 72 LOC):
- Title, description (line-clamped), gap type badge
- Confidence bar (visual progress bar)
- Idea count badge → clickable → navigates to ideas filtered by gap title
- Entire card clickable → gap detail page

**Gap Detail** (`gap-detail.tsx`, 217 LOC)

**Layout sections:**
1. Back button + title
2. Gap type colored badge + confidence progress bar + **lifecycle status dropdown** (identified → investigating → addressed)
3. Description card with potential impact
4. **Truth Values card**: 3-column grid showing frequency, confidence, evidence count (OpenNARS)
5. **Cluster Membership**: cluster ID pills
6. **Related Ideas**: count + "View Related Ideas" button
7. Metadata (Gap ID, Pipeline Run)
8. **Feedback Form** (star rating 1-5 + notes textarea + character counter)

### Journey 4: Knowledge Search & Graph

**Knowledge Search** (`knowledge-search.tsx`, 147 LOC)

**Layout:**
- Stats banner (documents count, chunks count)
- **Upload Zone** (`upload-zone.tsx`, 176 LOC): drag-and-drop file upload with progress
- Search input with form submission
- Results: text excerpt, source badge, year badge, authors, relevance score (color-coded: green/amber/red)

**Knowledge Graph** (`knowledge-graph.tsx`, 184 LOC)

**Layout:**
- Stats bar (entities, relationships, type breakdown)
- **World Model Panel** (`world-model-panel.tsx`, 130 LOC)
- Entity type filter dropdown + search input
- **SVG Graph Canvas** (`graph-canvas.tsx`, 199 LOC): client-side rendered, max 100 entities
- **Entity Detail Panel** (`entity-detail.tsx`, 129 LOC): shows on entity click, with navigation to related entities

### Journey 5: Autonomous Research

**Autonomous Page** (`autonomous.tsx`, 328 LOC)

**Layout sections:**
1. Header with consciousness state badge (idle/exploring/focused/contemplating/dreaming)
2. **Start New Cycle** form: domain + max runs + start button
3. **Scheduler Controls**: start/stop periodic execution, next run time
4. **Evolution Status**: enabled, overlays generated, recent outcomes
5. **Cycle History** list with stop confirmation
6. Error display card

### Journey 6: Cost Management

**Costs Page** (`costs.tsx`, 163 LOC)

**Layout:**
1. **Summary + Budget**: side-by-side cards showing total spend and budget utilization bar
2. **Cost by Provider**: table (Object.entries iteration)
3. **Cost by Stage**: table
4. **Cost by Model**: table
5. **Per-Run Cost Breakdown**: expandable list

### Journey 7: Settings & Configuration

**Settings Page** (`settings.tsx`, 316 LOC)

**Layout sections:**
1. **API Connection**: URL + API Key inputs + Test Connection button + status dot
2. **Backend Info**: version, provider (read-only)
3. **Defaults**: default research domain (saved to localStorage)
4. **Self-Improvement** (read-only): evolution status, overlays, outcomes
5. **User Management** (admin only): table with username, email, role badges
6. **Appearance**: Light/Dark theme buttons

---

## 5. Component Interaction Matrix

### 5.1 Data Flow Patterns

| Pattern | Implementation | Pages Using |
|:---|:---|:---|
| **Query + Cache** | React Query (`useQuery`) with `queryKey` | All data-fetching pages |
| **Mutation + Invalidate** | React Query (`useMutation`) + `invalidateQueries` | Feedback, comments, shares, exports |
| **SSE Stream** | `useSSE` hook → `sseFetch` (fetch-based) | Pipeline progress |
| **Local State** | `useState` for form fields, filters, pagination | All pages |
| **Context State** | AuthContext, SettingsContext | App-wide |
| **localStorage** | API URL, API key, JWT token, theme, default domain | Settings, Auth |

### 5.2 Interaction Feedback Patterns

| Interaction | Feedback Mechanism | Implementation |
|:---|:---|:---|
| Form submission | Button disabled + spinner | `disabled={isLoading}` + `<Loader2 className="animate-spin">` |
| Success | Sonner toast (bottom-right) | `toast.success("message")` |
| Error | Sonner toast + inline error card | `toast.error("message")` + `<Card className="border-destructive">` |
| Loading | Skeleton placeholders | `<Skeleton className="h-8 w-16">` |
| Empty state | Icon + message | `<FlaskConical className="h-8 w-8">` + "No runs yet" |
| Destructive action | Confirmation dialog | Cancel run, stop cycle, delete memory |
| Hover | Scale transform | `hover:scale-110 transition-transform` (star ratings) |
| Click | Cursor pointer + hover shadow | `cursor-pointer hover:shadow-md transition-shadow` (gap/idea cards) |

### 5.3 Loading Strategy

| Strategy | Where | UX Impact |
|:---|:---|:---|
| **Skeleton loading** | Dashboard, Ideas, Gaps, Knowledge | Gray rectangles matching content shape |
| **Lazy loading** | Charts (ScoreDistribution, DomainBreakdown, RunStatusChart) | Deferred until data available |
| **Progressive loading** | Knowledge Graph (100 entity limit) | Prevents UI freeze |
| **Stale-while-revalidate** | React Query (30s staleTime) | Instant cache hits |
| **Code splitting** | Vite manual chunks (katex, markdown, recharts) | Faster initial load |

---

## 6. State Management Architecture

### 6.1 Global State

| Store | Mechanism | Contents |
|:---|:---|:---|
| Auth | React Context + localStorage | JWT token, user object (id, username, email, role) |
| Settings | React Context + localStorage | API URL, API key, theme (light/dark) |
| Server Cache | React Query | All API responses with automatic cache management |

### 6.2 Local State

Each page manages its own filters, pagination, form inputs, and UI state independently. No global state management library (Redux, Zustand) is used — React Query handles server state, and local `useState` handles UI state.

### 6.3 Data Invalidation

Mutations trigger targeted cache invalidation:

| Mutation | Invalidation |
|:---|:---|
| Submit idea feedback | `["idea", ideaId]` |
| Add comment | `["comments", ideaId]` |
| Refine idea | `["idea", ideaId]` |
| Upload document | `["knowledge-stats"]` |
| Install plugin | `["plugins"]` |

---

## 7. Error Handling Architecture

### 7.1 Error Boundary (`error-boundary.tsx`)

Catches all unhandled render errors. Displays:
- "Something went wrong" message
- Error details (in development)
- "Try again" button (reloads page)

### 7.2 API Error Handling (`client.ts`)

- All API errors wrapped in `ApiError` class (status + detail)
- Non-200 responses parsed for error detail
- 204 responses handled as empty returns

### 7.3 Error Display Patterns

| Pattern | Component | Example |
|:---|:---|:---|
| Inline card | `<Card className="border-destructive">` | Pipeline error, cost error |
| Toast notification | `toast.error()` | Feedback failure, export failure |
| Empty state | Icon + "Not found" message | Run not found, Gap not found |
| Form validation | Browser native (required, type, min/max) | Login, Pipeline config |

---

## 8. Responsive Design

### 8.1 Breakpoints

| Breakpoint | Layout Change |
|:---|:---|
| Mobile (default) | Bottom nav, single column, stacked cards |
| `sm:` (640px) | Side-by-side form controls |
| `md:` (768px) | 2-column grid (ideas), 3-column dashboard stats |
| `lg:` (1024px) | 3-column graph + detail panel |

### 8.2 Responsive Components

- **Sidebar**: Desktop only, collapses to icons
- **MobileBottomNav**: Mobile only, 5 items
- **Idea cards**: `md:grid-cols-2` → 2 columns on desktop
- **Dashboard stats**: `md:grid-cols-3` → 3 columns on desktop
- **Knowledge Graph**: `lg:grid-cols-3` → canvas 2/3 + detail 1/3

---

## 9. Accessibility Analysis

### 9.1 Implemented

| Feature | Implementation |
|:---|:---|
| Semantic HTML | Proper heading hierarchy (`h1` → `h2` → `h3`) |
| Form labels | `<label htmlFor>` on all form fields |
| ARIA labels | `aria-label` on search inputs, buttons |
| Keyboard navigation | Native form inputs, Tab order |
| Color contrast | TailwindCSS color system (primary, muted, etc.) |
| Screen reader text | `aria-label` on status indicators |
| `data-testid` | Comprehensive test IDs on interactive elements |

### 9.2 Gaps

| Issue | Severity | Recommendation |
|:---|:---|:---|
| Skip navigation link missing | Medium | Add "Skip to content" link |
| Focus trap in dialogs | Low | Use Radix Dialog (already imported) |
| Color-only indicators | Low | Score badges use text + color |
| ARIA live regions | Low | Add for SSE progress updates |
| Keyboard shortcuts | Enhancement | Ctrl+K for global search (BATCH-47 planned) |

---

## 10. Performance Considerations

### 10.1 Optimizations

| Optimization | Impact |
|:---|:---|
| React Query caching (30s staleTime) | Eliminates redundant API calls |
| Lazy-loaded charts | Reduces initial bundle by ~50KB (Recharts) |
| Vite manual chunks | Separate bundles for katex, markdown, recharts |
| Knowledge Graph entity limit (100) | Prevents DOM overload |
| Skeleton loading | Perceived performance improvement |
| SSE reconnect with backoff | Graceful degradation on network issues |

### 10.2 Potential Bottlenecks

| Concern | Location | Mitigation |
|:---|:---|:---|
| Dashboard queries 5 endpoints | `dashboard.tsx` | Parallel `useQuery` calls, 30s cache |
| Ideas list loads all for charts | `dashboard.tsx` | Limited to 200 via `limit` param |
| SVG graph rendering | `graph-canvas.tsx` | Hard limit of 100 entities |
| Knowledge search no debounce | `knowledge-search.tsx` | Submit on Enter only (not on type) |

---

## 11. User Journey Maps

### 11.1 New User Journey

```
1. /login
   → Sign In (or Register → Sign In)
   
2. / (Dashboard)
   → See empty state: "No runs yet. Start your first pipeline!"
   → Click "New run" 
   
3. /pipeline/new
   → Enter domain, keep defaults
   → Click "Start Pipeline"
   
4. /pipeline/new (progress)
   → Watch 8 stages progress in real-time via SSE
   → See "Complete" badge
   
5. /pipeline/new (results)
   → Click generated idea
   
6. /ideas/:id
   → Read problem statement, proposed method
   → View novelty/feasibility tabs
   → Give star rating feedback
   → Export to PDF
   → Share link
```

### 11.2 Researcher Journey

```
1. /gaps
   → Search for gaps by keyword
   → Filter by type (methodological, empirical, etc.)
   → Sort by confidence
   → Click gap card
   
2. /gaps/:id
   → Read description, truth values, cluster membership
   → Rate gap (1-5 stars)
   → Update lifecycle status (identified → investigating → addressed)
   → Click "View Related Ideas"
   
3. /ideas?search=gap-title
   → Review ideas addressing the gap
   → Click idea → full detail with proposal
   
4. /pipeline/new
   → Run another pipeline targeting the gap domain
```

### 11.3 Platform Operator Journey

```
1. /settings
   → Configure API connection (URL + key)
   → Test connection (green dot)
   → Switch theme (light/dark)
   → (Admin) Manage users
   
2. /costs
   → Review total spend
   → Check budget utilization bar
   → Break down by provider, stage, model
   
3. /autonomous
   → Start autonomous cycle (domain + max runs)
   → Monitor consciousness state
   → Configure periodic scheduler
   
4. /sessions
   → List all session groups
   → Expand session → see runs
   → Navigate to run details
```

---

## 12. Interaction Inventory

### 12.1 All Interactive Elements by Page

| Page | Interactive Elements | Count |
|:---|:---|:---|
| Login | Username input, Password input, Submit, Mode toggle | 4 |
| Dashboard | 5 navigation links, 2 charts (hover), 5 run cards (click), 5 idea cards (click) | ~17 |
| Pipeline New | Session ID input, 6 config fields, 3 toggles, Format select, Start button, Cancel button, Cancel confirm dialog | ~14 |
| Ideas Browser | Search input, Sort select, Score slider, Domain filter, Pagination (2), 20 idea cards (click), Select checkboxes (20), Export button | ~47 |
| Idea Detail | Back button, Export button, Refine button, 3 tabs, Star rating (5), Notes textarea, Submit feedback, Comment input, Reply button, Share button, Copy link | ~18 |
| Gaps Explorer | Search input, Type select, Confidence slider, Sort select, Reset button, Tab toggle, Pagination (2), 20 gap cards (click) | ~28 |
| Gap Detail | Back button, Status dropdown, Star rating (5), Notes textarea, Submit feedback, View ideas button | ~10 |
| Knowledge Search | Upload zone, Search input (Enter), 10 result cards | ~12 |
| Knowledge Graph | Search input, Type filter, Graph canvas (click entities), Entity detail (navigate) | ~5 |
| Settings | URL input, Key input, Test button, Domain input, Theme buttons (2) | ~6 |
| Costs | 4 tables, Budget bar | ~5 |
| Memory | Search input, Type filter, Delete confirm dialog | ~4 |
| Governance | Approve/deny buttons per item | ~2 per item |
| Traces | Trace click, metrics display | ~3 |
| Sessions | Session list (click), Run list (click) | ~4 |
| Literature | Search input, Ingest buttons per paper | ~3 |
| Autonomous | Domain input, Max runs input, Start button, Scheduler start/stop, Stop confirm | ~7 |
| Plugins | Search input, Install form (name + desc + submit) | ~4 |

**Total interactive elements across all pages: ~200+**

---

## 13. Frontend-Backend API Integration

### 13.1 API Client Architecture

```
api/client.ts          → Base fetch wrapper (apiFetch), SSE (sseFetch), connection test
api/types.ts           → 177 lines of TypeScript interfaces
api/auth.ts            → login, register, getMe, listUsers
api/autonomous.ts      → 7 functions (trigger, stop, history, consciousness, evolution, scheduler)
api/collaboration.ts   → listComments, addComment, createShareLink, getSharedIdea
api/costs.ts           → 5 functions (summary, by-provider, by-stage, by-model, run-breakdown)
api/exports.ts         → exportPdf, bulkExport
api/gaps.ts            → listGaps, getGap, submitGapFeedback, updateGapStatus
api/governance.ts      → Policy operations
api/ideas.ts           → listIdeas, getIdea, submitFeedback, refineIdea
api/knowledge-graph.ts → 5 functions (stats, entities, entity, subgraph, world-model)
api/knowledge.ts       → searchKnowledge, getKnowledgeStats, uploadDocument
api/literature.ts      → search, sources, import
api/memory.ts          → getMemories, getStats, deleteMemory
api/pipeline.ts        → triggerRun, listRuns, getRunDetail, cancelRun, getRunIdeas, triggerAutonomous
api/sessions.ts        → listSessions
api/status.ts          → getSystemStatus
api/traces.ts          → 3 trace functions
```

### 13.2 Data Flow Summary

```
User Action → Page Component → API Module → apiFetch → Backend
                                                    ↓
User Sees ← Page Component ← React Query ← JSON Response
```

SSE flow:
```
Pipeline Start → useSSE hook → sseFetch (fetch-based) → Backend SSE endpoint
                                                          ↓
StageProgress update ← JSON.parse(raw) ← SSE "data: ..." events
```

---

## 14. Design System

### 14.1 UI Primitives (12 shadcn/ui components)

| Component | Purpose | Key Props |
|:---|:---|:---|
| Badge | Status labels, score display | `variant` (outline/secondary) |
| Button | All actions | `variant` (default/outline/ghost/destructive), `size` (sm/default) |
| Card | Content containers | `CardHeader` + `CardTitle` + `CardContent` |
| Dialog | Modal overlays | `DialogTrigger` + `DialogContent` |
| Input | Text fields | `type`, `placeholder`, `maxLength` |
| Progress | Progress bars | `value` |
| Select | Dropdowns | `SelectTrigger` + `SelectContent` + `SelectItem` |
| Separator | Horizontal rules | — |
| Skeleton | Loading placeholders | `className` for sizing |
| Slider | Range inputs | `value`, `min`, `max`, `step` |
| Tabs | Tab navigation | `TabsList` + `TabsTrigger` + `TabsContent` |

### 14.2 Color System

| Purpose | Colors |
|:---|:---|
| Primary | `bg-primary`, `text-primary` (blue) |
| Success | `bg-green-100 text-green-800`, `text-green-600` |
| Warning | `bg-amber-100 text-amber-800`, `text-amber-500` |
| Error | `bg-red-100 text-red-800`, `text-destructive` |
| Info | `bg-blue-100 text-blue-800` |
| Gap types | blue (methodological), green (empirical), purple (theoretical), orange (cross-domain) |
| Muted | `text-muted-foreground`, `bg-muted` |

### 14.3 Typography

- Headings: Tailwind font-bold tracking-tight
- Body: text-sm (14px)
- Labels: text-xs text-muted-foreground
- Scores: text-lg font-medium
- Large numbers: text-2xl font-bold

---

## 15. User Feedback Mechanisms

### 15.1 Idea Feedback
- **Star rating**: 1-5 stars with hover preview, fill animation, scale on hover
- **Notes**: Textarea with 2000 char limit
- **API**: POST `/api/v1/ideas/{id}/feedback`

### 15.2 Gap Feedback  
- **Star rating**: 1-5 stars with hover preview
- **Notes**: Textarea with character counter (X/2000)
- **API**: POST `/api/v1/gaps/{id}/feedback`

### 15.3 Gap Lifecycle
- **Status dropdown**: identified → investigating → addressed (forward-only)
- **API**: PATCH `/api/v1/gaps/{id}/status`

### 15.4 Comment Thread
- **Nested replies**: Parent comments with indented children
- **Author field**: Customizable name (default: "anonymous")
- **Reply button**: Appears on hover, sets reply-to state
- **Enter to send**: Keyboard shortcut
- **API**: POST `/api/v1/ideas/{id}/comments`

### 15.5 Sharing
- **Generate link**: Creates unique token URL
- **Copy to clipboard**: One-click copy with ✓ confirmation
- **Public access**: `/api/v1/shared/{token}` — no auth required

---

## 16. Internationalization

### 16.1 Current State
- i18next configured with English locale
- Language detector (localStorage + navigator)
- Language switcher component available
- Only `en.json` locale populated

### 16.2 Infrastructure
```
i18n/config.ts → initReactI18next
i18n/en.json → English translations
components/i18n/language-switcher.tsx → UI component
```

---

## 17. Security Considerations

| Measure | Implementation |
|:---|:---|
| JWT authentication | Bearer token in Authorization header |
| API key fallback | X-API-Key header when JWT not used |
| Password masking | type="password" on login form |
| Token storage | localStorage (vulnerable to XSS) |
| CSRF | Not implemented (API uses Bearer tokens, not cookies) |
| Input validation | Client-side maxLength, required, type attributes |
| API URL validation | None — trusts user input |
| XSS prevention | React JSX auto-escaping, MarkdownRenderer sanitizes |

---

## 18. Observations & Recommendations

### 18.1 UX Strengths

1. **Comprehensive feature coverage** — every backend capability has a frontend interface
2. **Real-time progress** — SSE with auto-reconnect provides excellent pipeline monitoring
3. **Defensive interactions** — confirmation dialogs for cancel, stop, delete actions
4. **Progressive disclosure** — advanced options hidden behind collapsible panels
5. **Consistent design system** — shadcn/ui primitives with TailwindCSS
6. **Lazy-loaded charts** — prevents unnecessary bundle bloat
7. **Responsive layout** — desktop sidebar + mobile bottom nav
8. **Dark mode** — system-level theme switching
9. **Test ID coverage** — almost every interactive element has `data-testid`
10. **Toast notifications** — non-intrusive success/error feedback

### 18.2 UX Gaps & Recommendations

| Gap | Severity | Recommendation |
|:---|:---|:---|
| No global search shortcut | Medium | Implement Ctrl+K → global search modal |
| No keyboard shortcuts | Low | Add `?` shortcut overlay |
| Ideas table view missing | Low | Add table/list toggle for power users |
| No bulk gap operations | Low | Multi-select gaps for status update |
| No onboarding tour | Medium | Add walkthrough for first-time users |
| No offline indicator | Low | Add network status badge |
| No undo for destructive actions | Low | Implement optimistic UI with rollback |
| No notification center | Medium | Add bell icon for pipeline completion alerts |
| No dashboard customization | Low | Allow rearranging/charts |
| i18n incomplete | Low | Populate Chinese, Spanish, French locales |
| JWT in localStorage | Medium | Consider httpOnly cookies for production |
| No input debouncing | Low | Add debounce to search inputs |

---

*Report — AIV Framework v5.1 — Lead Agent — 2026-05-02*
