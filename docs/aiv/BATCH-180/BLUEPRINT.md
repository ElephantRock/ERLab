BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-180
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          Craft Agent (Lead)
Date Issued:              2026-05-13
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Replace the tangled orchestrator config layer with a single YAML config
file, a structured JSON stage logger, and a DAG runner that reads the YAML
and executes stages in declared order. The old orchestrator is NOT deleted
—it remains untouched until the new system is verified end-to-end.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Define pipeline config (models, budgets, search, strategies) in a single YAML file
  - Provide a DAGRunner that reads the YAML and builds a stage execution plan
  - Provide a StageLogger that writes one JSON entry per stage execution
  - Provide a dry-run mode that prints every stage decision without executing
  - Each stage logs its inputs (counts), outputs (counts), config snapshot, and elapsed time
  - Existing stage implementations are NOT modified — they are wrapped by the DAG

What the code MUST NOT do:
  - Must NOT delete or modify backend/pipeline/orchestrator.py
  - Must NOT modify any existing stage implementation files
  - Must NOT change any API routes or frontend code
  - Must NOT read config from environment variables (YAML is the single source)
  - Must NOT use inheritance — stages are functions, not classes

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m ruff check backend/pipeline/dag/ --select E,F,W

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: The YAML file MUST be the only source of truth for pipeline config.
         No env vars, no .env overrides, no strategy presets, no gate booleans.
         The DAGRunner reads YAML and nothing else.

  HB-02: Existing orchestrator and stage files MUST NOT be modified.
         New code lives in backend/pipeline/dag/ only.

  HB-03: Every stage execution MUST produce exactly one JSON log entry
         with: run_id, stage, timestamp, event, elapsed_s, config, inputs, outputs, error.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

pipeline.yaml structure:
```yaml
models:
  thinking:  { provider, model, base_url }
  generation: { provider, model, base_url }
  embedding: { provider, model, dimension, base_url }
  reranker:  { strategy, model, base_url }

infrastructure:
  chroma_dir: str
  bm25_dir: str
  database: str
  server: { host, port }

budgets:
  max_papers: int
  max_gaps: int
  max_ideas: int
  max_abstract_chars: int
  trim_top_k: int
  stage_timeout: int
  total_timeout: int

search:
  sources: list[str]
  queries_per_source: int
  citation_explore: bool

strategies:
  <name>:
    stages: list[str]
    description: str
```

Stage log entry:
```json
{
  "run_id": "str",
  "stage": "str",
  "timestamp": "ISO 8601",
  "event": "start | complete | error",
  "elapsed_s": "float",
  "config": "dict (snapshot at execution time)",
  "inputs": "dict (counts: papers, gaps, ideas, proposals)",
  "outputs": "dict (counts + summary)",
  "error": "str | null"
}
```

