BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID: BATCH-34 | Version: 1.0 | STANDARD | Lead | 2026-05-02

BATCH GOAL: Comment threads, sharing, erock CLI enhancement.

TASK-01: Backend — Comments + Sharing
  Files: backend/db/models.py (MODIFY — add Comment + SharedIdea tables)
         backend/api/routes/collaboration.py (NEW — comments + sharing)
  Tests: TEST-34-01-01: POST /ideas/{id}/comments adds comment
         TEST-34-01-02: GET /ideas/{id}/comments lists comments
         TEST-34-01-03: POST /ideas/{id}/share creates share link
         TEST-34-01-04: GET /shared/{token} returns shared idea
  Commit: feat(batch-34/task-01)

TASK-02: Frontend — Comments + Share
  Files: frontend/src/components/idea/comment-thread.tsx (NEW)
         frontend/src/components/idea/share-dialog.tsx (NEW)
         frontend/src/pages/idea-detail.tsx (MODIFY)
  Tests: TEST-34-02-01: Comment thread renders comments
         TEST-34-02-02: Add comment form works
         TEST-34-02-03: Share dialog generates link
         TEST-34-02-04: Shared idea page renders
  Commit: feat(batch-34/task-02)

TASK-03: CLI Enhancement
  Files: backend/cli/commands/research.py (NEW — open, proposal, export)
         backend/cli/main.py (MODIFY — register commands)
  Tests: TEST-34-03-01: erock open {id} opens idea in browser
         TEST-34-03-02: erock proposal {id} generates proposal
         TEST-34-03-03: erock export {id} exports to file
  Commit: feat(batch-34/task-03)

DEPENDENCY: BATCH-32
BASELINE: ~1,840 | Delta: +11 | Target: ~1,851
BAC: ✓ | Lead Sign: Lead + 2026-05-02 12:10
═══════════════════════════════════════════════════════════
