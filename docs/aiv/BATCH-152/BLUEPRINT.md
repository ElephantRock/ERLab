BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-152
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (TASK-01→TASK-02→TASK-03)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────

Implement a cross-model adversarial review stage that routes completed
proposals through a different model family for adversarial scoring with
a revision loop. Completed proposals score ≥ 7/10 on Soundness, Novelty,
Feasibility, and Clarity before they are accepted. Rejected proposals
receive revision notes and are re-synthesized (max 2 revision rounds).

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────

What the code MUST do:
  - Create an `AdversarialReviewer` class in `backend/pipeline/evaluation/adversarial_reviewer.py`
  - The reviewer MUST use a different model/provider than the proposal synthesizer
    (cloud provider reviews what local model generated, or vice versa)
  - Score proposals on 4 dimensions: Soundness (1-10), Novelty (1-10),
    Feasibility (1-10), Clarity (1-10) — with written justification per dimension
  - Overall score = mean of 4 dimensions
  - If overall < 7.0, generate structured revision notes (max 500 words)
    listing specific weaknesses and improvement suggestions
  - Create an `AdversarialReviewStage` in `backend/pipeline/stages.py` that:
    (a) Runs after proposal_synthesis in the pipeline
    (b) Sends each proposal to the AdversarialReviewer
    (c) If rejected, feeds revision notes back to ProposalSynthesizer for re-generation
    (d) Max 2 revision rounds per proposal
    (e) Stores final scores in proposal metadata as `adversarial_review` JSON field
  - Register the stage in `PipelineOrchestrator._STAGE_ORDER` after
    `proposal_synthesis` (before `proposal_deepening`)
  - Create a new pipeline strategy preset `adversarial_review: true/false`
    (default: true for deep_research, false for fast_scan)

What the code MUST NOT do:
  - MUST NOT modify the ProposalSynthesizer's core generation logic
  - MUST NOT change any existing API endpoint signatures
  - MUST NOT add new database tables or migrations
  - MUST NOT use the same model/provider for both synthesis and review
  - MUST NOT block the pipeline if the adversarial review provider is unavailable
    (graceful fallback: log warning, skip review, mark proposal as "unreviewed")

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────

  Backend:  python -c "from backend.config import get_settings; print('OK')"
  Tests:    python -m pytest backend/tests/test_pipeline/test_batch152_adversarial_review.py -v -p no:asyncio

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: All 2,499 pre-existing tests MUST pass after Batch close.
  HB-02: The AdversarialReviewer MUST use a different provider instance than
         the ProposalSynthesizer. If both resolve to the same model, the review
         MUST be skipped with a warning log (not crash).
  HB-03: Pipeline MUST NOT block if adversarial review provider is unavailable.
         If the LLM call fails (timeout, rate limit, network error), log a warning
         and mark the proposal as `{"adversarial_review": {"status": "skipped", "reason": "..."}}`.
  HB-04: Max revision rounds = 2. After 2 failed revisions, accept the proposal
         with its current scores and add `{"max_revisions_reached": true}` to metadata.
  HB-05: Each dimension score MUST be an integer 1-10. Overall = float mean.
         If the LLM returns a score outside [1,10], clamp it and log a warning.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

New dataclass `AdversarialReviewScore` (in adversarial_reviewer.py):
  - soundness: int (1-10)
  - novelty: int (1-10)
  - feasibility: int (1-10)
  - clarity: int (1-10)
  - overall: float (mean of 4)
  - soundness_justification: str
  - novelty_justification: str
  - feasibility_justification: str
  - clarity_justification: str
  - revision_notes: str | None (non-None only if overall < 7.0)
  - round: int (1, 2, or 3 — initial + max 2 revisions)
  - model_used: str (provider class name for audit trail)

Storage: proposal.metadata["adversarial_review"] = dict from AdversarialReviewScore
No new DB tables — uses existing ResearchProposal.metadata JSON field.

