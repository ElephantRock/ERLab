# Front-End Design Remediation — AIV Batch Sequence

**Project**: Elephant Rock Research Platform
**Lead Programmer**: Craft Agent (Lead)
**Framework**: AIV v5.3
**Source Document**: `frontend_design_audit.md` (17KB, 8 design debt items, 5 voice/tone items)
**Total Estimated Effort**: 16 hours → 6 Batches

---

## Batch Sequence Overview

| Batch | Cycle | Goal | Strategic Bet | Tasks | Est. Tests |
|:------|:------|:-----|:-------------|:------|:-----------|
| **BATCH-DA-01** | STANDARD | Color Token System — replace 77 hardcoded colors with semantic design tokens | If we centralize colors, dark mode works everywhere and future changes are single-point | 3 | +14 |
| **BATCH-DA-02** | STANDARD | Typography & Card Normalization — standardize CardTitle, headings, icon sizes | If we fix the type scale and card title defaults, visual hierarchy becomes consistent across all 20 pages | 2 | +8 |
| **BATCH-DA-03** | STANDARD | Label, Button & Form Consistency — unify 3 label styles into 2 variants; replace 28 raw `<button>` with `<Button>` component | If we eliminate hand-coded buttons and normalize labels, every form on the platform looks and behaves identically | 3 | +12 |
| **BATCH-DA-04** | STANDARD | Error Display & Feedback Standardization — reduce 4 error patterns to 2; normalize 3 toast voices; standardize all 20+ error messages to Active Voice format | If we fix error rendering, users never miss critical feedback | 2 | +8 |
| **BATCH-DA-05** | STANDARD | Placeholder & Microcopy Polish — normalize all 29 placeholders to sentence-case + ASCII dots; fix 5 page title inconsistencies; codify voice rules | If we align microcopy, the platform sounds like one cohesive brand | 2 | +6 |
| **BATCH-DA-06** | STANDARD | Style Guide Codification & Dark Mode Verification — add 3 new CSS tokens (success/warning/info); document style guide as enforceable component spec; verify dark mode renders correctly on all 20 pages | If we codify the guide, all future features look like they belong | 3 | +10 |

**Total**: 6 batches, 15 tasks, ~58 new tests

---

## Batch Dependency Map

```
BATCH-DA-01 (Color Tokens)
    ↓
BATCH-DA-02 (Typography)  ←  independent of DA-01 but must follow to avoid merge conflicts
    ↓
BATCH-DA-03 (Labels/Buttons)  ←  depends on DA-02 (CardTitle default change affects forms)
    ↓
BATCH-DA-04 (Errors/Toasts)  ←  independent
    ↓
BATCH-DA-05 (Microcopy)  ←  independent
    ↓
BATCH-DA-06 (Style Guide + Dark Mode Verification)  ←  depends on ALL prior batches
```

---

## BATCH-DA-01 — Complete Blueprint Specimen

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-DA-01
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Craft Agent (Lead)
Date Issued:              2026-05-12
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Replace all 77 hardcoded Tailwind color classes (bg-blue-500, text-green-800,
etc.) with semantic design tokens (--success, --warning, --info) defined in
globals.css. Establish a ScoreColor utility function that maps score ranges
to semantic tokens. Verify dark mode renders correctly on all affected
components.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add 3 new CSS custom properties to globals.css: --success, --warning, --info
    (both :root and .dark variants)
  - Create a utility module at src/lib/colors.ts that exports:
    - scoreColor(score: number): string — maps 0-1 scores to success/warning/destructive tokens
    - statusColor(status: string): string — maps pipeline status strings to semantic tokens
  - Replace every hardcoded color class in components/ and pages/ with the
    corresponding semantic token class
  - All score-badge, status-pill, and notification components must use tokens
  - Dark mode must render all replaced colors with correct contrast

