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
Replace all 113 hardcoded Tailwind color classes across 36 source files with
semantic design tokens. Add success/warning/info CSS custom properties to
globals.css and wire them through tailwind.config.js. Update score-utils.ts
to emit token classes instead of hardcoded colors. Verify dark mode renders
correctly.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add 3 new CSS custom property PAIRS to globals.css: --success/--success-foreground,
    --warning/--warning-foreground, --info/--info-foreground (in both :root and .dark)
  - Extend tailwind.config.js theme.colors with: success, warning, info
    (each with DEFAULT and foreground subkeys using hsl(var(--token)))
  - Refactor src/lib/score-utils.ts: getScoreColor() and getScoreBg() must return
    semantic token classes (text-success, bg-success/10, etc.) instead of hardcoded
  - Replace all 113 hardcoded color classes in 36 non-test .tsx files with token equivalents
  - Update existing tests in score-utils.test.ts to expect new token class names
  - Verify dark mode contrast for new tokens

What the code MUST NOT do:
  - Change visual appearance in light mode (token HSL values must match current colors)
  - Modify any backend code
  - Add new npm dependencies
  - Change component behavior (onClick, state, routing)
  - Modify chart rendering internals (recharts color props are exempt)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  cd frontend && npx tsc --noEmit

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Zero hardcoded Tailwind color classes remain in any non-test .tsx file
         under pages/ or components/. Verified by grep pattern:
         grep -rn 'bg-blue-\|bg-green-\|bg-red-\|bg-yellow-\|bg-amber-\|bg-orange-\|text-blue-\|text-green-\|text-red-\|text-yellow-\|text-amber-\|text-purple-\|text-orange-\|border-blue-\|border-green-\|border-red-\|border-yellow-\|border-purple-' frontend/src/pages/ frontend/src/components/
         MUST return 0 lines. Charts (recharts) are exempt.
  HB-02: The 3 new token PAIRS MUST appear in both :root and .dark selectors.
         Dark mode values MUST have contrast ratio >= 4.5:1 against --background.
  HB-03: TypeScript compilation passes: cd frontend && npx tsc --noEmit → exit 0
  HB-04: Existing passing test count MUST NOT decrease. Baseline: 361 passing.
         The score-utils tests will be UPDATED (not broken) to match new return values.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

NEW CSS TOKENS (globals.css):

  :root {
    --success: 142 76% 36%;
    --success-foreground: 210 40% 98%;
    --warning: 38 92% 50%;
    --warning-foreground: 222.2 84% 4.9%;
    --info: 217 91% 60%;
    --info-foreground: 210 40% 98%;
  }
  .dark {
    --success: 142 60% 45%;
    --success-foreground: 210 40% 98%;
    --warning: 38 80% 55%;
    --warning-foreground: 222.2 84% 4.9%;
    --info: 217 91% 65%;
    --info-foreground: 210 40% 98%;
  }

TAILWIND CONFIG EXTENSION (tailwind.config.js):

  theme: {
    extend: {
      colors: {
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(var(--info-foreground))",
        },
      },
    },
  },

SCORE-UTILS.TS NEW RETURN VALUES:

  getScoreColor(0.1, "novelty") → "text-destructive"   (was "text-red-500")
  getScoreColor(0.4, "novelty") → "text-warning"        (was "text-amber-500")
  getScoreColor(0.7, "novelty") → "text-success"        (was "text-emerald-500")
  getScoreColor(0.9, "novelty") → "text-success"        (was "text-green-600")

  getScoreBg(0.1, "novelty") → "bg-destructive/10 text-destructive"  (was "bg-red-100 text-red-800")
  getScoreBg(0.4, "novelty") → "bg-warning/10 text-warning"          (was "bg-amber-100 text-amber-800")
  getScoreBg(0.9, "novelty") → "bg-success/10 text-success"          (was "bg-green-100 text-green-800")

