# F0 — Frontend Baseline Recovery

> Restore a clean, reproducible TypeScript build without changing product
> semantics or hiding errors through relaxed compiler settings.

## F0.0 — Baseline fingerprint (reproduced)

| Field | Value |
|---|---|
| Reference baseline commit | `db4d499e54900f7c2d3fdbb1e626ef75664c5720` |
| Reproduced at HEAD | `8919a81` (this branch) |
| Build command | `cd frontend && npx tsc -b --force` |
| Error count | **101** (`error TS` lines) — exact match to baseline |
| Raw errors fingerprint (SHA-256) | `5eb4044096dba0720aeea05e582c80943abedff6d702a9ed40991fe76df8ff33` |
| Raw errors artifact | `docs/f0_frontend_recovery/baseline_tsc_errors.txt` (101 lines) |
| `npm run build` (`tsc -b && vite build`) | **FAILS** (short-circuits at tsc) |

Master compiles with 0 errors (verified in `docs/frontend-ts-baseline.md`);
the 101 errors were introduced by this branch's 5-phase frontend redesign.

## F0.1 — Error classification by TS code

| Count | TS code | Meaning |
|---:|---|---|
| 34 | TS6133 | declared but value never read (unused vars/imports) |
| 31 | TS18048 | variable is possibly 'undefined' |
| 8 | TS2532 | object is possibly 'undefined' |
| 8 | TS2322 | type is not assignable |
| 7 | TS2345 | argument type mismatch |
| 6 | TS6196 | declared but never used (type imports) |
| 5 | TS2339 | property does not exist on type |
| 1 | TS6192 | all imports in declaration unused |
| 1 | TS2741 | missing required property |
| **101** | | |

## F0.1 — Root-cause classification (directive's 8 categories)

Each of the 101 errors maps to one of the directive's required categories.
Counts are derived from the TS code + the error message text.

### 1. Dead or unreachable frontend code — 41 errors (41/101 = 41%)

`TS6133` (34) + `TS6196` (6) + `TS6192` (1). Unused variables, imports, and
type imports left over from the 5-phase redesign. These are the largest
single category and the lowest-risk cleanup: deleting the declaration is
the correct fix, no behavior change.

Examples:
- `idea-card.tsx(18,9): 'refs' is declared but its value is never read`
- `global-search-dialog.tsx(11,3): 'IdeaSearchItem' is declared but never used`
- `stage-model-selector.tsx(3,1): All imports in import declaration are unused`

### 2. Nullable-state errors — 39 errors (39/101 = 39%)

`TS18048` (31) + `TS2532` (8). Missing null/undefined guards before property
access or method calls. Concentrated in `run-detail.tsx` (most of the 32
errors there are `run` being possibly undefined) and `onboarding-overlay.tsx`
(array-index access without guards). Correct fix: add explicit guards,
early returns, or `??` defaults — NOT non-null assertions.

Examples:
- `run-detail.tsx(165,38): 'run' is possibly 'undefined'`
- `onboarding-overlay.tsx(125,49): Object is possibly 'undefined'`

### 3. API/schema drift — 2 errors (2/101 = 2%)

`TS2339` errors where frontend types reference backend fields that no longer
exist. Concentrated in `gap-detail.tsx`: `Property 'pipeline_run_id' does
not exist on type 'ResearchGap'`. The backend `ResearchGap` schema dropped
or renamed `pipeline_run_id`; the frontend type wasn't updated. Correct fix:
update the frontend type to match the backend (verify against the live
backend model, not by guessing).

### 4. Missing or stale generated types — 4 errors (4/101 = 4%)

`TS2339` for `import.meta.env` (3 in `stage-model-selector.tsx`/`sentry.ts`)
+ `TS2741` for the lucide-icon `$$typeof` mismatch in `data-view.tsx`.
The `import.meta.env` errors indicate a missing `vite-env.d.ts` reference
or stale Vite client types. The lucide error is a library-type-version
mismatch (component-forwarded-ref shape). Correct fix: regenerate Vite
client types; pin or update lucide-react type definitions.

### 5. Invalid component props — 8 errors (8/101 = 8%)

`TS2322` where a prop value's type doesn't match the declared prop type.
Concentrated in `run-config-form.tsx` (string vs string-literal-union for
`"concise" | "standard" | "detailed"`) and `revision-history-drawer.tsx`
(`boolean | ""` vs `boolean | undefined`). Correct fix: narrow the value
type at the call site or fix the prop type — not cast.

### 6. Unsafe unknown/any handling — 1 error (1/101 = 1%)

`TS2322` in `governance-panel.tsx(225,9)`: `Type 'unknown' is not
assignable to type ...ReactNode`. A caught-error value is being rendered
without narrowing. Correct fix: narrow the unknown to a string before
rendering.

### 7. Argument-type mismatch (state setters) — 7 errors (7/101 = 7%)

`TS2345` — passing `number` to `SetStateAction<5>` (literal types inferred
from initial state) in `run-config-form.tsx`, and `number | undefined` to
`SetStateAction<number>` in `gaps-explorer.tsx`. These are useState typing
bugs: the initial state used a literal so the setter type collapsed to the
literal. Correct fix: type the useState generic explicitly
(`useState<number>(5)` not `useState(5)`).

### 8. Module/import resolution — 0 errors (0/101 = 0%)

No errors in this category. All imports resolve; the issues are type-level,
not path-level.

### 9. Library-version incompatibility — 1 error (1/101 = 1%)

The `TS2741` lucide `$$typeof` mismatch (counted under category 4 above for
its generated-types aspect, but also a library-type-version signal).

## F0.1 — Repair priority (by risk and dependency)

```
P1  Category 1 (dead code, 41)         — lowest risk, do first; pure deletion
P2  Category 7 (state setter types, 7) — localized, fix useState generics
P3  Category 2 (nullable state, 39)    — bulk of the work; add real guards
P4  Category 5 (component props, 8)    — narrow types at call sites
P5  Category 6 (unsafe unknown, 1)     — narrow the caught-error render
P6  Category 3 (API drift, 2)          — verify backend ResearchGap, update FE type
P7  Category 4 (generated types, 4)    — regenerate Vite client types; lucide pin
```

## F0.1 — Prohibited repair patterns (per directive)

These will NOT be used to drive the count to zero:

```
@ts-ignore
@ts-expect-error without tracked justification
broad any casts
skipLibCheck changes
weaker strictness (relaxing tsconfig)
excluded production directories
```

Every repair must address the root cause. The TS-code → category → root-cause
chain is recorded so the closeout can prove no error was suppressed.

## Top files (error concentration)

```
32  src/pages/run-detail.tsx                  (mostly nullable 'run')
 9  src/components/onboarding/onboarding-overlay.tsx  (nullable array index)
 6  src/components/pipeline/run-config-form.tsx       (props + setter types)
 5  src/components/search/global-search-dialog.tsx    (unused imports)
 4  src/pages/settings.tsx                            (unused + nullable)
 4  src/pages/pipeline-new.tsx                        (unused)
 4  src/pages/ideas-browser.tsx                       (unused)
 3  src/pages/gap-detail.tsx                          (API drift)
 3  src/pages/autonomous.tsx                          (unused)
 3  src/components/knowledge-graph/graph-canvas.tsx   (unused)
38  remaining files with 1-2 errors each
```

The top 3 files account for 47/101 errors (47%).

## Posture entering F0.2

```
baseline fingerprint    frozen (5eb40440...)
classification          complete (8 directive categories + repair priority)
tsconfig strictness     UNCHANGED (and will remain so)
target                  101 → 0 errors, no suppressions, green build
```
