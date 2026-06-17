# Web UI Rebuild — Deferred Work

## Scope

This document captures UI work that was identified during the
Web UI rebuild (Phases 0–6) but deferred because the backend
contract was unclear, missing, or out of scope for the phase.

## Deferred Items

### 1. Literature Source Links (Idea → Papers)

**Why deferred:** The `IdeaDetail` API response (`GET /ideas/{id}`)
does not include source paper IDs. The `source_gap_ids` field exists
but links ideas to gaps, not to individual papers.

**What's needed:**
- Backend: Add `source_paper_ids: string[] | null` to the idea detail response
- Frontend: Render source paper links in `idea-detail.tsx` when the field is present
- Do NOT infer paper links from titles — this was explicitly ruled out

### 2. Editable Stage Model Overrides

**Why deferred:** The backend `GET /settings/assignments` endpoint
is read-only. No PUT/POST endpoint exists for updating stage-to-model
routing from the UI.

**What's needed:**
- Backend: `PUT /settings/assignments` with stage→model_id mapping
- Frontend: Edit mode in `ModelStatusPanel` or a dedicated routing editor
- Validation: Ensure assigned models are certified for the target stage

### 3. Per-Idea LaTeX Export

**Why deferred:** The backend LaTeX export endpoint (`GET /export/latex/{run_id}`)
is run-level, not idea-level. The per-idea export supports PDF and Markdown only.

**What's needed:**
- Backend: `POST /export/latex` with `idea_id` (or extend existing endpoint)
- Frontend: Add LaTeX option to `ExportDialog` for single-idea mode

### 4. Deeper Review Workflows

**Why deferred:** The governance queue (`GET /governance/pending`)
returns a flat list. There's no detail view, history, or batch operations.

**What's needed:**
- Backend: `GET /governance/{id}` for decision detail with context
- Backend: `GET /governance/history` for past decisions
- Frontend: Detail panel, history view, batch approve/deny

### 5. Experiment Results in Run Detail

**Why deferred:** `PipelineRunDetail` doesn't include experiment results.
They appear only in `IdeaDetail.experiment_results`.

**What's needed:**
- Backend: Add `experiment_summary` to run detail (count, success rate)
- Frontend: Summary card in `run-detail.tsx`

### 6. Live E2E Smoke Test (Start-to-Export)

**Why deferred:** Belongs in Phase 6 once UI stabilizes, but requires
a running backend + LM Studio instance. Should be run manually before
each release, not in CI.

**Manual smoke test procedure:**
1. Start backend: `python -m uvicorn backend.api.main:app`
2. Start frontend: `cd frontend && npm run dev`
3. Navigate to `/pipeline/new`
4. Start a run with domain "machine learning"
5. Wait for completion (watch SSE progress)
6. Click "View Run Details"
7. Export as Markdown
8. Export as LaTeX
9. Navigate to an idea, verify proposal sections render
10. Copy a section to clipboard
