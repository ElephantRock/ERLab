BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-75
Blueprint Version:        1.1
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-06
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Fix all 6 defects discovered during the first real end-to-end pipeline run
(commit `81d5c3f`), re-enable tree search (currently disabled via env var
workaround), and verify the pipeline completes with tree search active.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Convert IdeaCandidate → ResearchIdea in TreeSearchStage before assignment to PipelineResult
  - Guard persistence against IdeaCandidate objects missing domain/source_gap_ids fields
  - Deduplicate idea rows before DB insert in persist_ideas()
  - Store EnsembleReviewResult as dict (model_dump()) in proposal.sections
  - Retry arXiv 429 responses with exponential backoff (5→15→30s, max 3 retries)
  - Pipeline completes end-to-end with tree_of_thought_enabled=True

What the code MUST NOT do:
  - Modify IdeatorAgent.generate_ideas() return type (still returns list[IdeaCandidate])
  - Modify TreeSearchEngine.search() return type (still returns list[IdeaCandidate])
  - Modify ResearchIdea or IdeaCandidate model fields
  - Disable tree search as a "fix"
  - Change any existing test assertions unrelated to these defects

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m pytest backend/tests/ --co -q 2>/dev/null | tail -1
  (Compilation check — zero collection errors = clean)

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: TreeSearchStage.execute() MUST assign only list[ResearchIdea] to
         ctx.result.ideas — never raw IdeaCandidate objects. A runtime
         isinstance() check must assert this before assignment.
  HB-02: persist_ideas() MUST NOT raise AttributeError on any idea-like
         object — all field accesses MUST use getattr() with defaults.
  HB-03: persist_ideas() MUST NOT insert duplicate rows for the same
         (title, pipeline_run_id) pair within a single call.
  HB-04: proposal.sections["ensemble_review"] MUST be a plain dict
         (JSON-serializable) — never a Pydantic model instance.
  HB-05: arXiv HTTP 429 MUST be retried at least once before returning
         an empty result. Max 3 retries with exponential backoff.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
