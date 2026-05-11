BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-159
Blueprint Version:        1.0 (Lead-Reviewed, Direct Implementation)
Cycle Mode:               STANDARD (§5.3 Lead Override)

BATCH GOAL
───────────────────────────────────────────────────────────
Replace binary citation verification with 5-state enum.
Wire TrustTier gates into CitationClaimAuditor.
Add temporal decay for confidence scores.

HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: All 2,605 pre-existing tests pass.
  HB-02: New enum is additive — existing code continues to work.
  HB-03: Trust gates are advisory flags, not hard blocks (HB-02).

TASKS
───────────────────────────────────────────────────────────
TASK-01: VerificationState 5-state enum (5 tests)
  - SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE,
    CONTRADICTED, UNVERIFIED
  - Update CitationCheck to use new state field
  - Backward compat: `found_in_corpus` still works

TASK-02: TrustTier gates in CitationClaimAuditor (5 tests)
  - Each audit item gets trust_tier computed from 3-axis results
  - CitationAuditReport gets trust_gate_warnings list
  - Proposals with <50% SUPPORTED citations get flagged

TASK-03: Temporal decay for confidence (4 tests)
  - decay_factor(age_days, half_life=30) → 0.0-1.0
  - Applied to CitationCheck.confidence and audit trust scores
  - Recent citations boosted; old ones decayed

TEST BASELINE: 2,605 → 2,619 (+14)
═══════════════════════════════════════════════════════════
