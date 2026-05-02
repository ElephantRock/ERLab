# BATCH-53 BLUEPRINT — Plugin SDK Docs + E2E Smoke Fix

**Lead Programmer:** Lead Agent  
**Date:** 2026-05-02  
**AIV Framework:** v5.1  
**Phase:** 6 — Documentation & Quality (FINAL BATCH)

---

## TASK-01: Plugin SDK Documentation

### Target Files (NEW)
- `docs/plugin-sdk.md` — Full Plugin SDK documentation
- `docs/examples/hello-plugin/plugin.json` — Plugin manifest example
- `docs/examples/hello-plugin/main.py` — Minimal plugin implementation

### Specification

Create comprehensive Plugin SDK documentation covering:
1. **Architecture overview** — Plugin system design, lifecycle
2. **Plugin manifest schema** — plugin.json format and required fields
3. **Hook system** — Available events (pipeline.start, pipeline.completed, gap.found, idea.generated, etc.)
4. **API reference** — CRUD operations, tool registration, config access
5. **Tutorial** — Step-by-step "Build your first plugin" with the hello-plugin example
6. **Security model** — Sandboxing, permissions, resource limits

Read the existing plugin infrastructure first:
- `backend/pipeline/plugins/` — Plugin loader and registry
- `backend/api/routes/plugins.py` — Plugin API endpoints
- `backend/pipeline/tools/registry.py` — Tool registration system

The docs should be written for an external developer audience.

---

## TASK-02: E2E Smoke Test Fix

### Target Files (MODIFY)
- Find the failing E2E test and fix it to use mock providers instead of live API keys

### Specification

1. Locate the failing E2E/smoke test
2. Replace any live API key dependencies with mock LLM providers
3. Ensure the test passes without `OPENAI_API_KEY` or any external service
4. Verify the complete test suite (1,819+) passes with zero failures

### Expected Outcome
- 0 failing tests across the entire suite
- No external service dependencies for any test

---

## Acceptance Criteria

| Criterion | Verification |
|:---|:---|
| `docs/plugin-sdk.md` exists with 6 sections | File check |
| `docs/examples/hello-plugin/` has manifest + code | File check |
| E2E smoke test fixed | pytest output |
| Zero test failures | pytest + vitest |
| All existing tests pass | Full suite run |

---

*BLUEPRINT — BATCH-53 — AIV Framework v5.1 — Lead Agent*