Current types (verified in codebase):

  IdeaCandidate (backend/pipeline/generation/models.py):
    id: str (UUID hex)
    title: str
    problem_statement: str
    proposed_method: str
    expected_contributions: str = ""
    novelty_rationale: str = ""
    evaluation_approach: str = ""
    overall_score: float = 0.0
    parent_idea_ids: list[str] | None = None

  ResearchIdea (backend/pipeline/generation/models.py):
    title: str
    problem_statement: str
    proposed_method: str
    expected_contributions: str (required)
    novelty_rationale: str (required)
    evaluation_approach: str (required)
    domain: str = "AI/NLP"
    round_generated: int = 1
    score: float = 0.0
    supporting_papers: list[str] (required, default_factory=list)
    source_gap_ids: list[str] (required, default_factory=list)

  Conversion map (IdeaCandidate → ResearchIdea):
    title           → title
    problem_statement → problem_statement
    proposed_method → proposed_method
    expected_contributions → expected_contributions (default "")
    novelty_rationale → novelty_rationale (default "")
    evaluation_approach → evaluation_approach (default "")
    overall_score   → score
    parent_idea_ids → source_gap_ids (best-effort; default [])
    (no equivalent) → domain = "AI/NLP"
    (no equivalent) → round_generated = 1
    (no equivalent) → supporting_papers = []

  ResearchProposal (backend/pipeline/synthesis/proposal_synthesizer.py):
    Not a Pydantic model — plain class with __init__(idea_id, **sections).
    self.sections is dict[str, Any]. Must be JSON-serializable after fix.

  PipelineResult (backend/pipeline/result.py):
    ideas: list[ResearchIdea]  ← type annotation; TreeSearchStage violates this

  DB Idea model (backend/db/models.py):
    title: str, pipeline_run_id: int (used for dedup check)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  - TreeSearchStage is the SOLE conversion point between IdeaCandidate
    and ResearchIdea in the tree search path. No other stage should
    perform this conversion.
  - persist_ideas() is the SOLE point where ideas are written to the DB.
    Dedup must happen here, not in crud.create_idea().
  - proposal_synthesizer.py is the SOLE point where ensemble_review is
    added to proposal.sections.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  - Depends on commit `99deeb5` (AgentOrchestrator.generate_ideas() wrapper)
  - Depends on commit `81d5c3f` (proposal synthesizer timeout increase)
  - Depends on prior config: tree_of_thought_enabled = True (backend/config.py)
  - Depends on prior config: EROCK_EMBEDDING_PROVIDER=ollama (.env)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [ ] NO — first Batch under v5.3, will create at Batch Close
  Last Updated:            N/A
  Batches since update:    N/A (file does not exist yet)
  Reconciliation audit:    [ ] N/A — first Batch, creating STATE.md

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  1,869 tests (collected 2026-05-06)
  Expected delta (all Tasks):      +22 new tests
  Expected total at Batch close:   1,891

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-75/TASK-01
  Priority:          Critical
  Description:       Add IdeaCandidate → ResearchIdea conversion in TreeSearchStage.
                     The conversion happens in execute() before ctx.result.ideas assignment.
                     A static method _convert_to_research_ideas() handles field mapping with
                     safe defaults for fields that IdeaCandidate lacks (domain, round_generated,
                     supporting_papers, source_gap_ids).
  Files in scope:
    - backend/pipeline/stages.py (TreeSearchStage class, ~lines 696-845)
    - backend/tests/test_pipeline/test_tree_search_types.py (new file)
  Depends on:        None
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-75-01-01 | unit | _convert_to_research_ideas maps all 9 IdeaCandidate fields to ResearchIdea | TreeSearchStage assigns IdeaCandidate to PipelineResult, downstream persistence crashes on missing .domain | Remove the conversion call in execute() — test fails because output type is IdeaCandidate | assert isinstance(result[0], ResearchIdea) and result[0].domain == "AI/NLP" |
    | TEST-75-01-02 | unit | _convert_to_research_ideas handles IdeaCandidate with empty optional fields | Conversion crashes on None parent_idea_ids or empty strings | Set parent_idea_ids=None, expected_contributions="" — test passes with defaults | result.source_gap_ids == [] and result.expected_contributions == "" |
    | TEST-75-01-03 | unit | _convert_to_research_ideas preserves overall_score → score | Score is lost in conversion, downstream novelty/feasibility stages get 0.0 | Comment out score mapping line — test fails with assert score != 0.0 | assert result.score == 0.85 |
    | TEST-75-01-04 | unit | TreeSearchStage.execute() raises AssertionError if ideas are not ResearchIdea | HB-01 violation passes silently | Remove isinstance check — test fails because assertion is gone | with pytest.raises(AssertionError): stage.execute(ctx_with_idea_candidates) |
    | TEST-75-01-05 | unit | _convert_to_research_ideas maps parent_idea_ids → source_gap_ids | parent_idea_ids are lost, KG relationships break | Change mapping to source_gap_ids=[] — test fails | assert result.source_gap_ids == ["id1", "id2"] |
  Acceptance Criteria:
    AC-01-01: _convert_to_research_ideas() exists as a static method on TreeSearchStage
    AC-01-02: All 5 IdeaCandidate fields are mapped to ResearchIdea equivalents with safe defaults
    AC-01-03: execute() calls isinstance() assertion after conversion (HB-01)
    AC-01-04: All 5 tests pass
  Traceability:
    AC-01-01 → TEST-75-01-01, TEST-75-01-02
    AC-01-02 → TEST-75-01-03, TEST-75-01-05
    AC-01-03 → TEST-75-01-04
    AC-01-04 → TEST-75-01-01 through TEST-75-01-05

