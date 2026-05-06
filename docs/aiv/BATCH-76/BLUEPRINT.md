BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-76
Blueprint Version:        1.1
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-06
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          SEQUENTIAL

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Create a pluggable strategy architecture that allows the pipeline
to run in different modes (fast_scan, deep_research, academic_proposal,
literature_review) by selecting which stages execute and with what
parameters.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Define a PipelineStrategy enum with at least 4 strategies
  - Each strategy specifies: stages to run, stage parameters, timeouts
  - Strategy is selectable at pipeline start via API + frontend
  - Current pipeline becomes the "deep_research" strategy
  - Orchestrator reads strategy config and skips/configures stages accordingly

What the code MUST NOT do:
  - Must NOT change existing deep_research pipeline behavior
  - Must NOT remove any existing pipeline stages
  - Must NOT modify the database schema

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m ruff check backend/ && python -m pytest --co -q

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: The deep_research strategy MUST produce identical results to
         the current pipeline. No behavioral change for existing runs.
  HB-02: Strategy selection MUST be optional. If no strategy is specified,
         deep_research is the default. Backward compatibility required.
  HB-03: No new database migrations. Strategy config is stored in the
         pipeline_runs table as a JSON text column.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
  # New file: backend/pipeline/strategies/models.py
  class PipelineStrategy(str, Enum):
      FAST_SCAN = "fast_scan"
      DEEP_RESEARCH = "deep_research"
      ACADEMIC_PROPOSAL = "academic_proposal"
      LITERATURE_REVIEW = "literature_review"

  @dataclass
  class StageConfig:
      enabled: bool = True
      timeout: float = 300.0
      params: dict = field(default_factory=dict)

  @dataclass
  class StrategyConfig:
      name: PipelineStrategy
      stages: dict[str, StageConfig]
      max_total_time: float = 1800.0
      description: str = ""

  # New file: backend/pipeline/strategies/registry.py
  class StrategyRegistry:
      def get(name: str) -> StrategyConfig
      def register(name: str, config: StrategyConfig) -> None
      def list_all() -> list[StrategyConfig]

  # Modified: backend/pipeline/orchestrator.py
  # - Accept strategy param in PipelineOrchestrator.__init__
  # - Skip disabled stages, pass stage-specific params
  # - Default to "deep_research" if not specified

  # Modified: backend/api/routes/pipeline.py
  # - Accept "strategy" field in POST /pipeline/start

  # Modified: backend/api/schemas.py
  # - Add strategy field to PipelineStartRequest

  # Modified: frontend/src/pages/pipeline-new.tsx
  # - Add strategy selector dropdown

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  - Strategy selection is user-controlled via API parameter
  - Default strategy (deep_research) requires no user action
  - Strategy configs are immutable during a pipeline run
  - Only the Lead may add new strategy definitions

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: BATCH-75 (current pipeline architecture)
  Required by: BATCH-77, BATCH-78, BATCH-80, BATCH-82, BATCH-95

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-06
  Batches since update:    0 (BATCH-75 was last update)
  Reconciliation audit:    [x] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,901 existing tests
  Expected delta (all Tasks):      +21 new tests (TASK-01: 8, TASK-02: 8, TASK-03: 5)
  Expected total at Batch close:   1,922

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-76/TASK-01 — Strategy Models + Registry
  Priority:          Critical
  Description:       Create the PipelineStrategy enum, StageConfig and
                     StrategyConfig dataclasses, and StrategyRegistry class.
                     Pre-register all 4 strategies with correct stage configs.
  Files in scope:
    - backend/pipeline/strategies/__init__.py (NEW)
    - backend/pipeline/strategies/models.py (NEW)
    - backend/pipeline/strategies/registry.py (NEW)
    - backend/pipeline/strategies/presets.py (NEW)
  Depends on:        None
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-76-01-01 | unit | StrategyRegistry returns correct StrategyConfig for each known strategy name | Registry returns None or raises for unknown strategy | Remove a strategy from registry, assert get() raises ValueError | assert registry.get("deep_research").name == PipelineStrategy.DEEP_RESEARCH |
    | TEST-76-01-02 | unit | All 4 strategies pre-registered | New strategy not found if presets not loaded | Skip calling register_presets(), assert list_all() is empty | assert len(registry.list_all()) == 4 |
    | TEST-76-01-03 | unit | StageConfig defaults to enabled=True, timeout=300.0 | Wrong defaults cause pipeline to skip stages | Change default enabled to False, assert stage is disabled | assert StageConfig().enabled is True AND StageConfig().timeout == 300.0 |
    | TEST-76-01-04 | unit | StrategyConfig.stages maps actual _STAGE_ORDER stage names | Empty stages dict causes KeyError during pipeline run | Set stages={}, assert accessing stages["ingestion"] raises KeyError | assert "ingestion" in config.stages for deep_research |
    | TEST-76-01-05 | unit | StrategyConfig serialization round-trips via to_dict/from_dict | JSON serialization fails with non-serializable fields | Add a lambda to StageConfig.params, assert json.dumps raises TypeError | assert StrategyConfig.from_dict(config.to_dict()).name == config.name |
    | TEST-76-01-06 | unit | Custom strategy can be registered and retrieved | Custom strategies silently overwritten | Register same name twice, assert second overwrites first | assert registry.get("custom").description == "custom test" |
    | TEST-76-01-07 | unit | fast_scan disables idea_generation, novelty_checking, mechanical_metrics stages | fast_scan runs expensive stages, making it slow | Check fast_scan config, assert idea_generation StageConfig.enabled is False | assert not fast_scan.stages["idea_generation"].enabled |
    | TEST-76-01-08 | error | Registry raises ValueError for invalid strategy names | Invalid name silently returns default config | Call registry.get("nonexistent"), assert raises ValueError | with pytest.raises(ValueError): registry.get("nonexistent") |
  Acceptance Criteria:
    AC-01-01: PipelineStrategy enum has 4 members
    AC-01-02: StrategyRegistry.get() returns StrategyConfig for known names, ValueError for unknown
    AC-01-03: All 4 presets registered at import time
    AC-01-04: fast_scan disables idea_generation, novelty_checking, mechanical_metrics
    AC-01-05: deep_research enables all 9 stages
    AC-01-06: StrategyConfig is JSON-serializable
  Traceability:
    AC-01-01 → TEST-76-01-02
    AC-01-02 → TEST-76-01-01, TEST-76-01-08
    AC-01-03 → TEST-76-01-02
    AC-01-04 → TEST-76-01-07
    AC-01-05 → TEST-76-01-04
    AC-01-06 → TEST-76-01-05