Existing modules referenced:
  - `backend/pipeline/stages.py` — PipelineStage base class, StageContext
  - `backend/pipeline/orchestrator.py` — _STAGE_ORDER list (DEC-003)
  - `backend/pipeline/synthesis/proposal_synthesizer.py` — ProposalSynthesizer, ResearchProposal
  - `backend/pipeline/evaluation/ensemble_review.py` — EnsembleReviewer (existing but not used for this)
  - `backend/providers/provider_factory.py` — get_thinking_provider(), get_generation_provider()
  - `backend/pipeline/model_selection.py` — ModelSelection (thinking vs generation routing)
  - `backend/pipeline/strategies/presets.py` — strategy preset definitions

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────

  A-01: The adversarial reviewer MUST use the "thinking" provider (local LM Studio)
        while the synthesizer uses the "generation" provider (cloud). This ensures
        different model families. If both resolve to the same, skip review (HB-02).
  A-02: Revision notes are the ONLY input to re-synthesis. The synthesizer does NOT
        see the raw scores — only the textual revision notes. This prevents
        score-chasing behavior.
  A-03: The adversarial review prompt MUST instruct the reviewer to be critical.
        It is an adversarial role: find weaknesses, challenge assumptions, demand rigor.
  A-04: Stage registration follows DEC-003: the stage name MUST appear in _STAGE_ORDER
        exactly as declared. New stage name: `adversarial_review`.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────

  Depends on:
    - BATCH-78 (thinking/generation model split) — uses different provider for review
    - BATCH-114 (proposal_deepening stage) — adversarial_review runs BEFORE deepening
    - BATCH-151 (constants.py) — AI_HONESTY_BADGE pattern for new module

  Blocks:
    - BATCH-153 (LaTeX paper synthesis) — quality-gated proposals first
    - BATCH-171 (Internal Alpha) — adversarial review is P0 feature

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────

  State file exists:       [X] YES
  Last Updated:            2026-05-11 (BATCH-151 Close)
  Batches since update:    0
  Reconciliation audit:    [X] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline at Blueprint issuance:  2,499 existing tests
  Expected delta (all Tasks):      +14 new tests
  Expected total at Batch close:   2,513

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-152/TASK-01
  Priority:          Critical
  Description:       Create AdversarialReviewer class in
                     `backend/pipeline/evaluation/adversarial_reviewer.py`.
                     The class must:
                     (a) Accept a provider (injected, not created internally)
                     (b) Method `review(proposal_text: str, source_papers: list[str]) -> AdversarialReviewScore`
                     (c) Use structured LLM output to get 4 dimension scores + justifications
                     (d) If overall < 7.0, populate `revision_notes` with specific improvement suggestions
                     (e) If LLM call fails, return AdversarialReviewScore with all scores=0,
                         justification="Review skipped: {error}", round=0, model_used="none"
                     (f) Clamp all scores to [1,10] range (HB-05)
  Files in scope:
    - backend/pipeline/evaluation/adversarial_reviewer.py (NEW)
    - backend/pipeline/evaluation/prompts/adversarial_review.md (NEW — prompt template)
  Depends on:        None
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-152-01-01   | unit   | AdversarialReviewScore dataclass has 11 fields | Missing fields cause AttributeError downstream | Remove a field from dataclass | All 11 fields accessible: soundness, novelty, feasibility, clarity, overall, soundness_justification, novelty_justification, feasibility_justification, clarity_justification, revision_notes, round, model_used |
    | TEST-152-01-02   | unit   | Scores clamped to [1,10] range           | LLM returns score=15, crashes downstream | Return score=15 from mock LLM          | Clamped to 10, no crash                    |
    | TEST-152-01-03   | unit   | Revision notes populated when overall < 7 | Accepted weak proposals without feedback | Return all scores as 3 | revision_notes is non-empty string |
    | TEST-152-01-04   | unit   | Revision notes empty when overall >= 7   | Unnecessary revision notes on good proposals | Return all scores as 9 | revision_notes is None or empty |
    | TEST-152-01-05   | unit   | Graceful fallback on LLM failure          | Pipeline crashes when reviewer provider down | Raise Exception in mock provider | Returns AdversarialReviewScore with scores=0, model_used="none" |
    | TEST-152-01-06   | unit   | Prompt instructs adversarial/critical role | Reviewer gives rubber-stamp approvals | Check prompt template content | Prompt contains "critical", "weakness", "challenge" keywords |
  Acceptance Criteria:
    AC-01-01: AdversarialReviewer class exists with review() method
    AC-01-02: All scores clamped to [1,10] (HB-05)
    AC-01-03: Revision notes populated only when overall < 7.0
    AC-01-04: LLM failure returns graceful fallback (HB-03)
    AC-01-05: Prompt file contains adversarial instructions (A-03)
  Traceability:
    AC-01-01 → TEST-152-01-01
    AC-01-02 → TEST-152-01-02
    AC-01-03 → TEST-152-01-03, TEST-152-01-04
    AC-01-04 → TEST-152-01-05
    AC-01-05 → TEST-152-01-06

