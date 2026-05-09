# UX & User Journey Audit Report — Elephant Rock Research Platform

**Date**: 2026-05-09  
**Auditor**: Craft Agent  
**Scope**: Full frontend UX analysis — 21 pages, 82 components, 21 API modules, 6 hooks, 9-language i18n  
**Methodology**: Line-by-line code review of every page, component, layout, interaction pattern, and data flow

---

## Executive Summary

Elephant Rock presents itself as an **AI-powered research accelerator** — give it a topic, wait 20 minutes, receive publication-ready research proposals. The platform delivers on this promise technically but creates a **steep cliff between "what it can do" and "what a first-time user understands it can do."**

The core UX tension is this: the platform has **15 sidebar navigation items** for a user who just wants to **type a topic and get results**. The information architecture was built bottom-up (one nav item per backend feature) rather than top-down (user goal → interface).

**Overall UX Grade: B-**

| Dimension | Grade | Summary |
|:----------|:------|:--------|
| First-time onboarding | **D+** | No walkthrough, no sample data, no guided flow |
| Core journey (run pipeline) | **A-** | Clean form → live progress → results — excellent |
| Information architecture | **C** | 15 nav items for a single-user research tool |
| Visual hierarchy | **B** | Clear headings, good spacing, consistent components |
| Accessibility | **C+** | Some ARIA labels, but low coverage (25 total) |
| Error handling | **B** | Error boundaries, inline errors, toast notifications |
| Empty states | **B+** | 16 meaningful empty states with icons and CTAs |
| Mobile experience | **B-** | Bottom nav, responsive grid, but pages aren't optimized |
| Search & discoverability | **A** | Global search (⌘K) with recent searches and categories |
| Feedback & iteration | **B** | Feedback forms, comments, share dialogs — good |

---

## User Journey Map

### Journey 1: First-Time Researcher (Critical Path)

