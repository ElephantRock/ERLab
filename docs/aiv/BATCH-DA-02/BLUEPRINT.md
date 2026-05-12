BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-DA-02
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
Change CardTitle default from text-2xl to text-lg. Remove redundant text-lg
overrides from 25 CardTitle instances. Replace transition-all with specific
transition properties. Establish heading hierarchy constants.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Change CardTitle default class from "text-2xl font-semibold leading-none tracking-tight"
    to "text-lg font-semibold leading-none tracking-tight"
  - Remove redundant "text-lg" overrides from CardTitle instances that now match the default
  - Replace all 11 "transition-all" with specific transition-* (transition-colors,
    transition-shadow, transition-transform, transition-opacity)
  - Create frontend/src/lib/typography.ts with heading constants for documentation

What the code MUST NOT do:
  - Change any visual appearance (the override removal must be pixel-identical)
  - Modify page-level <h1> elements (they use text-2xl font-bold, which is correct)
  - Add new npm dependencies
  - Change component behavior or routing

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  cd frontend && npx tsc --noEmit

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Zero CardTitle instances with redundant "text-lg" override that matches
         the new default. (CardTitle instances that add OTHER classes like
         "text-lg flex items-center gap-2" are NOT redundant — they combine
         the default size with extra layout classes.)
  HB-02: Zero "transition-all" in non-test .tsx files.
  HB-03: TypeScript compilation passes (0 new errors).
  HB-04: Test count must not decrease from baseline (361).

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-DA-02/TASK-01 — CardTitle Default Change + Override Cleanup
  Priority:          High
  Description:       Change CardTitle default to text-lg. Remove redundant text-lg
                     overrides from ~18 CardTitle instances that only specify "text-lg".
                     Keep overrides that combine text-lg with other classes (flex, gap, etc).
                     Create typography.ts constants file.
  Files in scope:
    - frontend/src/components/ui/card.tsx (MODIFY — change default class)
    - frontend/src/lib/typography.ts (NEW — heading constants)
    - frontend/src/components/idea/comment-thread.tsx
    - frontend/src/components/idea/share-dialog.tsx
    - frontend/src/components/ideas/feedback-form.tsx
    - frontend/src/components/pipeline/autonomous-form.tsx
    - frontend/src/components/pipeline/run-config-form.tsx
    - frontend/src/pages/autonomous.tsx
    - frontend/src/pages/idea-detail.tsx
    - frontend/src/pages/pipeline-new.tsx
    - frontend/src/pages/plugins.tsx
    - frontend/src/pages/sessions.tsx
    - frontend/src/pages/settings.tsx
  Depends on:        None
  Required Tests:
    | Test ID              | Type | Behavior Verified                      | Failure Mode                  | Falsified By                        | Pass Criteria                                  |
    |:---------------------|:-----|:---------------------------------------|:------------------------------|:------------------------------------|:-----------------------------------------------|
    | TEST-DA-02-01-01     | unit | CardTitle default is text-lg           | Default still text-2xl        | Revert to text-2xl                  | card.tsx CardTitle class includes "text-lg font-semibold" |
    | TEST-DA-02-01-02     | unit | No redundant text-lg on CardTitle      | 18 files still have text-lg   | Add text-lg to a CardTitle          | grep for 'CardTitle className="text-lg"' returns 0 |
    | TEST-DA-02-01-03     | unit | typography.ts exports heading constants| File missing or empty         | Delete typography.ts                 | File exists and exports PAGE_TITLE, SECTION_TITLE, BODY_TEXT, CAPTION |
  Acceptance Criteria:
    AC-01-01: CardTitle default class includes text-lg (not text-2xl)
    AC-01-02: No CardTitle has bare className="text-lg" (redundant with default)
    AC-01-03: typography.ts exists with 4 heading constants
  Traceability:
    AC-01-01 → TEST-DA-02-01-01
    AC-01-02 → TEST-DA-02-01-02
    AC-01-03 → TEST-DA-02-01-03


TASK-02: BATCH-DA-02/TASK-02 — Replace transition-all + Verification
  Priority:          Medium
  Description:       Replace all 11 "transition-all" instances with specific
                     transition properties based on what the element actually
                     animates (colors, shadows, transforms). Then run full
                     verification suite.
  Files in scope:
    - All .tsx files containing "transition-all" (11 instances)
  Depends on:        TASK-01
  Required Tests:
    | Test ID              | Type | Behavior Verified                      | Failure Mode                  | Falsified By                        | Pass Criteria                                  |
    |:---------------------|:-----|:---------------------------------------|:------------------------------|:------------------------------------|:-----------------------------------------------|
    | TEST-DA-02-02-01     | unit | No transition-all in non-test files    | Missed an instance            | Add transition-all to any file      | grep returns 0 matches                          |
    | TEST-DA-02-02-02     | unit | tsc passes clean (0 new errors)        | New TS error from changes     | Introduce a typo                    | tsc --noEmit exits 0 (excluding pre-existing)  |
    | TEST-DA-02-02-03     | unit | Test count maintained                  | Broken test from changes      | Delete a test file                  | passing >= 361                                  |
  Acceptance Criteria:
    AC-02-01: Zero "transition-all" in non-test .tsx
    AC-02-02: tsc passes with 0 new errors
    AC-02-03: 361+ tests pass
  Traceability:
    AC-02-01 → TEST-DA-02-02-01
    AC-02-02 → TEST-DA-02-02-02
    AC-02-03 → TEST-DA-02-02-03

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: CardTitle default is text-lg. No redundant text-lg overrides.
  BAC-02: Zero transition-all in non-test .tsx files.
  BAC-03: CHANGELOG.md updated with BATCH-DA-02 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-DA-02/.

═══════════════════════════════════════════════════════════