TASK-02: BATCH-75/TASK-02
  Priority:          Critical
  Description:       Harden persist_ideas() to accept IdeaCandidate-like objects with
                     getattr() guards for .domain, .source_gap_ids, .expected_contributions,
                     and .novelty_rationale. Add dedup check before crud.create_idea() to
                     prevent duplicate (title, pipeline_run_id) rows.
  Files in scope:
    - backend/pipeline/persistence.py (persist_ideas method, ~lines 141-200)
    - backend/tests/test_pipeline/test_persistence_hardening.py (new file)
  Depends on:        None
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-75-02-01 | unit | persist_ideas handles IdeaCandidate objects without crashing | persist_ideas raises AttributeError on idea.domain | Remove getattr guard, use idea.domain directly — test crashes | No exception raised; idea persisted with domain="AI/NLP" |
    | TEST-75-02-02 | unit | persist_ideas skips duplicate ideas with same title + run_id | Multiple identical ideas appear in DB after retry | Remove dedup check — test fails with count > 1 | session.query(Idea).count() == 1 after two calls |
    | TEST-75-02-03 | unit | persist_ideas handles ResearchIdea objects (no regression) | Existing ResearchIdea flow breaks after adding getattr guards | Pass ResearchIdea instead of IdeaCandidate — test still works | Idea persisted with correct domain field |
    | TEST-75-02-04 | unit | getattr defaults are applied for missing fields | Fields like source_gap_ids=None cause JSON serialization to fail | Set source_gap_ids=None without default — json.dumps crashes | idea row created with source_gap_ids=None in DB |
  Acceptance Criteria:
    AC-02-01: All field accesses in persist_ideas use getattr() with defaults
    AC-02-02: Dedup query checks for existing idea with same (title, pipeline_run_id) before insert
    AC-02-03: IdeaCandidate objects can be persisted without error
    AC-02-04: No duplicate ideas in DB after multiple persist_ideas() calls with same data
    AC-02-05: All 4 tests pass
  Traceability:
    AC-02-01 → TEST-75-02-01, TEST-75-02-04
    AC-02-02 → TEST-75-02-02
    AC-02-03 → TEST-75-02-01
    AC-02-04 → TEST-75-02-02
    AC-02-05 → TEST-75-02-01 through TEST-75-02-04

TASK-03: BATCH-75/TASK-03
  Priority:          High
  Description:       Fix EnsembleReviewResult serialization. Change proposal_synthesizer.py
                     line 222 to store model_dump() instead of the raw Pydantic object.
                     Also ensure the persistence safety net handles any remaining cases.
  Files in scope:
    - backend/pipeline/synthesis/proposal_synthesizer.py (~line 222)
    - backend/tests/test_pipeline/test_synthesis.py (extend existing)
  Depends on:        None
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-75-03-01 | unit | proposal.sections["ensemble_review"] is a dict after synthesis | json.dumps(proposal.sections) raises TypeError on Pydantic model | Revert to storing raw EnsembleReviewResult — test fails with TypeError | isinstance(proposal.sections["ensemble_review"], dict) |
    | TEST-75-03-02 | unit | proposal.sections["ensemble_review"] contains expected fields | EnsembleReviewResult fields (overall_score, summary) are lost in conversion | Replace model_dump() with str() — test fails on missing keys | "overall_score" in proposal.sections["ensemble_review"] |
    | TEST-75-03-03 | unit | json.dumps succeeds on all proposal sections | json.dumps crashes on non-serializable values in sections | Remove serialization fix — test fails | json.dumps(sections) does not raise |
  Acceptance Criteria:
    AC-03-01: proposal.sections["ensemble_review"] is stored as dict, not Pydantic model
    AC-03-02: dict contains all EnsembleReviewResult fields (overall_score, summary, etc.)
    AC-03-03: json.dumps(proposal.sections) succeeds without custom encoder
    AC-03-04: All 3 tests pass
  Traceability:
    AC-03-01 → TEST-75-03-01
    AC-03-02 → TEST-75-03-02
    AC-03-03 → TEST-75-03-03
    AC-03-04 → TEST-75-03-01 through TEST-75-03-03

