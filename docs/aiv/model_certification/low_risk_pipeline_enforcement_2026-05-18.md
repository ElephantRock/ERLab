# Low-Risk Pipeline Enforcement Integration Report

**Date:** 2026-05-18
**Run ID:** `dry_run_20260518_114556`
**Model:** qwen/qwen3-4b-2507 (LM Studio, 65K context)
**Mode:** enforce (per-stage allowlist: repair, query_generation)

## 1. Executive Summary

**VERDICT: ALL PASS** — 10/10 pass criteria met.

The LLMRepairService and LLMQueryGenerator are now wired into the real ERLab pipeline execution paths. Query generation was exercised naturally during the pipeline run with enforcement applied. Repair enforcement was not naturally triggered (structured output ensures valid JSON) but is covered by targeted tests.

## 2. Configuration

```yaml
smart_router:
  enabled: true
  mode: enforce
  require_certified_models: true
  enforced_stages:
    - repair
    - query_generation
```

### Non-Enforced Stages (dry-run/legacy only)

| Stage | Risk Level | Reason |
|-------|-----------|--------|
| evidence_table | medium | citation_fabrication_rate=0.268 |
| citation_audit | critical | depends on evidence_table |
| adversarial_review | high | fab=0.522, unsup=0.862 |
| paper_synthesis | high | v0.2 cap at limited_use |
| proposal_synthesis | high | grounding hard gate failure |
| idea_generation | medium | not yet promoted to enforcement |
| gap_analysis | — | no direct LLM routing contract |
| feasibility_scoring | medium | maps to idea_generation contract |
| proposal_deepening | medium | not in enforced list |
| ingestion | low | maps to literature_search contract |

## 3. Integration Points

### 3.1 JSON Repair Integration (Phase 2)

**File:** `backend/pipeline/utils/json_extraction.py`

```python
async def extract_json_with_llm_repair(
    text, gateway=None, *, schema=None, schema_hint="",
    run_id="", strict=False
) -> tuple[dict | list, RepairLog]:
```

**Flow:**
```
raw LLM output
  → extract_json (mechanical: direct, fence, brackets)
  → if mechanical succeeds: return (method=mechanical)
  → if mechanical fails AND gateway:
      → LLMRepairService.repair_json (stage=repair, enforced)
      → schema validation on repaired output
      → return (method=llm_repair) or fail
  → if all fail: return {} with RepairLog(method=failed)
```

**Key guarantees:**
- Mechanical repair always tried first (no unnecessary LLM calls)
- Schema validation runs on repaired output (not bypassed)
- Original invalid JSON preserved in `RepairLog.original_invalid_json`
- Degraded repair returns `{}` explicitly, never fake data
- `repair_method` tracked: `"mechanical"` | `"llm_repair"` | `"failed"`

**RepairLog fields:**
- `repair_attempted`, `repair_method`, `enforcement_applied`
- `routed_model`, `actual_model`, `schema_valid_after_repair`
- `degraded`, `repair_error`, `original_invalid_json`
- `llm_repair_log_fields` (enforcement details dict)

### 3.2 Literature Search Query Expansion (Phase 3)

**File:** `backend/pipeline/stages.py` — `LiteratureSearchStage`

```python
class LiteratureSearchStage(PipelineStage):
    def __init__(self, search, hooks, gateway=None):
        ...
```

**Flow:**
```
user topic / search_queries
  → original queries from ctx.search_queries
  → if self._gateway:
      → LLMQueryGenerator.generate_queries (stage=query_generation, enforced)
      → filter: len >= 5, len <= 200, not empty
      → deduplicate against original (case-insensitive)
      → add accepted queries
  → run PubMed/CrossRef/OpenAlex searches
  → continue existing retrieval flow
```

**Key guarantees:**
- Query expansion is non-blocking — if degraded, uses original queries
- Generated queries validated: no empty, short (<5), long (>200), or duplicates
- Literature search itself remains tool-only (not enforced)
- Gateway injected from orchestrator via constructor

### 3.3 Orchestrator Wiring

**File:** `backend/pipeline/orchestrator/_orchestrator.py`

```python
LiteratureSearchStage(
    self._services.search, self._services.hooks,
    gateway=self._gateway  # NEW: pass gateway for query expansion
),
```

## 4. Full Pipeline Validation Run

| Metric | Value |
|--------|-------|
| Run ID | dry_run_20260518_114456 |
| Pipeline status | COMPLETED |
| Total LLM calls | 155 |
| Enforced calls | 1 (query_generation) |
| Dry-run only calls | 154 |
| Degraded calls | 0 |
| Router exceptions | 0 |
| Elapsed | ~870s |

### Query Generation Results

| Field | Value |
|-------|-------|
| query_generation_attempted | True |
| Generated queries | 3 |
| Accepted queries | 3 |
| Rejected queries | 0 |
| enforcement_applied | True |
| routed_model | qwen3-4b-2507 |
| degraded | False |

**Log line:**
```
[ENFORCE] stage=query_generation model=qwen3-4b-2507 strategy=single_call confidence=0.68
LLM query expansion: 3 generated, 3 accepted, 0 rejected (enforced=True)
```

