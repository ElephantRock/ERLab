# BATCH-143 Blueprint — Navigation & Dead-End Remediation

**Batch ID:** BATCH-143
**Cycle Mode:** STANDARD (Lead Override §5.3)
**Lead Programmer:** ivory-wolf
**Date Issued:** 2026-05-10
**Framework Version:** AIV v5.3
**Preceding Batch:** BATCH-142 (CLOSED)

---

## 1. Strategic Bet

3 navigation issues remain after BATCH-141's Resume button fix: (a) source gap IDs in idea-detail are plain text instead of links, (b) global search "papers" navigates to /literature without the search query, (c) run-detail back button goes to / (dashboard) instead of the pipeline page. Fixing all 3 closes every dead-end in the user journey.

## 2. Tasks

### TASK-01: Make Source Gap IDs Clickable Links (High)

**File:** `frontend/src/pages/idea-detail.tsx` lines 153-169

**Current:** Source gap IDs rendered as plain `<li>` text
**Fix:** Wrap each gap ID in a `<Link to="/gaps/{gapId}">` or `<button onClick={() => navigate(/gaps/${gapId})>`

### TASK-02: Global Search Papers Navigate with Query (Medium)

**File:** `frontend/src/components/search/global-search-dialog.tsx`

**Current:** `case "papers": navigate("/literature"); break;`
**Fix:** `case "papers": navigate("/literature?q=" + encodeURIComponent(item.title)); break;`
Also update literature.tsx to read `q` from URL search params and auto-search.

### TASK-03: Run-Detail Back Button → Pipeline Page (Medium)

**File:** `frontend/src/pages/run-detail.tsx`

**Current:** 3 instances of `onClick={() => navigate("/")}` (dashboard)
**Fix:** Change to `onClick={() => navigate("/pipeline")}` — the pipeline new page, which shows the runs list.

### TASK-03: Test Coverage

12 tests in `frontend/src/__tests__/batch143-navigation.test.tsx`

## 3. Hard Boundaries

| HB | Description |
|----|-------------|
| HB-01 | gap IDs must link to `/gaps/{id}` (not just any page) |
| HB-02 | Paper search must pass the query term via URL param |
| HB-03 | All back buttons in run-detail must go to `/pipeline` (not `/`) |
| BAC-01 | 0 new TS errors |
| BAC-02 | No backend changes |
