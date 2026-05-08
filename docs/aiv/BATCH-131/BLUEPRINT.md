# BATCH-131 BLUEPRINT — LLM-Grounded WikiVerifier

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-131
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-09
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Replace the WikiVerifier's keyword-overlap heuristic with LLM-based claim
verification. Each claim in a wiki entry is sent to the LLM with the source
text, and the LLM judges whether it is supported. Falls back to keyword
overlap if LLM fails. The strategic bet: LLM can judge claim support with
<20% false positive rate and catch intentionally wrong claims.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add an LLM verification path to WikiVerifier.verify()
  - For each claim extracted from the wiki, call provider.complete() with
    the claim + source text + a verification prompt
  - LLM returns JSON: {"supported": bool, "reasoning": str}
  - Aggregate supported/total into quality_score
  - Unsupported claims get their reasoning stored in unsupported_claims
  - Keep keyword overlap as fallback when provider is None or on LLM failure
  - Add a verification prompt template at wiki/prompts/wiki_verification.md

What the code MUST NOT do:
  - Must NOT break existing WikiVerifier tests (backward compatible)
  - Must NOT modify ClaimExtractor or any claims/ package modules
  - Must NOT call provider.structured_output() — use complete() for free-text
    reasoning (structured_output forces JSON schema which can truncate reasoning)
  - Must NOT block on LLM failure — always return a WikiEntry (HB-01)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m pytest backend/tests/test_pipeline/test_batch131_wiki_verifier_deep.py -v --tb=short 2>&1 | tail -5

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: WikiVerifier.verify() MUST return a WikiEntry even if every
         LLM call fails — degrade to keyword overlap silently.
  HB-02: The LLM verification prompt MUST explicitly instruct:
         "Only answer based on the source text. Do NOT use outside knowledge."
  HB-03: The verify() method MUST NOT modify the input WikiEntry — return
         a new one (deep copy).

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

  WikiVerifier (backend/pipeline/wiki/verifier.py) — MODIFIED:
    Current:
      - __init__(self, provider=None)
      - async verify(self, wiki: WikiEntry, source_text: str) -> WikiEntry
      - _extract_claims(wiki) -> list[str]  (static)
      - _claim_supported(claim, source_lower) -> bool  (static, keyword overlap)

    New:
      - __init__(self, provider=None)  — no change
      - async verify(self, wiki, source_text) -> WikiEntry  — enhanced
      - _extract_claims(wiki) -> list[str]  — no change
      - async _verify_claim_with_llm(self, claim: str, source: str) -> dict
         Returns: {"supported": bool, "reasoning": str}
      - _claim_supported_keyword(claim, source_lower) -> bool  — RENAMED from _claim_supported
      - _claim_supported(claim, source_lower) -> bool  — DELEGATES to keyword (fallback)

  Prompt template (backend/pipeline/wiki/prompts/wiki_verification.md):
    Instructions for the LLM to judge claim support:
    - Given a CLAIM and SOURCE TEXT
    - Determine if the claim is supported by the source text
    - Return JSON: {"supported": true/false, "reasoning": "explanation"}
    - ONLY use the source text — no outside knowledge (HB-02)

  No new data models. WikiEntry.unsupported_claims now contains
  richer reasoning strings instead of just the claim text.

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  A-01: LLM judgment is authoritative when available.
         Keyword overlap is the fallback authority when LLM is unavailable.
  A-02: quality_score = supported_claims / total_claims regardless of
         which authority (LLM or keyword) was used.
  A-03: The verification prompt (wiki_verification.md) is the SOLE source
         of verification instructions. No inline prompt strings.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Internal: backend/providers/base.py (LLMProvider.complete)
  Internal: backend/pipeline/wiki/models.py (WikiEntry)
  Internal: backend/pipeline/wiki/verifier.py (existing module — MODIFY)
  Preceded by: BATCH-123 (created WikiVerifier)
  No blocking external dependencies.

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-09 (BATCH-130 close)
  Batches since update:    0
  Reconciliation audit:    N/A (< 5 batches)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,361
  Expected delta:                  +8
  Expected total at Batch close:   2,369

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Add LLM Verification Path + Prompt Template
  Priority:          Critical
  Description:       Modify WikiVerifier to use LLM-based claim verification.
                     Add _verify_claim_with_llm() method that calls
                     provider.complete() with the verification prompt.
                     The verify() method should:
                     1. If provider exists, use LLM for each claim
                     2. If LLM fails for a claim, fall back to keyword overlap
                     3. If provider is None, use keyword overlap for all
                     4. Aggregate into quality_score and unsupported_claims

                     Create the prompt template at
                     wiki/prompts/wiki_verification.md with explicit
                     closed-book instruction (HB-02).

                     Rename _claim_supported → _claim_supported_keyword.
                     Keep the method for fallback use.

  Files in scope:
    - backend/pipeline/wiki/verifier.py (MODIFY — add LLM path)
    - backend/pipeline/wiki/prompts/wiki_verification.md (NEW — prompt)
  Depends on:        None
  Required Tests:
    | Test ID          | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-----------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-131-01-01   | unit | _verify_claim_with_llm returns dict  | Returns str or None           | Mock provider returns non-dict         | Result has "supported" and "reasoning" keys |
    | TEST-131-01-02   | unit | LLM path produces higher quality     | Same score as keyword         | Use mock that returns supported=true   | quality_score > keyword-only score   |
    | TEST-131-01-03   | unit | Fallback to keyword on LLM failure   | Crash or empty result         | Mock provider raises RuntimeError      | Returns WikiEntry with keyword score  |
    | TEST-131-01-04   | unit | Fallback to keyword when provider=None | Crash                      | Instantiate with provider=None         | Returns WikiEntry with keyword score  |
    | TEST-131-01-05   | unit | Prompt template exists (HB-02)       | File missing                  | Delete prompt file                     | Path exists, contains "source text" and "ONLY" |
    | TEST-131-01-06   | unit | Deep copy — original wiki unchanged (HB-03) | Original mutated          | Verify original quality_score==0 after | assert original.quality_score == 0   |
  Acceptance Criteria:
    AC-01: _verify_claim_with_llm returns {"supported": bool, "reasoning": str}
    AC-02: verify() uses LLM when provider exists, keyword when not
    AC-03: Falls back gracefully on LLM failure (HB-01)
    AC-04: Prompt template exists with closed-book instruction (HB-02)
    AC-05: Original wiki entry is not modified (HB-03)
    AC-06: Existing BATCH-123 tests still pass (backward compatible)
  AC-to-Test Traceability: AC-01→TEST-131-01-01, AC-02→TEST-131-01-02+04, AC-03→TEST-131-01-03, AC-04→TEST-131-01-05, AC-05→TEST-131-01-06, AC-06→TEST-131-02-01