COLOR REPLACEMENT MAPPING (all 36 files):

  Hardcoded                    → Token
  ──────────────────────────────────────────────
  text-green-800/700/600/500   → text-success
  text-green-400/300           → text-success/70
  text-green-200               → text-success/50
  bg-green-100                 → bg-success/10
  bg-green-500                 → bg-success
  bg-green-900/950             → bg-success/20
  bg-green-50                  → bg-success/5
  border-green-*               → border-success

  text-red-800/700/600/500/400 → text-destructive
  bg-red-100                   → bg-destructive/10
  bg-red-500                   → bg-destructive
  bg-red-50                    → bg-destructive/5
  bg-red-950                   → bg-destructive/20
  border-red-*                 → border-destructive

  text-blue-800/700/600/500    → text-info
  text-blue-400/300/200        → text-info/70
  text-blue-200                → text-info/50
  bg-blue-100                  → bg-info/10
  bg-blue-500                  → bg-info
  bg-blue-900/950              → bg-info/20
  bg-blue-50                   → bg-info/5
  border-blue-*                → border-info

  text-amber-800/600/500/400   → text-warning
  text-amber-200               → text-warning/50
  bg-amber-100                 → bg-warning/10
  bg-amber-500                 → bg-warning
  bg-amber-900                 → bg-warning/20
  bg-amber-50                  → bg-warning/5
  bg-amber-200                 → bg-warning/15

  text-yellow-800/700/600      → text-warning
  text-yellow-500/400          → text-warning
  text-yellow-200              → text-warning/50
  bg-yellow-100                → bg-warning/10
  bg-yellow-500                → bg-warning
  bg-yellow-900                → bg-warning/20
  bg-yellow-50                 → bg-warning/5
  border-yellow-*              → border-warning

  text-purple-800/700/600/500  → text-info
  text-purple-400/300/200      → text-info/70
  bg-purple-*                  → bg-info/10 (light) / bg-info (500)
  border-purple-*              → border-info

  text-orange-800/700/600      → text-warning
  bg-orange-100                → bg-warning/10
  bg-orange-500                → bg-warning

  text-gray-500/400/300        → text-muted-foreground
  bg-gray-700                  → bg-muted
  bg-gray-400/200              → bg-muted/50

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AUTH-01: Only globals.css may define color tokens. No inline color values
           in component files.
  AUTH-02: Score-based colors MUST go through getScoreColor()/getScoreBg()
           in score-utils.ts. No inline score-to-color ternaries.
  AUTH-03: Status-based colors use getScoreBg() or inline token classes only.
  AUTH-04: Chart internals (recharts <Cell>, <Bar>, <Line> color props) are
           EXEMPT — they use hex/rgb directly.
  AUTH-05: When both a hardcoded bg-X AND text-X appear in the same element
           (e.g., "bg-green-100 text-green-800"), they map to
           "bg-success/10 text-success" (preserve the opacity pattern).

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: None (first design-audit batch)
  Blocks: BATCH-DA-02 through BATCH-DA-06

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [ ] YES  [x] NO — first Design Audit batch
  Last Updated:            N/A (will create entry)
  Batches since update:    0
  Reconciliation audit:    [x] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  361 passing frontend tests (28 pre-existing failures)
  Expected delta (all Tasks):      +8 new tests
  Expected total at Batch close:   369

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-DA-01/TASK-01 — Foundation: CSS Tokens + Tailwind Config + Score Utils
  Priority:          Critical
  Description:       Add 3 new CSS token pairs to globals.css. Extend tailwind.config.js
                     with success/warning/info color mappings. Refactor score-utils.ts
                     to return semantic token classes. Update score-utils.test.ts to
                     match new return values.
  Files in scope:
    - frontend/src/globals.css (MODIFY — add 12 new CSS variable lines)
    - frontend/tailwind.config.js (MODIFY — add colors to theme.extend)
    - frontend/src/lib/score-utils.ts (MODIFY — change getScoreColor/getScoreBg return values)
    - frontend/src/lib/__tests__/score-utils.test.ts (MODIFY — update expected values)
  Depends on:        None
  Required Tests:
    | Test ID              | Type | Behavior Verified                    | Failure Mode                    | Falsified By                          | Pass Criteria                                        |
    |:---------------------|:-----|:-------------------------------------|:--------------------------------|:--------------------------------------|:-----------------------------------------------------|
    | TEST-DA-01-01-01     | unit | getScoreColor returns token classes  | Returns hardcoded "text-red-500" | Revert to "text-red-500"              | getScoreColor(0.9,"novelty")==="text-success"        |
    | TEST-DA-01-01-02     | unit | getScoreBg returns token bg+text     | Returns "bg-red-100 text-red-800"| Revert to "bg-green-100 text-green-800"| getScoreBg(0.1,"novelty").includes("destructive")   |
    | TEST-DA-01-01-03     | unit | getScoreColor feasibility normalized | Scale not divided by 10         | Remove /10 normalization              | getScoreColor(9,"feasibility")==="text-success"      |
    | TEST-DA-01-01-04     | unit | globals.css has all 6 tokens in :root| Missing --warning-foreground    | Delete a token line                  | 6 new --success/--warning/--info + foreground vars   |
    | TEST-DA-01-01-05     | unit | globals.css has all 6 tokens in .dark| Dark mode missing --info        | Delete dark --info                    | .dark block has matching 6 vars                       |
    | TEST-DA-01-01-06     | unit | tailwind config has 3 color entries  | Missing warning.color mapping   | Remove warning from config            | config.theme.extend.colors has success/warning/info   |
  Acceptance Criteria:
    AC-01-01: globals.css has --success, --success-foreground, --warning, --warning-foreground,
              --info, --info-foreground in both :root and .dark
    AC-01-02: tailwind.config.js theme.extend.colors includes success, warning, info
    AC-01-03: getScoreColor() and getScoreBg() return token classes (no hardcoded color strings)
    AC-01-04: All 6 unit tests pass
    AC-01-05: score-utils.test.ts updated and passes with new return values
  Traceability:
    AC-01-01 → TEST-DA-01-01-04, TEST-DA-01-01-05
    AC-01-02 → TEST-DA-01-01-06
    AC-01-03 → TEST-DA-01-01-01, TEST-DA-01-01-02, TEST-DA-01-01-03
    AC-01-04 → TEST-DA-01-01-01 through TEST-DA-01-01-06
    AC-01-05 → TEST-DA-01-01-01, TEST-DA-01-01-02