TASK-04: BATCH-75/TASK-04
  Priority:          Medium
  Description:       Add exponential backoff retry for arXiv HTTP 429 responses.
                     Wrap self._client.get() in a retry loop: on 429, sleep with
                     exponential backoff (5s → 15s → 30s). Max 3 retries. On other
                     HTTP errors, fail immediately (no retry). Preserve existing
                     3-second pre-request delay for rate limiting.
  Files in scope:
    - backend/pipeline/literature/arxiv_source.py (search method, ~lines 38-65)
    - backend/tests/test_pipeline/test_arxiv_retry.py (new file)
  Depends on:        None
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-75-04-01 | unit | arXiv retries on 429 and succeeds on second attempt | arXiv returns empty results on 429, losing papers | Remove retry loop — test fails (returns empty list) | len(results) > 0 after one 429 then one 200 |
    | TEST-75-04-02 | unit | arXiv retries up to 3 times then gives up on persistent 429 | Infinite retry loop hangs the pipeline | Change max_retries to 99 — test times out | Returns empty list after 3 retries, no exception |
    | TEST-75-04-03 | unit | arXiv does NOT retry on non-429 errors (e.g., 500) | Retrying on server errors wastes time and masks bugs | Change condition to retry on all status codes — test fails (retries on 500) | Returns empty list immediately on 500, no retry attempted |
    | TEST-75-04-04 | unit | Backoff delays are 5s, 15s, 30s (exponential) | Fixed 1s delay causes continued 429s | Change delay formula to constant 1s — test fails on wrong delays | mock_sleep.call_args_list matches [5, 15, 30] |
  Acceptance Criteria:
    AC-04-01: search() retries on HTTP 429 with backoff (5→15→30s)
    AC-04-02: search() gives up after 3 retries
    AC-04-03: search() does NOT retry on non-429 HTTP errors
    AC-04-04: All 4 tests pass
  Traceability:
    AC-04-01 → TEST-75-04-01, TEST-75-04-04
    AC-04-02 → TEST-75-04-02
    AC-04-03 → TEST-75-04-03
    AC-04-04 → TEST-75-04-01 through TEST-75-04-04

TASK-05: BATCH-75/TASK-05
  Priority:          Medium
  Description:       Update existing tests that may break due to TASK-01 through TASK-04
                     changes. Verify all 1,891+ tests pass. Run full suite and document results.
  Files in scope:
    - backend/tests/test_pipeline/test_source_reordering.py (if broken by arxiv changes)
    - backend/tests/test_pipeline/test_synthesis.py (extended in TASK-03)
    - Any other test files that reference modified code
  Depends on:        TASK-01, TASK-02, TASK-03, TASK-04
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-75-05-01 | integration | Full test suite passes with 0 failures (excluding 196 pre-existing trio-mode failures) | New code breaks existing tests | Introduce a breaking change in stages.py — suite fails | pytest exits 0 (or only trio-mode failures) |
    | TEST-75-05-02 | unit | New test files import and execute correctly | Import errors or fixture issues in new test files | Delete an __init__.py — test collection fails | All new test files collected without error |
    | TEST-75-05-03 | unit | test_source_reordering.py still passes after arxiv retry changes | ArxivSource internal changes break source ordering tests | Change source list construction — test fails | 2 tests in test_source_reordering.py pass |
  Acceptance Criteria:
    AC-05-01: Full pytest backend/tests/ completes with 0 unexpected failures
    AC-05-02: All new test files from TASK-01 through TASK-04 are collected
    AC-05-03: Pre-existing test_source_reordering.py tests still pass
  Traceability:
    AC-05-01 → TEST-75-05-01
    AC-05-02 → TEST-75-05-02
    AC-05-03 → TEST-75-05-03