StageContext:
```python
@dataclass
class StageContext:
    domain: str
    papers: list          # from literature_search
    gaps: list            # from gap_analysis
    ideas: list           # from idea_generation
    proposals: dict       # from proposal_synthesis (keyed by idea index)
    novelty_reports: dict # from novelty_checking
    feasibility_reports: dict
    mechanical_metrics: dict
    config: dict          # read-only snapshot of pipeline.yaml
    run_id: str
    strategy: str
    log: StageLogger
```

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AUTH-01: YAML config is immutable during a pipeline run. Snapshot at start.
  AUTH-02: StageContext fields are append-only. Stages may add but not remove.
  AUTH-03: dry-run mode MUST NOT execute any stage. It only prints the plan.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  None — this is foundation layer. No prior batches needed.

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────

  State file exists:       [x] YES
  Last Updated:            2026-05-13
  Batches since update:    0 (just updated in BATCH-RAG-04)
  Reconciliation audit:    [x] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline at Blueprint issuance:  2765 existing tests
  Expected delta (all Tasks):      +18 new tests
  Expected total at Batch close:   2783

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-180/TASK-01
  Priority:          Critical
  Description:       Create pipeline.yaml config file and the ConfigLoader
                     that reads it and returns a validated dict.
  Files in scope:    backend/pipeline/dag/__init__.py (new)
                     backend/pipeline/dag/config.py (new)
                     backend/pipeline/dag/pipeline.yaml (new)
  Depends on:        None
  Required Tests:
    | Test ID          | Type | Behavior Verified                                      | Failure Mode                              | Falsified By                                       | Pass Criteria                                      |
    |:-----------------|:-----|:-------------------------------------------------------|:------------------------------------------|:---------------------------------------------------|:---------------------------------------------------|
    | TEST-180-01-01   | unit | ConfigLoader reads pipeline.yaml and returns dict      | YAML missing or malformed returns empty   | Delete YAML file — test fails with FileNotFoundError | assert config["models"]["thinking"]["provider"] exists |
    | TEST-180-01-02   | unit | ConfigLoader validates required fields present          | Missing field not caught                  | Remove budgets section from YAML — test fails      | assert raises ValueError with field name            |
    | TEST-180-01-03   | unit | ConfigLoader snapshots config (immutable copy)          | Mutation leaks between reads              | Modify returned dict, re-read — assert original unchanged | assert snapshot1 != snapshot2 after mutation       |
    | TEST-180-01-04   | unit | All 4 strategies present in config                     | Strategy missing from YAML                | Delete deep_research from YAML — test fails        | assert len(config["strategies"]) == 4              |
    | TEST-180-01-05   | unit | Each strategy has stages list and description           | Strategy missing stages field             | Remove stages from fast_scan — test fails           | assert "stages" in config["strategies"]["fast_scan"] |
    | TEST-180-01-06   | unit | ConfigLoader resolves relative paths to absolute        | Relative path breaks at runtime           | Pass relative path, assert output is absolute       | assert os.path.isabs(resolved)                     |
  Acceptance Criteria:
    AC-01-01: pipeline.yaml contains all 4 strategies with correct stage lists
    AC-01-02: ConfigLoader validates and returns immutable config snapshot
    AC-01-03: All 6 tests pass
  Traceability:
    AC-01-01 → TEST-180-01-04, TEST-180-01-05
    AC-01-02 → TEST-180-01-01, TEST-180-01-02, TEST-180-01-03
    AC-01-03 → TEST-180-01-01 through TEST-180-01-06

TASK-02: BATCH-180/TASK-02
  Priority:          Critical
  Description:       Create StageLogger that writes one JSON entry per stage
                     execution to a structured log file.
  Files in scope:    backend/pipeline/dag/stage_log.py (new)
  Depends on:        None
  Required Tests:
    | Test ID          | Type | Behavior Verified                                      | Failure Mode                              | Falsified By                                       | Pass Criteria                                      |
    |:-----------------|:-----|:-------------------------------------------------------|:------------------------------------------|:---------------------------------------------------|:---------------------------------------------------|
    | TEST-180-02-01   | unit | StageLogger writes JSON entry with all required fields  | Missing field breaks log consumer         | Remove a field from entry — test fails              | assert all(k in entry for k in required_fields)    |
    | TEST-180-02-02   | unit | StageLogger appends entries (not overwrites)            | Second log entry overwrites first         | Write 2 entries, read file — assert 2 lines        | assert len(entries) == 2                           |
    | TEST-180-02-03   | unit | StageLogger handles error entries correctly             | Error not captured in log                 | Call log_error, assert error field is populated     | assert entry["error"] is not None                  |
    | TEST-180-02-04   | unit | StageLogger creates log directory if missing            | Log write fails on fresh system           | Delete log dir, write entry — assert no exception   | assert log_dir.exists()                            |
    | TEST-180-02-05   | unit | StageLogger input/output counts are integers            | Non-int counts break metrics consumer     | Pass float count — assert converted to int          | assert isinstance(entry["inputs"]["papers_count"], int) |
  Acceptance Criteria:
    AC-02-01: StageLogger writes valid JSON with all 8 required fields
    AC-02-02: Multiple log entries accumulate (append, not overwrite)
    AC-02-03: All 5 tests pass
  Traceability:
    AC-02-01 → TEST-180-02-01, TEST-180-02-05
    AC-02-02 → TEST-180-02-02, TEST-180-02-04
    AC-02-03 → TEST-180-02-01 through TEST-180-02-05

