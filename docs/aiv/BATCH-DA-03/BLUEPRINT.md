BATCH BLUEPRINT
Batch ID: BATCH-DA-03 | Version: 1.0 | Cycle: STANDARD
Lead: Craft Agent | Date: 2026-05-12 | Task Sequencing: Parallel

BATCH GOAL: Replace link-styled raw <button> elements with <Button variant="link">.
Standardize all 29 <label> elements to use a consistent Label component.

TASK-01: Replace Link-Style Raw Buttons with <Button variant="link">
  Priority: High
  Files: pages/login.tsx, pages/idea-detail.tsx, pages/dashboard.tsx
  Scope: 8 raw <button> elements that use text-primary underline/bg-transparent styles
  Tests:
    | TEST-DA-03-01-01 | unit | Login uses Button variant link | Still has raw <button> | Revert change | grep '<button' login.tsx returns 0 |

TASK-02: Standardize Labels to Two Variants
  Priority: Medium
  Files: 10 files with 29 <label> elements
  Scope: Create Label wrapper. Primary (text-sm font-medium) for forms.
         Secondary (text-xs text-muted-foreground uppercase tracking-wider) for filters.
  Tests:
    | TEST-DA-03-02-01 | unit | No bare <label> with inline styles | Still has inline className | Add inline label | grep returns 0 bare labels |

BAC-01: Zero link-styled raw <button> in login, idea-detail, dashboard
BAC-02: Zero inline-styled <label> elements
BAC-03: CHANGELOG updated
BAC-04: Documents archived under /docs/aiv/BATCH-DA-03/