```
Step 1: Arrive at login page
  ┌─────────────────────────────────────────────────────────────────┐
  │ WHAT USER SEES: Small centered card "Sign In" / "Create Account"│
  │ WHAT USER THINKS: "Is this the right tool? Where's the demo?"   │
  │ FRICTION: ★★★☆☆ — No value proposition, no preview, no demo    │
  │ TIME TO VALUE: Must create account before seeing anything        │
  └─────────────────────────────────────────────────────────────────┘
         │
         ▼
Step 2: Dashboard (empty state)
  ┌─────────────────────────────────────────────────────────────────┐
  │ WHAT USER SEES: "Total Runs: 0, Total Ideas: 0" + 3 stat cards │
  │                 "No runs yet. Start your first pipeline!"        │
  │ WHAT USER THINKS: "Ok... now what?"                              │
  │ FRICTION: ★★★★☆ — No CTA button, just a text link               │
  │             15 nav items compete for attention                    │
  │             Analytics section hidden (no data)                    │
  └─────────────────────────────────────────────────────────────────┘
         │
         ▼ (clicks "New run" text link — easy to miss)
Step 3: Pipeline configuration
  ┌─────────────────────────────────────────────────────────────────┐
  │ WHAT USER SEES: Session ID (optional) + tabs (Single/Auto)      │
  │                 Research Domain input + strategy dropdown         │
  │                 Max Gaps / Ideas Per Round / Generation Rounds    │
  │                 Advanced Options (collapsed)                      │
  │ WHAT USER THINKS: "What's a gap? What strategy should I use?"    │
  │ FRICTION: ★★☆☆☆ — Strategy descriptions help, but:             │
  │             "Max Gaps" is meaningless to new users                │
  │             Domain defaults to "AI/NLP" — too narrow              │
  │             Session ID field adds confusion                       │
  └─────────────────────────────────────────────────────────────────┘
         │
         ▼ (clicks "Start Pipeline")
Step 4: Pipeline running (LIVE PROGRESS — best UX moment)
  ┌─────────────────────────────────────────────────────────────────┐
  │ WHAT USER SEES: Blue progress card with animated spinner          │
  │                 Stage-by-stage completion with checkmarks         │
  │                 Cancel button with confirmation dialog            │
  │                 Badge: "Live" | "Run #run_20260509_171234"       │
  │ WHAT USER THINKS: "This is cool — I can see it working"          │
  │ FRICTION: ★☆☆☆☆ — Excellent live feedback!                      │
  │   ★ GOOD: Animated spinner per stage, elapsed time, progress bar │
  │   ★ GOOD: Stale run detection (>5min warning)                    │
  │   ⚠ ISSUE: No estimated completion time                          │
  │   ⚠ ISSUE: No way to see partial results while running           │
  └─────────────────────────────────────────────────────────────────┘
         │
         ▼ (wait 20 minutes)
Step 5: Pipeline complete → Results
  ┌─────────────────────────────────────────────────────────────────┐
  │ WHAT USER SEES: "Pipeline Complete" + idea cards with scores     │
  │                 "View All Ideas" | "Run Another" buttons         │
  │ WHAT USER THINKS: "I got ideas! But what do these scores mean?"  │
  │ FRICTION: ★★☆☆☆ —                                                │
  │   ★ GOOD: Ideas are immediately clickable                         │
  │   ★ GOOD: Score badges are visible at a glance                    │
  │   ⚠ ISSUE: No explanation of what "88%" means                    │
  │   ⚠ ISSUE: No way to compare ideas side-by-side                  │
  └─────────────────────────────────────────────────────────────────┘
         │
         ▼ (clicks an idea)
Step 6: Idea detail page
  ┌─────────────────────────────────────────────────────────────────┐
  │ WHAT USER SEES: Title + domain + score badges                    │
  │                 Problem Statement → Proposed Method →             │
  │                 Expected Contributions → Source Gaps →            │
  │                 TABS: Proposal | Novelty | Feasibility | Metrics  │
  │                 Table of contents sidebar for proposal            │
  │                 Export | Refine | Feedback | Comment | Share      │
  │ WHAT USER THINKS: "This is a LOT of content — where do I start?" │
  │ FRICTION: ★★☆☆☆ —                                                │
  │   ★ GOOD: Proposal has ToC sidebar + section rendering            │
  │   ★ GOOD: Word count shown (e.g., "3,388 words")                  │
  │   ⚠ ISSUE: Everything above the fold is metadata, not content    │
  │   ⚠ ISSUE: No "quick summary" — user must scroll to find value   │
  └─────────────────────────────────────────────────────────────────┘
```

**End-to-end time-to-value for first-time user**: ~25 minutes (5 min confusion + 20 min pipeline)

**With recommended improvements**: ~22 minutes (1 min setup + 1 min config + 20 min pipeline)

---

### Journey 2: Returning Researcher (Happy Path)

```
Login → Dashboard (sees past runs) → Clicks "New run"
  → Domain auto-filled from settings → Strategy: deep_research
  → Start → Progress → Results → Compare ideas → Export best one

TIME: ~22 minutes, 8 clicks
FRICTION: ★☆☆☆☆ (Low — the system is designed for this flow)
```

### Journey 3: Gap Explorer (Secondary Path)

```
Dashboard → Gaps → Filter by type/confidence → Click gap → 
  See details + related ideas → Give feedback

TIME: 2-3 minutes, 5 clicks
FRICTION: ★★☆☆☆ (Filters work well, but gap detail is sparse)
```

### Journey 4: Knowledge Search (Utility Path)

```
Dashboard → Knowledge → Upload PDF → Wait → Search → See chunks

TIME: 5 minutes, 6 clicks
FRICTION: ★★★☆☆ (Upload + index wait is opaque)
```

---

## Navigation Architecture Analysis

### Current Information Architecture