TASK-02: BATCH-DA-01/TASK-02 — Replace Hardcoded Colors in Components
  Priority:          Critical
  Description:       Replace all hardcoded color classes in the 24 component files
                     with semantic token equivalents per the mapping table. Ensure
                     score-badge.tsx already uses getScoreBg() from score-utils.ts
                     (no additional change needed). Run tsc --noEmit to verify.
  Files in scope:
    - frontend/src/components/ideas/evaluation-card.tsx
    - frontend/src/components/ideas/feasibility-report-view.tsx
    - frontend/src/components/ideas/feedback-form.tsx
    - frontend/src/components/ideas/idea-card.tsx
    - frontend/src/components/ideas/novelty-report-view.tsx
    - frontend/src/components/gaps/gap-card.tsx
    - frontend/src/components/gaps/gap-feedback-form.tsx
    - frontend/src/components/notifications/notification-bell.tsx
    - frontend/src/components/search/global-search-dialog.tsx
    - frontend/src/components/knowledge-graph/entity-detail.tsx
    - frontend/src/components/knowledge/upload-zone.tsx
    - frontend/src/components/pipeline/run-card.tsx
    - frontend/src/components/pipeline/run-stats.tsx
    - frontend/src/components/pipeline/stage-model-selector.tsx
    - frontend/src/components/pipeline/stage-progress.tsx
    - frontend/src/components/memory/memory-card.tsx
    - frontend/src/components/literature/paper-card.tsx
    - frontend/src/components/onboarding/onboarding-overlay.tsx
    - frontend/src/components/costs/budget-bar.tsx
    - frontend/src/components/autonomous/cycle-progress.tsx
    - frontend/src/components/autonomous/consciousness-state.tsx
    - frontend/src/components/auth/role-badge.tsx
    - frontend/src/components/idea/share-dialog.tsx
    - frontend/src/components/pipeline/stage-model-selector.tsx
  Depends on:        TASK-01 (tokens and tailwind config must exist)
  Required Tests:
    | Test ID              | Type | Behavior Verified                       | Failure Mode                    | Falsified By                        | Pass Criteria                                    |
    |:---------------------|:-----|:----------------------------------------|:--------------------------------|:------------------------------------|:-------------------------------------------------|
    | TEST-DA-01-02-01     | unit | No hardcoded colors in components/      | Missed text-green-800 in a file | Add bg-blue-500 to any component    | grep pattern returns 0 matches in components/    |
    | TEST-DA-01-02-02     | unit | TypeScript compiles cleanly             | Token class not recognized      | Misspell a token class              | tsc --noEmit exits 0                              |
  Acceptance Criteria:
    AC-02-01: grep returns 0 hardcoded color matches across components/ non-test .tsx
    AC-02-02: npx tsc --noEmit passes with zero errors
  Traceability:
    AC-02-01 → TEST-DA-01-02-01
    AC-02-02 → TEST-DA-01-02-02


