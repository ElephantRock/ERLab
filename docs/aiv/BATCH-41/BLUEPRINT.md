# BATCH-41 BLUEPRINT — Gap Feedback & Lifecycle

**Batch ID:** BATCH-41 | **Version:** 1.0 | **Cycle Mode:** STANDARD  
**Lead:** Lead Agent | **Date:** 2026-05-02  
**SLAs:** Review 30min | Execution 60min | Partial 15min | **Sequencing:** Sequential  

## BATCH GOAL
Add user feedback (star rating + notes) and lifecycle status tracking to research gaps.

## SCOPE
**MUST:**
1. Add status (String(20), default="identified"), user_rating (Integer, nullable), user_notes (Text, nullable) to ResearchGapDB
2. Create Alembic migration 003_gap_feedback
3. Add POST /gaps/{id}/feedback (rating 1-5 + optional notes) and PATCH /gaps/{id}/status endpoints
4. Add GapFeedbackForm component (star rating + notes textarea)
5. Add status dropdown on gap detail page
6. Include feedback and status in API responses

**MUST NOT:** Add gap deduplication (BATCH-42), modify gap analysis pipeline

## HARD BOUNDARIES
- HB-01: status ∈ {identified, investigating, addressed} — 422 for others
- HB-02: user_rating ∈ [1, 5] — 422 for others
- HB-03: Forward-only lifecycle: identified → investigating → addressed
- HB-04: No existing test may break

## TASK LIST

### TASK-01: Backend Feedback & Status Endpoints
- Files: backend/db/models.py, alembic/versions/003_gap_feedback.py, backend/db/crud.py, backend/api/routes/gaps.py, backend/api/schemas.py
- Tests: backend/tests/test_api/test_batch41_task01.py (8 tests)
- AC: Both endpoints return correct status codes; validation matches HB-01/HB-02/HB-03

### TASK-02: Frontend Feedback Form & Status Dropdown
- Files: frontend/src/components/gaps/gap-feedback-form.tsx (new), frontend/src/pages/gap-detail.tsx, frontend/src/api/gaps.ts, frontend/src/api/types.ts
- Tests: frontend/src/pages/__tests__/batch41-feedback.test.tsx (8 tests)
- AC: Star rating appears on gap detail; status dropdown in header

## BATCH ACCEPTANCE
- BAC-01: Users can rate gaps 1-5 stars
- BAC-02: Forward-only status transitions
- BAC-03: CHANGELOG updated
- BAC-04: Docs archived

## LEAD RESPONSE TO REVIEW
**Verdict:** APPROVE (Inline — 0 flags). Cleared for execution.