What the code MUST NOT do:
  - Change the visual appearance in light mode (token values must match current
    hardcoded colors exactly in light theme)
  - Modify any backend code
  - Add new npm dependencies
  - Change component behavior (onClick handlers, state logic, etc.)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  cd frontend && npx tsc --noEmit

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Zero hardcoded Tailwind color classes (bg-blue-*, text-green-*, etc.)
         may remain in any non-test .tsx file under pages/ or components/.
         Exception: colors used in chart SVGs (recharts, d3) are exempt.
  HB-02: The 3 new tokens MUST be defined in both :root and .dark selectors
         in globals.css with contrast-ratio ≥ 4.5:1 against their background.
  HB-03: Light-mode visual regression — screenshots of 3 key pages before and
         after must show pixel-identical color rendering (charts exempt).
  HB-04: No new TypeScript compilation errors (tsc --noEmit must pass clean).

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

New CSS custom properties (added to :root and .dark):

  :root {
    --success: 142 76% 36%;      /* green-600 equivalent */
    --success-foreground: 210 40% 98%;
    --warning: 38 92% 50%;       /* amber-500 equivalent */
    --warning-foreground: 222.2 84% 4.9%;
    --info: 217 91% 60%;         /* blue-500 equivalent */
    --info-foreground: 210 40% 98%;
  }
  .dark {
    --success: 142 60% 45%;
    --success-foreground: 210 40% 98%;
    --warning: 38 80% 55%;
    --warning-foreground: 222.2 84% 4.9%;
    --info: 217 91% 60%;
    --info-foreground: 210 40% 98%;
  }

New utility module src/lib/colors.ts:

  export function scoreColor(score: number): string {
    if (score >= 0.7) return "text-success";       // green
    if (score >= 0.4) return "text-warning";        // amber
    return "text-destructive";                       // red
  }

  export function scoreBg(score: number): string {
    if (score >= 0.7) return "bg-success/10 text-success";
    if (score >= 0.4) return "bg-warning/10 text-warning";
    return "bg-destructive/10 text-destructive";
  }

  export function statusPill(status: string): string {
    const map: Record<string, string> = {
      completed: "bg-success/10 text-success",
      running: "bg-info/10 text-info",
      failed: "bg-destructive/10 text-destructive",
      pending: "bg-muted text-muted-foreground",
      cancelled: "bg-muted text-muted-foreground",
    };
    return map[status] || "bg-muted text-muted-foreground";
  }

