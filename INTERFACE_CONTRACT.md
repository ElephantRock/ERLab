# 🐘 Elephant Rock — Interface Contract

> **Status: v0 specification — derived from [`PRODUCT.md`](./PRODUCT.md).**
> This is the engineering specification that makes `PRODUCT.md`'s principles
> *load-bearing*. Where `PRODUCT.md` says *what* and *why*, this says *how* —
> the only legal paths, the shared primitives, and the enforcement that makes
> them impossible to bypass without an explicit, recorded exception.
>
> **Relationship to existing code:** This contract *consolidates and completes*
> the work already begun — `globals.css` tokens, `EmptyState`, `ErrorCard`,
> the `Button` variants, TanStack Query's QueryClient. None of it is wrong;
> all of it was *optional*. This document makes it *the* path.
>
> **Every section cites the `PRODUCT.md` principle it derives from.** A
> primitive that cannot cite a principle does not belong in this contract.

---

## 0. The One-Way Ratchet

The backend enforces its philosophy via 2,848 tests — a stage that doesn't
emit a receipt fails. The frontend has had no equivalent. This contract is
that equivalent.

**Three things make a contract load-bearing rather than aspirational:**

1. **Single path.** There is one sanctioned way to fetch, one to color, one
   to show empty / error / loading. Alternatives exist in the codebase
   today; they are deprecated on contact with this contract.
2. **Mechanical enforcement.** Lint rules fail the build; the shared
   primitives are imported, not reinvented. Review cites `PRODUCT.md`
   sections, not personal taste.
3. **Recorded exceptions.** When a page genuinely cannot use the path (e.g.
   a non-fetch side effect), the deviation is documented in-code with a
   `// CONTRACT-EXCEPTION: <reason, citing PRODUCT.md>` comment. Exceptions
   are visible; they are not silent.

> The ratchet only tightens. Once a page complies, it stays compliant.

---

## 1. Data Layer — `useResource` (cites: PRODUCT.md §"Interface Principles" 2, 6)

### Problem being solved
11 of 20 pages hand-roll `useEffect + useState + loading + error`. This
produces: no caching, no dedup, no retry, dead code (`loadPending` in
governance), state-after-unmount bugs, and silent `console.warn` swallows.
The root cause: TanStack Query exists but is optional. `useResource` makes it
the only legal fetch path.

### Specification

```ts
// src/lib/useResource.ts — the only sanctioned data-fetching hook.

type ResourceState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: Error; retry: () => void }
  | { status: "empty"; data: T };  // T is [] or null/empty-shaped

function useResource<T>(
  key: readonly unknown[],
  fetcher: () => Promise<T>,
  options?: { staleTime?: number; isEmpty?: (d: T) => boolean },
): ResourceState<T>;
```

**Properties (non-negotiable):**

- **State is a discriminated union, not four booleans.** Callers
  pattern-match on `status`; impossible states are unrepresentable. This
  kills the "loading and error both true" class of bug.
- **Never throws to the caller.** Errors surface as `{ status: "error" }`
  with a `retry` closure. No more `console.warn` swallows — the error is a
  first-class render state (PRODUCT.md §6: "if data failed to load, it says so").
- **Empty is distinct from ready.** `isEmpty` discriminates "loaded
  nothing" from "loaded something," so the empty state is never dressed up
  as success (PRODUCT.md anti-pattern: *The Decorative Indicator*).
- **Backed by TanStack Query.** `useResource` is a thin wrapper over
  `useQuery`; caching, dedup, refetch-on-focus, retry are inherited, not
  re-implemented.
- **`staleTime` defaults to 30s** (matches existing QueryClient). Pages
  override only when freshness is product-critical (e.g. a running-pipeline
  view), and the override cites why.

### Usage contract

