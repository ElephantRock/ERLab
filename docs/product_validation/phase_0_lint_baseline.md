# Phase 0 Lint Baseline & Warning-Budget Policy

> **Purpose:** freeze the Phase 0 warning count so it cannot silently grow,
> and codify the rule that pre-existing warnings may remain temporarily but
> **new** warnings require a recorded exception. This is the "lint debt
> ledger" the Phase-0 acceptance review asked for.
>
> **Status:** the mechanical guard is **live** (Wave 0.5D). The policy is no
> longer honor-system — `npm run lint:budget` enforces it.

## How to reproduce

```bash
cd frontend
npm run lint:budget              # the guard — checks against the frozen baseline
npm run lint                     # raw eslint (warnings visible, non-blocking)
```

The baseline is frozen in `frontend/lint-budget.json`. The count, not a
file list, is what matters — refactors move warnings between files without
changing contract health.

## Baseline — Phase 0 freeze

### Total

```
192 warnings, 0 errors  (frozen in frontend/lint-budget.json)
```

The count dropped from the original 194 to 192 after the two Wave 0.5B
correctness fixes (the `StageModelSelector` auth-bypass migration removed
two unused-symbol warnings; the consciousness-state wiring cleaned one
exhaustive-deps). **The ratchet is already doing its job** — that's the
guard working.

### By rule

| Rule | Count | Bucket | Notes |
|---|---|---|---|
| `@typescript-eslint/no-unused-vars` | 120 | **pre-existing debt** | Surfaces because lint was broken; flagged for cleanup pass. |
| `erock/no-telemetry-headings` | 32 | **contract** | Ops-aesthetic pattern. Migrates to 0 in Phase 2 (reading surface) + Phase 3. |
| `erock/no-sub-micro-type` | 12 | **contract** | `text-[8px]`/`[9px]`/`[10px]`. Migrates in Phases 2–4. |
| `erock/no-raw-colors` | 12 | **contract** | Hardcoded palette. Migrates in Phase 3. |
| `@typescript-eslint/no-explicit-any` | 8 | **pre-existing debt** | TS hygiene; cleanup pass. |
| `@typescript-eslint/no-require-imports` | 4 | **pre-existing debt** | Likely vestigial; investigate. |
| `react-hooks/exhaustive-deps` | 2 | **pre-existing debt** | Intentional `tick` refresh-nudges (see eslint.config.js comment). |
| `prefer-const` | 1 | **pre-existing debt** | Auto-fixable. |
| `erock/no-raw-use-effect-fetch` | 1 | **contract (under-counted)** | Conservative heuristic. The manual migration candidate list is authoritative: ~10 pages. |

**Totals by bucket:**
- Contract rules: **57** (target: 0 by Phase 5)
- Pre-existing TS/JS debt: **135** (target: reduced by a focused cleanup pass; no hard deadline, but see budget)

## Warning-budget policy

> The ratchet only works if the baseline cannot silently grow. This policy
> is the enforcement — and as of Wave 0.5D, it is mechanically enforced.

### Rule

```text
Pre-existing warnings (the 192 above) may remain temporarily.

New warnings may not be introduced without a recorded exception:
    // LINT-EXCEPTION: <rule> — <reason, citing PRODUCT.md if applicable>

The Phase 5 lint-flip gate requires:
    1. All 4 contract rules at 0 warnings (before flipping to "error").
    2. Pre-existing debt reduced or explicitly accepted in this file.
```

### Mechanical enforcement — `npm run lint:budget` (live since Wave 0.5D)

The guard lives at `frontend/scripts/check-lint-budget.cjs`. It:

1. Runs eslint via the programmatic API (avoids Windows `.cmd`/npx spawn issues).
2. Counts warnings, split into **contract** (`erock/*`) and **hygiene** (everything else).
3. Compares against `frontend/lint-budget.json`.
4. **Exits 1 if either category grew** — fails CI, blocks merge.
5. **Exits 0 if counts held or shrank** — reductions welcome.

The guard tracks contract and hygiene **separately**. This matters: it's
fine for a Phase 3 page migration to *reduce* contract warnings while
*temporarily increasing* hygiene warnings (e.g. typing a blob might surface
new unused-vars). The category split prevents a hygiene increase from
masking a contract regression and vice versa.

### Workflow

```text
On every PR touching frontend:
  npm run lint:budget

If it fails (budget exceeded):
  1. Fix the regression — the per-rule delta in the failure output shows
     exactly which rule grew.
  2. OR add a // LINT-EXCEPTION comment citing PRODUCT.md and hand-edit
     lint-budget.json (do NOT use --update-baseline for growth).

When you've reduced warnings (always welcome):
  npm run lint:budget -- --update-baseline
  → writes the new (lower) count to lint-budget.json
  → review the diff before committing
  → the guard REFUSES to write a larger baseline (ratchet only tightens)
```

### Why contract debt is treated differently from TS debt

The 4 contract rules (`erock/*`) are load-bearing — they encode
`PRODUCT.md`/`INTERFACE_CONTRACT.md`. They **must** reach 0 before Phase 5
flips them to `error`. The TS/JS debt (`no-unused-vars` etc.) is hygiene;
it's worth reducing but doesn't block the contract hardening. Treating
them the same would either (a) delay Phase 5 indefinitely on hygiene, or
(b) force a rushed 135-fix churn that violates the no-churn principle.
Separating them lets the contract lock on schedule while hygiene proceeds
at its own pace.

## Phase 0 → Phase 5 trajectory (expected)

| Phase | Contract warnings (target) | Notes |
|---|---|---|
| 0 (now) | 57 | Baseline. |
| 1 (shell + IA) | ~45 | Shell retype removes telemetry-headings + sub-micro from sidebar/app-shell. |
| 2 (reading surface) | ~25 | `idea-detail` retype removes the densest telemetry/sub-micro cluster; reading-scale tokens adopted. |
| 3 (triage + dashboard) | ~10 | Migrate dense list pages; fix raw-colors as tokens complete. |
| 4 (direct + monitor) | ~3 | `pipeline-new`/`run-detail`. |
| 5 (long tail + flip) | **0** | Remaining pages; lint flips `erock/*` to `error`. |

The numbers are estimates, not commitments — the guard ensures monotonic
decrease regardless of exact per-phase counts.

## Open items

1. **Wire `lint:budget` into CI.** The script is ready (`npm run lint:budget`,
   exits 1 on regression). The GitHub Actions workflow (or equivalent) needs
   a step that runs it on every PR. Until then it runs locally/on-demand.
2. **`no-raw-use-effect-fetch` heuristic is conservative** — it found 1,
   the manual audit says ~10. The migration candidate list is authoritative
   for Phase 3. The rule improves after pages convert (fewer hand-rolled
   effects to match against) and tightens to catch the rest.
3. **Two intentional `exhaustive-deps` `tick` deps** — documented in
   `eslint.config.js`. Either formalize as `// LINT-EXCEPTION` or refactor
   to a `useResource` refetch trigger during the cleanup pass.
