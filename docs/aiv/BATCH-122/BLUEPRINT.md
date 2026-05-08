# BATCH-122 BLUEPRINT — Claim Storage & Query Layer

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-122
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
Create a ClaimStore service that persists extracted claims in SQLite and provides
query methods: store_claims, get_claims_by_paper, find_similar_claims (via vector
embedding), get_claims_by_type. Add a claims table to the database schema.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add research_claims table to database models (SQLAlchemy)
  - Create ClaimStore class with CRUD operations
  - Embed claim descriptions for vector similarity search
  - Support batch storage from ClaimExtractor.extract_batch()
  - Wire into the existing database session pattern

What the code MUST NOT do:
  - Must NOT modify ClaimExtractor (B121 code is frozen)
  - Must NOT modify orchestrator.py or stages.py (that's B128)
  - Must NOT add API routes (that's a future batch)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m pytest backend/tests/test_pipeline/test_batch122_claim_store.py -v --tb=short 2>&1 | tail -5

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: store_claims MUST be idempotent — calling twice with same
         paper_id must not create duplicates (upsert behavior).
  HB-02: find_similar_claims MUST NOT crash when the vector store
         is empty — return [] gracefully.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

  research_claims table (SQLAlchemy):
    - id:              Integer, PK, autoincrement
    - claim_id:        String(36), unique, not null  (UUID from Claim)
    - claim_type:      String(20), not null
    - title:           String(500), not null
    - description:     Text, not null
    - source_paper_id: String(256), not null, indexed
    - source_section:  String(50)
    - confidence:      Float, default 0.5
    - method_name:         String(200), nullable
    - method_category:     String(50), nullable
    - dataset:             String(200), nullable
    - metric:              String(100), nullable
    - value:               String(100), nullable
    - baseline_method:     String(200), nullable
    - baseline_value:      String(100), nullable
    - limitation_category: String(50), nullable
    - acknowledged:        Boolean, nullable
    - feasibility:         String(20), nullable
    - potential_impact:    String(20), nullable
    - compared_to:         String(200), nullable
    - relationship:        String(50), nullable
    - extra_json:          Text, nullable  (constraints + other dicts as JSON)
    - created_at:          DateTime, default utcnow

  ClaimStore:
    - __init__(self, session: Session, embedding_service=None)
    - store_claims(self, claims: list[Claim]) -> int (count stored)
    - get_claims_by_paper(self, paper_id: str) -> list[Claim]
    - get_claims_by_type(self, claim_type: ClaimType) -> list[Claim]
    - find_similar_claims(self, query: str, top_k: int = 10) -> list[tuple[Claim, float]]
    - delete_claims_by_paper(self, paper_id: str) -> int (count deleted)
    - count_claims(self) -> int

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  A-01: ClaimStore is the SOLE authority for claim persistence.
         No raw SQL outside ClaimStore.
  A-02: claim_type stored as string, validated against ClaimType enum on read.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  BATCH-121: Claim, ClaimType, ClaimExtractor (models + extractor)
  External:  backend/db/database.py (Session, engine)
  External:  backend/db/models.py (existing table patterns)
  External:  backend/pipeline/knowledge/embedding_service.py (optional, for vector search)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-07 (BATCH-120 close)
  Batches since update:    1 (B121)
  Reconciliation audit:    N/A (< 5 batches)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,304
  Expected delta:                  +12
  Expected total at Batch close:   2,316

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: ResearchClaims Database Model + Migration
  Priority:          Critical
  Description:       Add ResearchClaim SQLAlchemy model to backend/db/models.py
                     following the existing pattern. Create Alembic migration
                     for the new table.
  Files in scope:
    - backend/db/models.py (MODIFY — add ResearchClaim model)
    - alembic/versions/007_research_claims.py (NEW — migration)
  Depends on:        None
  Required Tests:
    | Test ID          | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-----------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-122-01-01   | unit | ResearchClaim model has all fields   | Column missing                | Create model instance                 | No AttributeError on any field       |
    | TEST-122-01-02   | unit | ResearchClaim.claim_id is unique     | Duplicate claim_id inserted   | Insert same claim_id twice            | IntegrityError on second insert      |
  Acceptance Criteria:
    AC-01: ResearchClaim model exists with all fields from schema
    AC-02: claim_id column has unique constraint
  AC-to-Test Traceability: AC-01→TEST-122-01-01, AC-02→TEST-122-01-02

TASK-02: ClaimStore Service
  Priority:          Critical
  Description:       Create backend/pipeline/claims/store.py with ClaimStore
                     class. Implements all query methods. Uses SQLAlchemy session.
                     store_claims converts Claim dataclass → ResearchClaim ORM.
                     get_claims_by_* converts ResearchClaim → Claim dataclass.
                     find_similar_claims uses embedding_service if available,
                     else falls back to keyword matching on description.
  Files in scope:
    - backend/pipeline/claims/store.py (NEW)
    - backend/pipeline/claims/__init__.py (MODIFY — add ClaimStore export)
    - backend/tests/test_pipeline/test_batch122_claim_store.py (NEW — all tests)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-----------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-122-02-01   | unit | store_claims persists claims to DB   | Claims not found after store  | Store 3 claims, query by paper_id     | len(get_claims_by_paper(pid)) == 3   |
    | TEST-122-02-02   | unit | store_claims is idempotent (HB-01)   | Duplicate claims on re-store  | Store same claims twice               | count unchanged after second call    |
    | TEST-122-02-03   | unit | get_claims_by_type filters correctly | Returns wrong type            | Store METHOD + RESULT, filter METHOD  | All returned claims have type METHOD |

    | TEST-122-02-05   | unit | delete_claims_by_paper removes claims | Claims remain after delete    | Store then delete                     | get_claims_by_paper returns []       |
    | TEST-122-02-06   | unit | count_claims returns total           | Wrong count                   | Store 5 claims                        | count_claims() == 5                  |
    | TEST-122-02-07   | integ| Round-trip: Claim → DB → Claim       | Data loss in conversion       | Create Claim, store, retrieve         | All fields match original            |
    | TEST-122-02-08   | unit | find_similar_claims success path      | Returns [] on populated DB    | Store claims, search relevant query   | Non-empty results with similarity > 0 |
    | TEST-122-02-09   | unit | Keyword fallback when no embeddings   | Crashes without embedding_svc | Call with embedding_service=None      | Returns results via keyword match     |
    | TEST-122-02-10   | unit | Invalid claim_type raises on read     | Silent corruption             | Store invalid type string, read back  | ValueError raised (A-02)             |
    | TEST-122-02-11   | unit | find_similar_claims returns [] on empty DB (HB-02) | Crash on empty | Call on fresh DB | Returns [] without error |
  Acceptance Criteria:
    AC-01: store_claims persists and retrieves claims correctly
    AC-02: store_claims is idempotent (HB-01)
    AC-03: find_similar_claims handles empty DB (HB-02)
    AC-04: Round-trip preserves all fields
    AC-05: find_similar_claims returns relevant results on populated DB
    AC-06: Keyword fallback works when embedding_service=None
    AC-07: Invalid claim_type string raises ValueError (A-02)
  AC-to-Test Traceability: AC-01→TEST-122-02-01, AC-02→TEST-122-02-02, AC-03→TEST-122-02-11, AC-04→TEST-122-02-07, AC-05→TEST-122-02-08, AC-06→TEST-122-02-09, AC-07→TEST-122-02-10

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All 12 new tests pass
  BAC-02: ClaimStore with full CRUD + vector search
  BAC-03: No modifications to claims/models.py or claims/extractor.py
  BAC-04: Documents archived under /docs/aiv/BATCH-122/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID: REVIEW-BATCH-122-2026-05-09
Review Cycle: 1
Reviewer: 260509-witty-puma

FLAGS RESOLVED:
  CHK-13/23 (MEDIUM): Added TEST-122-02-08 (find_similar_claims success path),
    TEST-122-02-09 (keyword fallback), TEST-122-02-10 (invalid claim_type).
    Removed old TEST-122-02-04, renumbered to TEST-122-02-11.
  CHK-14/17 (LOW): Reconciled test count: 2+10=12 tests total.
    Updated delta +7→+12, total 2,311→2,316, BAC-01 9→12.
  CHK-19 advisory: source_paper_id widened String(100)→String(256) to match Paper model.
  NOTE: ClaimStore methods will be async to match EmbeddingService.embed_single() contract.

Lead Decision: [x] ACCEPT
Blueprint v1.1 corrections applied. 4 flags resolved. PROCEED.
Lead Sign: ivory-wolf — 2026-05-09
═══════════════════════════════════════════════════════════
```