```tsx
// ✅ Legal
const ideas = useResource(["ideas", { limit: 50 }], () => listIdeas({ limit: 50 }));
switch (ideas.status) {
  case "loading":  return <Loading />;
  case "error":    return <Errored onRetry={ideas.retry} />;
  case "empty":    return <Empty what="ideas" />;
  case "ready":    return <IdeaGrid ideas={ideas.data} />;
}

// ❌ Forbidden by lint rule `erock/no-raw-use-effect-fetch`
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
useEffect(() => { fetchThing().then(setData).finally(() => setLoading(false)); }, []);
```

### Migration
The 11 non-compliant pages migrate by becoming `useResource` consumers. The
act of migration *deletes* the dead `loadPending`, *fixes* the unmount bug,
*adds* caching, and *surfaces* the swallowed errors — all in the same pass,
because they are all the same root (PRODUCT.md root-cause analysis).

---

## 2. State Primitives — `<DataView>` (cites: PRODUCT.md §"Interface Principles" 6)

### Problem being solved
Three patterns coexist for loading (`<Skeleton>`, `<Loader2>`, `"Loading..."`
text), three for empty (shared `<EmptyState>`, inline `<Card>`, inline
`<FlaskConical>`), and errors are ad-hoc. `DataView` composes them into the
single render primitive for any resource-bound surface.

### Specification

```tsx
// Composes useResource's four states into renderable output.

function DataView<T>(props: {
  resource: ResourceState<T>;
  empty?:  { what: string; action?: ReactNode };   // defaults to a sensible empty
  error?:  { onRetry?: () => void };                // defaults to ErrorCard + retry
  loading?: { lines?: number };                     // defaults to a content-shaped skeleton
  children: (data: T) => ReactNode;                 // render-prop for the ready/empty-with-data case
}): ReactNode;
```

**Properties:**

- **The ready case is a render-prop**, so the four states never leak into
  the page's JSX tree. A page becomes: fetch → `<DataView>` → content.
- **Empty is a first-class state, not "ready with `[]`."** This is the
  distinction `useResource` makes, surfaced in the component.
- **Loading is content-shaped**, not a generic spinner. A list shows list
  skeletons; a detail page shows detail skeletons. This is already the
  dashboard's pattern — `DataView` makes it universal.
- **Error always offers retry** (PRODUCT.md §6). No dead-end error screens.

### Convention
> **Mutations → `toast`. Queries → `<DataView>`/`useResource`.** (This is
> already `ErrorCard`'s stated convention; `DataView` enforces it
> structurally.)

### testId ownership (added Tier 2.5)

When a page passes `testId="X"` to `<DataView>`, two layers of testids
derive from the stem and **must not collide**:

```
WRAPPER (owned by DataView itself — page tests target these):
  X-loading, X-error, X-empty, X-ready

INNER PRIMITIVES (default when a stem is set):
  X-error-card    (the <ErrorCard> inside the error branch)
  X-empty-state   (the <EmptyState> inside the empty branch)
```

Rules:
- **Page-level tests target the wrapper ids** (e.g. `ideas-error`). These
  identify which DataView state is rendered — the load-bearing assertion.
- **Inner ids are for component-specific assertions** (rare).
- **Never pass `error.testId` / `empty.testId` equal to a wrapper-owned
  id.** `error={{ testId: "ideas-error" }}` when `testId="ideas"` creates
  a duplicate and `getByTestId` throws. The default (`X-error-card`) is
  correct in almost all cases.
- If no stem is passed, wrappers get `data-view-*` and inner primitives
  get `error-card` / `empty-state`.

This convention is documented (not runtime-enforced). If the duplicate-
testid pattern recurs after documentation, escalate to a dev-only runtime
invariant.

#### Page-owned testId collisions (Tier 3.5)

A third collision class: the page may already use one of the wrapper-owned
ids (`X-error`, `X-empty`, etc.) for a *different* purpose — e.g. a
mutation-error banner with `data-testid="autonomous-error"` that predates
the DataView adoption. When adopting DataView with `testId="autonomous"`,
both the mutation banner and the history-fetch error wrapper would produce
`autonomous-error`, causing `getByTestId` to throw on duplicates.