### Routing Decisions by Stage

| Stage | Calls | Mode | Strategy |
|-------|-------|------|----------|
| adversarial_review | 54 | DRY-RUN | compressed_review_packet |
| proposal_synthesis | 37 | DRY-RUN | single_call |
| ingestion | 24 | DRY-RUN | single_call |
| feasibility_scoring | 20 | DRY-RUN | single_call |
| paper_synthesis | 16 | DRY-RUN | section_wise |
| proposal_deepening | 2 | DRY-RUN | single_call |
| idea_generation | 1 | DRY-RUN | single_call |
| **query_generation** | **1** | **ENFORCE** | **single_call** |

### Repair Results

Repair was NOT naturally triggered during the pipeline run. The structured output path with `response_format json_schema` ensures 100% schema validity. Repair coverage is provided by targeted tests.

## 5. Pass Criteria

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | Pipeline completes | ✅ PASS | 155 LLM calls, completed in ~870s |
| 2 | At least one query_generation call naturally exercised | ✅ PASS | 1 enforced query_generation call |
| 3 | Repair enforcement exercised or covered by tests | ✅ PASS | 8 targeted tests (not needed in pipeline) |
| 4 | No uncertified model for enforced stages | ✅ PASS | All enforced calls use qwen3-4b-2507 (certified) |
| 5 | Non-enforced stages remain dry-run/legacy | ✅ PASS | 154 DRY-RUN calls, 0 enforcement |
| 6 | No router exceptions | ✅ PASS | No exceptions logged |
| 7 | Query-generation degradation falls back to original | ✅ PASS | Tested in test_degraded_falls_back_to_original |
| 8 | LLM repair degradation returns explicit failure | ✅ PASS | Tested in test_degraded_repair_returns_failure |
| 9 | No increase in critical contract violations | ✅ PASS | 0 new violations |
| 10 | Final report written | ✅ PASS | This report |

## 6. Test Suite

| Test Suite | Tests | Status |
|-----------|-------|--------|
| test_enforcement_integration.py | 19 | ✅ ALL PASS |
| test_staged_enforcement.py | 17 | ✅ ALL PASS |
| test_routing/ | 59 | ✅ ALL PASS |
| test_gateway.py | 19 | ✅ ALL PASS |
| test_structured_synthesis.py | 17 | ✅ ALL PASS |
| test_model_certification/ | 154 | ✅ ALL PASS |

### New Integration Tests (19 total)

**Extract JSON with LLM Repair (8 tests):**
- Mechanical succeeds → LLM not called
- Mechanical fails → LLM repair with enforcement_applied=true
- Schema validation on repaired output
- Degraded repair returns empty (not fake)
- No gateway → skip LLM repair
- Strict mode raises on total failure
- Original JSON preserved in log
- Enforcement fields captured in RepairLog

**Query Generation (3 tests):**
- Query generation enforced through gateway
- LLM returns valid queries
- Degraded falls back to empty list

**Literature Search Filtering (4 tests):**
- Short queries rejected
- Long queries rejected
- Empty queries rejected
- Duplicate queries rejected

**Routing Contract (2 tests):**
- Only repair + query_generation enforced
- High-risk stages remain dry-run

**RepairLog (2 tests):**
- Default values
- Fields set correctly

## 7. Retrieval Impact

Query generation added 3 additional search queries to the literature search stage. This expands coverage beyond the user-provided queries.

**Before query expansion:**
- `tool use bottleneck LLM agent architectures`
- `function calling limitations large language models`
- `agentic AI tool selection overhead`

**After query expansion:**
- Original 3 queries + 3 LLM-generated queries = 6 total
- All 3 generated queries accepted (no rejections)
- No duplicates with original queries

## 8. Commit Chain

```
1ad8086  Staged enforcement framework
e35f5d0  Targeted enforcement exercise (prove enforcement works)
af85140  Integrate into real pipeline paths (this commit)
```

## 9. Recommendation for Next Steps

### Safe to enforce next (Phase 2 candidates):
1. **`idea_generation`** — limited_use, no grounding requirement, high call count
2. **`feasibility_scoring`** — maps to idea_generation contract, no grounding

### Pre-conditions for Phase 2:
1. Run targeted idea_generation enforcement exercise (similar to repair/query)
2. Monitor idea quality under enforcement vs legacy
3. Verify no degradation in idea diversity metrics

### NOT ready for enforcement:
- ❌ evidence_table — citation_fabrication_rate=0.268
- ❌ adversarial_review — citation_fabrication_rate=0.522
- ❌ paper_synthesis — v0.2 cap at limited_use
- ❌ proposal_synthesis — grounding hard gate failure
- ❌ citation_audit — depends on evidence_table

### Prerequisites for grounded stage enforcement:
1. Larger model certified (qwen2.5-14b-instruct or better)
2. Multi-model 65K dry-run clean
3. Grounding gates pass (fab < 0.05, support > 0.70)
4. Anthropic API key refreshed for hybrid local/cloud routing