Color replacement mapping (applied across all files):

  Hardcoded              → Token
  ─────────────────────────────────────
  text-green-800/600/500 → text-success
  text-green-700/400/300 → text-success (darker/lighter variants)
  bg-green-500/100       → bg-success / bg-success/10
  text-red-800/700/600   → text-destructive
  text-red-500/400       → text-destructive
  bg-red-500/100         → bg-destructive / bg-destructive/10
  text-blue-800/600/500  → text-info
  text-blue-400/300      → text-info
  bg-blue-500/100/900    → bg-info / bg-info/10 / bg-info/20
  text-yellow-800/600    → text-warning
  text-yellow-500/400    → text-warning
  bg-yellow-500/100      → bg-warning / bg-warning/10
  bg-amber-500/100/200   → bg-warning / bg-warning/10 / bg-warning/20
  text-amber-800/600     → text-warning
  text-purple-800/600    → text-info (purple is used for novelty → semantic = info)
  text-purple-500/400    → text-info
  border-yellow-800/500  → border-warning
  border-purple-700      → border-info
  text-orange-800        → text-warning
  bg-orange-500          → bg-warning
  text-gray-800          → text-foreground
  text-gray-500/400/300  → text-muted-foreground
  bg-gray-700/400/200    → bg-muted / bg-muted/50 / bg-muted/30

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AUTH-01: Only globals.css may define color tokens. No inline color values
           in component files.
  AUTH-02: Score-based color decisions MUST go through scoreColor()/scoreBg()
           in src/lib/colors.ts — no inline ternaries for score colors.
  AUTH-03: Status-based color decisions MUST go through statusPill() — no
           inline status-to-color mappings in component files.
  AUTH-04: Chart libraries (recharts) are EXEMPT from HB-01 — they use
           their own color prop systems.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: None — this is the first design-remediation batch.
  Blocks: BATCH-DA-02 through BATCH-DA-06 (token system must exist first).

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [ ] YES  [x] NO — first Design Audit batch, will update
  Last Updated:            2026-05-11 (BATCH-DA-01 not yet in STATE.md)
  Batches since update:    0
  Reconciliation audit:    [x] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  63 frontend tests (frontend/src/__tests__/ + components/__tests__/)
  Expected delta (all Tasks):      +14 new tests
  Expected total at Batch close:   77

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-DA-01/TASK-01 — Add Semantic Color Tokens
  Priority:          Critical
  Description:       Add 3 new CSS custom property pairs (success, warning, info)
                     to globals.css in both :root and .dark selectors. Create
                     src/lib/colors.ts with scoreColor(), scoreBg(), and statusPill()
                     utility functions.
  Files in scope:
    - frontend/src/globals.css
    - frontend/src/lib/colors.ts (NEW)
  Depends on:        None
  Required Tests:
    | Test ID              | Type | Behavior Verified                          | Failure Mode                          | Falsified By                              | Pass Criteria                                    |
    |:---------------------|:-----|:-------------------------------------------|:--------------------------------------|:------------------------------------------|:-------------------------------------------------|
    | TEST-DA-01-01-01     | unit | scoreColor returns correct token for score | Wrong color for boundary scores       | Change 0.7 boundary to 0.8               | scoreColor(0.8) === "text-success", scoreColor(0.5) === "text-warning", scoreColor(0.1) === "text-destructive" |
    | TEST-DA-01-01-02     | unit | scoreBg returns correct bg+text combo      | Missing text color in combo           | Remove text-success from return           | scoreBg(0.9) includes "bg-success/10" and "text-success" |
    | TEST-DA-01-01-03     | unit | statusPill maps all known statuses          | New status returns wrong class        | Add "error" to map                       | statusPill("completed") includes "success", statusPill("unknown") includes "muted" |
    | TEST-DA-01-01-04     | unit | CSS tokens are parseable HSL values        | Malformed CSS variable                | Change "142 76% 36%" to "not-a-color"    | All 6 token values match pattern /^\d+ \d+% \d+$/ |
  Acceptance Criteria:
    AC-01-01: globals.css contains --success, --warning, --info in both :root and .dark
    AC-01-02: src/lib/colors.ts exports scoreColor, scoreBg, statusPill
    AC-01-03: All 4 unit tests pass
  Traceability:
    AC-01-01 → TEST-DA-01-01-04
    AC-01-02 → TEST-DA-01-01-01, TEST-DA-01-01-02, TEST-DA-01-01-03
    AC-01-03 → TEST-DA-01-01-01 through TEST-DA-01-01-04


TASK-02: BATCH-DA-01/TASK-02 — Replace Hardcoded Colors in Components
  Priority:          Critical
  Description:       Replace all hardcoded Tailwind color classes in the 15+
                     component files under frontend/src/components/ with semantic
                     token classes. Use scoreColor()/scoreBg()/statusPill() where
                     appropriate. Exempt chart SVG internals.
  Files in scope:
    - frontend/src/components/ideas/score-badge.tsx
    - frontend/src/components/ideas/evaluation-card.tsx
    - frontend/src/components/ideas/feasibility-report-view.tsx
    - frontend/src/components/ideas/novelty-report-view.tsx
    - frontend/src/components/ideas/idea-card.tsx
    - frontend/src/components/gaps/gap-card.tsx
    - frontend/src/components/notifications/notification-bell.tsx
    - frontend/src/components/search/global-search-dialog.tsx
    - frontend/src/components/knowledge-graph/entity-detail.tsx
    - frontend/src/components/knowledge-graph/world-model-panel.tsx
    - frontend/src/components/pipeline/run-card.tsx
    - frontend/src/components/pipeline/stage-progress.tsx
    - frontend/src/components/pipeline/stage-model-selector.tsx
    - frontend/src/components/memory/memory-card.tsx
    - frontend/src/components/governance/approval-card.tsx
    - frontend/src/components/governance/approval-card.tsx
  Depends on:        TASK-01 (tokens and utility must exist)
  Required Tests:
    | Test ID              | Type | Behavior Verified                          | Failure Mode                          | Falsified By                              | Pass Criteria                                    |
    |:---------------------|:-----|:-------------------------------------------|:--------------------------------------|:------------------------------------------|:-------------------------------------------------|
    | TEST-DA-01-02-01     | unit | score-badge uses scoreColor utility        | Still uses text-green-800             | Revert to hardcoded color                | ScoreBadge component calls scoreColor(score) internally |
    | TEST-DA-01-02-02     | unit | notification-bell uses bg-destructive       | Still uses bg-red-500                 | Change bg-red-500 back                   | Notification badge renders with bg-destructive token class |
    | TEST-DA-01-02-03     | unit | gap-card type badges use semantic tokens    | Still uses bg-amber-100 text-amber-800 | Revert to amber hardcoded                | Type badge uses bg-warning/10 text-warning classes |
    | TEST-DA-01-02-04     | unit | No hardcoded colors remain in components    | Missed a file                         | Add a new bg-blue-500 to any component   | grep for hardcoded colors returns 0 matches (charts exempt) |
  Acceptance Criteria:
    AC-02-01: score-badge.tsx uses scoreColor() from colors.ts
    AC-02-02: notification-bell.tsx uses bg-destructive, not bg-red-500
    AC-02-03: gap-card.tsx type badges use warning token, not amber
    AC-02-04: grep -c 'bg-blue-\|bg-green-\|bg-red-\|bg-yellow-\|bg-amber-\|text-blue-\|text-green-\|text-red-\|text-yellow-\|text-amber-\|text-purple-\|text-orange-' returns 0 across all component .tsx files
  Traceability:
    AC-02-01 → TEST-DA-01-02-01
    AC-02-02 → TEST-DA-01-02-02
    AC-02-03 → TEST-DA-01-02-03
    AC-02-04 → TEST-DA-01-02-04