Rule: **when adopting DataView with `testId="x"`, scan the page for
pre-existing uses of `x-loading`, `x-error`, `x-empty`, `x-ready`.** If any
exist for another purpose, either rename the pre-existing id (e.g.
`autonomous-mutation-error`) or choose a more specific stem (e.g.
`testId="autonomous-history"`).

This is the last documentation warning for this class. A fourth collision
after this documentation triggers a dev-only runtime invariant.

#### `isEmpty` for non-standard shapes (Tier 3.5)

`useResource`'s default `isEmpty` covers common shapes: `null`, `[]`, `""`,
`{ total: 0 }`, and objects with a zero-length array under standard keys
(`ideas`, `gaps`, `runs`, `pending`, `items`, `results`, `data`).

For **domain-shaped payloads** with non-standard list keys — e.g.
`{ cycles: [] }`, `{ sessions: [] }`, `{ memories: [] }` — the default will
NOT detect empty. Callers **must pass `isEmpty` explicitly**:

```ts
useResource(["history"], fetchHistory, {
  isEmpty: (d) => d.cycles.length === 0,
});
```

The default list is intentionally NOT expanded with every domain noun. Empty
semantics belong to the resource owner, not a global heuristic.

---

## 3. Type Scale — Calibrated to the Reading Surface (cites: PRODUCT.md §"Interface Principles" 1, 5)

### Problem being solved
Type sizes today range from `text-[8px]` (stage timers) to `text-3xl` (hero),
with `text-[10px]`/`[9px]` mono labels used ~30+ times as section headers.
This is a telemetry density, not a reading density. The scale below is
derived from the primary task (read 2,000+ words of proposal) and propagates
outward.

### Specification — two named scales

```
READING SCALE — for prose surfaces (proposal body, gap description, paper text)
─────────────────────────────────────────────────────────────────────────────
prose-body      text-[17px] leading-[1.7]   the proposal itself
prose-lede      text-[19px] leading-[1.6]   abstract / opening paragraph
prose-caption   text-[13px] leading-[1.5]   footnotes, provenance notes
prose-quote     text-[15px] leading-[1.6] italic  blockquotes, cited text

The reading scale is non-negotiable on reading surfaces. It is the calibrator;
everything else is calibrated against it, never the reverse.
```

```
UI SCALE — for everything around the reading surface (chrome, controls, metadata)
─────────────────────────────────────────────────────────────────────────────
ui-display     text-[28px] font-display     page titles, hero headings
ui-heading     text-[18px] font-semibold    card & section headings
ui-label       text-[14px]                  buttons, nav, primary controls
ui-meta        text-[13px]                  metadata, timestamps, secondary info
ui-micro       text-[11px]                  the floor. badges, tags, dense tables

ui-micro is the minimum. There is no text-[10px], [9px], or [8px] in the
product. The `font-mono uppercase tracking-widest` telemetry-label pattern is
removed from section headers; it survives only in genuinely tabular/data
contexts (traces, ops tables), never as a heading.
```

### Enforcement
- **Tailwind preset** exposes only these as named sizes; arbitrary `text-[Npx]`
  below `ui-micro` (11px) is a lint error.
- **The reading scale tokens ship as utility classes** (`.text-prose-body`
  etc.) so reading surfaces are unambiguous in review.

### What this resolves (from the UI evaluation)
- Kills `text-[8px]` elapsed timers and `text-[9px]` micro-badges.
- Removes the telemetry-header pattern from research sections.
- Makes the reading workspace visibly the largest, calmest surface — the
  PRODUCT.md §1 commitment, made structural.

---

## 4. Color Tokens — Completed & Enforced (cites: PRODUCT.md §"Interface Principles" 6)

