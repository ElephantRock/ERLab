# BATCH-142 Blueprint — Silent Error Fix: Kill the `catch {}` Blocks

**Batch ID:** BATCH-142  
**Cycle Mode:** STANDARD  
**Lead Programmer:** ivory-wolf  
**Date Issued:** 2026-05-10  
**Framework Version:** AIV v5.3  
**Preceding Batch:** BATCH-141 (CLOSED)  

---

## 1. Strategic Bet

11 API catch blocks silently swallow errors. Users think actions succeeded when they didn't. Adding toast notifications to 5 user-initiated actions and console.warn to 7 background fetches restores trust in every feedback loop across the app. This is a low-risk, high-clarity batch — no structural changes, only error handling.

## 2. Scope & Boundaries

### In Scope
- 5 user-initiated catch blocks: add `toast.error()` with contextual message
- 7 background-fetch catch blocks: add `console.warn()` with endpoint context
- Test each fix with a unit test verifying the toast/warn fires

### Out of Scope (Hard Boundary HB-01)
- `error-boundary.tsx:24` — catches by design (React error boundary)
- `sessions.tsx:50` — date formatting fallback (returns raw string)
- `search/global-search-dialog.tsx:29` — localStorage parse (returns [])

### Files Touched
1. `frontend/src/pages/gap-detail.tsx` — 1 catch block
2. `frontend/src/pages/memory.tsx` — 2 catch blocks (1 user + 1 background)
3. `frontend/src/components/notifications/notification-bell.tsx` — 4 catch blocks (2 user + 2 background)
4. `frontend/src/components/search/global-search-dialog.tsx` — 1 catch block (user)
5. `frontend/src/pages/autonomous.tsx` — 1 catch block (background)
6. `frontend/src/pages/costs.tsx` — 1 catch block (background)
7. `frontend/src/pages/knowledge-graph.tsx` — 1 catch block (background)
8. `frontend/src/pages/traces.tsx` — 1 catch block (background)

**Total: 8 files, 12 catch blocks (5 toast + 7 warn)**

## 3. Tasks

### TASK-01: User-Initiated Action Error Toasts (Critical)

Add `toast.error()` to 5 catch blocks where the user explicitly triggered the action:

| # | File | Line | User Action | Toast Message |
|---|------|------|-------------|---------------|
| 1 | gap-detail.tsx | 110 | Change gap status | "Failed to update gap status" |
| 2 | memory.tsx | 114 | Delete memory item | "Failed to delete memory item" |
| 3 | notification-bell.tsx | 80 | Mark all notifications read | "Failed to mark notifications as read" |
| 4 | notification-bell.tsx | 90 | Mark single notification read | "Failed to mark notification as read" |
| 5 | global-search-dialog.tsx | 74 | Search execution | "Search failed — please try again" |

**Implementation pattern:**
```typescript
// BEFORE:
} catch {
  // ignore
}

// AFTER:
} catch (err) {
  toast.error("Failed to update gap status");
}
```

For files that don't yet import `toast` from `sonner`, add the import:
```typescript
import { toast } from "sonner";
```

**Acceptance Criteria:**
- AC-01-01: Each of the 5 catch blocks calls `toast.error()` with a human-readable message.
- AC-01-02: The import `import { toast } from "sonner"` is present in each file.
- AC-01-03: Original error is NOT shown to user (no `err.message` leak) — only the fixed message.

### TASK-02: Background Fetch Error Logging (High)

Add `console.warn()` to 7 catch blocks for background/optional data fetches:

| # | File | Line | What Fails | Warn Message |
|---|------|------|-----------|--------------|
| 1 | autonomous.tsx | 60 | Status fetch | "[autonomous] Failed to load status: {err}" |
| 2 | costs.tsx | 74 | Cost breakdown | "[costs] Failed to load cost data: {err}" |
| 3 | knowledge-graph.tsx | 58 | Entity detail | "[knowledge-graph] Failed to load entity: {err}" |
| 4 | memory.tsx | 47 | Memory stats | "[memory] Failed to load stats: {err}" |
| 5 | notification-bell.tsx | 38 | Unread count | "[notifications] Failed to fetch unread count: {err}" |
| 6 | notification-bell.tsx | 49 | Notification list | "[notifications] Failed to load notifications: {err}" |
| 7 | traces.tsx | 66 | Trace detail | "[traces] Failed to load trace detail: {err}" |