TASK-02: Quality + Adversarial Tests
  Priority:          High
  Description:       Write quality tests that verify the LLM verification
                     produces semantically correct results, not just
                     "doesn't crash" tests.

                     Quality test: Create a wiki with a supported claim
                     and an intentionally wrong claim. Verify the LLM
                     flags the wrong claim and supports the correct one.

                     Adversarial test: Create a wiki where the "proposed_method"
                     is fabricated (not in source text). Verify it's flagged.

                     Backward compatibility: Run existing BATCH-123 tests
                     to confirm nothing broke.
  Files in scope:
    - backend/tests/test_pipeline/test_batch131_wiki_verifier_deep.py (NEW)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-----------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-131-02-01   | integ| Existing B123 tests still pass       | Regression                   | Run test_batch123 suite               | 8/8 pass                             |
    | TEST-131-02-02   | qual | LLM flags intentionally wrong claim  | Wrong claim passes            | Wiki claims "quantum" method; source says "neural network" | "quantum" in unsupported_claims |
    | TEST-131-02-03   | qual | LLM supports correct claim          | Correct claim flagged         | Wiki claims "Transformer"; source describes Transformer | claim NOT in unsupported_claims |

  Acceptance Criteria:
    AC-01: All existing BATCH-123 tests pass (backward compatible)
    AC-02: LLM flags an intentionally fabricated claim
    AC-03: LLM does NOT flag a correct, source-grounded claim
  AC-to-Test Traceability: AC-01→TEST-131-02-01, AC-02→TEST-131-02-02, AC-03→TEST-131-02-03

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All 9 new tests pass (6 TASK-01 + 3 TASK-02)
  BAC-02: WikiVerifier uses LLM when provider is available
  BAC-03: WikiVerifier falls back to keyword overlap without crashing (HB-01)
  BAC-04: Prompt template enforces closed-book verification (HB-02)
  BAC-05: Original wiki entry never modified (HB-03)
  BAC-06: All 8 existing BATCH-123 tests still pass
  BAC-07: Documents archived under /docs/aiv/BATCH-131/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
[To be completed after Review Report]
═══════════════════════════════════════════════════════════
```