### Problem being solved
The DA-01 token sweep left 6 hardcoded sites (`bg-red-100`, `text-yellow-600`,
`bg-green-500`, etc.). Root cause: tokens were optional. The 6 sites are
symptoms; the fix is making raw colors a build error.

### Specification — token completion

`globals.css` is extended so every color used anywhere has a token. The
current gap is **banner backgrounds** (the traces warning/error banners use
`bg-yellow-50`/`bg-red-50` with no token). Add:

```css
:root {
  --banner-warning-bg:  38 88% 96%;
  --banner-warning-border: 38 88% 50%;
  --banner-error-bg: 0 72% 96%;
  --banner-error-border: 0 72% 51%;
}
.dark {
  --banner-warning-bg: 38 30% 14%;
  --banner-warning-border: 38 80% 55%;
  --banner-error-bg: 0 30% 14%;
  --banner-error-border: 0 62% 45%;
}
```

Tailwind extend gains `banner-warning-{bg,border}`, `banner-error-{bg,border}`.

### Enforcement — the mechanical ratchet

```js
// eslint — erock/no-raw-colors
// Forbids: bg-{red,green,blue,yellow,amber,orange,pink,rose,violet,indigo,cyan,teal,emerald,lime,sky}-*
// Forbids: arbitrary text-[...]/bg-[...] containing hex or hsl()
// Forbids: text-[8px], text-[9px], text-[10px]  (below the ui-micro floor)
// Allows:   only semantic tokens (success, warning, destructive, banner-*, accent, muted, primary, ...)
```

Bare Tailwind palette colors are removed from the codebase; semantic tokens
are the only path. The 6 current violations are fixed as the token
completes — `bg-red-100 text-red-800` → `bg-destructive/10 text-destructive`;
the traces banners → `banner-warning-*`/`banner-error-*`.

### Why this is permanent, not a sweep
A token sweep fixes today's 6. A lint rule makes the 7th impossible. DA-01
through DA-06 were sweeps; this is the ratchet that ends the need for DA-07.

---

## 5. Information Architecture — Derived from the Core Loop (cites: PRODUCT.md §"The Core Loop")

### Problem being solved
The current nav groups — **Studio / Research / System / Advanced** — mirror
backend feature buckets, not the researcher's workflow. Symptom: Governance
("Review") is under Studio but Operations is under System, though both are
queues; Knowledge Search is a real page with no nav entry; 13 routes are
unreachable on mobile. Root cause: the IA mirrors the backend, violating
PRODUCT.md anti-pattern *The Mirror*.

### Specification — nav reorganized by the loop

```
┌─────────────────────────────────────────────────────────────┐
│ DIRECT    New Run · (Autonomous)                            │
│            ↳ feeds the loop; <1 min to launch               │
│                                                              │
│ TRIAGE    Results · Gaps · (Literature)                     │
│            ↳ scanning surfaces; density allowed here        │
│                                                              │
│ READ      [current proposal workspace] · Knowledge Search   │
│            ↳ the center; reached from any triage item       │
│                                                              │
│ REFINE    [contextual, on the artifact] · Sessions          │
│            ↳ refinement lives on the reading surface;       │
│              Sessions groups the refinement history          │
│                                                              │
│ GOVERN    Review · (Export is an action, not a destination)  │
│                                                              │
│ ──────── (separator) ────────                                │
│                                                              │
│ SECONDARY  Operations · Costs · Traces · Memory ·           │
│            Knowledge Graph · Plugins · Settings             │
│            ↳ functional, not tonal; for power users         │
└─────────────────────────────────────────────────────────────┘
```

**Properties:**

- **Grouped by loop step, not by backend subsystem.** A researcher's mental
  model is "what am I doing," not "which feature am I using."
- **Reading has no top-level destination — it's reached *through* triage.**
  You don't navigate *to* a proposal; you navigate *from* a result. This
  matches the actual workflow and prevents the orphan-proposal problem.
