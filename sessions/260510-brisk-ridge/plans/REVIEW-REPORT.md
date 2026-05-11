# BATCH-142 Review Report — REV-142-01

Reviewer: 260510-brisk-ridge
Date: 2026-05-10
Blueprint Version: 1.0

## Summary

**5 of 12 catch blocks have already been implemented in a prior batch** (likely BATCH-141). The Blueprint scope is stale for gap-detail.tsx, memory.tsx, and the two background catches in notification-bell.tsx. Only 7 catch blocks remain silent. Line numbers across the Blueprint are drifted by up to +8 lines in several files. The `global-search-dialog.tsx` search catch is not truly empty — it has a `setResults(null)` side effect that must be preserved.

## Verification Matrix

| # | File | Blueprint Line | Actual Line | Silent? | Current State | Delta |
|---|------|---------------|-------------|---------|---------------|-------|
| 1 | gap-detail.tsx | 110 | 111 | Was silent | **Already fixed** — `toast.error("Failed to update gap status")` | +1 |
| 2 | memory.tsx (stats) | 47 | 48 | Was silent | **Already fixed** — `console.warn("[memory] Failed to load stats:", err)` | +1 |
| 3 | memory.tsx (delete) | 114 | 115 | Was silent | **Already fixed** — `toast.error("Failed to delete memory item")` | +1 |
| 4 | notification-bell.tsx (unread) | 38 | 39 | Was silent | **Already fixed** — `console.warn("[notifications] Failed to fetch unread count:", err)` | +1 |
| 5 | notification-bell.tsx (list) | 49 | 50 | Was silent | **Already fixed** — `console.warn("[notifications] Failed to load notifications:", err)` | +1 |
| 6 | notification-bell.tsx (mark-all) | 80 | 81 | Yes — `// ignore` | Needs `toast.error` | +1 |
| 7 | notification-bell.tsx (mark-one) | 90 | 91 | Yes — `// ignore` | Needs `toast.error` | +1 |
| 8 | global-search-dialog.tsx | 74 | 74 | No — has `setResults(null)` | Needs `toast.error` + preserve side effect | 0 |
| 9 | autonomous.tsx | 60 | 60 | Yes — `// Non-fatal` | Needs `console.warn` | 0 |
| 10 | costs.tsx | 74 | 74 | Yes — `// Silently ignore` | Needs `console.warn` | 0 |
| 11 | knowledge-graph.tsx | 58 | 58 | Yes — `// Silently handle` | Needs `console.warn` | 0 |
| 12 | traces.tsx | 66 | 66 | Yes — `// Silently ignore` | Needs `console.warn` | 0 |

### HB-01 Exclusion Verification

| File | Blueprint Line | Actual State | Unchanged? |
|------|---------------|--------------|------------|
| error-boundary.tsx | 24 | `catch { // Sentry not initialized — ignore }` | ✅ Not modified |
| sessions.tsx | 50 | `catch { return dateStr; }` | ✅ Not modified |
| global-search-dialog.tsx (localStorage) | 29 | `catch { return []; }` | ✅ Not modified |

### Import Status (toast from sonner)

| File | Needs toast import? | Current state |
|------|-------------------|---------------|
| gap-detail.tsx | No — already imported at line 4 | `import { toast } from "sonner"` |
| memory.tsx | No — already imported at line 12 | `import { toast } from "sonner"` |
| notification-bell.tsx | No — already imported at line 6 | `import { toast } from "sonner"` |
| global-search-dialog.tsx | **Yes** — not imported | Needs adding |
| autonomous.tsx | N/A — console.warn only | — |
| costs.tsx | N/A — console.warn only | — |
| knowledge-graph.tsx | N/A — console.warn only | — |
| traces.tsx | N/A — console.warn only | — |

## Flags