TASK-03: BATCH-DA-01/TASK-03 — Replace Hardcoded Colors in Pages + Dark Mode Verification
  Priority:          High
  Description:       Replace all hardcoded Tailwind color classes in the 20 page
                     files under frontend/src/pages/ with semantic tokens. Then
                     verify dark mode rendering: create a manual verification test
                     that checks each affected page renders without invisible text
                     (contrast ≥ 4.5:1 for all text elements).
  Files in scope:
    - frontend/src/pages/idea-detail.tsx
    - frontend/src/pages/run-detail.tsx
    - frontend/src/pages/dashboard.tsx
    - frontend/src/pages/ideas-browser.tsx
    - frontend/src/pages/gaps-explorer.tsx
    - frontend/src/pages/gap-detail.tsx
    - frontend/src/pages/knowledge-search.tsx
    - frontend/src/pages/knowledge-graph.tsx
    - frontend/src/pages/literature.tsx
    - frontend/src/pages/sessions.tsx
    - frontend/src/pages/costs.tsx
    - frontend/src/pages/governance.tsx
    - frontend/src/pages/traces.tsx
    - frontend/src/pages/autonomous.tsx
    - frontend/src/pages/login.tsx
    - frontend/src/pages/settings.tsx
    - frontend/src/pages/memory.tsx
    - frontend/src/pages/plugins.tsx
    - frontend/src/pages/pipeline-new.tsx
    - frontend/src/pages/run-detail.tsx
  Depends on:        TASK-01 (tokens must exist), TASK-02 (component imports may change)
  Required Tests:
    | Test ID              | Type | Behavior Verified                          | Failure Mode                          | Falsified By                              | Pass Criteria                                    |
    |:---------------------|:-----|:-------------------------------------------|:--------------------------------------|:------------------------------------------|:-------------------------------------------------|
    | TEST-DA-01-03-01     | unit | No hardcoded colors in page files          | Missed text-blue-600 in idea-detail   | Add text-blue-600 to any page            | grep returns 0 matches across pages/            |
    | TEST-DA-01-03-02     | unit | idea-detail uses text-info for links       | Still uses text-blue-600              | Revert change                            | Link-styled elements use text-info or text-primary |
    | TEST-DA-01-03-03     | unit | run-detail status uses statusPill()        | Still uses bg-blue-100 text-blue-800  | Revert to hardcoded                      | Status badge uses statusPill() output            |
    | TEST-DA-01-03-04     | e2e  | Dark mode globals.css has all 3 tokens     | Missing --success in .dark            | Delete --success from .dark              | computedStyle for --success in dark mode matches expected HSL |
    | TEST-DA-01-03-05     | e2e  | Dark mode text contrast check             | text-success invisible on dark bg     | Change --success to same luminance as bg | All token text colors have contrast ≥ 4.5:1 against --background in dark mode |
    | TEST-DA-01-03-06     | e2e  | Light mode visual unchanged               | Token values differ from originals    | Change --success hue by 30 degrees       | 3 key page screenshots pixel-match within 1% tolerance |
  Acceptance Criteria:
    AC-03-01: grep returns 0 hardcoded color matches across pages/ .tsx files
    AC-03-02: idea-detail.tsx uses text-info/text-primary for links
    AC-03-03: run-detail.tsx uses statusPill() for run status rendering
    AC-03-04: .dark selector in globals.css contains --success, --warning, --info
    AC-03-05: All 6 new tests pass
  Traceability:
    AC-03-01 → TEST-DA-01-03-01
    AC-03-02 → TEST-DA-01-03-02
    AC-03-03 → TEST-DA-01-03-03
    AC-03-04 → TEST-DA-01-03-04
    AC-03-05 → TEST-DA-01-03-05, TEST-DA-01-03-06

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Zero hardcoded Tailwind color classes remain in any .tsx file under
          pages/ or components/ (charts exempt). Verified by:
            grep -rn 'bg-blue-\|bg-green-\|bg-red-\|bg-yellow-\|bg-amber-\|bg-orange-\|bg-gray-\|text-blue-\|text-green-\|text-red-\|text-yellow-\|text-amber-\|text-purple-\|text-orange-\|text-gray-\|border-blue-\|border-green-\|border-red-\|border-yellow-\|border-purple-\|border-gray-' frontend/src/pages/ frontend/src/components/
          Returns 0 lines (excluding chart internals and test files).
  BAC-02: TypeScript compilation passes with zero new errors:
            cd frontend && npx tsc --noEmit
  BAC-03: CHANGELOG.md updated with BATCH-DA-01 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-DA-01/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       [Pending — awaiting Phase I-B]
