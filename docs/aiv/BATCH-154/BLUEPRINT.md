BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-154
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

Create a post-processing audit stage that verifies every citation and
quantitative claim in generated proposals/papers against the actual
source papers. Three verification axes:
  (1) Citation Existence — does [SOURCE-X] point to a real source?
  (2) Citation Context — is the claim attributed to that source accurate?
  (3) Quantitative Accuracy — are numbers/metrics faithful to source text?

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────

What the code MUST do:
  - Create a `CitationClaimAuditor` class in
    `backend/pipeline/verification/citation_claim_auditor.py` that:
    (a) Extracts all [SOURCE-X] references from proposal/paper text
    (b) Verifies each reference index exists in the source papers list
    (c) For each reference, uses LLM to verify the claim attributed to
        that source is actually supported by the source text (context check)
    (d) Extracts quantitative claims (numbers, percentages, metrics) and
        verifies them against source paper text
    (e) Returns a structured audit report per proposal
  - Create a `CitationAuditStage` in `backend/pipeline/stages.py` that:
    (a) Runs after `paper_synthesis` in the pipeline
    (b) Audits each proposal's text (proposal + full paper if available)
    (c) Stores audit results in `proposal.metadata["citation_audit"]`
    (d) Flags proposals with trust_score < 0.5 as low-trust
    (e) Only runs when strategy has `citation_audit: true`
  - Register the stage in `_STAGE_ORDER` after `paper_synthesis`
  - Extend the existing `ReferenceVerifier` with `[SOURCE-X]` pattern support
    (currently only handles "Author et al., YEAR" patterns)

What the code MUST NOT do:
  - MUST NOT modify existing ClaimExtractor logic
  - MUST NOT modify existing API endpoint signatures
  - MUST NOT add new database tables or migrations
  - MUST NOT require network access (audit uses local source text only)
  - MUST NOT block pipeline if audit fails (graceful fallback)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────

  Backend:  python -c "from backend.config import get_settings; print('OK')"
  Tests:    python -m pytest backend/tests/test_pipeline/test_batch154_citation_audit.py -v -p no:asyncio

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: All 2,536 pre-existing tests MUST pass after Batch close.
  HB-02: Audit stage MUST NOT block if LLM call fails. Log warning
         and store `{"citation_audit": {"status": "skipped", "reason": "..."}}`.
  HB-03: [SOURCE-X] indices MUST be validated against actual source count.
         If index > len(source_papers), flag as fabricated.
  HB-04: Trust score MUST be 0.0-1.0 float. Clamped if out of range.
  HB-05: Audit must complete within 60 seconds per proposal. If LLM
         timeout occurs, return partial results with timeout flag.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

