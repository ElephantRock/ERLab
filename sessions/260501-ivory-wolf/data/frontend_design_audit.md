# Elephant Rock — Front-End Design Audit & Style Guide

**Auditor**: Senior Product Designer (Codebase-only audit)
**Date**: 2026-05-12
**Scope**: 98 frontend files — 20 pages, 51 components, 12 UI primitives, globals.css
**Method**: Static analysis of every `className`, color, spacing, typography, and microcopy string

---

## Part 1: Design Debt Inventory

### D-01. Color Token Anarchy — **CRITICAL**

The design system defines 18 HSL tokens in `globals.css` (`--primary`, `--destructive`, etc.), but the codebase contains **77 instances of hardcoded Tailwind color classes** that bypass the token system entirely.

| Hardcoded Color | Count | Found In |
|:----------------|:------|:----------|
| `text-red-800/500/700` | 13 | idea-detail, gap-card, run-detail, score-badge |
| `text-green-800/600/500` | 16 | idea-detail, gap-card, run-detail, score-badge |
| `text-blue-800/600/500` | 16 | idea-detail, gap-card, notification-bell, global-search |
| `text-yellow-800/600/500` | 6 | idea-detail, score-badge |
| `text-purple-800/500/300` | 5 | idea-detail, run-detail |
| `bg-red-500/100/950` | 11 | notification-bell, score-badge, run-card |
| `bg-green-500/100` | 8 | score-badge, gap-card, idea-card |
| `bg-yellow/amber-500/100` | 6 | gap-card, score-badge |
| `bg-blue-500/100/900` | 4 | notification-bell, knowledge-graph |
| `text-gray-800/500/400/300` | 4 | autonomous, knowledge-graph |

**Why this matters**: Dark mode breaks silently. `text-green-800` becomes invisible on the dark `222.2 84% 4.9%` background. The notification bell's `bg-red-500` doesn't adapt. Users in dark mode see broken contrast in score badges, status pills, and the knowledge graph.

**Fix**: Replace all hardcoded colors with semantic tokens. Add to `globals.css`:
```
--success: 142 76% 36%;
--warning: 38 92% 50%;
--info: 217 91% 60%;
```
Then use `text-success`, `bg-warning`, etc. throughout.

---

### D-02. CardTitle Size Schizophrenia — **HIGH**

The `CardTitle` UI primitive defaults to `text-2xl font-semibold`, but 11 of 16 usages override it:

| Override | File |
|:---------|:-----|
| `text-lg` | autonomous-form, run-config-form, feedback-form, comment-thread, share-dialog, autonomous page |
| `text-xl` | onboarding-overlay |
| `text-sm font-mono` | cycle-progress |
| No override (keeps `text-2xl`) | dashboard stat cards |

Cards on the same page use different title sizes — a dashboard with `text-2xl` stat cards next to `text-lg` pipeline config creates visual hierarchy confusion.

**Fix**: Change `CardTitle` default to `text-lg font-semibold`. Use `text-2xl` only for page-level headings.

---

### D-03. Label Inconsistency — **HIGH**

Two distinct label styles coexist with no clear rule:

| Style | Usage | Files |
|:------|:------|:------|
| `text-sm font-medium` | Form labels (login, settings, pipeline config) | 11 instances |
| `text-xs text-muted-foreground mb-1 block` | Filter labels (gaps, ideas, plugins) | 8 instances |
| Raw `<label>` with no styling | Run-config-form toggles | 3 instances |

Form labels are prominent (`font-medium`); filter labels are de-emphasized (`text-muted-foreground`). Toggle labels have no consistent styling at all — some use `<label className="text-sm font-medium">`, others use bare text next to `<input type="checkbox">`.

**Fix**: Two label variants:
- **Primary label**: `text-sm font-medium` — for form inputs that require user action
- **Secondary label**: `text-xs text-muted-foreground uppercase tracking-wider` — for filters, sort controls, metadata