TASK-03: BATCH-DA-01/TASK-03 — Replace Hardcoded Colors in Pages + Verification
  Priority:          High
  Description:       Replace all hardcoded color classes in the 12 page files.
                     Run full test suite. Verify no regressions. Verify dark mode
                     tokens exist and have valid HSL format.
  Files in scope:
    - frontend/src/pages/run-detail.tsx
    - frontend/src/pages/idea-detail.tsx
    - frontend/src/pages/dashboard.tsx
    - frontend/src/pages/pipeline-new.tsx
    - frontend/src/pages/gap-detail.tsx
    - frontend/src/pages/sessions.tsx
    - frontend/src/pages/settings.tsx
    - frontend/src/pages/knowledge-search.tsx
    - frontend/src/pages/login.tsx
    - frontend/src/pages/memory.tsx
    - frontend/src/pages/governance.tsx
    - frontend/src/pages/traces.tsx
    - frontend/src/pages/plugins.tsx
    - frontend/src/pages/costs.tsx
  Depends on:        TASK-01, TASK-02
  Required Tests:
    | Test ID              | Type | Behavior Verified                       | Failure Mode                    | Falsified By                        | Pass Criteria                                    |
    |:---------------------|:-----|:----------------------------------------|:--------------------------------|:------------------------------------|:-------------------------------------------------|
    | TEST-DA-01-03-01     | unit | No hardcoded colors in pages/           | text-blue-600 in idea-detail    | Add text-green-500 to any page      | grep pattern returns 0 matches in pages/         |
    | TEST-DA-01-03-02     | unit | idea-detail links use text-info         | Still has text-blue-600         | Revert to hardcoded                 | No "text-blue" in idea-detail.tsx                |
    | TEST-DA-01-03-03     | unit | run-detail status uses token classes    | Still has bg-blue-100           | Revert to hardcoded                 | No "bg-blue" in run-detail.tsx                   |
    | TEST-DA-01-03-04     | unit | All dark tokens have valid HSL          | --success has invalid value     | Change value to "invalid"           | All dark token values match /^\d+[\s.]\d+%\s\d+%/|
    | TEST-DA-01-03-05     | unit | Test count not decreased                | Broken tests from token changes | Delete a test file                  | passing >= 361 (baseline) + 8 (new) = 369 min    |
    | TEST-DA-01-03-06     | e2e  | tsc clean compile                       | Type errors from new classes    | Introduce a typo                    | tsc --noEmit exits 0                              |
  Acceptance Criteria:
    AC-03-01: grep returns 0 hardcoded color matches across pages/ non-test .tsx
    AC-03-02: idea-detail.tsx uses text-info/text-primary for links
    AC-03-03: run-detail.tsx uses token classes for status display
    AC-03-04: All dark mode tokens have valid HSL values
    AC-03-05: Full test suite runs: >= 369 tests pass
    AC-03-06: TypeScript compilation clean
  Traceability:
    AC-03-01 → TEST-DA-01-03-01
    AC-03-02 → TEST-DA-01-03-02
    AC-03-03 → TEST-DA-01-03-03
    AC-03-04 → TEST-DA-01-03-04
    AC-03-05 → TEST-DA-01-03-05
    AC-03-06 → TEST-DA-01-03-06

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: grep -rn 'bg-blue-\|bg-green-\|bg-red-\|bg-yellow-\|bg-amber-\|bg-orange-\|text-blue-\|text-green-\|text-red-\|text-yellow-\|text-amber-\|text-purple-\|text-orange-\|border-blue-\|border-green-\|border-red-\|border-yellow-\|border-purple-' frontend/src/pages/ frontend/src/components/
          returns 0 lines in non-test .tsx files.
  BAC-02: cd frontend && npx tsc --noEmit exits 0.
  BAC-03: CHANGELOG.md updated with BATCH-DA-01 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-DA-01/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       [Pending Phase I-B]
Review Cycle:             [Pending]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

Blueprint Version after response: [1.0]
Lead Sign:                [Craft Agent — 2026-05-12]

═══════════════════════════════════════════════════════════