```
┌─────────────────────────────────────────────┐
│              SIDEBAR (15 items)              │
├─────────────────────────────────────────────┤
│ ★ Dashboard          (/)         [primary]  │
│ ★ Pipeline           (/pipeline/new) [primary] │
│ ★ Ideas              (/ideas)    [primary]  │
│   Gaps               (/gaps)     [secondary] │
│   Knowledge          (/knowledge)[secondary] │
│   Settings           (/settings) [utility]  │
│   Costs              (/costs)    [admin]    │
│   Memory             (/memory)   [admin]    │
│   Governance         (/governance)[admin]   │
│   Traces             (/traces)   [admin]    │
│   Sessions           (/sessions) [admin]    │
│   Literature         (/literature)[secondary] │
│   Graph              (/knowledge-graph)[adv] │
│ ★ Autonomous         (/autonomous)[adv]      │
│   Plugins            (/plugins)  [admin]    │
└─────────────────────────────────────────────┘
★ = shown on mobile bottom nav (5 of 15)
```

### Problem: Flat Navigation Without Grouping

All 15 items are at the same level. There are no section headers, no dividers, no grouping. A new user sees an undifferentiated list of 15 links and has no idea which ones matter.

**Recommended grouping:**

```
RESEARCH
  Dashboard
  Pipeline
  Ideas
  Gaps
  Knowledge
  
LIBRARY
  Literature
  Knowledge Graph

SYSTEM
  Settings
  Costs
  Memory
  Governance
  Traces
  Sessions
  Autonomous
  Plugins
```

### Navigation Metrics

| Metric | Value | Assessment |
|:-------|:------|:-----------|
| Total nav items | 15 | Too many for a research tool |
| Clicks to start pipeline | 2 (Dashboard → Pipeline) | Good |
| Clicks to view results | 3 (Dashboard → Run → Idea) | Good |
| Max nav depth | 1 level | Flat (good for speed, bad for organization) |
| Mobile nav items | 5 | Appropriate |
| Breadcrumbs | None | Missing — no way to navigate up |
| Back buttons | Present on 4 pages | Inconsistent |

---

## Page-by-Page UX Assessment

### 1. Login Page — Grade: **B**

**What works:**
- Clean centered card layout
- Toggle between login/register (no page change)
- Error messages appear inline
- Loading state on submit button

**What needs work:**
- **No value proposition** — The page says "Sign In" but not what the tool does
- **No demo / guest access** — User must create account to see the product
- **No password strength indicator** on registration
- **No "forgot password" link** — Dead end if user forgets
- **No social login** options (Google, GitHub)

### 2. Dashboard — Grade: **B-**

**What works:**
- 3 stat cards (Total Runs, Total Ideas, System) — clear KPIs
- Recent Runs + Recent Ideas in 2-column layout
- Empty states with icons and CTAs
- Analytics charts appear when data exists (lazy loaded)

**What needs work:**
- **No prominent CTA** — "Start your first pipeline!" is just text, not a button
- **5 parallel API calls on load** (status, runs×2, ideas×2) — slow on empty state
- **"System: Elephant Rock v1.0"** stat card is wasted space for most users
- **No pipeline status summary** — Can't see if a pipeline is currently running from the dashboard
- **No "quick start" card** — A card that says "Enter a research topic to get started" with an input field right on the dashboard

### 3. Pipeline Configuration — Grade: **A-**

**What works:**
- Strategy selector with descriptions and time estimates ("~2-5 min", "~25 min")
- Domain input as the first field (primary action)
- Advanced options collapsed by default (reduces cognitive load)
- Client-side validation matching backend exactly (HB-01)
- Clean form layout with logical grouping

**What needs work:**
- **"Session ID (optional)" at the top** confuses first-time users — move to advanced
- **"Max Gaps" terminology** is meaningless to non-researchers — use "Max Research Gaps to Find"
- **Domain defaults to "AI/NLP"** — too narrow, should be empty with placeholder examples
- **No "What will happen?" explainer** — A brief description of the pipeline stages would help
- **No estimated cost** before starting — Users don't know how many API calls this will make

### 4. Pipeline Running (Live Progress) — Grade: **A**

**This is the best UX moment in the entire platform.**

**What works:**
- Blue progress banner with animated progress bar
- Stage-by-stage completion with green checkmarks and spinning blue icon for current
- Live elapsed timer (1-second tick)
- Cancel button with explicit confirmation dialog (no accidental cancels)
- Stale run detection (>5 min warning)
- Badge system: "Live" → "Complete" → "Cancelled"