---

### D-04. Button Style Drift — **MEDIUM**

28 raw `<button>` elements exist outside the `<Button>` component. These bypass the design system's `buttonVariants`:

| Pattern | File |
|:--------|:-----|
| `text-blue-600 hover:underline cursor-pointer bg-transparent border-none p-0` | idea-detail.tsx |
| `text-primary hover:underline` | dashboard.tsx |
| `text-primary underline` | login.tsx (×4) |
| `text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded border border-input` | stage-model-selector.tsx |
| `text-xs bg-primary text-primary-foreground px-3 py-1 rounded hover:bg-primary/90` | stage-model-selector.tsx |

Some are link-buttons, some are pill buttons, some are ghost buttons. None share a common variant.

**Fix**: Add link-like variant to `<Button>`: `variant="link"`. Replace raw `<button>` with `<Button variant="ghost">` or `<Button variant="link">`.

---

### D-05. Inconsistent Error Display — **MEDIUM**

Error messages use 4 different rendering patterns:

| Pattern | Files |
|:--------|:------|
| `<span className="text-sm text-destructive">` | autonomous.tsx |
| `<p className="text-sm">{error}</p>` (no color) | costs.tsx, governance.tsx, memory.tsx |
| `<Alert variant="destructive">` | pipeline-new.tsx, run-detail.tsx |
| `toast.error(...)` | idea-detail.tsx, export-dialog.tsx, feedback-form.tsx |

Some errors are red, some inherit body color (invisible), some use toast notifications, some use inline alerts. Users cannot predict where errors will appear or how they look.

**Fix**: Standardize on two patterns:
1. **Toast** for action outcomes (save, delete, export)
2. **Inline `<Alert variant="destructive">`** for page-level errors
3. Ban plain `<p>` / `<span>` for error text

---

### D-06. Shadow Token Sprawl — **LOW**

Shadow usage is minimal but inconsistent:

| Value | Count | Context |
|:------|:------|:--------|
| `shadow-sm` | 3 | Card component default |
| `shadow-lg` | 4 | notification dropdown, global search |
| `shadow-md` | 2 | gap-card hover |
| `shadow-xl` | 1 | onboarding overlay |
| `shadow` | 1 | knowledge-graph |

No clear rule: when do you use `shadow-sm` vs `shadow-lg`? The Card primitive defaults to `shadow-sm`, but overlays jump to `shadow-xl`.

**Fix**: Establish three shadow levels:
- **Resting**: `shadow-sm` — cards, inputs
- **Elevated**: `shadow-md` — dropdowns, popovers
- **Floating**: `shadow-xl` — modals, overlays

---

### D-07. Spacing Scale Violations — **LOW**

The most common gap value is `gap-2` (88 uses), followed by `gap-3` (34), `gap-4` (28), and `gap-1` (25). This is healthy. But `space-y` shows a different pattern:

| Value | Count | Issue |
|:------|:------|:------|
| `space-y-6` | 28 | Used for page-level section spacing |
| `space-y-4` | 29 | Used for card content spacing |
| `space-y-3` | 32 | Used for form field spacing |
| `space-y-2` | 34 | Used for tight list spacing |
| `space-y-8` | 1 | One-off in knowledge-graph |

The gap between sections (`space-y-6` = 24px) and form fields (`space-y-3` = 12px) is reasonable. The single `space-y-8` outlier should be normalized.

---

### D-08. Transition Inconsistency — **LOW**

| Transition | Count | Context |
|:----------|:------|:--------|
| `transition-colors` | 18 | Buttons, links, nav items |
| `transition-all` | 11 | Cards, overlays, search |
| `transition-shadow` | 2 | Gap card hover |
| `transition-transform` | 2 | Hover scale effects |
| `transition-opacity` | 1 | Fade in/out |

`transition-all` is expensive (triggers layout on every property change). It's used on cards and overlays where only colors or shadows change.

