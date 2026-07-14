# Status Indicator Source Map

> **Purpose:** every UI string, dot, badge, or indicator that implies system,
> run, or model state — classified by the actual source of the state. This is
> validation-independent: PRODUCT.md rejects decorative status and hardcoded
> system-state claims regardless of who the user is.
>
> **Source:** machine-generated audit of `frontend/src/`. ~63 sites total.

## Classification scheme

| Class | Meaning |
|---|---|
| **query-backed** | Value comes from a fetched API response. (Name the endpoint.) |
| **config-backed** | Static local lookup table (color maps, label maps). |
| **derived-from-artifact-state** | Computed from a field on a fetched object (e.g. `run.status === "completed"`). |
| **hardcoded** | Literal string with no variable behind it. The "lying" indicators. |
| **remove** | Hardcoded and either contradicts nearby query-backed data or serves no honest purpose. |

## The reference endpoints

Query-backed indicators draw from these. Stating them once makes the
classifications unambiguous:

- `getSystemStatus()` → `GET /status` → `SystemStatus { config, defaults }`
- `getDetailedStatus()` → `GET /status/detailed` → `{ version, provider, db_status }`
- `testConnection()` → `GET /health`
- `getCatalog()` → `GET /settings/catalog` → models `{ is_loaded, health_status }`, `gpu`
- `listRuns()` / `getRunDetail()` → `run.status` ∈ `pending|running|completed|failed`
- `getOpsDashboard()` → run_health, source_health, quality_trends
- `api/autonomous.ts` → `getSchedulerStatus`, `getEvolutionStatus`, `getConsciousnessState`, `getAutonomousHistory`

---

## A. HARDCODED — the "lying" indicators (7 sites)

These imply system/run/model state but have no backing data. All violate
PRODUCT.md §6 ("honesty in state, not decoration"). Highest cleanup priority.

| # | File:line | Indicator | Problem |
|---|---|---|---|
| 1 | `components/layout/app-shell.tsx:111-116` | `SYS_OK` + green pulse dot | Always green, unconditional, global. **Remove** or wire to `/status`. |
| 2 | `pages/pipeline-new.tsx:241-244` | "Local GPU" + `status="ok"` | Literal string, forced green. Directly contradicts the query-backed rows at 246-256. |
| 3 | `pages/pipeline-new.tsx:260-262` | "System ready" + green pulse | Unconditional. Page *fetches* `systemStatus` (line 61) but this dot ignores it. |
| 4 | `pages/pipeline-new.tsx:237, 243` | `status="ok"` props on Provider & Compute rows | Even where the *value* is query-backed, the dot is hardcoded green. |
| 5 | `pages/dashboard.tsx:403` | "Telemetry live" | Literal mono label inside a card of genuine data — easy to mistake for real. |
| 6 | `pages/autonomous.tsx:30, 207` | Consciousness badge stuck at "Idle" | `consciousnessState` initialized to `"idle"`, **`getConsciousnessState()` never called** — badge is effectively hardcoded despite the API existing. |
| 7 | `components/pipeline/stage-model-selector.tsx:43,72,90` | Whole component | Legacy parallel to `ModelStatusPanel`; hits `/settings/models` via raw `fetch`, bypassing `apiFetch`/auth. Candidate for **removal**. |

## B. QUERY-BACKED — the honest majority (40 sites)

### Run/model state from `listRuns` / `getRunDetail`

| # | File:line | Indicator |
|---|---|---|
| 8 | `app-shell.tsx:18-22,142-152` | Header "Running" pulse pill — only when `runs.find(r => r.status === "running")` |
| 9 | `dashboard.tsx:90,163-170` | Latest-investigation status dot — `bg-accent` (running) / `bg-success` (completed) |
| 10 | `run-detail.tsx:31-36,196` | Run status `<Badge>` via `statusColors` map |
| 11 | `run-detail.tsx:75,99-104,226-236` | Stale-run warning (5min threshold) — derived from `created_at + status` |
| 12 | `run-detail.tsx:348,440,455,528` | Conditional sections gated on `status === "completed"/"failed"` |
| 13 | `components/pipeline/run-card.tsx:12-42` | Status badge + `isStaleRun()` ⚠ icon |
| 14 | `sessions.tsx:162-172` | Per-run status badge in session list |