**What needs work:**
- **No estimated time remaining** — "Stage 4 of 11" doesn't tell me how long is left
- **No partial results visible** during run — Papers found, gaps identified, etc. are invisible until completion
- **No notification when complete** — If user navigates away, they won't know the run finished
- **Run ID is UUID** (`run_20260509_171234`) — Not human-friendly, should be `#42`

### 5. Ideas Browser — Grade: **B+**

**What works:**
- Search, sort, filter, paginate — all the controls a researcher needs
- Multi-select with checkboxes for bulk export
- Score filter slider with real-time update
- Sort by date, score, novelty, feasibility
- Pagination with page indicator

**What needs work:**
- **No "card view vs list view" toggle** — All ideas shown as cards
- **Domain filter is a text input** — Should be a dropdown of known domains
- **No "compare" feature** — Can select multiple but only export, not compare side-by-side
- **Export button only appears when items are selected** — Discoverable but hidden initially

### 6. Idea Detail — Grade: **B**

**What works:**
- Rich proposal rendering with Table of Contents sidebar
- Markdown + LaTeX rendering (KaTeX)
- Tabbed sections: Proposal, Novelty Report, Feasibility Report, Metrics
- Action buttons: Export, Refine, Share, Comment, Feedback
- Source gap traceability shown

**What needs work:**
- **Content overload** — Above the fold: title, domain, 3 score badges, 4 action buttons. Content starts below.
- **No executive summary / TL;DR** — A 5,000-word proposal with no 2-sentence summary
- **"Refine" button is ambiguous** — Does it re-run the LLM? Edit the idea? Re-score?
- **Score badges have no explanation** — "Novelty: 0.88" — Is that good? Bad? Average?
- **No "related ideas" section** — Missing discoverability loop

### 7. Gaps Explorer — Grade: **B**

**What works:**
- Confidence slider filter
- Gap type dropdown (methodological, empirical, theoretical, cross-domain)
- Clusters tab with scatter plot visualization
- Reset filters button
- Click-through to gap detail

**What needs work:**
- **Gap cards show minimal information** — Title, confidence, type, description (truncated)
- **No "generate ideas from this gap" action** — Natural next step is missing
- **Cluster scatter plot loads lazily** — But there's no loading indicator while switching tabs

### 8. Knowledge Search — Grade: **B-**

**What works:**
- Stats banner (Documents, Chunks)
- Upload zone for PDFs
- Relevance scoring with color coding (green/amber/red)
- Metadata badges (source, year, authors)

**What needs work:**
- **Upload zone is always visible** — Takes up space even when user just wants to search
- **No search history** — Unlike global search, no recent searches shown
- **No "search within results"** — Can't refine a search
- **Distance scores (0.234) are meaningless** to most users — "High/Medium/Low" helps but the number is confusing

### 9. Settings — Grade: **C+**

**What works:**
- API connection test with visual status dot
- Backend info section (version, provider)
- Default domain prefill
- Dark mode toggle
- User management for admins

**What needs work:**
- **No "setup wizard"** — First-time users must manually enter API URL and test connection
- **Self-improvement section is read-only** — Show it, but explain WHY it's read-only
- **No explanation of what "API Key" is** — Where do I get one? What happens without it?
- **Theme toggle is buried** — Should be in the top-right header, not settings

### 10. Secondary Pages (Costs, Memory, Governance, Traces, Sessions, Literature, Knowledge Graph, Autonomous, Plugins)

These 9 pages serve power users and administrators. For first-time users, they're noise in the navigation.

| Page | Grade | Purpose | First-time relevance |
|:-----|:------|:--------|:--------------------|
| Costs | B | Cost tracking per provider/stage | Low |
| Memory | B- | Memory tier browser | Low |
| Governance | C+ | Approval queue for policy gates | Very low |
| Traces | B | Observability spans | Very low |
| Sessions | B- | Run grouping | Low |
| Literature | B | Paper search + ingestion | Medium |
| Knowledge Graph | B | Entity relationship visualization | Medium |
| Autonomous | B | Autonomous cycle scheduler | Low |
| Plugins | C | Plugin marketplace (stub) | Very low |