TASK-03: BATCH-180/TASK-03
  Priority:          Critical
  Description:       Create DAGRunner with StageContext, STAGE_REGISTRY,
                     build_plan(), run_stage(), execute(), and dry_run().
  Files in scope:    backend/pipeline/dag/runner.py (new)
                     backend/pipeline/dag/context.py (new)
                     backend/pipeline/dag/registry.py (new)
  Depends on:        TASK-01, TASK-02
  Required Tests:
    | Test ID          | Type | Behavior Verified                                      | Failure Mode                              | Falsified By                                       | Pass Criteria                                      |
    |:-----------------|:-----|:-------------------------------------------------------|:------------------------------------------|:---------------------------------------------------|:---------------------------------------------------|
    | TEST-180-03-01   | unit | DAGRunner.build_plan returns correct stage list         | Wrong strategy returns wrong stages       | Request fast_scan — assert no idea_generation in list | assert "idea_generation" not in plan               |
    | TEST-180-03-02   | unit | DAGRunner.build_plan validates strategy name            | Unknown strategy returns empty list       | Request nonexistent strategy — assert raises        | assert raises ValueError                           |
    | TEST-180-03-03   | unit | DAGRunner.dry_run prints stage list without executing   | dry_run actually executes stages          | Add a stage that raises — assert no exception       | assert "dry_run" in output                         |
    | TEST-180-03-04   | unit | DAGRunner.dry_run prints model assignment per stage     | Model routing not visible in dry_run      | Remove model assignment — assert output missing     | assert "thinking" in dry_run_output                |
    | TEST-180-03-05   | unit | StageContext is immutable-in (config snapshot)          | Config mutation leaks across stages       | Modify ctx.config, assert original unchanged        | assert original_config != modified_config          |
    | TEST-180-03-06   | unit | StageContext tracks paper/gap/idea/proposal counts      | Counts wrong after stage execution        | Set ctx.papers = [...], assert ctx.paper_count == N | assert ctx.paper_count == expected                 |
    | TEST-180-03-07   | unit | STAGE_REGISTRY maps all 16 stage names                 | Missing stage breaks pipeline             | Remove entry — assert KeyError on lookup            | assert len(registry) >= 16                         |
  Acceptance Criteria:
    AC-03-01: DAGRunner builds correct plans for all 4 strategies
    AC-03-02: dry_run prints every stage with its model without executing
    AC-03-03: StageContext carries data between stages with append-only semantics
    AC-03-04: All 7 tests pass
  Traceability:
    AC-03-01 → TEST-180-03-01, TEST-180-03-02
    AC-03-02 → TEST-180-03-03, TEST-180-03-04
    AC-03-03 → TEST-180-03-05, TEST-180-03-06
    AC-03-04 → TEST-180-03-01 through TEST-180-03-07

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: pipeline.yaml is the single source of truth — no env vars or strategy presets needed
  BAC-02: DAGRunner dry_run deep_research "test" prints all stages with model assignments
  BAC-03: CHANGELOG.md updated with BATCH-180 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-180/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:       REVIEW-BATCH-180-2026-05-13
Review Cycle:             1
Lead Decision:            [x] ACCEPT

If ACCEPT WITH MODIFICATIONS:
  N/A — 0 flags raised.

If REJECT:
  N/A

Blueprint Version after response: 1.0
Lead Sign:                Craft Agent (Lead) — 2026-05-13 02:55

═══════════════════════════════════════════════════════════