**Fix**: Replace `transition-all` with specific `transition-colors` or `transition-shadow`.

---

## Part 2: Voice & Tone Audit

### T-01. Placeholder Text — Inconsistent Capitalization

| Placeholder | Style |
|:------------|:------|
| `"AI/NLP"` | UPPERCASE technical term |
| `"e.g., machine learning, nlp, computer vision"` | Sentence case |
| `"Search ideas by title..."` | Sentence case with trailing ellipsis |
| `"Filter by domain..."` | Sentence case with trailing ellipsis |
| `"Optional notes..."` | Sentence case with trailing ellipsis |
| `"Optional notes (max 2000 chars)..."` | Includes constraint |
| `"Optional amendment…"` | Unicode ellipsis (…) not three dots (...) |
| `"transformer attention, few-shot learning"` | No capitalization |
| `"you@example.com"` | Email format |

Three problems:
1. **Ellipsis inconsistency**: Some use `...` (three ASCII dots), one uses `…` (Unicode ellipsis)
2. **Capitalization**: Some start with "e.g.," some with "Search", some with lowercase
3. **Constraint visibility**: Only one placeholder shows a character limit

**Standard**: All placeholders should be:
- **Sentence case**, no leading capital for sentence fragments
- **Three dots** (`...`) for trailing off — never Unicode `…`
- **No "e.g."** — use descriptive phrasing: `"machine learning, nlp, computer vision..."`

---

### T-02. Error Message Voice

Current error messages fall into two voices:

| Voice | Example | Count |
|:------|:--------|:------|
| **Passive/Technical** | `"Failed to load history"` | 11 |
| **Action-oriented** | `"Idea refined — scores updated"` | 5 |
| **Raw technical** | `err.message` (passed through) | 8 |
| **Friendly** | `"Plugin installed successfully"` | 3 |

**The problem**: `"Failed to load history"` blames the system without helping the user. Passing `err.message` directly exposes internal API errors like `"connect ECONNREFUSED 127.0.0.1:8000"`.

**Standard**: All user-facing errors should follow:
> **[What happened]** + **[What to do]**

Examples:
- ❌ `"Failed to load history"` → ✅ `"Couldn't load your run history. Try refreshing the page."`
- ❌ `err.message` → ✅ `"Something went wrong. Please try again."` (hide raw errors)
- ✅ `"Idea refined — scores updated"` (good — confirms the action)

---

### T-03. Button Microcopy

| Button | Page | Tone |
|:-------|:-----|:-----|
| `"Start Pipeline"` | pipeline-new | Action verb, clear |
| `"Start Pipeline"` | pipeline-new (loading) | → `"Starting..."` ✅ |
| `"New Pipeline"` | dashboard | Noun phrase |
| `"Search"` | memory | Action verb |
| `"Save Config"` | stage-model-selector | Action verb |
| `"Reset to Defaults"` | stage-model-selector | Action phrase |
| `"View all"` | dashboard | Generic |
| `"Previous"` / `"Next"` | ideas, gaps | Navigation |
| `"Cancel Run"` | run-detail | Action verb |
| `"Back"` | run-detail | Navigation |
| `"Search… ⌘K"` | app-shell | Action + shortcut |
| `"Switch to dark mode"` | app-shell | Descriptive |

**Inconsistency**: `"New Pipeline"` (noun) vs `"Start Pipeline"` (verb) for the same action. `"View all"` is vague — view all what?

**Standard**:
- Primary actions: **Verb first** — "Start", "Save", "Export", "Search"
- Navigation: **Destination** — "Back to Pipelines", not just "Back"
- Loading states: **Present participle** — "Starting...", "Saving..."

---

### T-04. Toast Notification Consistency

| Toast | Style |
|:------|:------|
| `"Feedback submitted"` | Passive ✅ |
| `"Comment added"` | Passive ✅ |
| `"Share link created"` | Passive |
| `"Link copied to clipboard"` | Passive |
| `"Plugin installed successfully"` | With adverb |
| `"PDF exported successfully"` | With adverb |
| `"Idea refined — scores updated"` | Em-dash + detail |