- **Refinement is contextual, not a destination.** Fix/regenerate/feedback
  live on the artifact (PRODUCT.md §4). Sessions is the only refinement
  surface that's a destination, because it's cross-artifact.
- **Secondary surfaces are below a separator.** They're reachable and
  functional but explicitly *do not set the tone* (PRODUCT.md §"Scope").
- **No orphan routes.** Knowledge Search, currently unreachable, enters
  the READ group. Every page has exactly one nav home.

### Mobile
`MOBILE_ITEMS` is replaced by a **mobile sheet** exposing the full IA. The
bottom-nav shortcut keeps only DIRECT (New Run), TRIAGE (Results), READ
(continue last), GOVERN (Review). 13 unreachable routes → 0. This is a
PRODUCT.md §"Scope" commitment made structural.

---

## 6. The Score Primitive — `<ScoreReport>` (cites: PRODUCT.md §"Interface Principles" 2; anti-pattern *The Flat Score*)

### Problem being solved
`ScoreBadge` is 18 lines showing `0.82 High`. Scores are the product
(PRODUCT.md §2: "trust must be earned visibly"). Novelty has 4 axes,
feasibility 6, evaluation 7, plus 5 mechanical metrics — none exposed. The
flat pill flattens the product.

### Specification

```tsx
// A score is never a flat number. It is a summary + an inspectable breakdown.

function ScoreReport(props: {
  kind: "novelty" | "feasibility" | "overall";
  summary: number;                    // the headline, still shown
  confidence?: number;                // PRODUCT.md §2: uncertainty is visible
  axes?: Array<{ name: string; score: number; weight: number }>;
  evidence?: { closestPriorWork?: PriorWork[]; dimensions?: Dimension[] };
}): ReactNode;
```

**Properties:**

- **Summary + breakdown in one primitive.** The pill survives as the
  summary (scannable in triage), but it is always backed by a breakdown
  reachable on click/hover — axis bars, weights, closest prior work.
- **Confidence is rendered.** A 0.5 "unverifiable" novelty shows *as*
  uncertain (PRODUCT.md §2). The pill's color/weight reflects confidence,
  not just score. This is the integrity commitment made visible.
- **Comparison-ready.** The primitive accepts multiple ideas' scores so the
  triage view can show relative standing — addressing PRODUCT.md open
  question 6 (compare side-by-side) without committing to it yet.

### What this resolves
The flat-score anti-pattern, the missing axis breakdown, and the
"unverifiable dressed as confident" risk all collapse into one primitive
that *cannot* flatten a score by construction.

---

## 7. Status & State — Truthful by Construction (cites: PRODUCT.md §"Interface Principles" 6; anti-pattern *The Decorative Indicator*)

### Problem being solved
`SYS_OK`, pulsing green "system ready" dots, hardcoded "Local GPU" labels —
decorative indicators that don't reflect state. Root cause: UI surfaces
backend flags verbatim rather than meaning.

### Specification

**A status indicator either reflects real, queryable state, or it does not
exist.** Concretely:

- `SYS_OK` footer → **removed**. If system health matters, it's a real
  `/status` query rendered in Operations, not a decorative footer.
- "System ready" pulsing dot → bound to an actual health query, or removed.
- "Local GPU" → reads `systemStatus.config.default_provider`; if absent,
  shows "—" not a guess.