Review Cycle:             [1 or 2]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:
  FLAG-02 → Action taken:

If REJECT — reason and next action:

Blueprint Version after response: [1.0 or 1.1 if revised]
Lead Sign:                [Craft Agent — 2026-05-12]

═══════════════════════════════════════════════════════════
```

---

## BATCH-DA-02 through BATCH-DA-06 — Roadmap Summary

### BATCH-DA-02: Typography & Card Normalization
**Cycle**: STANDARD | **Tasks**: 2 | **Est.**: +8 tests | **~3 hours**

**Strategic Bet**: If we change `CardTitle` default from `text-2xl` to `text-lg` and standardize page headings to a 3-level hierarchy, every page feels structurally consistent.

**TASK-01**: Change `CardTitle` in `ui/card.tsx` from `text-2xl font-semibold` to `text-lg font-semibold`. Update the 5 remaining pages that use `text-2xl` for page-level headings to use explicit `<h1 className="text-2xl font-semibold">` instead of `<CardTitle>`. Normalize icon sizes: `h-3` for inline, `h-4` for default, `h-5` for card headers.

**TASK-02**: Establish heading hierarchy in `globals.css` or a shared `typography.ts` constants file:
- Page title: `text-2xl font-semibold`
- Section title: `text-lg font-semibold` (CardTitle default)
- Subsection: `text-base font-medium`
- Body: `text-sm`
- Caption: `text-xs text-muted-foreground`

---

### BATCH-DA-03: Label, Button & Form Consistency
**Cycle**: STANDARD | **Tasks**: 3 | **Est.**: +12 tests | **~3 hours**

**Strategic Bet**: If we create two label variants (Primary and Secondary) and replace all 28 raw `<button>` elements with the `<Button>` component, forms and CTAs become visually and behaviorally consistent.

**TASK-01**: Add `Label` component to `ui/` with two variants: `variant="primary"` (`text-sm font-medium`) and `variant="secondary"` (`text-xs text-muted-foreground uppercase tracking-wider`). Replace all 19 `<label>` instances.

**TASK-02**: Replace 28 raw `<button>` elements with `<Button variant="link">` or `<Button variant="ghost">`. Remove inline style hacks (`bg-transparent border-none p-0`).

**TASK-03**: Standardize toggle/checkbox labels in `run-config-form.tsx` — wrap in `<Label>` with consistent spacing.

---

### BATCH-DA-04: Error Display & Feedback Standardization
**Cycle**: STANDARD | **Tasks**: 2 | **Est.**: +8 tests | **~2 hours**

**Strategic Bet**: If we reduce error display to exactly 2 patterns (toast for actions, Alert for page-level), users always know where to look for feedback.

**TASK-01**: Create `components/ui/error-alert.tsx` wrapper that ensures all page-level errors use `<Alert variant="destructive">` with consistent styling. Replace 8 bare `<p>` / `<span>` error elements.

**TASK-02**: Normalize all 20+ toast messages to bare passive voice ("Feedback submitted", not "Feedback submitted successfully"). Remove `err.message` passthrough — wrap in "Something went wrong. Please try again." for user-facing display.

---

### BATCH-DA-05: Placeholder & Microcopy Polish
**Cycle**: STANDARD | **Tasks**: 2 | **Est.**: +6 tests | **~2 hours**

**Strategic Bet**: If we normalize all 29 placeholders and 5 page titles to a consistent style guide, the platform sounds like one professional product.

**TASK-01**: Fix all placeholders: sentence case, trailing `...` (ASCII, never `…`), no "e.g." prefix. Normalize 5 page titles (Pipeline → Pipelines, Research Ideas → Ideas, etc.).

**TASK-02**: Audit all button labels — ensure verb-first convention ("Start Pipeline" not "New Pipeline"). Fix "View all" → "View all ideas" / "View all runs" etc.

---

### BATCH-DA-06: Style Guide Codification & Dark Mode Verification
**Cycle**: STANDARD | **Tasks**: 3 | **Est.**: +10 tests | **~2 hours**

**Strategic Bet**: If we write the style guide as a TypeScript constants file and verify dark mode on every page, future developers can't accidentally break the design system.

**TASK-01**: Create `frontend/src/lib/style-guide.ts` — exported constants for typography scale, spacing, icon sizes, radius, shadow levels. Import in component files instead of hardcoded values.

**TASK-02**: Create `frontend/src/styles/design-tokens.css` — extract all design tokens from globals.css into a dedicated file with comments documenting each token's purpose and usage rules.

**TASK-03**: Write dark mode verification test suite — programmatically check that all 20 pages render without zero-contrast text in dark mode. Run as part of CI.

---

## STATE.md Update Plan

After BATCH-DA-01 close, update `docs/aiv/STATE.md`:

```
## Design Remediation Phase

