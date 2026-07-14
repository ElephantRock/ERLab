# Route Reachability Fix Plan

> **Purpose:** separate the route-reachability fixes that are *invariant*
> (must happen regardless of validation) from those that are *gated* (depend
> on the IA answers from PRODUCT validation). Validation-independent fixes
> can proceed; gated fixes wait for Phase 1.
>
> **Source:** `route_inventory.md` (the 20-route audit) + PRODUCT.md
> anti-patterns *The Orphan Route* and *The Unreachable Mobile Route*.

## The principle

```text
Invariant: every route must be reachable somewhere (desktop + mobile).
Gated:     the exact IA group and hierarchy for each route.
```

A real page with no navigation path to it is a correctness gap, not a
design judgment. Where it lives in the nav *is* a design judgment — and
that's what Phase 1 decides, informed by validation.

## Invariant fixes (validation-independent — can proceed now)

These are correctness gaps. They must close regardless of Q1/Q5/Q6 outcomes.

### INV-1: `/knowledge` (Knowledge Search) is a true orphan
- **Current:** no nav entry at all — desktop or mobile. Reachable only by URL or global search.
- **Fix:** assign it a desktop nav home now. The *group* (READ vs RESEARCH) can be revisited in Phase 1, but it must be reachable today.
- **Lowest-regret placement:** under **Research** (alongside Literature and Knowledge Graph — it's a knowledge surface). This matches the existing grouping of the other two knowledge surfaces and is unlikely to be overturned by validation.
- **Mobile:** add to the mobile sheet when it ships (Phase 1). Until then, it inherits desktop reachability.

### INV-2: 13 mobile-unreachable routes
- **Current:** `MOBILE_ITEMS` (`sidebar.tsx:79`) filters to `mobile: true` — set on only 4 routes (Home, New Run, Results, Settings). The other 13 are URL-only on mobile.
- **The 13:** governance, gaps, literature, knowledge-graph, ops, costs, traces, memory, autonomous, plugins, sessions, knowledge, (and any new route).
- **Fix:** the mobile bottom nav should expose a **"More" sheet** listing every route, with the bottom-nav shortcut keeping only the 3–4 highest-traffic (DIRECT, TRIAGE, READ-continue, GOVERN). This is specified in `INTERFACE_CONTRACT.md §5` and is validation-independent in *shape* (every route reachable) even if the shortcut selection is gated.
- **Phase 1 implements the sheet.** Until then, no partial fix — a half-fixed mobile nav is worse than the current honest "4 shortcuts" because it implies completeness.

### INV-3: `/runs/:id` has no upstream landing page
- **Current:** no `/runs` list route. Runs surface only via dashboard "recent runs" and `/sessions`.
- **Diagnosis:** may be intentional (runs scoped to sessions). But "show me all my runs" has no canonical destination.
- **Fix:** defer to Phase 1 IA decision — either add `/runs` or make the sessions page the canonical runs landing. Not a correctness gap (runs *are* reachable), just an IA smell. **Not invariant.**

## Gated fixes (depend on validation — wait for Phase 1)

These depend on Q1 (primary user), Q5 (governance frequency), Q6 (compare).

### GATED-1: Governance placement (Q5)
- **If Q5 = daily/gate:** `/governance` stays a primary nav group (GOVERN).
- **If Q5 = rare audit:** `/governance` drops to SECONDARY. The Core Loop's step 7 is no longer daily.
- **If Q5 = collaborative:** approval UI complexity grows; governance may warrant its own top-level destination.
- **Decision owner:** Q5 validation → `decision_rules.md` Q5.

### GATED-2: Autonomous + Sessions placement (Q1, Q4)
- **Current:** both buried under collapsed "Advanced."
- **Issue:** Autonomous is a top-level CLI command and a primary workflow; Sessions is cross-artifact refinement history. Both are primary surfaces disguised as "advanced."
- **If Q1 = individual researcher:** Autonomous may stay secondary (a researcher triggers runs directly, not via autonomous cycles); Sessions stays secondary.
- **If Q4 = many-fast preferred:** Autonomous becomes more prominent (tight iteration loops).
- **Decision owner:** Q1 + Q4 validation.

### GATED-3: Knowledge surfaces grouping (Q1)
- `/knowledge` (Search), `/literature`, `/knowledge-graph` are three knowledge surfaces. Today: Literature + KG in Research; Search orphaned.
- **If Q1 = researcher:** all three group under READ-adjacent or RESEARCH.
- **If Q1 = manager:** knowledge surfaces may be less central; grouping matters less.
- **Lowest-regret:** group all three under one heading (Research or Knowledge). The INV-1 fix does this provisionally.

### GATED-4: Compare surface entry (Q6)
- **If Q6 = side-by-side:** a new COMPARE entry enters the nav between TRIAGE and READ.
- **If Q6 = serial:** no new entry.
- **Decision owner:** Q6 validation — the highest-impact IA question.

### GATED-5: Secondary surfaces tone
- Costs, Traces, Memory, Ops, Plugins are SECONDARY (functional, not tonal). They live below a separator. This is validation-independent in *principle* but the *separator placement* depends on how many primary surfaces the gated decisions add.

## Fix ordering

```text
Now (validation-independent):
  INV-1: assign /knowledge a desktop nav home (Research group, lowest-regret).

Phase 1 (after validation):
  INV-2: mobile "More" sheet (every route reachable).
  GATED-1..5: apply decision_rules.md outcomes to the IA.

Phase 5+:
  Mechanical CI check: a test asserting "every non-detail route has a nav
  entry" — prevents the orphan class from regenerating.
```

## The orphan-prevention CI check (Phase 5)

The fix plan is only durable if orphans can't regenerate. A small test:

```ts
// Asserts: every <Route path="..."> (excluding :id detail routes and /login)
// appears in the flattened nav items list.
```

This catches the exact regression that produced the `/knowledge` orphan —
someone adds a route, forgets the nav entry, ships. The test makes that a
build failure. It's validation-independent and should ship in Phase 1
alongside the mobile sheet (both are "completeness" guards).

## What NOT to do yet

- **Do not reorganize the existing nav groups.** The Studio/Research/System/Advanced split mirrors backend feature buckets (PRODUCT.md anti-pattern *The Mirror*), but fixing it is Phase 1 — gated on validation.
- **Do not build the mobile sheet yet.** It's Phase 1 scope; a half-built sheet is worse than the current honest 4-shortcut nav.
- **Do not add `/runs`.** Defer to Phase 1 IA decision.
- **Do not add a compare entry.** Gated on Q6.

The only fix that proceeds now is INV-1: give `/knowledge` a desktop nav home. Everything else waits for Phase 1, when the IA is reorganized against validated product direction.