New dataclass `CitationAuditItem` (in citation_claim_auditor.py):
  - ref_index: int (the X in [SOURCE-X])
  - ref_exists: bool (does the source paper exist?)
  - claim_text: str (the text surrounding the citation)
  - context_verified: bool (LLM says claim matches source)
  - context_justification: str (LLM's reasoning)
  - quantitative_claims: list[dict] (extracted numbers/metrics)
  - quantitative_verified: bool (all numbers match source)
  - trust_contribution: float (0.0-1.0 for this citation)

New dataclass `CitationAuditReport` (in citation_claim_auditor.py):
  - proposal_id: int
  - total_citations: int
  - verified_citations: int
  - fabricated_citations: int
  - context_mismatches: int
  - quantitative_errors: int
  - trust_score: float (0.0-1.0, mean of item trust contributions)
  - items: list[CitationAuditItem]
  - model_used: str
  - status: str ("complete" | "partial" | "skipped")

Storage: proposal.metadata["citation_audit"] = CitationAuditReport.to_dict()

Existing modules referenced:
  - `backend/pipeline/verification/reference_verifier.py` — ReferenceVerifier, CitationCheck, VerificationReport
  - `backend/pipeline/stages.py` — PipelineStage, StageContext, _get_metadata/_set_metadata
  - `backend/pipeline/orchestrator.py` — _STAGE_ORDER (12 entries → 13)
  - `backend/providers/provider_factory.py` — get_thinking_provider()
  - `backend/pipeline/strategies/presets.py` — strategy presets

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────

  A-01: Citation audit uses the THINKING provider (local LM Studio),
        not the generation provider. This is an analysis/verification task.
  A-02: The auditor receives the PROPOSAL TEXT + FULL PAPER TEXT (if
        available from paper_synthesis stage) and the SOURCE PAPERS list.
  A-03: Only [SOURCE-X] format citations are audited (not "Author et al."
        style — that's already handled by ReferenceVerifier).
  A-04: Stage name: `citation_audit`. Must appear in _STAGE_ORDER after
        `paper_synthesis` and before `proposal_deepening`.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────

  Depends on:
    - BATCH-153 (paper_synthesis stage) — audits papers after generation
    - BATCH-111 (closed-book citation policy) — [SOURCE-X] format
    - BATCH-112 (reference_verifier.py) — extends existing verification

  Blocks:
    - BATCH-159 (5-State Verification) — uses audit trust scores

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────

  State file exists:       [X] YES
  Last Updated:            2026-05-11 (BATCH-153 Close)
  Batches since update:    0
  Reconciliation audit:    [X] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline at Blueprint issuance:  2,536 existing tests
  Expected delta (all Tasks):      +14 new tests
  Expected total at Batch close:   2,550

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-154/TASK-01
  Priority:          Critical
  Description:       Create `CitationClaimAuditor` class.
                     The class must:
                     (a) Accept a thinking provider (injected)
                     (b) Method `audit(proposal_text, source_papers) -> CitationAuditReport`
                     (c) Extract [SOURCE-X] references using regex
                     (d) Verify each reference index < len(source_papers) (HB-03)
                     (e) For valid references, use LLM to verify claim context
                     (f) Extract quantitative claims (numbers, %, metrics)
                     (g) Verify quantitative claims against source text
                     (h) Compute trust_score as mean of item trust contributions
                     (i) Clamp trust_score to [0.0, 1.0] (HB-04)
                     (j) Return partial results on timeout (HB-05)
                     (k) Return skipped report on LLM failure (HB-02)
  Files in scope:
    - backend/pipeline/verification/citation_claim_auditor.py (NEW)
    - backend/pipeline/verification/prompts/citation_audit.md (NEW — prompt)
  Depends on:        None
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-154-01-01   | unit   | [SOURCE-X] extraction works              | Missing citations go undetected | Text with [SOURCE-1], [SOURCE-3] | Extracts indices [1, 3] |
    | TEST-154-01-02   | unit   | Fabricated index flagged                 | Non-existent source used | Index 99 with 5 sources | ref_exists=False for index 99 |
    | TEST-154-01-03   | unit   | Trust score clamped to [0.0, 1.0]       | Score > 1.0 breaks downstream | Return score 1.5 from mock | Clamped to 1.0 |
    | TEST-154-01-04   | unit   | Graceful fallback on LLM failure          | Pipeline crashes when audit fails | Raise Exception in mock | Returns report with status="skipped" |
    | TEST-154-01-05   | unit   | CitationAuditReport has all required fields | Missing fields cause AttributeError | Access all fields | total_citations, verified_citations, fabricated_citations, trust_score, items, status all accessible |
    | TEST-154-01-06   | unit   | Quantitative claim extraction works       | Numbers not detected | Text "achieved 95.2% accuracy" | Extracts "95.2%" as quantitative claim |

TASK-02: BATCH-154/TASK-02
  Priority:          Critical
  Description:       Create `CitationAuditStage` in stages.py and register in
                     orchestrator. Must:
                     (a) Extend PipelineStage
                     (b) For each proposal, run CitationClaimAuditor on proposal text + full paper
                     (c) Store report in proposal.metadata["citation_audit"]
                     (d) Log warning if trust_score < 0.5
                     (e) Add `citation_audit` to _STAGE_ORDER after `paper_synthesis`
                     (f) Only run when strategy has citation_audit enabled
  Files in scope:
    - backend/pipeline/stages.py (MODIFY — add CitationAuditStage)
    - backend/pipeline/orchestrator.py (MODIFY — _STAGE_ORDER now 13)
    - backend/pipeline/strategies/presets.py (MODIFY — add citation_audit)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-154-02-01   | unit   | citation_audit in _STAGE_ORDER           | Stage never runs | Remove from list | "citation_audit" in _STAGE_ORDER |
    | TEST-154-02-02   | unit   | Stage position after paper_synthesis     | Runs before papers exist | Check index | citation_audit idx > paper_synthesis idx |
    | TEST-154-02-03   | unit   | Audit report stored in metadata          | Results lost after stage | Run stage, check metadata | proposal.metadata["citation_audit"] is dict |
    | TEST-154-02-04   | unit   | Low trust score logged as warning        | Bad proposals pass silently | Mock auditor to return score=0.3 | Warning log emitted |
    | TEST-154-02-05   | unit   | Stage skipped when flag disabled         | Runs unnecessarily | Set flag false | Stage skips |

TASK-03: BATCH-154/TASK-03
  Priority:          High
  Description:       Wire strategy presets for citation audit and add
                     [SOURCE-X] support to ReferenceVerifier. Must:
                     (a) deep_research: citation_audit=true
                     (b) academic_proposal: citation_audit=true
                     (c) fast_scan: citation_audit=false
                     (d) literature_review: citation_audit=false
                     (e) Extend ReferenceVerifier with [SOURCE-X] pattern support
  Files in scope:
    - backend/pipeline/strategies/presets.py (MODIFY)
    - backend/pipeline/verification/reference_verifier.py (MODIFY)
  Depends on:        TASK-02
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-154-03-01   | unit   | deep_research enables citation_audit     | Audit not run | Check flag | citation_audit=true |
    | TEST-154-03-02   | unit   | fast_scan disables citation_audit        | Slows fast_scan | Check flag | citation_audit=false |
    | TEST-154-03-03   | unit   | ReferenceVerifier detects [SOURCE-X]     | [SOURCE-X] citations missed | Text with [SOURCE-1] | Detected as numbered reference |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: CitationClaimAuditor class produces CitationAuditReport with 3-axis checks.
  BAC-02: CitationAuditStage registered in _STAGE_ORDER at correct position.
  BAC-03: All 2,536 pre-existing tests pass (HB-01).
  BAC-04: CHANGELOG.md updated with BATCH-154 entry.
  BAC-05: All documents archived under /docs/aiv/BATCH-154/.
  BAC-06: STATE.md updated with DEC-012 (citation_audit stage), test count.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

[Completed by Lead after Phase I-B.]

Reviewer Report ID:       REVIEW-BATCH-154-2026-05-11
Review Cycle:             1
Lead Decision:            [X] ACCEPT WITH MODIFICATIONS

Must-fix before execution (2 items):
  FLAG-02 → Use StageConfig() / StageConfig(enabled=False) for gating, NOT params flag.
  FLAG-03 → Added TEST-154-01-07 for timeout → partial results.

Non-blocking (2 items):
  FLAG-01 → ACKNOWLEDGED: metadata helper duplication is tech debt for future batch.
  FLAG-04 → ACKNOWLEDGED: TASK-03 stays combined (both low-risk).

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-11 03:36

═══════════════════════════════════════════════════════════