| Batch | Status | Summary |
|:------|:-------|:--------|
| BATCH-DA-01 | CLOSED | Color token system — 77 hardcoded colors → semantic tokens |
| BATCH-DA-02 | PENDING | Typography & card normalization |
| BATCH-DA-03 | PENDING | Label, button & form consistency |
| BATCH-DA-04 | PENDING | Error display standardization |
| BATCH-DA-05 | PENDING | Placeholder & microcopy polish |
| BATCH-DA-06 | PENDING | Style guide codification |
```

---

## Known Gotchas

1. **Chart libraries are exempt** — recharts, d3 SVG internals use their own color systems. Don't try to token-ize those.
2. **`text-primary` vs `text-info`**: Both are blue. `text-primary` is for CTAs and links; `text-info` is for informational status. Don't conflate.
3. **Score boundaries**: The 0.7/0.4 thresholds in `scoreColor()` must match the existing hardcoded thresholds in `score-badge.tsx` or visual regression occurs.
4. **Dark mode contrast**: Some hardcoded dark variants (e.g., `text-green-800` in dark mode) were already invisible. The fix will actually improve dark mode, not just maintain it.
5. **`border-input` is already a token** — don't replace it with a custom border color.

## Adaptation Log

| Date | Adaptation | Reason |
|:-----|:-----------|:-------|
| 2026-05-12 | Initial roadmap created | Design audit identified 77 hardcoded colors, 28 raw buttons, 4 error patterns |