TASK-06: BATCH-75/TASK-06
  Priority:          Critical
  Description:       Run the full pipeline with tree_of_thought_enabled=True (the default,
                     no env var override). Verify end-to-end completion: ideas generated
                     via tree search, novelty scored, feasibility scored, proposal synthesized.
                     This is a manual/live verification task — no new test files.
  Files in scope:
    - No new files (verification-only)
  Depends on:        TASK-01, TASK-02, TASK-03, TASK-05
  Required Tests:
    | Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
    |:--------|:-----|:------------------|:-------------|:-------------|:--------------|
    | TEST-75-06-01 | manual | Pipeline completes with tree search enabled (no env var override) | Pipeline crashes in TreeSearchStage with IdeaCandidate type error | Remove TASK-01 conversion — pipeline crashes with AttributeError | Pipeline exits with "COMPLETE" and ≥1 idea |
    | TEST-75-06-02 | manual | Generated ideas are ResearchIdea instances (not IdeaCandidate) | Downstream stages receive IdeaCandidate and crash | Remove isinstance assertion from TASK-01 — crash occurs later in pipeline | No AttributeError in any stage output |
    | TEST-75-06-03 | manual | Proposals persist to DB without serialization error | "Object of type EnsembleReviewResult is not JSON serializable" in log | Revert TASK-03 fix — error reappears in log | No serialization errors in pipeline output |
  Acceptance Criteria:
    AC-06-01: Pipeline completes with tree_of_thought_enabled=True, no env var override
    AC-06-02: ≥1 idea generated via tree search with score ≥ 0.5
    AC-06-03: Proposal synthesized (≥5000 chars) OR synthesis stage reached without crashes
    AC-06-04: No AttributeError or TypeError in any stage log
    AC-06-05: Results documented in Task Implementation Report
  Traceability:
    AC-06-01 → TEST-75-06-01
    AC-06-02 → TEST-75-06-01, TEST-75-06-02
    AC-06-03 → TEST-75-06-03
    AC-06-04 → TEST-75-06-02, TEST-75-06-03
    AC-06-05 → TEST-75-06-01

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Pipeline completes end-to-end with tree search enabled (no env var workaround)
  BAC-02: No IdeaCandidate objects leak into PipelineResult.ideas (HB-01 satisfied)
  BAC-03: CHANGELOG.md updated with BATCH-75 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-75/.
  BAC-05: STATE.md created with initial entries (first v5.3 Batch)
  BAC-06: All 22 new tests pass; no regressions in existing 1,869 tests

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:       REVIEW-BATCH-75-2026-05-06
Review Cycle:             1
Lead Decision:            [X] ACCEPT WITH MODIFICATIONS

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-CHK-11 (TASK-02 mixes two concerns) → NOTED. Both concerns (getattr guards + dedup)
    are in the same method persist_ideas() and are <40 LOC combined. Splitting would create
    a 2-line Task. Keeping as-is.
  FLAG-CHK-14 (Test count wrong: 19 not 22) → CORRECTED. Baseline updated to +22 tests.
    After extending TASK-01 (2 new tests for _build_tree_data) and TASK-03 (1 error-path
    test), total new tests = 5+2 + 4 + 3+1 + 4 + 3 + 0 = 22.
  FLAG-CHK-16 (_build_tree_data not covered) → ACTED ON. TASK-01 scope extended to include
    _build_tree_data() update. Two new tests added to TASK-01.
  FLAG-CHK-17 (_build_tree_data will crash on idea.id) → ACTED ON. Same fix as CHK-16.
    _build_tree_data() will use getattr(idea, 'id', idea.title[:60]) and
    getattr(idea, 'parent_idea_ids', []) or idea.source_gap_ids.
  FLAG-CHK-23 (TASK-03 lacks error-path test) → ACTED ON. TEST-75-03-04 added to TASK-03.
    Tests that proposal.sections gracefully handles ensemble_reviewer returning None.

If REJECT — reason and next action:
  N/A

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf 2026-05-06

═══════════════════════════════════════════════════════════