TASK-02: BATCH-152/TASK-02
  Priority:          Critical
  Description:       Create AdversarialReviewStage in `backend/pipeline/stages.py`
                     and register it in the orchestrator. The stage must:
                     (a) Extend PipelineStage base class
                     (b) For each proposal in the pipeline result, run AdversarialReviewer
                     (c) If rejected (overall < 7.0) and rounds < 2, re-synthesize with revision notes
                     (d) Store final scores in proposal.metadata["adversarial_review"]
                     (e) Add `adversarial_review` to _STAGE_ORDER after `proposal_synthesis`
                     (f) Only run when strategy preset has `adversarial_review: true`
  Files in scope:
    - backend/pipeline/stages.py (MODIFY — add AdversarialReviewStage class)
    - backend/pipeline/orchestrator.py (MODIFY — add to _STAGE_ORDER)
    - backend/pipeline/strategies/presets.py (MODIFY — add adversarial_review flag)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type       | Behavior Verified                      | Failure Mode                      | Falsified By                       | Pass Criteria                          |
    |:-----------------|:-----------|:---------------------------------------|:----------------------------------|:-----------------------------------|:---------------------------------------|
    | TEST-152-02-01   | unit       | Stage registered in _STAGE_ORDER       | Stage never runs, proposals unreviewed | Remove from _STAGE_ORDER | "adversarial_review" in PipelineOrchestrator._STAGE_ORDER |
    | TEST-152-02-02   | unit       | Stage position: after proposal_synthesis | Review runs before synthesis, has nothing to review | Move before proposal_synthesis | Order index of adversarial_review > proposal_synthesis |
    | TEST-152-02-03   | unit       | Re-synthesis triggered on rejection     | Weak proposals accepted without revision | Mock reviewer to return score=4 | Re-synthesis called with revision_notes |
    | TEST-152-02-04   | unit       | Max 2 revision rounds enforced          | Infinite revision loop | Mock reviewer to always return score=4 | After round 3, proposal accepted with max_revisions_reached=true |
    | TEST-152-02-05   | unit       | Strategy flag controls stage execution  | Stage runs on fast_scan when it shouldn't | Set adversarial_review=false in preset | Stage skipped when flag is false |
  Acceptance Criteria:
    AC-02-01: adversarial_review appears in _STAGE_ORDER after proposal_synthesis (DEC-003)
    AC-02-02: Revision loop max 2 rounds (HB-04)
    AC-02-03: Stage skipped when strategy preset disables it
    AC-02-04: Scores stored in proposal metadata
  Traceability:
    AC-02-01 → TEST-152-02-01, TEST-152-02-02
    AC-02-02 → TEST-152-02-04
    AC-02-03 → TEST-152-02-05
    AC-02-04 → TEST-152-02-03

