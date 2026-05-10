# Three-Report Remediation Roadmap

**Lead Programmer:** ivory-wolf  
**Date Issued:** 2026-05-10  
**Framework:** AIV v5.3  
**Preceding Batch:** BATCH-140 (CLOSED)  
**Source Reports:**
- Technical Architecture Audit (`technical_audit_2026-05-10.md`)
- UX & User Journey Audit (`ux_audit_2026-05-10.md`)
- E2E QA Audit (`e2e_qa_audit_2026-05-10.md`)

---

## Batch Sequence Overview

### BATCH-141 — Quick Wins: Time-to-Value & Dead-Action Fixes
**Cycle Mode:** STANDARD  
**Strategic Bet:** Changing 3 lines of code cuts first-time-user wait from 25 min to 3 min and eliminates 2 dead-action buttons. This is the highest-impact-to-effort ratio batch in the entire roadmap.  
**Tasks:** 3 | **Expected Tests:** +18 | **Effort:** ~2 hours

### BATCH-142 — Silent Error Fix: Kill the `catch {}` Blocks
**Cycle Mode:** STANDARD  
**Strategic Bet:** 11 API catch blocks silently swallow errors. Users think actions succeeded when they didn't. Adding toast notifications to all 11 restores trust in every feedback loop across the app.  
**Tasks:** 3 | **Expected Tests:** +12 | **Effort:** ~2 hours

### BATCH-143 — Navigation & Dead-End Remediation
**Cycle Mode:** STANDARD  
**Strategic Bet:** 3 navigation dead-ends (Resume button, source gap IDs, paper search results) plus inconsistent back-button targets create confusion. Fixing them closes every broken path in the user journey.  
**Tasks:** 3 | **Expected Tests:** +12 | **Effort:** ~3 hours

### BATCH-144 — Pipeline Config UX: Reduce Form Density
**Cycle Mode:** STANDARD  
**Strategic Bet:** The pipeline config form shows 7 fields by default. A first-time user needs only 2 (domain + strategy). Collapsing non-essential fields into smart defaults with an "Advanced" toggle reduces cognitive load from 7±2 to 3±1.  
**Tasks:** 2 | **Expected Tests:** +10 | **Effort:** ~2 hours

### BATCH-145 — Sidebar Navigation Restructure
**Cycle Mode:** STANDARD  
**Strategic Bet:** 15 flat sidebar items violate Miller's Law (7±2). Grouping into 3 sections (Primary / Research Tools / System) with visual dividers cuts scanning time by ~10 seconds per visit.  
**Tasks:** 2 | **Expected Tests:** +8 | **Effort:** ~2 hours

### BATCH-146 — Feedback Loop Hardening: Toast Standardization
**Cycle Mode:** STANDARD  
**Strategic Bet:** 6 components lack success or error toast notifications. Standardizing all interactive actions to produce toast feedback creates a consistent "action → acknowledgment" pattern that users can trust.  
**Tasks:** 2 | **Expected Tests:** +8 | **Effort:** ~1.5 hours

### BATCH-147 — Onboarding Recovery & First-Run Optimization
**Cycle Mode:** STANDARD  
**Strategic Bet:** The onboarding overlay is permanently dismissible with no recovery path. Adding a "Show onboarding" option in Settings and auto-selecting "Quick Scan" when arriving from onboarding creates a guided path that never truly disappears.  
**Tasks:** 2 | **Expected Tests:** +8 | **Effort:** ~2 hours

### BATCH-148 — Export Dialog Fix & Gap Detail Query Fix
**Cycle Mode:** STANDARD  
**Strategic Bet:** Two broken features: the export format selector is cosmetic (always exports PDF regardless of selection) and the gap detail "Related Ideas" section queries the gaps endpoint instead of the ideas endpoint. Both are functional bugs that produce wrong results silently.  
**Tasks:** 2 | **Expected Tests:** +10 | **Effort:** ~2 hours

### BATCH-149 — Accessibility Quick Fixes (WCAG 2.1 AA)
**Cycle Mode:** STANDARD  
**Strategic Bet:** 4 accessibility gaps (no skip-to-content, no aria-live for progress, small mobile touch targets, color-only indicators) block ~8% of potential users. These are structural, not cosmetic, and fixing them opens the platform to keyboard-only and screen-reader users.  
**Tasks:** 3 | **Expected Tests:** +10 | **Effort:** ~3 hours

### BATCH-150 — Loading State Standardization
**Cycle Mode:** STANDARD  
**Strategic Bet:** 3 pages (Costs, Governance, Traces) use plain text "Loading..." instead of skeleton cards. Standardizing all data-loading pages to use `<Skeleton>` components creates visual consistency and prevents layout shift.  
**Tasks:** 2 | **Expected Tests:** +6 | **Effort:** ~1 hour

---

## Roadmap Summary

| Batch | Goal | Tasks | +Tests | Effort |
|:------|:-----|:------|:-------|:-------|
| **BATCH-141** | Quick wins: strategy default + dead buttons | 3 | +18 | 2h |
| **BATCH-142** | Kill silent `catch {}` blocks | 3 | +12 | 2h |
| **BATCH-143** | Navigation dead-ends & back-button consistency | 3 | +12 | 3h |
| **BATCH-144** | Pipeline config form density reduction | 2 | +10 | 2h |
| **BATCH-145** | Sidebar navigation restructure (15→3 groups) | 2 | +8 | 2h |
| **BATCH-146** | Toast notification standardization | 2 | +8 | 1.5h |
| **BATCH-147** | Onboarding recovery + first-run optimization | 2 | +8 | 2h |
| **BATCH-148** | Export dialog fix + gap detail query fix | 2 | +10 | 2h |
| **BATCH-149** | Accessibility quick fixes (WCAG AA) | 3 | +10 | 3h |
| **BATCH-150** | Loading state standardization | 2 | +6 | 1h |
| **TOTAL** | **10 batches, 24 tasks** | **24** | **+102** | **~20.5h** |

### Cumulative Test Baseline

| After Batch | Total Tests |
|:------------|:------------|
| BATCH-140 (current) | 2,480 |
| BATCH-141 | 2,498 |
| BATCH-145 | 2,540 |
| BATCH-150 | 2,582 |

### Dependency Graph

```
BATCH-141 ──── independent (start immediately)
BATCH-142 ──── independent
BATCH-143 ──── independent
BATCH-144 ──── independent
BATCH-145 ──── independent
BATCH-146 ──── independent
BATCH-147 ──── depends on BATCH-141 (quick-scan default feeds onboarding)
BATCH-148 ──── independent
BATCH-149 ──── independent
BATCH-150 ──── independent
```

All batches except BATCH-147 are independent and could theoretically run in parallel. BATCH-147 should follow BATCH-141 because it references the `fast_scan` strategy default.

---

*Below: Complete BATCH-141 Specimen Blueprint*
