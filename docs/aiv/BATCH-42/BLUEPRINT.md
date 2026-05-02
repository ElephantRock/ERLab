# BATCH-42 BLUEPRINT — Cross-Run Gap Deduplication

**Batch ID:** BATCH-42 | **Version:** 1.0 | **Cycle Mode:** STANDARD  
**Lead:** Lead Agent | **Date:** 2026-05-02  
**SLAs:** Review 30min | Execution 60min | Partial 15min | **Sequencing:** Sequential  

## BATCH GOAL
Prevent duplicate gap rows across pipeline runs by content-hash deduplication, with truth revision.

## SCOPE
**MUST:**
1. Add canonical_id (String(128), nullable) and content_hash (String(64), nullable) to ResearchGapDB
2. Create Alembic migration 004_gap_dedup
3. Create normalize_title() function: lowercase → strip [^\w\s] → strip extra whitespace → SHA-256
4. Update persist_gaps() to check for existing gaps by content_hash
5. When duplicate found: revise truth via OpenNARS revise(), skip insert
6. Add GET /gaps/canonical endpoint

**MUST NOT:** Delete existing gap rows, modify gap analysis stage, change frontend

## HARD BOUNDARIES
- HB-01: Same title → same hash (deterministic)
- HB-02: Case-insensitive, strip non-word chars
- HB-03: Truth revision via OpenNARS revise(), never overwrite
- HB-04: No existing test may break

## TASK LIST

### TASK-01: Content Hash Dedup
- Files: backend/db/models.py, alembic/versions/004_gap_dedup.py, backend/db/crud.py, backend/pipeline/persistence.py, backend/api/routes/gaps.py
- Tests: backend/tests/test_pipeline/test_batch42_task01.py (6 tests)

## LEAD RESPONSE TO REVIEW
**Verdict:** APPROVE (Inline — 0 flags). Cleared for execution.