| Check | Severity | Issue |
|-------|----------|-------|
| CHK-01 | **High** | **5 of 12 catch blocks already implemented.** gap-detail.tsx (1 block), memory.tsx (2 blocks), notification-bell.tsx (2 background blocks) have already been fixed with the exact messages the Blueprint specifies. Re-implementing would create duplicate code or overwrite correct implementations. **Scope must be reduced to 7 remaining blocks.** |
| CHK-02 | **High** | **global-search-dialog.tsx search catch is NOT empty.** Line 74 catch body contains `setResults(null)` — a functional side effect that clears stale results on failure. The Blueprint's implementation pattern (`} catch (err) { toast.error("..."); }`) would **drop the `setResults(null)` call**, causing stale results to persist after a failed search. Implementation must preserve: `} catch (err) { setResults(null); toast.error("Search failed — please try again"); }` |
| CHK-03 | **Medium** | **toast already imported in 3 of 4 toast-targeted files.** gap-detail.tsx (line 4), memory.tsx (line 12), and notification-bell.tsx (line 6) already have `import { toast } from "sonner"`. Adding it again would cause a duplicate-import compile error. Only global-search-dialog.tsx needs the import added. Blueprint TASK-01 instruction to "add the import" is over-broad. |
| CHK-04 | **Medium** | **Strategic bet says "11 catch blocks" but scope says "12."** Section 1 states "11 API catch blocks silently swallow errors" while Section 2 and Section 3 list 12 total (5 toast + 7 warn). Internal inconsistency in the Blueprint document. |
| CHK-05 | **Medium** | **knowledge-graph.tsx and traces.tsx classification debatable.** Both catches fire on explicit user clicks (entity selection, trace click). Users click an item expecting detail — failure produces no visible feedback. Blueprint classifies as "background" with `console.warn`, but `toast.error` would better match user expectations. Recommend Lead consider reclassifying these 2 blocks as user-initiated. |
| CHK-06 | **Low** | **notification-bell.tsx mark-all-read / mark-single-read line numbers slightly drifted.** Blueprint says lines 80 and 90; actual lines are 81 and 91. Delta of +1 line each. Within ±5 tolerance — implementer can locate blocks easily. |
| CHK-07 | **Low** | **costs.tsx handleLoadRun is user-triggered, not background.** The function loads per-run cost breakdown on demand. Blueprint classifies as "background fetch" but it's invoked by user action (run ID lookup). Low impact since the function may not be actively called in the current UI. |

## Revised Scope (Recommended)

If the Lead accepts CHK-01, the effective scope reduces to:

**TASK-01 (User-initiated — toast.error): 3 blocks** (was 5)
- notification-bell.tsx line 81 — mark all read
- notification-bell.tsx line 91 — mark single read
- global-search-dialog.tsx line 74 — search (preserve `setResults(null)`)

**TASK-02 (Background — console.warn): 4 blocks** (was 7)
- autonomous.tsx line 60 — scheduler/evolution status
- costs.tsx line 74 — run cost breakdown
- knowledge-graph.tsx line 58 — entity detail
- traces.tsx line 66 — trace detail

**TASK-03 (Tests): Reduce from 12 to 7 tests** — remove tests for the 5 already-implemented blocks, or convert them to regression tests that verify existing behavior is unchanged.

**Total: 7 blocks (3 toast + 4 warn), 1 new import (global-search-dialog.tsx only)**

## Recommendation

**HOLD** — Blueprint must be revised before implementation:

1. **Remove 5 already-completed blocks** from scope (CHK-01)
2. **Fix implementation pattern** for global-search-dialog.tsx to preserve `setResults(null)` (CHK-02)
3. **Remove duplicate import instructions** for files that already import toast (CHK-03)
4. **Consider reclassification** of knowledge-graph.tsx and traces.tsx catches (CHK-05)

Once Blueprint v1.1 addresses CHK-01 through CHK-03, the batch can PROCEED. CHK-05 is advisory and can be deferred to Lead discretion.

---

*Review completed: 2026-05-10T06:34+03:00 — Session 260510-brisk-ridge*
