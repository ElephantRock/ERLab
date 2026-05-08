# REVIEW REPORT — BATCH-121

Reviewer: 260509-focal-ruby
Date: 2026-05-09
Framework Version: 5.3

## VERDICT: FLAG

## FLAGS

| CHK | Severity | Finding | Recommendation |
|:----|:---------|:--------|:---------------|
| CHK-11 | MAJOR | TASK-02 traceability maps AC-04 → TEST-121-02-06, but this test ID does not exist. The TASK-02 test table defines only TEST-121-02-01 through TEST-121-02-05 (5 tests). AC-04 ("Prompt template exists and contains 'closed-book' instruction") has no corresponding test. | Either add TEST-121-02-06 to the TASK-02 test table (e.g., a test that asserts the prompt template file exists and contains "closed-book"), or remap AC-04 to an existing test and remove the dangling reference. |
| CHK-12 | MAJOR | BAC-01 states "All 8 new tests pass" and the Test Baseline declares delta +8 / expected total 2,300. However the three task test tables define 11 tests total (TASK-01: 3, TASK-02: 5, TASK-03: 3). The expected delta and BAC-01 count do not match the actual test table definitions. | Reconcile the count: if all 11 tests are intended, update delta to +11, expected total to 2,303, and BAC-01 to "All 11 new tests pass". If only 8 are intended, identify and remove 3 tests from the tables. |

## NOTES

### Investigative Layer — Verified

The following files were read to evaluate CHK-04, CHK-18, CHK-19, CHK-23, and CHK-24:

- **backend/providers/base.py** — `LLMProvider.structured_output()` confirmed as abstract method taking `(messages, schema, temperature) → dict`. CHK-23 PASS.
- **backend/pipeline/literature/models.py** — `Paper` model confirmed with `id: str` and `arxiv_id: str | None` fields matching the Blueprint's `source_paper_id` references. CHK-04 PASS.
- **backend/pipeline/generation/models.py** — `IdeaCandidate`, `Critique`, `ResearchIdea` models reviewed. No conflict with proposed Claim/ClaimType models. CHK-18 PASS.
- **backend/pipeline/result.py** — `PipelineResult` dataclass reviewed. Blueprint correctly does NOT propose adding a `claims` field here (that is B122's scope). CHK-04 PASS.
- **backend/pipeline/knowledge/contradiction.py** — `ContradictionScanner` + `ContradictionReport` operate on knowledge graph entity pairs. Fundamentally different from claim extraction from paper text. CHK-19 PASS.
- **backend/pipeline/knowledge/faithfulness.py** — `FaithfulnessChecker` validates gap analysis claims against source papers. Uses string-based claims, not typed Claim objects. No duplication. CHK-19 PASS.

### Non-flag Observations

- **CHK-07** (Test Baseline): Verified `python -m pytest --co -q` returns **2,292 tests collected** — matches Blueprint baseline exactly.
- **CHK-06** (STATE.md): Confirmed last updated 2026-05-07 (BATCH-120 close), 0 batches since update, no reconciliation audit needed (< 5 threshold).
- **CHK-20** (File paths): `backend/pipeline/claims/` follows established `backend/pipeline/PACKAGE/` convention (parallel to `generation/`, `literature/`, `verification/`).
- **CHK-21** (Test naming): `test_batch121_claim_extraction.py` follows `test_batchNNN_description.py` convention.
- **CHK-22** (Re-exports): The project has mixed patterns — `verification/__init__.py` re-exports, while `generation/`, `literature/`, `knowledge/` have empty `__init__.py` files. The Blueprint follows the more explicit verification pattern, which is acceptable and arguably better practice.
- **CHK-03** (Hard Boundaries): All three HBs are well-formed and falsifiable. HB-01 testable via invalid-JSON mock. HB-02 testable by asserting `source_paper_id` on returned claims. HB-03 testable via git diff.
- **CHK-24** (Network access): No task requires network access beyond the configured LLM provider. TASK-03 integration tests use mock providers.

### Summary

2 MAJOR flags, 0 CRITICAL, 0 MINOR. Both flags are count/traceability inconsistencies that should be corrected before execution to prevent confusion during Partial Sign-Off. The core architecture (Claim model, ClaimExtractor, prompt template, file layout) is sound and consistent with the codebase.