TASK-02: BATCH-76/TASK-02 — Orchestrator Strategy Integration
  Priority:          Critical
  Description:       Modify PipelineOrchestrator to accept a strategy parameter,
                     read stage configs, skip disabled stages, and pass stage-specific
                     params to each stage.
  Files in scope:
    - backend/pipeline/orchestrator.py (MODIFY)
    - backend/pipeline/strategies/__init__.py (MODIFY — exports)
  Depends on:        TASK-01
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-76-02-01 | unit | PipelineOrchestrator accepts strategy param | Orchestrator ignores strategy | Remove strategy param, assert default is deep_research | assert orchestrator.strategy_name == "deep_research" |
    | TEST-76-02-02 | integration | deep_research runs all 9 stages in same order as current pipeline | Stage order changes when strategy applied | Compare stage execution list with/without strategy param | assert stages_executed == ["literature_search","ingestion","gap_analysis","idea_generation","novelty_checking","feasibility_scoring","mechanical_metrics","proposal_synthesis","export"] |
    | TEST-76-02-03 | unit | fast_scan skips idea_generation, novelty_checking, mechanical_metrics | fast_scan still runs all stages | Set strategy to fast_scan, assert idea_generation not executed | assert "idea_generation" not in stages_executed |
    | TEST-76-02-04 | unit | Stage params forwarded from strategy config | Stage uses defaults ignoring strategy | Set param in strategy, assert stage received it | assert stage.timeout == strategy_config.stages["ingestion"].timeout |
    | TEST-76-02-05 | integration | strategy=None defaults to deep_research with all 9 stages | Missing strategy skips stages | Pass strategy=None, assert all stages execute | assert len(stages_executed) == 9 |
    | TEST-76-02-06 | error | Invalid strategy raises ValueError before pipeline starts | Pipeline starts with wrong config | Pass strategy="invalid", assert ValueError | with pytest.raises(ValueError): create orchestrator with strategy="invalid" |
    | TEST-76-02-07 | unit | Strategy timeout overrides default stage timeout | Stage uses default ignoring strategy | Set strategy timeout to 60s, assert stage timeout is 60s | assert stage.timeout == 60.0 |
    | TEST-76-02-08 | integration | deep_research with strategy produces identical stage list to current pipeline (HB-01) | Strategy param changes pipeline behavior | Run pipeline without strategy and with strategy="deep_research", compare stage lists | assert stages_no_strategy == stages_deep_research |
  Acceptance Criteria:
    AC-02-01: PipelineOrchestrator accepts strategy parameter
    AC-02-02: deep_research produces identical stage execution to current pipeline (HB-01)
    AC-02-03: fast_scan skips idea_generation, novelty_checking, mechanical_metrics
    AC-02-04: strategy=None defaults to "deep_research"
    AC-02-05: Stage-specific params forwarded correctly
    AC-02-06: Invalid strategy raises ValueError before any stage runs
  Traceability:
    AC-02-01 → TEST-76-02-01
    AC-02-02 → TEST-76-02-02, TEST-76-02-05, TEST-76-02-08
    AC-02-03 → TEST-76-02-03
    AC-02-04 → TEST-76-02-01, TEST-76-02-05
    AC-02-05 → TEST-76-02-04, TEST-76-02-07
    AC-02-06 → TEST-76-02-06

