# Phase 7 Master Roadmap — Elephant Rock Research Platform

**Generated**: 2026-05-07
**Lead**: ivory-wolf
**Framework**: AIV v5.3
**Test Baseline**: 2,152
**Previous Phase**: Phase 6 (BATCH-76→BATCH-100, ALL CLOSED)

---

## Phase 7 Overview

Phase 6 built 26 new modules as standalone components. Phase 7 **integrates them into the live pipeline** and delivers the remaining high-value additions from the master list.

### Goals
1. **Wire Phase 6 modules into the orchestrator** — SoulLoader, KnowledgeLibrary, ErrorKnowledgeStore, JournalWriter, ContextManager, ConcurrencyManager, PlanningAgent, HealthMonitor, CostTracker, AntiFabricationGuard, RelevanceFilter, MultiSourceSearcher
2. **Deliver remaining Tier 4 items** — Budget/Time Controls, Proposal Versioning, Domain Prompts, Dark Mode, Keyboard Shortcuts, Email Notifications
3. **End-to-end validation** — Run the full pipeline with all Phase 7 integrations enabled

---

## Phase 7A — Pipeline Integration (BATCH-101→BATCH-104)

### BATCH-101: Wire Soul + Context + Journal into Orchestrator
**Depends on**: BATCH-100 | **Tasks**: 3 | **Priority**: Critical

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | Inject SoulLoader into all LLM prompt construction | orchestrator.py, stages.py |
| 02 | Wire JournalWriter into PipelineOrchestrator run lifecycle | orchestrator.py |
| 03 | Wire ContextManager into stage prompt assembly | orchestrator.py, stages.py |

### BATCH-102: Wire Knowledge + Error Learning into Pipeline
**Depends on**: BATCH-101 | **Tasks**: 3 | **Priority**: Critical

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | LibraryIndexer runs after pipeline completes, indexes results | orchestrator.py |
| 02 | KnowledgeLibrary queried before literature search | orchestrator.py, search_service.py |
| 03 | ErrorKnowledgeStore records quality failures | gap_analyzer.py, proposal_synthesizer.py |

### BATCH-103: Wire Health + Cost + Planning into Pipeline
**Depends on**: BATCH-101 | **Tasks**: 3 | **Priority**: High

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | HealthMonitor runs at pipeline start, skips unhealthy sources | orchestrator.py |
| 02 | CostTracker records every LLM call's token usage | provider_factory.py |
| 03 | PlanningAgent generates pre-execution plan, exposed via API | orchestrator.py, pipeline.py routes |

### BATCH-104: Wire MultiSource + Relevance + Anti-Fabrication
**Depends on**: BATCH-102 | **Tasks**: 3 | **Priority**: High

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | MultiSourceSearcher replaces single-source search in orchestrator | orchestrator.py |
| 02 | RelevanceFilter applied after search, before gap analysis | orchestrator.py |
| 03 | AntiFabricationGuard checks proposals before export | orchestrator.py, stages.py |

---

## Phase 7B — Remaining Tier 4 Polish (BATCH-105→BATCH-108)

### BATCH-105: Budget/Time Controls + Domain Prompts
**Tasks**: 3

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | max_time and max_cost params in PipelineRunRequest | schemas.py, orchestrator.py |
| 02 | Pipeline degrades gracefully when approaching limits | orchestrator.py, watchdog.py |
| 03 | Domain-specific prompt templates (CS, bio, social science) | backend/pipeline/prompts/ |

### BATCH-106: Proposal Versioning + Diffing
**Tasks**: 2

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | ProposalVersion model + CRUD | models.py, crud.py |
| 02 | Diff endpoint returns text diff between versions | pipeline.py routes |

### BATCH-107: Frontend Polish — Dark Mode + Keyboard Shortcuts
**Tasks**: 2

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | Dark mode toggle with persistence | App.tsx, settings-context.tsx |
| 02 | Keyboard shortcuts (j/k navigation, / search, ? help) | hooks/useKeyboard.ts |

### BATCH-108: Notifications + Export Integrations
**Tasks**: 2

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | Notification system (in-app + optional webhook) | backend/pipeline/notifications/ |
| 02 | Markdown file export (download .md + .bib) | export_service.py, frontend |

---

## Phase 7C — End-to-End Validation (BATCH-109→BATCH-110)

### BATCH-109: Full Integration Test Suite
**Tasks**: 2

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | Integration test: full pipeline with all Phase 7 modules active | tests/integration/ |
| 02 | Performance test: verify no regressions from Phase 6/7 integration | tests/integration/ |

### BATCH-110: Phase 7 Close + Completion Report
**Tasks**: 2

| TASK | Description | Files |
|:-----|:------------|:------|
| 01 | Update STATE.md, CHANGELOG.md, SKILL.md | docs/aiv/ |
| 02 | Generate Phase 7 Completion Report | sessions/ |

---

## Summary

| Sub-Phase | Batches | Est. Tests | Focus |
|:----------|:--------|:-----------|:------|
| **7A Integration** | B101-104 | 40 | Wire Phase 6 into live pipeline |
| **7B Polish** | B105-108 | 30 | Budget, versioning, dark mode, notifications |
| **7C Validation** | B109-110 | 15 | Integration tests + completion |
| **TOTAL** | **10** | **~85** | |

**Expected test count at Phase 7 close: ~2,237**