---

## Visual Hierarchy Analysis

### Color System

The platform uses a **well-structured CSS custom property system** with light/dark mode:

```
Primary: Blue (#3B82F6 HSL 221.2 83.2% 53.3%) — Actions, links, active states
Secondary: Light gray (HSL 210 40% 96.1%) — Backgrounds, cards
Destructive: Red (HSL 0 84.2% 60.2%) — Errors, cancel, delete
Muted: Gray (HSL 215.4 16.3% 46.9%) — Secondary text
```

**Assessment**: Color system is consistent and follows semantic naming. Good use of blue for progress, green for completion, red for errors.

### Typography

```
Headings: system-ui, bold, tracking-tight
  H1: 2xl (24px), bold
  H2: lg (18px), semibold
  H3: lg (18px), semibold (in cards)
  
Body: system-ui, regular
  Text: sm (14px)
  Muted text: sm, text-muted-foreground
  
Labels: sm (14px), font-medium
  Captions: xs (12px), text-muted-foreground
```

**Assessment**: Type scale is appropriate. The 2xl → lg jump is steep — consider adding an xl step. All pages follow the same `<h1>` + subtitle pattern consistently.

### Spacing

Pages consistently use `space-y-6` for top-level sections and `space-y-4` for card internals. Cards use `p-4` for content. Grid gaps are `gap-4` (16px).

**Assessment**: Consistent and clean. No spacing inconsistencies found across pages.

### Card Patterns

Every page uses the same `<Card><CardHeader><CardTitle>...</CardTitle></CardHeader><CardContent>...</CardContent></Card>` pattern. This creates visual consistency but also **visual monotony** — every section looks the same, making it hard to distinguish primary from secondary content.

---

## Accessibility Audit

### WCAG 2.1 AA Compliance Check

| Criterion | Status | Details |
|:----------|:-------|:--------|
| **1.1.1 Non-text Content** | ❌ Fail | 0 `alt` attributes found; icons have no text alternatives |
| **1.3.1 Info and Relationships** | ⚠️ Partial | 30 `<label>` + `htmlFor` associations; 25 ARIA attributes total |
| **1.4.3 Contrast (Minimum)** | ✅ Pass | CSS variables use proper HSL values; blue primary passes 4.5:1 |
| **2.1.1 Keyboard** | ⚠️ Partial | ⌘K search shortcut works; `j/k` navigation defined but not wired |
| **2.4.1 Bypass Blocks** | ❌ Fail | No skip-to-content link |
| **2.4.3 Focus Order** | ⚠️ Partial | Tab order follows DOM; no explicit focus management |
| **2.4.7 Focus Visible** | ⚠️ Partial | Tailwind `focus-visible:ring-2` used on inputs/buttons |
| **3.2.1 On Focus** | ✅ Pass | No unexpected context changes on focus |
| **3.3.1 Error Identification** | ✅ Pass | Error messages use `text-red-500` + `text-destructive` |
| **3.3.2 Labels** | ⚠️ Partial | 30 labels across 21 pages — many inputs lack labels |
| **4.1.2 Name, Role, Value** | ⚠️ Partial | 3 `role` attributes; many interactive elements lack ARIA |

### Accessibility Score: **C+** (estimated)

**Critical gaps:**
1. **No skip-to-content link** — Keyboard users must tab through the entire sidebar
2. **No alt text on any images** — Icons are decorative but images would fail
3. **Checkbox toggles use bare `<input type="checkbox">`** — No ARIA toggle pattern
4. **Custom select dropdowns** lack screen reader announcements
5. **Modal dialogs** (cancel confirmation, export, share) may trap focus incorrectly
6. **No focus management** after navigation — Focus stays where it was on the previous page