Three patterns: bare passive, passive + "successfully", and passive + em-dash detail.

**Standard**: Use the bare passive consistently:
- ✅ `"Feedback submitted"`
- ✅ `"Plugin installed"`
- ✅ `"PDF exported"`
- ❌ `"Plugin installed successfully"` — redundant

---

### T-05. Page Title Conventions

| Page | `<h1>` / Heading Text |
|:-----|:----------------------|
| Dashboard | `"Dashboard"` |
| Pipeline New | `"Pipeline"` |
| Ideas Browser | `"Research Ideas"` |
| Gaps Explorer | `"Research Gaps"` |
| Literature | `"Literature"` |
| Knowledge Search | `"Knowledge Search"` |
| Knowledge Graph | `"Knowledge Graph"` |
| Memory | `"Memory Browser"` |
| Autonomous | (no h1, sub-card titles only) |
| Sessions | `"Sessions"` |
| Costs | `"Cost Tracking"` |
| Governance | `"Governance Queue"` |
| Traces | `"Traces"` |
| Plugins | `"Plugins"` |
| Settings | `"Settings"` |
| Login | (no h1, card title `"Sign In"`) |
| Run Detail | `"Run #N"` |

**Inconsistency**: Some use the feature name (`"Dashboard"`, `"Literature"`), some use compound names (`"Research Ideas"`, `"Governance Queue"`), one uses just `"Pipeline"` for the pipeline configuration page.

**Standard**: Page titles = feature name, no qualifiers:
- `"Dashboard"` ✅
- `"Pipelines"` (not just `"Pipeline"`)
- `"Ideas"` (not `"Research Ideas"`)
- `"Gaps"` (not `"Research Gaps"`)
- `"Knowledge"` (not `"Knowledge Search"`)
- `"Graph"` (not `"Knowledge Graph"`)
- `"Memory"` ✅
- `"Autonomous"` ✅
- `"Sessions"` ✅
- `"Costs"` ✅
- `"Governance"` ✅
- `"Traces"` ✅
- `"Plugins"` ✅
- `"Settings"` ✅

---

## Part 3: Simplified Style Guide

### Typography Scale

| Role | Class | Size | Weight | Usage |
|:-----|:------|:-----|:-------|:------|
| **Page title** | `text-2xl font-semibold` | 24px | 600 | One per page, top heading |
| **Section title** | `text-lg font-semibold` | 18px | 600 | Card headers, section breaks |
| **Body** | `text-sm` | 14px | 400 | Paragraphs, descriptions, labels |
| **Caption** | `text-xs text-muted-foreground` | 12px | 400 | Metadata, timestamps, hints |
| **Micro** | `text-[10px] text-muted-foreground` | 10px | 400 | Keyboard shortcuts, badges |

### Spacing Scale

| Token | Value | Usage |
|:------|:------|:------|
| `space-y-2` | 8px | Tight lists, badge groups |
| `space-y-3` | 12px | Form fields, inline groups |
| `space-y-4` | 16px | Card content, detail rows |
| `space-y-6` | 24px | Page sections, major blocks |
| `gap-2` | 8px | Default flex/grid gap |
| `gap-4` | 16px | Wide flex/grid gap |
| `p-2` | 8px | Tight padding (badges, pills) |
| `p-4` | 16px | Card padding |
| `p-6` | 24px | Page-level padding |

### Color Tokens