### Pipeline progress (SSE-derived via `usePipelineProgress`)

| # | File:line | Indicator |
|---|---|---|
| 15 | `pipeline-new.tsx:297-316` | Cancelled/Complete/Live/Connecting badge trio |
| 16 | `pipeline-new.tsx:334-377` | Stage-flow colors/checks from `stage.status` |
| 17 | `components/pipeline/stage-progress.tsx:16-49` | Per-stage Check/Loader2/number icon |
| 18 | `run-detail.tsx:403-434` | Stages timeline (CheckCircle2/Loader2/Circle) |

### Model status (`getCatalog`, `getAssignments`, `getCertification`)

| # | File:line | Indicator |
|---|---|---|
| 19 | `components/settings/model-status-panel.tsx:95-105` | Per-model Loaded/Not-loaded icon (`is_loaded`) |
| 20 | `model-status-panel.tsx:67-73` | GPU name + VRAM free/total |
| 21 | `model-status-panel.tsx:147-164` | Stage-routing badges |
| 22 | `components/settings/stage-model-editor.tsx:71` | Filters `health_status !== "unreachable"` |
| 23 | `stage-model-editor.tsx:353-363` | Per-stage Certified/Not-certified icon |
| 24 | `stage-model-editor.tsx:339-343` | Dropdown "✓" / "(uncertified)" suffix |

### System status (`getSystemStatus`, `getDetailedStatus`, `testConnection`)