TASK-03: BATCH-76/TASK-03 — API + Frontend Strategy Selection
  Priority:          High
  Description:       Add strategy field to POST /pipeline/start API endpoint.
                     Add strategy selector dropdown to pipeline-new.tsx.
  Files in scope:
    - backend/api/routes/pipeline.py (MODIFY)
    - backend/api/schemas.py (MODIFY)
    - frontend/src/pages/pipeline-new.tsx (MODIFY)
    - frontend/src/pages/run-detail.tsx (MODIFY)
    - frontend/src/api/types.ts (MODIFY)
  Depends on:        TASK-02
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-76-03-01 | unit | POST /pipeline/start accepts strategy field | API rejects strategy field | Send POST with strategy="fast_scan", assert 200 | assert response.status_code == 200 |
    | TEST-76-03-02 | unit | POST defaults strategy to deep_research when omitted | API crashes when strategy missing | Send POST without strategy, assert default | assert response.json()["strategy"] == "deep_research" |
    | TEST-76-03-03 | unit | GET /pipeline/runs returns strategy field | Strategy field missing from response | Call GET /runs, assert strategy key present | assert "strategy" in response.json() |
    | TEST-76-03-04 | error | Invalid strategy returns 400 | Invalid strategy accepted | Send strategy="bad", assert 400 | assert response.status_code == 400 |
    | TEST-76-03-05 | unit | PipelineStartRequest validates strategy enum | Invalid string passes validation | Set strategy="hack", assert ValidationError | with pytest.raises(ValidationError): PipelineStartRequest(strategy="hack") |
  Acceptance Criteria:
    AC-03-01: POST /pipeline/start accepts optional "strategy" field
    AC-03-02: Strategy defaults to "deep_research" when omitted
    AC-03-03: Invalid strategy returns HTTP 400
    AC-03-04: Pipeline run response includes strategy name
    AC-03-05: Frontend has strategy dropdown with 4 options
  Traceability:
    AC-03-01 → TEST-76-03-01
    AC-03-02 → TEST-76-03-02
    AC-03-03 → TEST-76-03-04
    AC-03-04 → TEST-76-03-03
    AC-03-05 → manual (frontend)

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All 4 pipeline strategies are selectable via API and frontend
  BAC-02: deep_research strategy produces identical output to pre-BATCH-76 pipeline
  BAC-03: CHANGELOG.md updated with BATCH-76 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-76/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-76-2026-05-06
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 (CHK-14) → Action: Corrected test baseline from +45 to +21 (8+8+5).
                        Expected total updated to 1,922.
  FLAG-02 (CHK-17) → Action: CRITICAL FIX. Replaced fictional stage names
                        ("tree_search", "knowledge") with actual _STAGE_ORDER names
                        ("idea_generation", "novelty_checking", "mechanical_metrics").
                        All test assertions and ACs updated to use real stage names.
  FLAG-03 (CHK-23) → Action: Added TEST-76-02-08 integration test that explicitly
                        verifies HB-01 by comparing stage lists between no-strategy
                        and strategy="deep_research" runs. Added to TASK-02.
  FLAG-04 (CHK-20) → Action: FALSE POSITIVE. Verified pipeline-new.tsx EXISTS on
                        filesystem (14,370 bytes, dated 2026-05-02). No change needed.

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-06

═══════════════════════════════════════════════════════════