| Token | Light | Dark | Usage |
|:------|:------|:-----|:------|
| `--primary` | Blue 221/83/53 | Blue 217/91/60 | CTAs, links, active states |
| `--destructive` | Red 0/84/60 | Red 0/63/31 | Errors, danger actions |
| `--muted-foreground` | Gray 215/16/47 | Gray 215/20/65 | Captions, secondary text |
| `--border` | Gray 214/32/91 | Gray 217/33/18 | Dividers, input borders |
| **`--success`** *(new)* | Green 142/76/36 | Green 142/60/45 | Positive scores, "completed" |
| **`--warning`** *(new)* | Amber 38/92/50 | Amber 38/80/45 | Medium scores, "running" |
| **`--info`** *(new)* | Blue 217/91/60 | Blue 217/91/60 | Informational, neutral |

### Component Patterns

| Component | Variant | Class |
|:----------|:--------|:------|
| **Primary button** | default | `<Button>Save</Button>` |
| **Secondary button** | outline | `<Button variant="outline">Cancel</Button>` |
| **Danger button** | destructive | `<Button variant="destructive">Delete</Button>` |
| **Link button** | ghost | `<Button variant="ghost">View Details</Button>` |
| **Card** | default | `<Card><CardHeader><CardTitle className="text-lg">...</CardTitle></CardHeader><CardContent>...</CardContent></Card>` |
| **Badge** | default/secondary/outline | `<Badge>status</Badge>` |
| **Error** | destructive alert | `<Alert variant="destructive"><AlertDescription>message</AlertDescription></Alert>` |
| **Toast** | success/error | `toast.success("Action completed")` / `toast.error("Couldn't do X. Try Y.")` |

### Icon Sizes

| Size | Class | Usage |
|:-----|:------|:------|
| **Small** | `h-3 w-3` | Inline icons next to text |
| **Default** | `h-4 w-4` | Buttons, list items, nav |
| **Medium** | `h-5 w-5` | Card headers, feature highlights |
| **Large** | `h-8 w-8` | Empty states, feature icons |

### Border Radius

| Value | Usage |
|:------|:------|
| `rounded-sm` | Small elements, tags |
| `rounded-md` | Buttons, inputs |
| `rounded-lg` | Cards, panels |
| `rounded-full` | Avatars, status dots, badges |

### Voice & Tone Rules

1. **Direct address**: Use "your" not "the" — "your pipeline" not "the pipeline"
2. **Active voice**: "Export PDF" not "PDF is exported"
3. **No exclamation marks**: Professional, not enthusiastic
4. **Sentence case** everywhere except proper nouns and acronyms
5. **Error format**: "Couldn't [action]. [Suggestion]."
6. **Success format**: "[Noun] [verb past tense]" — "Pipeline completed", "Idea saved"
7. **Loading format**: "[Verb]ing..." — "Starting...", "Loading..."
8. **Truncation marker**: Always `...` (three ASCII dots), never `…`

---

## Summary Statistics

| Metric | Count |
|:-------|:------|
| Total `className` instances | ~1,150 |
| Hardcoded color violations | 77 |
| Raw `<button>` outside design system | 28 |
| CardTitle size overrides | 11 of 16 |
| Label style variants | 3 (should be 2) |
| Error display patterns | 4 (should be 2) |
| Placeholder ellipsis inconsistency | 2 styles (`...` vs `…`) |
| Toast voice inconsistency | 3 patterns |
| **Estimated remediation effort** | **~16 hours** |

### Priority Remediation Order

| Priority | Fix | Effort | Impact |
|:---------|:----|:-------|:-------|
| **P0** | Replace 77 hardcoded colors with tokens | 4h | Fixes dark mode |
| **P1** | Standardize CardTitle to `text-lg` | 1h | Visual consistency |
| **P1** | Standardize label styles to 2 variants | 2h | Form consistency |
| **P1** | Standardize error display (2 patterns only) | 2h | UX reliability |
| **P2** | Replace 28 raw `<button>` with `<Button>` | 3h | Design system compliance |
| **P2** | Normalize placeholder text | 1h | Polish |
| **P2** | Normalize toast voice | 1h | Voice consistency |
| **P3** | Normalize transitions | 1h | Performance + consistency |
| **P3** | Add success/warning/info tokens | 1h | Semantic color system |