**Implementation pattern:**
```typescript
// BEFORE:
} catch {
  // Non-fatal
}

// AFTER:
} catch (err) {
  console.warn("[autonomous] Failed to load status:", err);
}
```

**Acceptance Criteria:**
- AC-02-01: Each of the 7 catch blocks calls `console.warn()` with the module tag prefix.
- AC-02-02: The error object is included in the warn for stack trace debugging.
- AC-02-03: No UI change — these are logging-only fixes.

### TASK-03: Test Coverage for Error Handling

Write tests in a new file `frontend/src/__tests__/batch142-error-handling.test.tsx`:

| Test ID | Type | Description | Pass Criteria | Falsification |
|---------|------|-------------|---------------|---------------|
| TEST-142-01-01 | unit | gap-detail shows toast on status update failure | `toast.error` called with "Failed to update gap status" | Remove the catch block or change the message |
| TEST-142-01-02 | unit | memory delete shows toast on failure | `toast.error` called with "Failed to delete memory item" | Remove the catch block |
| TEST-142-01-03 | unit | notification mark-all-read shows toast on failure | `toast.error` called with "Failed to mark notifications as read" | Remove the toast call |
| TEST-142-01-04 | unit | notification mark-single-read shows toast on failure | `toast.error` called with "Failed to mark notification as read" | Remove the toast call |
| TEST-142-01-05 | unit | global search shows toast on failure | `toast.error` called with "Search failed — please try again" | Remove the toast call |
| TEST-142-02-01 | unit | autonomous status fetch logs console.warn | `console.warn` called with "[autonomous]" prefix | Remove the warn call |
| TEST-142-02-02 | unit | costs fetch logs console.warn | `console.warn` called with "[costs]" prefix | Remove the warn call |
| TEST-142-02-03 | unit | memory stats fetch logs console.warn | `console.warn` called with "[memory]" prefix | Remove the warn call |
| TEST-142-02-04 | unit | notification list fetch logs console.warn | `console.warn` called with "[notifications]" prefix | Remove the warn call |
| TEST-142-02-05 | unit | traces detail fetch logs console.warn | `console.warn` called with "[traces]" prefix | Remove the warn call |
| TEST-142-03-01 | unit | error-boundary catch is NOT changed | Verify catch block is unchanged from HEAD | Modify the file |
| TEST-142-03-02 | unit | sessions date fallback is NOT changed | Verify catch block is unchanged from HEAD | Modify the file |

**Total: 12 tests**

## 4. Data Models

No data model changes. All modifications are to catch block bodies and imports.

## 5. Dependency Map

```
TASK-01 (toast errors) ──── independent
TASK-02 (console.warn) ──── independent
TASK-03 (tests)       ──── depends on TASK-01 + TASK-02
```

## 6. Authority Rules

| Rule | Applies To |
|------|-----------|
| HB-01: Do NOT modify error-boundary, sessions date fallback, or localStorage parse | TASK-01, TASK-02 |
| HB-02: Every modified catch block must have a `catch (err)` parameter (was bare `catch`) | TASK-01, TASK-02 |
| HB-03: Toast messages must NOT include raw error text (no err.message leak) | TASK-01 |
| HB-04: All 12 new tests must pass | TASK-03 |
| BAC-01: TypeScript compilation must produce 0 NEW errors | All |
| BAC-02: No backend changes | All |
| BAC-03: No new dependencies | All |
| BAC-04: LINT COMMAND: `cd frontend && npx tsc --noEmit 2>&1 | grep -c "error TS"` must return same count as pre-batch | All |

## 7. Test Traceability

| AC | Tests |
|----|-------|
| AC-01-01 | TEST-142-01-01, 01-02, 01-03, 01-04, 01-05 |
| AC-01-02 | TEST-142-03-01 (negative: verifies files NOT changed) |
| AC-01-03 | TEST-142-01-01 through 01-05 (check message is fixed, not err.message) |
| AC-02-01 | TEST-142-02-01 through 02-05 |
| AC-02-02 | TEST-142-02-01 through 02-05 (verify err object in warn call) |
| AC-02-03 | TEST-142-02-01 through 02-05 (no UI change = no rendering needed) |

---

## Lead Response Section (Post-Review)

Reviewer Report ID:       [Pending — awaiting review]
Review Cycle:             [1]
Lead Decision:            [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:
  FLAG-02 → Action taken:

Blueprint Version after response: 1.0
Lead Sign:                ivory-wolf — [pending]
