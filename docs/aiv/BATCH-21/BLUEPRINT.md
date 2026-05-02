BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-21
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Lead
Date Issued:              2026-05-02

BATCH GOAL: Traces page with summary stats, trace list, span detail view.

SCOPE:
  MUST: Replace /traces placeholder, show trace summary, trace list with spans, latency metrics
  MUST NOT: Modify backend trace endpoints

HB-01: No backend modifications. Endpoints:
  GET /api/v1/traces/summary → {total_traces, active_traces, error_rate}
  GET /api/v1/traces/trace/{id} → {trace_id, spans: [{name, duration_ms, ...}]}
  GET /api/v1/traces/metrics → {p50_ms, p99_ms, error_rate}

DEPENDENCY: BATCH-16 (placeholder)
BASELINE: 1,695 tests | Delta: +12 | Target: 1,707

TASK LIST (SEQUENTIAL):
───────────────────────────────────────────────────────────

TASK-01: Traces API Client & Components
  Files: frontend/src/api/traces.ts (NEW)
         frontend/src/components/traces/trace-summary.tsx (NEW)
         frontend/src/components/traces/span-detail.tsx (NEW)
  Tests: TEST-21-01-01: getTraceSummary() correct endpoint
         TEST-21-01-02: getTrace(id) correct endpoint
         TEST-21-01-03: getTraceMetrics() correct endpoint
         TEST-21-01-04: TraceSummary renders stats
         TEST-21-01-05: SpanDetail renders span data
  Commit: feat(batch-21/task-01): add traces API client and components

TASK-02: Traces Page
  Files: frontend/src/pages/traces.tsx (NEW — replaces placeholder)
         frontend/src/App.tsx (MODIFY)
  Tests: TEST-21-02-01: Page renders summary
         TEST-21-02-02: Trace list loads from summary
         TEST-21-02-03: Click trace shows span detail
         TEST-21-02-04: Latency metrics displayed
         TEST-21-02-05: Error state handled
         TEST-21-02-06: Empty state shown
         TEST-21-02-07: Service unavailable shows message
  Commit: feat(batch-21/task-02): add traces viewer page

BAC: BAC-01 Traces page shows summary+detail | BAC-02 CHANGELOG | BAC-03 docs archived
LEAD RESPONSE: Inline review. All shapes verified from traces.py. ACCEPT.
Lead Sign: Lead + 2026-05-02 08:35

═══════════════════════════════════════════════════════════