### Positive Accessibility Patterns
- `aria-label` on search inputs, sliders, and select triggers
- `aria-expanded` on the advanced options toggle
- `role="status"` on the connection status dot
- `aria-label="Mobile navigation"` on the bottom nav
- Loading states use `<Skeleton>` instead of spinner-only patterns
- Error boundary catches crashes and provides a "Reload" button

---

## Cognitive Load Analysis

### Hick's Law Applied

The sidebar presents **15 choices** on every screen. Hick's Law says decision time increases logarithmically with the number of choices. For a first-time user, this is overwhelming.

**Recommended reduction:**
- **Primary (5 items)**: Dashboard, Pipeline, Ideas, Gaps, Knowledge
- **Secondary (expandable)**: Literature, Graph, Sessions, Costs
- **Admin (collapse by default)**: Settings, Memory, Governance, Traces, Autonomous, Plugins

### Miller's Law (7 ± 2)

The pipeline configuration form shows **8 fields** (domain, strategy, max gaps, ideas per round, generation rounds, export format, search queries, advanced toggles). This is at the upper limit of working memory.

**Recommended simplification:**
- Show only **3 fields** by default: Domain, Strategy, Search Queries
- Move everything else into "Advanced Configuration"
- Show **estimated time** and **estimated papers** based on strategy selection

### Fitts's Law

Primary action buttons are well-sized:
- "Start Pipeline" — full-width button, easy to target ✅
- "Cancel Run" — small but with confirmation dialog ✅
- "View All Ideas" — medium button ✅
- Sidebar nav items — 36px height, adequate ✅

**Issue**: The "New run" link on the dashboard is small text (`text-sm text-primary hover:underline`) — poor click target for the primary action.

---

## Time-to-Value Analysis

### Current First-Time User Timeline

```
0:00  → Arrive at login
0:30  → Create account (register form)
0:45  → See empty dashboard, confused
1:00  → Find "New run" text link
1:15  → Arrive at pipeline config, confused by Session ID
1:45  → Enter domain, select strategy, start pipeline
1:50  → See live progress — first "aha" moment
21:50 → Pipeline completes
22:00 → See idea cards — second "aha" moment
22:30 → Click into idea detail, see full proposal
23:00 → Export proposal — VALUE ACHIEVED
```

**Total time-to-value: ~23 minutes** (including 2 minutes of confusion)

### Recommended First-Time User Timeline

```
0:00  → Arrive at landing page with "Try it free" CTA
0:15  → Auto-provisioned guest account (no registration)
0:20  → Dashboard shows "Enter a research topic" card with input
0:30  → User types topic, clicks "Start Research"
0:35  → Strategy auto-selected (fast_scan for first run)
0:40  → See live progress with "What's happening" explainer
3:00  → Quick scan completes (3 min strategy)
3:15  → See 2-3 ideas with TL;DR summaries
3:30  → Click idea, see executive summary + full proposal
4:00  → Export — VALUE ACHIEVED
```

**Recommended time-to-value: ~4 minutes** (83% reduction)

---

## Friction Point Inventory

| # | Friction Point | Location | Severity | Fix Effort |
|:--|:---------------|:---------|:---------|:-----------|
| FP-01 | No onboarding walkthrough | Login → Dashboard | HIGH | 2-3 days |
| FP-02 | 15 undifferentiated nav items | Sidebar | HIGH | 1 day |
| FP-03 | Empty dashboard with no CTA button | Dashboard | HIGH | 0.5 day |
| FP-04 | Session ID field on pipeline page | Pipeline config | MEDIUM | 0.5 day |
| FP-05 | No estimated time/cost before starting | Pipeline config | MEDIUM | 1 day |
| FP-06 | No partial results during pipeline run | Pipeline running | MEDIUM | 2-3 days |
| FP-07 | No TL;DR summary on idea detail | Idea detail | MEDIUM | 1 day |
| FP-08 | Score badges lack context | Ideas browser + detail | LOW | 0.5 day |
| FP-09 | No "generate ideas from gap" action | Gap explorer | MEDIUM | 1 day |
| FP-10 | Domain filter is free text | Ideas browser | LOW | 0.5 day |
| FP-11 | No "forgot password" flow | Login | LOW | 1 day |
| FP-12 | Upload zone always visible | Knowledge search | LOW | 0.5 day |
| FP-13 | Theme toggle buried in settings | Settings | LOW | 0.5 day |
| FP-14 | No keyboard shortcut overlay (?) | Global | LOW | 0.5 day |
| FP-15 | No breadcrumbs | All detail pages | LOW | 1 day |