| # | File:line | Indicator |
|---|---|---|
| 25 | `pipeline-new.tsx:236-238` | Provider row value — query-backed; *dot* hardcoded (see #4) |
| 26 | `pipeline-new.tsx:246-256` | Governance + Memory rows — **both value AND dot query-backed** (the correct pattern) |
| 27 | `dashboard.tsx:373` | Research Health "Model route" — query-backed value |
| 28 | `settings.tsx:163-231` | Connection dot — `connState` from `testConnection()` |
| 29 | `settings.tsx:232-243` | "Connected" success + latency badge |
| 30 | `settings.tsx:261-277` | Backend Version/Provider/Database — `getDetailedStatus` |

### Ops dashboard (`getOpsDashboard`)

| # | File:line | Indicator |
|---|---|---|
| 31 | `ops.tsx:95-141` | Run Health card — Total/Completed/Failed/Running/Pending counts |
| 32 | `ops.tsx:195-225` | Source Health — per-source papers + ⚠ when `zero_result_runs > 0` |
| 33 | `dashboard.tsx:379-399` | "Sources Connected" — `s.papers > 0 ? "OK" : "Idle"` |
| 34 | `dashboard.tsx:341-345` | "Healthy" badge when `passRate >= 80` |
| 35 | `dashboard.tsx:348-369` | Quality pass-rate / citation %s with success/warning coloring |

### Autonomous / scheduler / evolution

| # | File:line | Indicator |
|---|---|---|
| 36 | `autonomous.tsx:205-215` | Scheduler "Status: {status}" + "Next Run" |
| 37 | `autonomous.tsx:219,228` | Start/Stop button disabled-states keyed on scheduler status |
| 38 | `autonomous.tsx:251-265` | Evolution Enabled/overlays/outcomes |
| 39 | `settings.tsx:379-388` | Self-Improvement "Evolution: Enabled/Disabled" |
| 40 | `components/autonomous/cycle-progress.tsx:11-25` | Cycle status badge via `STATUS_COLORS` |

### Traces / notifications / charts

| # | File:line | Indicator |
|---|---|---|
| 41 | `traces.tsx:172-188` | Per-trace "Active" badge (`i < summary.active_traces`) |
| 42 | `notifications/notification-bell.tsx:106-113` | Unread-count badge (`bg-destructive`, "9+") |
| 43 | `notification-bell.tsx:23-25,147,151-153` | Notification type icon + unread dot |
| 44 | `components/charts/run-status-chart.tsx:8-13` | Pie-slice colors via `STATUS_COLORS` |

## C. DERIVED-FROM-ARTIFACT-STATE (10 sites)

Computed from a field on a fetched object, not a direct status string.

| # | File:line | Indicator |
|---|---|---|
| 45 | `components/ideas/idea-card.tsx:36-67` | Status pills (Proposal/Idea-only, QC, governance) |
| 46 | `idea-detail.tsx:153-162` | QC badge PASS/ISSUES from `qualityChecks` |
| 47 | `idea-detail.tsx:491,516-527` | Failing-check dots + remediation hint severity |
| 48 | `dashboard.tsx:268-313` | "Needs Attention" + Quality Flag from `qualityFailures` |
| 49 | `dashboard.tsx:295-299` | "Proposal Ready" when `focusIdea.has_proposal` |
| 50 | `evidence-panel.tsx:195` | Source-gap resolved dot |
| 51 | `estimate-card.tsx:71-82` | "Cloud: $..." / "Local compute: Free" from estimate |
| 52 | `pipeline-new.tsx:213-217` | "Local" badge when `local_cost_usd === 0` |
| 53 | `traces.tsx:31,47-58` | `serviceUnavailable` flag from API error text |

## D. CONFIG-BACKED (4 sites)

Local lookup tables — color/label maps. Config-backed by definition even
when the value is query-backed.

| # | File:line | Map |
|---|---|---|
| 54 | `pipeline-new.tsx:515-519` | `SystemRow` dotColor map (`ok/warn/neutral`) |
| 55 | `idea-detail.tsx:81-86` | `GAP_TYPE_COLORS` + status options |
| 56 | `tree-visualization.tsx:345-354` | Legend dots (novelty thresholds) |
| 57 | `consciousness-state.tsx:9-16` | `STATE_CONFIG` map (state → label/color) |

## E. Decorative / non-status (excluded)

All `animate-spin` Loader2 instances (generic loaders), `Skeleton`
`animate-pulse`, progress bars, score badges, cluster dots. ~40 sites
flagged in the raw audit but correctly *not* status indicators.

---

## Findings worth surfacing now

### 1. The "lying" cluster is concentrated in 3 files
Of the 7 hardcoded sites, **5 are in `pipeline-new.tsx` and `app-shell.tsx`**
— the same files the UI evaluation flagged. The fix is local: wire the
dots to the `systemStatus` query the pages already fetch, or remove them.

### 2. A dead component is shipping bugs
`stage-model-selector.tsx` is a legacy parallel to `ModelStatusPanel` that
bypasses `apiFetch`/auth with raw `fetch`. It's not reachable from primary
nav (verify), but if reachable it both lies about state and bypasses
security. Candidate for **removal**, not migration.

### 3. The autonomous page has a fetch that's never made
`getConsciousnessState()` exists in the API client but the page initializes
`consciousnessState = "idle"` and never calls it. The badge is decorative
by accident. Either wire the call or remove the badge.

### 4. One genuine type bug surfaced
`SystemStatus.config` is typed `Record<string, boolean>` in
`api/types.ts:402`, but `pipeline-new.tsx:236` and `dashboard.tsx:373` read
`config.default_provider` as a string. The provider read may not typecheck
against the declared contract — worth verifying whether this is a type
looseness or an actual mismatch.

### 5. The honest pattern already exists as a template
`pipeline-new.tsx:246-256` (Governance + Memory rows) shows the correct
pattern: **both the value AND the status dot are query-backed**. Every
hardcoded site should converge on this pattern during Phase 3/4 migration.

## Cleanup priority (for Phase 3/4 — validation-independent)

| Priority | Site | Action |
|---|---|---|
| P0 | `app-shell.tsx:111-116` (SYS_OK) | Remove or wire to `/status` |
| P0 | `pipeline-new.tsx:241-244` (Local GPU) | Wire value to catalog GPU query; remove forced `ok` |
| P0 | `pipeline-new.tsx:260-262` (System ready) | Wire to `systemStatus` health, or remove |
| P0 | `autonomous.tsx` consciousness badge | Call `getConsciousnessState()` or remove badge |
| P1 | `stage-model-selector.tsx` (whole component) | Verify reachability; remove if dead |
| P1 | `pipeline-new.tsx:237,243` hardcoded `ok` dots | Make dot conditional on query |
| P2 | `dashboard.tsx:403` "Telemetry live" | Remove or make honest |
| P2 | `api/types.ts:402` type mismatch | Fix the `config` type |
