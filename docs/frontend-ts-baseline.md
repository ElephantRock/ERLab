# Frontend TypeScript Build — Known Blocker Baseline

> **Status: CAPTURED, NOT REPAIRED.** This document records the broken
> frontend TS build as a known blocker. It is deliberately excluded from
> P0.2 (backend-only). Do not mix frontend remediation into provenance work.

## Measurement

| Field | Value |
|---|---|
| Build command | `cd frontend && npx tsc -b --force` (the `tsc -b` half of `npm run build`) |
| Error count | **101** (`error TS` lines) |
| Commit | `d380fa5` (branch `feat/quarantine-and-frontend-redesign`) |
| Vite half (`vite build`) | Not reached — `tsc -b && vite build` short-circuits on the tsc failure |
| `npm run build` result | **FAILS** |

## Correction to the prior session report

The handoff report stated "86 pre-existing errors — `npm run build` fails.
Not caused by this session."

**This is inaccurate on two counts:**

1. **Count:** actual is **101**, not 86.
2. **"Pre-existing / not caused by this session":** FALSE. A clean comparison
   against `master` (via an isolated git worktree) shows **master compiles
   with 0 errors**. The 101 errors were introduced by this branch's 5-phase
   frontend redesign (59 files changed, 4743 insertions / 2716 deletions).

### Evidence

- `master` worktree: `npx tsc -b --force` → **0 errors**
- HEAD (`d380fa5`): `npx tsc -b --force` → **101 errors**
- 33 of 35 error-bearing files exist on master (where they compile clean);
  the branch rewrote or indirectly affected them. Only 2 files are new.
- Example direct edit: `src/pages/run-detail.tsx` — 32 of the 101 errors,
  branch rewrote it (97 insertions / 166 deletions vs master).
- Example indirect edit: `src/components/onboarding/onboarding-overlay.tsx`
  — 9 errors, NOT touched on this branch, but errors via a type change in a
  shared dependency. Collateral, not a direct edit.

## Error categories (by TS code)

| Count | Code | Meaning |
|---|---|---|
| 34 | TS6133 | declared but value never read (unused vars/imports) |
| 31 | TS18048 | possibly undefined (missing null checks) |
| 8 | TS2532 | object possibly undefined |
| 8 | TS2322 | type not assignable |
| 7 | TS2345 | argument type mismatch |
| 6 | TS6196 | declared but never used (type imports) |
| 5 | TS2339 | property does not exist on type |
| 1 | TS6192 | all imports unused |
| 1 | TS2741 | missing required property |

**~63% (40/101) are unused-symbol warnings** (TS6133+TS6196+TS6192) — low-risk
cleanup. The remainder are real type-safety gaps (null-check, assignability).

## Top files (by error count)

| Errors | File |
|---|---|
| 32 | `src/pages/run-detail.tsx` |
| 9 | `src/components/onboarding/onboarding-overlay.tsx` |
| 6 | `src/components/pipeline/run-config-form.tsx` |
| 5 | `src/components/search/global-search-dialog.tsx` |
| 4 | `src/pages/settings.tsx` |
| 4 | `src/pages/pipeline-new.tsx` |
| 4 | `src/pages/ideas-browser.tsx` |
| 3 | `src/pages/gap-detail.tsx` |
| 3 | `src/pages/autonomous.tsx` |
| 3 | `src/components/knowledge-graph/graph-canvas.tsx |

## Posture for P0.2

```
Backend provenance work:   CAN PROCEED (P0.2 is backend-only)
Repository-wide "shipped": BLOCKED until this baseline is resolved
Frontend follow-on work:   BLOCKED until TS baseline is resolved
```

## Reproducing

```bash
cd frontend
npx tsc -b --force 2>&1 | grep -c "error TS"   # expect 101
```

To compare against master:
```bash
git worktree add /tmp/er-master master
cd /tmp/er-master/frontend
ln -s $OLDPWD/../frontend/node_modules node_modules
npx tsc -b --force 2>&1 | grep -c "error TS"   # expect 0
git worktree remove /tmp/er-master --force
```
