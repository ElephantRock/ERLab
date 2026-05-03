# BATCH-54 BLUEPRINT — Full UX E2E Test

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-03  
**AIV Framework:** v5.2  
**Status:** DRAFT  
**Cycle Mode:** Standard (2 Tasks)

---

## Objective

Conduct a comprehensive user experience end-to-end test of the Elephant Rock Research Platform by starting both backend and frontend servers, then systematically exercising every user journey via a real browser. The output is a **UX E2E Test Report** documenting every interaction, every page render, every API call, and every visual state — including screenshots.

---

## TASK-01: Platform Startup & Smoke Verification

### Objective
Start the full platform (backend + frontend), verify all services are healthy, and capture baseline screenshots of every page.

### Steps

1. **Start backend server:**
   ```bash
   cd C:/Next-Era/elephant-rock-platform
   python -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
   ```
   Wait for `INFO: Uvicorn running on http://0.0.0.0:8000`

2. **Start frontend dev server:**
   ```bash
   cd C:/Next-Era/elephant-rock-platform/frontend
   npm run dev
   ```
   Wait for `Local: http://localhost:3000/`

3. **Verify backend health:**
   - GET `http://localhost:8000/health` — should return 200
   - GET `http://localhost:8000/api/v1/status/` — should return system status

4. **Screenshot every page (20 pages):**
   Navigate to each route in the browser and take a screenshot:
   - `/` — Dashboard
   - `/pipeline/new` — New Pipeline
   - `/ideas` — Ideas Browser
   - `/gaps` — Gaps Explorer
   - `/knowledge` — Knowledge Search
   - `/knowledge-graph` — Knowledge Graph
   - `/settings` — Settings
   - `/costs` — Costs
   - `/memory` — Memory
   - `/governance` — Governance
   - `/traces` — Traces
   - `/sessions` — Sessions
   - `/literature` — Literature
   - `/autonomous` — Autonomous
   - `/plugins` — Plugins
   - `/login` — Login

5. **Record findings per page:**
   For each page, document:
   - Does it render? (Y/N)
   - Are there console errors?
   - Is the layout correct? (sidebar, header, content area)
   - Are there visible UI defects?
   - Screenshot file path

### Deliverable
- `sessions/260501-ivory-wolf/data/ux_e2e_smoke.md` — Page-by-page smoke results with screenshots

---

## TASK-02: Core User Journey Execution

### Objective
Execute the 5 core user journeys of the platform, documenting every interaction, response, and visual state.

### Journey 1: Pipeline Execution (The primary flow)
1. Navigate to `/pipeline/new`
2. Fill in the pipeline configuration form:
   - Domain: "Artificial Intelligence / Natural Language Processing"
   - Search queries: "transformer attention mechanisms recent advances"
   - Max gaps: 3
   - Generation rounds: 1
   - Ideas per round: 2
3. Submit the pipeline run
4. Watch the pipeline progress (stages advancing)
5. Wait for completion
6. Navigate to run detail page `/runs/{id}`
7. Verify: ideas generated, gaps found, proposals created
8. Take screenshots at each stage

### Journey 2: Idea Exploration
1. Navigate to `/ideas`
2. Browse the ideas list (verify pagination, search, filters)
3. Click on an idea → `/ideas/{id}`
4. Verify: idea detail renders with title, description, scores, source gaps
5. Submit feedback on the idea (star rating)
6. Take screenshots

### Journey 3: Gap Analysis
1. Navigate to `/gaps`
2. Browse gaps (verify search, filter, sort)
3. Click on a gap → `/gaps/{id}`
4. Verify: gap detail with truth values, cluster membership, feedback form
5. Submit feedback (star rating + notes)
6. Click on the Clusters tab
7. Take screenshots

### Journey 4: Global Search (Ctrl+K)
1. Press Ctrl+K on any page
2. Type "transformer"
3. Verify search results appear grouped by type
4. Click a result → verify navigation
5. Take screenshots

### Journey 5: Knowledge Graph
1. Navigate to `/knowledge-graph`
2. Verify graph renders (SVG canvas)
3. Click on an entity → verify detail panel
4. Take screenshots

### Additional Checks
- **Notification bell**: Verify it renders in header with badge
- **Language switcher**: Switch to 中文, verify Chinese text, switch to Español, switch back to English
- **Dark mode toggle**: If available, verify theme switching
- **Settings page**: Verify all 227+ config parameters render
- **Mobile responsiveness**: Resize browser to 375px width, verify layout adapts

### Deliverable
- `sessions/260501-ivory-wolf/data/ux_e2e_journey_report.md` — Full journey documentation with screenshots

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| Backend starts and responds on :8000 | Health check returns 200 |
| Frontend starts and responds on :3000 | Homepage loads |
| All 20 pages render without crash | Screenshot evidence |
| Pipeline run completes end-to-end | Ideas + gaps + proposals generated |
| Ideas browser shows results | Screenshot + API verification |
| Gap detail page renders truth values | Screenshot |
| Global search (Ctrl+K) works | Results appear |
| Knowledge graph renders | SVG visible |
| i18n switching works (en→zh→es→en) | Screenshots |
| Notification bell visible in header | Screenshot |

---

*BLUEPRINT — BATCH-54 — AIV Framework v5.2 — Lead Agent*
