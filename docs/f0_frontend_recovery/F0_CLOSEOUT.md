# F0 Closeout — Frontend Baseline Recovery

> Restore a clean, reproducible TypeScript build without changing product
> semantics or hiding errors through relaxed compiler settings.

## Status

```
F0         CLOSED — green TypeScript build, ratcheted, sealed
Frontend   GREEN (build, test, lint all pass)
```

## Result against the directive's targets

| Target | Result |
|---|---|
| TypeScript errors 101 → 0 | ✅ **0** |
| compiler strictness weakened | ❌ no (tsconfig UNCHANGED) |
| production paths excluded | ❌ no (no tsconfig `exclude` changes) |
| unresolved suppressions | ✅ 0 (zero `@ts-ignore`/`@ts-expect-error` in `frontend/src/`; zero new suppressions in the F0 diff) |
| frontend build green | ✅ `npm run build` succeeds (tsc + vite) |
| working tree clean | ✅ (after commit) |

## Commit chain (F0)

```
01f4bb2  fix(f0): restore green TypeScript build — 101 errors to 0
6004001  docs(f0): fingerprint + classify the 101-error TS baseline
(pending) feat(f0): add TypeScript error-budget ratchet (F0.5) + five-run seal
```

Reference baseline commit preserved: `db4d499e54900f7c2d3fdbb1e626ef75664c5720`.
Baseline raw-errors artifact: `docs/f0_frontend_recovery/baseline_tsc_errors.txt`
(SHA-256 `5eb40440…`, 101 lines, committed at `6004001`).

## Repair summary (101 → 0, by root-cause category)

| Category | Errors | Fix |
|---|---:|---|
| 1. dead/unreachable code | 41 | deleted unused vars/imports/type imports (delegated to a focused agent; deletions only, no logic change) |
| 2. nullable-state errors | 39 | real null guards — `run-detail.tsx` one explicit `if (!run) return null` (narrowed 31); `onboarding-overlay.tsx` extracted `const current = STEPS[step]` + guard; `stage-model-editor.tsx` `?? ""` on string index |
| 3. API/schema drift | 2 | added `pipeline_run_id?: number \| null` to `ResearchGap` (verified against backend `ResearchGapDB` + `gaps.py:387`) |
| 4. generated/stale types | 4 | added `src/vite-env.d.ts` referencing `vite/client`; replaced hand-rolled SVG with real lucide `CircleSlash` |
| 5. invalid component props | 8 | `dialog.tsx` coalesce optional callback; `revision-history-drawer.tsx` `Boolean()`; `idea-detail.tsx` typed prop as `IdeaDetail` (dropped an `as`); `pipeline-new.tsx` + `types.ts` corrected `SystemStatus.config` to `Record<string, boolean \| string>`; `run-config-form.tsx` typed 3 useState with literal unions |
| 6. unsafe unknown/any | 1 | `governance-panel.tsx` `typeof` narrowing on `event.detail.note` |
| 7. useState literal types | 3 | `run-config-form.tsx` explicit `<number>` generics |
| (other TS2345/TS2532) | 3 | `gaps-explorer`/`ideas-browser` Slider `v[0] ?? 0`; `pipeline-new` closure-capture for `runId` narrowing; `run-detail` `String(runId)` for `getRunIdeas` (backend route takes string) |

Every repair addresses the root cause. No `@ts-ignore`, no unjustified
`@ts-expect-error`, no `as any`, no `as unknown as`, no `skipLibCheck`
change, no strictness relaxation, no production-directory exclusion.

## F0.5 — TypeScript error-budget ratchet

`frontend/scripts/check-ts-budget.cjs` + `frontend/ts-budget.json` (frozen
at 0 errors, baseline `01f4bb2`). Wired into CI at `.github/workflows/ci.yml`
as an explicit step before `npm run build`.

Verified behavior:
- ✅ passes at 0 errors (exit 0, "OK: 0 errors (matches baseline of 0)")
- ✅ fails on regression (synthetic `const _x: number = "string"` → exit 1,
  clear "REGRESSION: current 2 errors > baseline 0" + full tsc output)
- ✅ `--update-baseline` refuses to raise the count (one-way ratchet)
- ✅ invokes the local TypeScript binary directly via `process.execPath`
  (avoids the Windows `npx`/`.cmd` issue that affects `execFileSync`)

The ratchet is belt-and-suspenders with `npm run build`: build is binary
(green/red), the ratchet reports the delta vs baseline and refuses to
silently weaken.

## F0.6 — Five-run seal

Five consecutive clean runs of each gate, all green:

```
npx tsc -b --force (×5):     exit 0, 0 errors, every run
npm run build (×5):          exit 0, "✓ built in ~6s", every run
```

Plus the standing verifications:
```
npm test (vitest):           690 passed across 105 files
npx eslint . :               0 errors (72 pre-existing warnings, none new)
backend tests/test_ranking:  137 passed
new suppressions in F0 diff: 0
tsconfig strictness:         UNCHANGED
```

## Posture

```
frontend TypeScript build   GREEN (101 -> 0, ratcheted at 0)
frontend build (tsc+vite)   GREEN
frontend tests              GREEN (690/690)
frontend lint               GREEN (0 errors; 72 warnings = pre-existing debt)
CI ratchet                  ACTIVE (ts:budget step fails on any regression)
legacyLexical_top20_v1      production-authoritative (unchanged — F0 is frontend-only)
P1                          OPEN and paused (unchanged — F0 doesn't reopen P1)
Frontend track              UNBLOCKED for the next frontend wave
```

## Honest notes

1. **72 eslint warnings remain** — these are pre-existing `no-unused-vars`
   warnings (mostly on `catch (err)` blocks where `err` is unused). They
   predate F0 and are tracked by the existing `lint-budget.json` ratchet
   (`hygiene: 122` baseline at the F0 entry; not regressed by F0). F0 did
   not touch warning debt — that's a separate hygiene schedule.

2. **One ambiguous case was left for explicit decision, then resolved.**
   The agent flagged `gaps-explorer.tsx:174` (`useState<number>`) as
   ambiguous because widening to `number | undefined` would create new
   TS18048 errors. I resolved it differently: kept `useState(0)` (number)
   and added `v[0] ?? 0` at the Slider call site — root-cause fix, no
   widening, no new errors.

3. **F0 is strictly frontend.** No backend code, no ranking policy, no
   production activation. `legacy_lexical_top20_v1` remains
   production-authoritative. P1 stays OPEN and paused. F0 unblocks the
   frontend track but does not change the ranking roadmap posture.

## Artifacts

```
docs/f0_frontend_recovery/baseline_tsc_errors.txt   frozen baseline (5eb40440...)
docs/f0_frontend_recovery/remaining_after_cat1_7.txt intermediate state (46 errors)
docs/f0_frontend_recovery/F0_BASELINE.md            F0.0 + F0.1 fingerprint + classification
docs/f0_frontend_recovery/F0_CLOSEOUT.md            this file
frontend/scripts/check-ts-budget.cjs                F0.5 ratchet
frontend/ts-budget.json                             F0.5 frozen baseline (0 errors)
frontend/src/vite-env.d.ts                          vite/client types (F0.2 Cat 4)
.github/workflows/ci.yml                            + ts:budget step
```