- Stage elapsed timers → kept (they're real), but rendered at `ui-micro`
  (11px), never `text-[8px]`.

### Convention (codified)
> **No hardcoded status text.** Any string implying system state
> (`"ready"`, `"ok"`, `"connected"`) must be sourced from a query or omitted.

---

## 8. Enforcement — Making It Load-Bearing

The contract is only as strong as its enforcement. Three layers, each
mechanical:

### 8.1 Lint (build-time, non-negotiable)
```
erock/no-raw-colors           — §4. Only semantic tokens.
erock/no-raw-use-effect-fetch — §1. Fetching must go through useResource.
erock/no-sub-micro-type       — §3. No text below ui-micro (11px).
erock/no-telemetry-headings   — §3. font-mono uppercase tracking-widest
                                banned as a heading style.
```
Each rule links to its `PRODUCT.md` justification in its docstring. Failures
cite the principle violated, not a generic lint message.

### 8.2 Shared primitives (the only imports allowed)
- Fetch: `useResource` (§1).
- Render states: `<DataView>` (§2).
- Scores: `<ScoreReport>` (§6).
- Status: sourced from a query, never hardcoded (§7).

A page that reinvents these is non-compliant by definition. Review rejects
on these grounds citing the contract section.

### 8.3 Review checklist (cites PRODUCT.md directly)
Every UI PR answers:
- [ ] *Which `PRODUCT.md` principle does this serve?* (cite section)
- [ ] *Which anti-pattern does it avoid?* (cite name)
- [ ] *Does it use the sanctioned primitives?* (or a recorded exception)
- [ ] *Is every status indicator truthful?* (§7)
- [ ] *Is every score inspectable?* (§6)

A PR that cannot answer #1 has no arbiter to justify it and should not merge.

---

## 9. Migration Order

The contract is the target, not the starting line. Pages move into
compliance in priority order — highest-traffic, highest-symptom first:

| Phase | Scope | Resolves (from UI evaluation) |
|---|---|---|
| **0. Foundation** | Build `useResource`, `<DataView>`, `<ScoreReport>`; complete tokens; ship lint rules (disabled-warn). | The primitives exist and are usable. |
| **1. Shell + IA** | App-shell, sidebar (loop IA), mobile sheet, route reachability. | Symptom 4 (mobile), 7 (IA), nav orphan routes. |
| **2. Reading surface** | `idea-detail` reading workspace at reading-scale type; `<ScoreReport>` wired. | Symptom 5 (aesthetic), 6 (flat score), reading density. |
| **3. Triage + dashboard** | `dashboard` (one action queue), `ideas-browser`, `gaps-explorer` on `useResource`+`<DataView>`. | Symptoms 1, 2, 8, 9, 10, 12. |
| **4. Direct + monitor** | `pipeline-new` (truthful preview), `run-detail`. | Symptoms 3, 14, 15. |
| **5. Long tail** | Remaining 11 pages → `useResource`; lint → error. | Symptom 1 fully; the ratchet locks. |

Each phase is independently shippable. Phase 0 is pure addition (no
regressions). Phase 5 is where the ratchet goes from *warn* to *error* —
only after every page complies.

---

## 10. What This Contract Does *Not* Specify

Deliberately out of scope, to prevent spec creep:

- **Exact pixel values of spacing/radius.** `globals.css` already has
  `--radius`; spacing follows Tailwind's scale. The contract specifies the
  *type scale* (§3) because that's where the reading-center commitment
  lives. Micro-tuning spacing is implementation, not contract.
- **Animation/transition specifics.** `animate-fade-in` exists and is fine.
  The contract doesn't govern motion unless it undermines a principle.
- **Copy/UX writing.** Governed by `PRODUCT.md` principles and the DA-04
  style guide already in place; not re-specified here.
- **Backend behavior.** This contract is the frontend's mirror of the
  backend's test suite. It assumes the backend's contracts (receipts, truth
  values, RRF) and consumes them; it does not redefine them.

---

## Commitment

This contract exists to make `PRODUCT.md`'s principles *impossible to
violate by accident*. A developer who reaches for `bg-red-100` or a fresh
`useEffect` fetch will not get a code-review note — they will get a build
error and a link to the principle they're circumventing.

That is the difference between a convention and a contract. The frontend
has had conventions. This is its first contract.

When the contract and `PRODUCT.md` disagree, `PRODUCT.md` wins and this
document is amended. When `PRODUCT.md` is silent, the contract's default is
the researcher's reading experience, not the engineer's convenience.
