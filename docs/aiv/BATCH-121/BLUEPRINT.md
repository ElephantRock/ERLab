# BATCH-121 BLUEPRINT — Claim Extraction Engine

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-121
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-08
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Create a ClaimExtractor that uses structured_output to decompose paper
abstracts + wiki entries into typed claims: method, result, limitation,
future_work, and comparison. Each claim has a defined JSON schema.
This is the keystone of Phase 9 — all downstream batches (wiki enrichment,
contradiction detection, method-problem gaps) depend on structured claims.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Define Claim dataclass with typed fields (type, title, description,
    method_name, dataset, metric, value, confidence, source_paper_id)
  - Define ClaimType enum: METHOD, RESULT, LIMITATION, FUTURE_WORK, COMPARISON
  - Create ClaimExtractor class that takes paper text + wiki JSON
    and returns list[Claim] via structured LLM output
  - Create a claim extraction prompt that demands closed-book grounding:
    "Only extract claims explicitly stated in the paper text. Do NOT infer."
  - Wire ClaimExtractor into a standalone stage that can be called from
    the orchestrator (but do NOT modify orchestrator.py yet — that's B122)
  - Validate extraction quality against 5 gold-standard papers with known claims

What the code MUST NOT do:
  - Must NOT modify existing pipeline stages or orchestrator (HB-03)
  - Must NOT store claims in database (that's B122)
  - Must NOT generate wiki entries (that's B123)
  - Must NOT call external APIs beyond the configured LLM provider

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m pytest backend/tests/test_pipeline/test_batch121_claim_extraction.py -v --tb=short 2>&1 | tail -5

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Claim extraction failure MUST NOT crash the calling code.
         If LLM returns invalid JSON, return empty list + log warning.
  HB-02: Every extracted claim MUST have source_paper_id tracing it to
         the originating paper. No orphan claims allowed.
  HB-03: No modifications to backend/pipeline/orchestrator.py or
         backend/pipeline/stages.py. ClaimExtractor is a standalone module.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

  ClaimType (enum):
    - METHOD:       Claims about a proposed method (architecture, training, loss)
    - RESULT:       Empirical results (dataset, metric, value, baseline)
    - LIMITATION:   Acknowledged or identified limitations
    - FUTURE_WORK:  Suggested future research directions
    - COMPARISON:   How it relates to other work (improves_on, contradicts)

  Claim (dataclass):
    - claim_id:         str (UUID auto-generated)
    - claim_type:       ClaimType
    - title:            str (one-line summary)
    - description:      str (detailed description)
    - source_paper_id:  str (paper.arxiv_id or paper.id)
    - source_section:   str (abstract | method | results | discussion)
    - confidence:       float (0.0-1.0, extractor's confidence in accuracy)

    # METHOD-specific fields (None for other types):
    - method_name:      str | None
    - method_category:  str | None  (architecture|training|loss|data|inference)
    - constraints:      dict | None (max_seq_length, parameter_count, gpu_memory)

    # RESULT-specific fields (None for other types):
    - dataset:          str | None
    - metric:           str | None
    - value:            str | None  (kept as string to handle "95.2%", "0.87", etc.)
    - baseline_method:  str | None
    - baseline_value:   str | None

    # LIMITATION-specific fields:
    - limitation_category: str | None (scale|generalization|compute|data|fairness)
    - acknowledged:     bool | None  (acknowledged by authors?)

    # FUTURE_WORK-specific fields:
    - feasibility:      str | None (high|medium|low)
    - potential_impact:  str | None (high|medium|low)

    # COMPARISON-specific fields:
    - compared_to:      str | None  (paper or method name)
    - relationship:     str | None  (improves_on|different|contradicts|complements)

  ClaimExtractor:
    - __init__(self, provider: LLMProvider)
    - extract(self, paper_text: str, wiki: dict | None = None) -> list[Claim]
    - extract_batch(self, papers: list[dict]) -> dict[str, list[Claim]]
       (maps paper_id -> claims)

  File layout:
    backend/pipeline/claims/
      __init__.py          — re-export Claim, ClaimType, ClaimExtractor
      models.py            — Claim, ClaimType dataclasses
      extractor.py         — ClaimExtractor class with LLM structured_output
      prompts/
        claim_extraction.md — extraction prompt template

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  A-01: ClaimType enum is the SOLE authority for claim categorization.
         No string-based claim types allowed.
  A-02: Claim.confidence is the extractor's confidence, NOT the paper's
         claim confidence. Field is required, default 0.5 if uncertain.
  A-03: Only ClaimExtractor may create Claim objects. External code
         must call extract() or extract_batch().

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  External: backend/providers/base.py (LLMProvider.structured_output)
  External: backend/pipeline/literature/models.py (Paper model)
  Blocks:   BATCH-122 (claim storage), BATCH-125 (contradiction),
             BATCH-126 (method-problem matrix), BATCH-129 (connections)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-07 (BATCH-120 close)
  Batches since update:    0
  Reconciliation audit:    N/A (< 5 batches)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,292
  Expected delta:                  +11
  Expected total at Batch close:   2,303

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Claim Data Models + ClaimType Enum
  Priority:          Critical
  Description:       Create backend/pipeline/claims/ package with models.py
                     defining ClaimType enum and Claim dataclass. All typed
                     fields must have defaults of None for non-applicable types.
                     Claim.claim_id auto-generates UUID if not provided.
  Files in scope:
    - backend/pipeline/claims/__init__.py (NEW — re-exports)
    - backend/pipeline/claims/models.py (NEW — ClaimType, Claim)
  Depends on:        None
  Required Tests:
    | Test ID          | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-----------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-121-01-01   | unit | ClaimType has 5 members              | Missing enum value            | `ClaimType("METHOD")` if not member   | assert len(ClaimType) == 5            |
    | TEST-121-01-02   | unit | Claim dataclass accepts all fields   | TypeError on optional fields  | Omit all optional fields              | Claim(claim_type=ClaimType.METHOD, title="T", description="D", source_paper_id="P1") succeeds |
    | TEST-121-01-03   | unit | Claim auto-generates claim_id        | Missing claim_id              | Create Claim without claim_id param   | assert claim.claim_id is not None and len(claim.claim_id) > 0 |
  Acceptance Criteria:
    AC-01: ClaimType has exactly 5 members: METHOD, RESULT, LIMITATION, FUTURE_WORK, COMPARISON
    AC-02: Claim can be constructed with only required fields (claim_type, title, description, source_paper_id)
    AC-03: claim_id auto-generates as UUID if not provided
  AC-to-Test Traceability: AC-01→TEST-121-01-01, AC-02→TEST-121-01-02, AC-03→TEST-121-01-03

TASK-02: ClaimExtractor with LLM Structured Output
  Priority:          Critical
  Description:       Create ClaimExtractor class that uses provider.structured_output
                     to extract claims from paper text. Include the claim extraction
                     prompt template at backend/pipeline/claims/prompts/claim_extraction.md.
                     The prompt demands:
                     1. ONLY extract claims explicitly stated in the text (closed-book)
                     2. Each claim has a type from ClaimType
                     3. Fill type-specific fields, leave others as null
                     4. Return as {"claims": [...]} JSON
                     On JSON parse failure, return [] and log warning (HB-01).
                     Every claim gets source_paper_id from the input (HB-02).
  Files in scope:
    - backend/pipeline/claims/extractor.py (NEW — ClaimExtractor)
    - backend/pipeline/claims/prompts/claim_extraction.md (NEW — prompt)
    - backend/pipeline/claims/__init__.py (MODIFY — add re-exports)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-----------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-121-02-01   | unit | ClaimExtractor.__init__ accepts LLMProvider | TypeError on wrong type | Pass None as provider                 | TypeError raised with clear message   |
    | TEST-121-02-02   | unit | extract() returns list[Claim] from mock LLM | Empty list on valid input    | Mock LLM returns valid JSON           | len(result) > 0, all are Claim instances |
    | TEST-121-02-03   | unit | extract() returns [] on LLM failure (HB-01) | Exception propagates          | Mock LLM raises Exception             | No exception, returns [], warning logged |
    | TEST-121-02-04   | unit | extract() returns [] on invalid JSON (HB-01) | JSONDecodeError propagates   | Mock LLM returns "not json"           | No exception, returns [], warning logged |
    | TEST-121-02-05   | unit | All claims have source_paper_id (HB-02)    | Missing source_paper_id      | Extract from text without paper_id    | All claims have non-None source_paper_id |
    | TEST-121-02-06   | unit | Prompt template exists with closed-book     | Missing file or instruction   | Delete prompt file                    | assert Path(prompt_path).exists() and "closed-book" in Path(prompt_path).read_text() |
  Acceptance Criteria:
    AC-01: ClaimExtractor.extract() returns list[Claim] from valid paper text
    AC-02: On LLM failure or invalid JSON, returns [] without crashing (HB-01)
    AC-03: Every returned Claim has source_paper_id set (HB-02)
    AC-04: Prompt template exists and contains "closed-book" instruction
  AC-to-Test Traceability: AC-01→TEST-121-02-02, AC-02→TEST-121-02-03+04, AC-03→TEST-121-02-05, AC-04→TEST-121-02-06

TASK-03: Gold-Standard Validation
  Priority:          High
  Description:       Create a test that validates claim extraction against
                     5 known papers with pre-defined expected claims.
                     Use the existing papers in the test database or
                     create Paper objects with known abstracts.
                     Assert that:
                     - ≥80% of expected claims are extracted (recall)
                     - ≥90% of extracted claims are accurate (precision)
                     - All 5 claim types are represented across the 5 papers
                     This test validates the strategic bet: "LLM can extract
                     structured claims from abstracts with >80% coverage."
  Files in scope:
    - backend/tests/test_pipeline/test_batch121_claim_extraction.py (NEW — all tests)
  Depends on:        TASK-02
  Required Tests:
    | Test ID          | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-----------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-121-03-01   | integ| ≥3 claim types present across 5 papers | Only 1-2 types detected       | Use 5 diverse abstracts               | assert len({c.claim_type for c in all_claims}) >= 3 |
    | TEST-121-03-02   | integ| METHOD claims have method_name filled  | method_name is None            | Extract from method paper abstract    | assert any(c.method_name for c in method_claims) |
    | TEST-121-03-03   | integ| RESULT claims have dataset + metric    | Fields empty                  | Extract from empirical paper abstract | assert any(c.dataset and c.metric for c in result_claims) |
  Acceptance Criteria:
    AC-01: At least 3 distinct ClaimTypes extracted across test papers
    AC-02: METHOD claims have method_name populated
    AC-03: RESULT claims have dataset and metric populated
  AC-to-Test Traceability: AC-01→TEST-121-03-01, AC-02→TEST-121-03-02, AC-03→TEST-121-03-03

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All 11 new tests pass
  BAC-02: backend/pipeline/claims/ package exists with __init__.py, models.py, extractor.py
  BAC-03: ClaimExtractor.extract() works with mock and real LLM providers
  BAC-04: No modifications to orchestrator.py or stages.py (HB-03)
  BAC-05: Documents archived under /docs/aiv/BATCH-121/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID: REVIEW-BATCH-121-2026-05-09
Review Cycle: 1
Reviewer: 260509-focal-ruby

FLAGS RESOLVED:
  CHK-11 (MAJOR): Added TEST-121-02-06 to TASK-02 test table.
    Prompt template file existence + closed-book instruction verified.
  CHK-12 (MAJOR): Reconciled test count.
    TASK-01: 3 tests, TASK-02: 6 tests, TASK-03: 3 tests = 11 total.
    Updated: delta +8→+11, expected total 2,300→2,303, BAC-01 8→11.

Lead Decision: [x] ACCEPT
Blueprint v1.1 corrections applied. 2 flags resolved. PROCEED.
Lead Sign: ivory-wolf — 2026-05-09
═══════════════════════════════════════════════════════════
```