TASK-03: BATCH-152/TASK-03
  Priority:          High
  Description:       Wire the AdversarialReviewStage to use the thinking provider
                     (local LM Studio) while ProposalSynthesizer uses generation provider
                     (cloud). Ensure different model families. Add `reviewer_provider` 
                     resolution in the stage's __init__ that:
                     (a) Gets the thinking provider from provider_factory
                     (b) Logs which provider/model is being used for review
                     (c) If thinking provider == generation provider, skips review (HB-02)
                     Also update the fast_scan and deep_research strategy presets:
                     - deep_research: adversarial_review=true (default)
                     - fast_scan: adversarial_review=false (skip for speed)
  Files in scope:
    - backend/pipeline/stages.py (MODIFY — provider resolution in AdversarialReviewStage)
    - backend/pipeline/strategies/presets.py (MODIFY — preset flags)
  Depends on:        TASK-02
  Required Tests:
    | Test ID          | Type       | Behavior Verified                      | Failure Mode                      | Falsified By                       | Pass Criteria                          |
    |:-----------------|:-----------|:---------------------------------------|:----------------------------------|:-----------------------------------|:---------------------------------------|
    | TEST-152-03-01   | unit       | deep_research preset has adversarial_review=true | Feature disabled for deep research | Set flag to false | deep_research preset has adversarial_review=true |
    | TEST-152-03-02   | unit       | fast_scan preset has adversarial_review=false | Slow fast_scan with unnecessary review | Set flag to true | fast_scan preset has adversarial_review=false |
    | TEST-152-03-03   | integration| Different providers for synthesis vs review | Self-play blind spots, rubber-stamp reviews | Mock both to same provider | Stage logs warning and skips when providers match |
  Acceptance Criteria:
    AC-03-01: deep_research enables adversarial review
    AC-03-02: fast_scan disables adversarial review
    AC-03-03: Review skipped when same provider (HB-02, A-01)
  Traceability:
    AC-03-01 → TEST-152-03-01
    AC-03-02 → TEST-152-03-02
    AC-03-03 → TEST-152-03-03

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: AdversarialReviewer class produces AdversarialReviewScore with 4 dimensions.
  BAC-02: AdversarialReviewStage registered in _STAGE_ORDER at correct position.
  BAC-03: Revision loop works: rejected proposals get re-synthesized (max 2 rounds).
  BAC-04: All 2,499 pre-existing tests pass (HB-01).
  BAC-05: CHANGELOG.md updated with BATCH-152 entry.
  BAC-06: All documents archived under /docs/aiv/BATCH-152/.
  BAC-07: STATE.md updated with new test count, DEC-010 for new stage order,
          and GOTCHA-008 for adversarial review provider mismatch behavior.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:       REVIEW-BATCH-152-2026-05-11
Review Cycle:             1
Lead Decision:            [X] ACCEPT WITH MODIFICATIONS

Must-fix (2 items) — addressed in Blueprint v1.1:
  FLAG-19b → ACTION: `ModelSelection` → `ModelSelector` corrected in Data Models.
  FLAG-07/17b → ACTION: `overall` is a stored field (computed in constructor).
              Test updated to expect 12 fields. Not a @property — simpler.

Should-fix (3 items) — addressed in Blueprint v1.1:
  FLAG-17a/20a → ACTION: TASK-02 scope expanded: must add BOTH `proposal_deepening`
                  AND `adversarial_review` to presets._all_stages_enabled().
  FLAG-23a → ACTION: Added TEST-152-02-06: regression test for all 4 existing
              presets loading without error after changes.
  FLAG-22a → ACKNOWLEDGED: TASK-02 adds stage name to _all_stages_enabled();
              TASK-03 adds flag defaults to preset dicts. Different regions
              of same file, sequential order prevents merge friction.

Can-fix during execution (3 items):
  FLAG-24a → Will update STATE.md with model_selection module in BAC-07.

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-11 01:00

═══════════════════════════════════════════════════════════
