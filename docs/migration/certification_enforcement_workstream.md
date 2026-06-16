# Certification & Gateway Enforcement — Deferred Workstream

**Created**: 2026-06-16
**Status**: Deferred (tracked, not blocking)
**Baseline**: 14 known failures, all in one coherent area

## Scope

The gateway enforces that only certified models run specific pipeline stages.
Without certified model records, every enforcement path degrades gracefully
instead of executing. This is a pre-existing defect chain that predates the
refactoring.

### Failure Categories (13 tests)

#### 1. Phase 2 Enforcement — No Certified Models (5 tests)

```
test_phase2_enforcement.py::TestIdeaGenerationEnforcement::test_idea_generation_enforced
test_phase2_enforcement.py::TestIdeaGenerationEnforcement::test_idea_generation_routed_model_certified
test_phase2_enforcement.py::TestIdeaGenerationEnforcement::test_idea_generation_strategy_is_valid
test_phase2_enforcement.py::TestPhase2RoutingContract::test_model_certified_for_idea_generation
test_phase2_enforcement.py::TestFeasibilityScoringEnforcement::test_feasibility_scoring_enforced
```

**Root cause**: Gateway checks `CertificationRecord` table for certified models
for each stage. No records exist → `degraded=True` → test assertions fail.

**Fix path**: Generate certification records by running the certification CLI
against eval cases, or seed test fixtures with mock certification records.

#### 2. Enforcement Integration — Gateway Routing (4 tests)

```
test_enforcement_integration.py::TestExtractJsonWithLlmRepair::test_mechanical_fails_llm_repair_succeeds
test_enforcement_integration.py::TestExtractJsonWithLlmRepair::test_schema_validation_on_repaired_output
test_enforcement_integration.py::TestExtractJsonWithLlmRepair::test_enforcement_fields_captured
test_enforcement_integration.py::TestQueryGenerationIntegration::test_query_generation_enforced
test_enforcement_integration.py::TestQueryGenerationIntegration::test_llm_returns_valid_queries
```

**Root cause**: Same as above — gateway degrades when no certified models exist.
Tests expect `degraded=False` and `enforced=True`.

**Fix path**: Same as Phase 2 enforcement — need certification records.

#### 3. Staged Enforcement — Gateway Routing (2 tests)

```
test_staged_enforcement.py::TestLLMRepairService::test_repair_routes_through_gateway
test_staged_enforcement.py::TestLLMQueryGenerator::test_query_gen_routes_through_gateway
```

**Root cause**: LLM repair and query generation services route through the
gateway, which degrades without certified models.

**Fix path**: Same — certification records needed.

#### 4. Certification CLI Runner (1 test)

```
test_model_certification/test_runner.py::TestRunner::test_cli_certify_produces_summary
```

**Root cause**: CLI output format mismatch — the test expects a specific
summary format that doesn't match the current CLI implementation.

**Fix path**: Align CLI output with test expectations, or update test to
match current CLI contract.

#### 5. Phase 2 Enforcement — Routed Model Certified (1 test)

Counted under category 1 above.

## Resolution Strategy

### Option A: Seed Certification Records (Quick Fix)

1. Run certification CLI against eval cases with a known model
2. Verify `CertificationRecord` table populated
3. Re-run all 13 tests

### Option B: Test Fixture Mocking (Isolation Fix)

1. Create conftest fixture that seeds mock certification records
2. Each test class gets certified models for the stages it tests
3. Does not require running the actual certification pipeline

### Option C: Fix Certification Pipeline (Proper Fix)

1. Debug the certification CLI output format (test_runner failure)
2. Run full certification against eval cases
3. Verify gateway enforcement works end-to-end
4. Add integration test: certification → enforcement → execution

## Dependencies

- Eval cases are present: `data/model_certification/eval_cases/` (16 YAML files)
- Candidates directory exists: `data/model_certification/candidates/`
- Gateway code is functional (tested in refactoring Phase 5)
- The only missing piece is certification records in the DB