---

## Specific Recommendations

### Recommendation 1: Guided Onboarding Flow (Priority: HIGH)

Add a **3-step onboarding overlay** for first-time users:

1. **"Welcome to Elephant Rock"** — 1-sentence value prop + animated pipeline diagram
2. **"Enter your research topic"** — Single input field, auto-starts fast_scan
3. **"Here are your results"** — Highlights the idea cards and export button

Show this only when `Total Runs === 0` and `!localStorage.getItem("erock_onboarding_complete")`.

### Recommendation 2: Navigation Restructure (Priority: HIGH)

Group sidebar items with section headers:

```
── RESEARCH ──────────
  Dashboard
  New Pipeline
  Ideas
  Research Gaps
  
── LIBRARY ───────────
  Knowledge Base
  Literature
  Knowledge Graph
  
── SYSTEM ────────────
  Settings
  [... collapsed: Costs, Memory, Governance, Traces, Sessions, Autonomous, Plugins]
```

Default state: System section collapsed. "Show more" link expands it.

### Recommendation 3: Dashboard CTA Card (Priority: HIGH)

Replace the empty state "No runs yet. Start your first pipeline!" with a **prominent CTA card**:

```
┌─────────────────────────────────────────────────────────────────┐
│  🚀 Start Your First Research Pipeline                          │
│                                                                 │
│  [Enter a research topic, e.g., "Transformer attention          │
│   mechanisms for long-context reasoning"              ] [Start] │
│                                                                 │
│  Strategy: ○ Quick Scan (3 min)  ● Deep Research (20 min)      │
│                                                                 │
│  ℹ Your first run will search academic papers, identify gaps,   │
│     and generate novel research ideas with full proposals.       │
└─────────────────────────────────────────────────────────────────┘
```

This eliminates the Dashboard → Pipeline navigation and lets users start immediately.

### Recommendation 4: Simplified Pipeline Config (Priority: MEDIUM)

For first-time users, show only:

1. **Research topic** (text input) — required
2. **Strategy** (3 radio buttons with time estimates) — required
3. **"What happens?"** expandable explainer

Move to advanced:
- Session ID, Max Gaps, Ideas Per Round, Generation Rounds, Export Format, Search Queries, Run toggles

### Recommendation 5: Idea TL;DR (Priority: MEDIUM)

Add an auto-generated **2-3 sentence executive summary** at the top of each idea detail page, above the score badges:

```
┌─────────────────────────────────────────────────────────────────┐
│  💡 TL;DR                                                       │
│  This proposal introduces a Sparse Mixture-of-Experts approach  │
│  to long-context reasoning that achieves 15% better performance │
│  than dense transformers while using 3x fewer FLOPs.            │
│                                                                 │
│  Novelty: 92%  ·  Feasibility: 78%  ·  Overall: 85%            │
│  [Export] [Refine] [Share]                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Recommendation 6: Score Context Tooltips (Priority: LOW)

Add hover tooltips to score badges:

- **Novelty: 92%** → "This idea is highly novel — only 8% of existing literature addresses this approach"
- **Feasibility: 78%** → "This idea is feasible — the required methods and datasets are available"
- **Overall: 85%** → "Combined score based on novelty (50%), feasibility (30%), and mechanical metrics (20%)"

### Recommendation 7: Pipeline Progress Enhancement (Priority: MEDIUM)

During pipeline execution, show:
- **Estimated time remaining** (based on average stage duration from past runs)
- **Partial results count** — "36 papers found", "5 gaps identified" (as stages complete)
- **Browser notification** when complete (using the Notification API)

### Recommendation 8: Gap → Idea Action Loop (Priority: MEDIUM)

On the Gap Detail page, add a **"Generate Ideas from This Gap"** button that:
1. Pre-fills the pipeline config with the gap as context
2. Runs idea generation focused on this specific gap
3. Links the resulting ideas back to the gap

This closes the **Gap → Idea → Proposal** loop that currently requires manual navigation.

### Recommendation 9: Accessibility Quick Wins (Priority: MEDIUM)

1. Add `<a href="#main-content" class="sr-only focus:not-sr-only">Skip to content</a>` at the top of AppShell
2. Add `aria-live="polite"` to the stage progress container for screen reader announcements
3. Replace bare `<input type="checkbox">` with a proper toggle component using `role="switch"` + `aria-checked`
4. Add `alt` text to all icons that convey meaning (or `aria-hidden="true"` for decorative ones)
5. Manage focus after route changes — focus the main heading on each page

### Recommendation 10: Dark Mode in Header (Priority: LOW)

Move the Light/Dark toggle from Settings → a sun/moon icon button in the top-right header area (next to notification bell). This is where users expect it.

---

## Comparative UX Benchmarking

| Feature | Elephant Rock | Google Scholar | Semantic Scholar | Elicit |
|:--------|:-------------|:---------------|:-----------------|:-------|
| Time to first result | ~22 min | <1s | <1s | ~30s |
| Onboarding | None | None needed | None needed | Tooltip tour |
| Navigation items | 15 | 5 | 4 | 3 |
| Search prominence | ⌘K dialog | Center stage | Center stage | Center stage |
| Progress visibility | Excellent (live) | N/A | N/A | Spinner only |
| Result detail | Excellent (full proposal) | Abstract only | Abstract + TL;DR | Summary + extraction |
| Export | Markdown + LaTeX | BibTeX only | BibTeX only | CSV + BibTeX |

**Elephant Rock's differentiator**: Not search speed, but **depth of output**. A Google Scholar search returns abstracts; Elephant Rock returns full proposals with novelty scores, feasibility analysis, and structured sections. The UX should emphasize this depth, not try to compete on speed.

---

## Implementation Priority Matrix

```
HIGH IMPACT, LOW EFFORT (Do First):
  ├── Dashboard CTA card (0.5 day)
  ├── Navigation grouping with headers (1 day)
  ├── Session ID → advanced section (0.5 day)
  ├── Dark mode in header (0.5 day)
  └── Score context tooltips (0.5 day)

HIGH IMPACT, HIGH EFFORT (Plan Next):
  ├── Guided onboarding flow (2-3 days)
  ├── Idea TL;DR generation (1 day)
  ├── Partial results during pipeline (2-3 days)
  └── Gap → Idea action loop (1 day)

LOW IMPACT, LOW EFFORT (Quick Wins):
  ├── Domain filter dropdown (0.5 day)
  ├── Upload zone collapsible (0.5 day)
  ├── Forgot password link (1 day)
  └── Keyboard shortcut overlay (0.5 day)

LOW IMPACT, HIGH EFFORT (Defer):
  ├── Skip-to-content link + focus management (1 day)
  ├── Screen reader announcements (2 days)
  └── Estimated time remaining for pipeline (1-2 days)
```

---

## Conclusion

Elephant Rock's **core pipeline UX is strong** — the live progress view, structured proposal rendering, and comprehensive idea detail page are genuinely excellent. The platform's weakness is the **first 2 minutes of the user journey**: arriving at an empty dashboard with 15 navigation options and no clear path to value.

The single highest-impact change would be a **"Start Research" card on the dashboard** that lets first-time users type a topic and click one button to begin. This would reduce time-to-value from 23 minutes to under 5 minutes for the first run and eliminate the need to navigate away from the dashboard.

The platform is at a **B- overall UX grade** today. With the 5 "High Impact, Low Effort" items addressed, it would move to **B+**. With the full set of recommendations, it could reach **A-** — matching the quality of its backend pipeline with an equally polished frontend experience.
