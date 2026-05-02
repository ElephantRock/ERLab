# BATCH-38 BLUEPRINT — Gap Data Persistence & Truth Values

**Batch ID:** BATCH-38  
**Blueprint Version:** 1.0  
**Cycle Mode:** STANDARD  
**Lead Programmer:** Lead Agent  
**Date Issued:** 2026-05-02  

---

## BATCH GOAL

Eliminate data loss in gap persistence by persisting TruthValue fields,
related_clusters, and ClusterReport to the database, enabling faithful
roundtrip reconstruction of ResearchGap objects.

---

## SCOPE STATEMENT

**What the code MUST do:**
1. Add `truth_frequency` (Float, default=0.5), `truth_confidence` (Float, default=0.5), `truth_evidence_count` (Integer, default=0) columns to `research_gaps` table via ResearchGapDB model
2. Add `related_clusters` (Text, nullable, JSON array string) column to `research_gaps`
3. Add `cluster_report_json` (Text, nullable, JSON object string) column to `pipeline_runs`
4. Update `persist_gaps()` in `backend/pipeline/persistence.py` to write truth columns + related_clusters when ResearchGap has truth data
5. Add `persist_cluster_report()` method to PipelinePersistence to write cluster_report_json
6. Update `load_gaps()` in `backend/pipeline/persistence.py` to reconstruct ResearchGap with truth and related_clusters
7. Create Alembic migration `002_gap_enrichment.py`

**What the code MUST NOT do:**
- Modify any frontend files
- Change the /gaps API response shape (that's BATCH-39)
- Remove or rename any existing database columns
- Alter the pipeline stage execution flow

---

## HARD BOUNDARIES

- **HB-01:** All new columns MUST have DEFAULT values so existing rows remain valid without a data migration
- **HB-02:** Alembic upgrade MUST use batch mode (`render_as_batch=True` already configured in `alembic/env.py`)
- **HB-03:** `load_gaps()` reconstruction MUST produce ResearchGap objects with truth and related_clusters matching what was persisted (roundtrip fidelity)
- **HB-04:** No existing test may break — baseline is 1,428 backend + 286 frontend = 1,714

---

## DATA MODELS

### Current ResearchGapDB (backend/db/models.py)
```
__tablename__ = "research_gaps"
Columns:
  id: int PK autoincrement
  title: Text
  description: Text (default="")
  gap_type: String(50) (default="")
  confidence: Float (default=0.5)
  potential_impact: Text (default="")
  pipeline_run_id: int FK nullable → pipeline_runs.id
  pipeline_run: relationship
  created_at: DateTime
Indexes: ix_research_gaps_pipeline_run_id, ix_research_gaps_confidence
```

### New columns to add to ResearchGapDB:
```
truth_frequency: Float, default=0.5
truth_confidence: Float, default=0.5
truth_evidence_count: Integer, default=0
related_clusters: Text, nullable (JSON array string, e.g. "[1,3,5]")
```

### Current PipelineRun (backend/db/models.py)
```
__tablename__ = "pipeline_runs"
Columns: id, status, domain, config_json, error_message, session_id,
         current_stage, stages_completed, created_at, completed_at
Relationships: ideas, gaps
```

### New column to add to PipelineRun:
```
cluster_report_json: Text, nullable (JSON object string)
```

### Pipeline ResearchGap model (backend/pipeline/gap_analysis/models.py)
```python
class ResearchGap(BaseModel):
    title: str
    description: str
    gap_type: str = ""
    related_clusters: list[int] = Field(default_factory=list)
    potential_impact: str = ""
    confidence: float = 0.5
    truth: TruthValue = Field(default_factory=TruthValue.initial)
```

### TruthValue (backend/pipeline/knowledge/truth.py)
```python
class TruthValue(BaseModel):
    frequency: float = 0.5
    confidence: float = 0.5
    evidence_count: int = 0
    propagation_debt: float = 0.0
```

### Current persistence (backend/pipeline/persistence.py)
- `persist_gaps(result, db_run_id)` — writes title, description, gap_type, confidence, potential_impact, pipeline_run_id. Does NOT write truth or related_clusters.
- `load_gaps(run_db_id)` — reconstructs ResearchGap with title, description, gap_type, confidence, potential_impact only. Does NOT reconstruct truth or related_clusters.
- `_session()` context manager used by load_gaps/load_ideas (note: `create_run_record` and `persist_*` use their own `get_session()` imports)

---

## AUTHORITY RULES

- **AR-01:** Only the persistence layer (PipelinePersistence) may write to the database. The pipeline stage must not write to ResearchGapDB directly.
- **AR-02:** Truth values are read-only in the API (BATCH-39 will expose them, but no endpoint may modify them).

---

## DEPENDENCY MAP

- **Depends on:** BATCH-29 (Alembic setup — already complete, 001_initial.py exists)
- **Blocks:** BATCH-39, BATCH-40, BATCH-41, BATCH-42, BATCH-43

---

## TEST BASELINE

- Baseline at Blueprint issuance: 1,428 backend (asyncio) + 286 frontend = 1,714
- Expected delta: +8 backend tests
- Expected total at Batch close: 1,722

---

## TASK LIST

### TASK-01: Database Schema Migration

**Description:** Add 4 new columns to ResearchGapDB and 1 new column to PipelineRun in `backend/db/models.py`. Create Alembic migration `alembic/versions/002_gap_enrichment.py`. Verify upgrade and downgrade.

**Files in scope:**
- `backend/db/models.py`
- `alembic/versions/002_gap_enrichment.py` (new)

**Depends on:** None

**Required Tests:**

| Test ID | Type | Pass Criteria |
|:---|:---|:---|
| TEST-38-01-01 | unit | Migration upgrade creates all 5 new columns |
| TEST-38-01-02 | unit | Migration downgrade removes all 5 new columns |
| TEST-38-01-03 | unit | Existing data survives migration roundtrip |

**Acceptance Criteria:**
- AC-01-01: `alembic upgrade head` succeeds without error
- AC-01-02: All 5 new columns have DEFAULT values per HB-01
- AC-01-03: `alembic downgrade -1` succeeds

### TASK-02: Update Persistence Layer

**Description:** Update `persist_gaps()` to write truth_frequency, truth_confidence, truth_evidence_count, related_clusters. Add `persist_cluster_report()` method. Update `load_gaps()` to reconstruct ResearchGap with TruthValue and related_clusters.

**Files in scope:**
- `backend/pipeline/persistence.py`

**Depends on:** TASK-01

**Required Tests:**

| Test ID | Type | Pass Criteria |
|:---|:---|:---|
| TEST-38-02-01 | unit | persist_gaps writes truth_frequency to DB |
| TEST-38-02-02 | unit | persist_gaps writes related_clusters as JSON to DB |
| TEST-38-02-03 | unit | persist_cluster_report writes cluster_report_json to PipelineRun |
| TEST-38-02-04 | unit | load_gaps reconstructs ResearchGap with truth values |
| TEST-38-02-05 | integration | Full roundtrip: persist → load → assert equality per HB-03 |

**Acceptance Criteria:**
- AC-02-01: persist_gaps() populates all truth columns when ResearchGap has truth
- AC-02-02: load_gaps() returns ResearchGap objects with truth matching what was persisted
- AC-02-03: All existing 1,428 backend tests still pass per HB-04

---

## BATCH-LEVEL ACCEPTANCE CRITERIA

- BAC-01: All 5 new database columns exist with correct types and defaults
- BAC-02: load_gaps() roundtrip fidelity confirmed by test TEST-38-02-05
- BAC-03: CHANGELOG.md updated with BATCH-38 entry
- BAC-04: All documents archived under /docs/aiv/BATCH-38/

---

## SLA Confirmation (Lead Response to CHK-02 FLAG-01)

Per AIV §3.3 defaults:
- **Review SLA:** 30 min
- **Execution SLA per Task:** 60 min
- **Partial Sign-Off SLA:** 15 min
- **Task Sequencing:** Sequential

## LEAD RESPONSE TO REVIEW REPORT

**Review Report:** docs/aiv/BATCH-38/REVIEW-REPORT.md (206 lines)
**Verdict:** CONDITIONALLY APPROVE
**Flags:** 1 LOW (CHK-02 — missing SLA fields, resolved above)

### Lead Decisions:
- **FLAG-01 (CHK-02):** ACCEPTED — SLA defaults confirmed per §3.3 above.
- **Observation 1 (`_session()`):** ACKNOWLEDGED — Assistant should normalize load_gaps() to use `get_session()` directly, recording as Adaptation in Task Report.
- **Observation 2 (`propagation_debt`):** ACKNOWLEDGED — ephemeral runtime value, correctly excluded from persistence.
- **Observation 3 (`truth_confidence` vs `confidence`):** ACKNOWLEDGED — semantically distinct, no collision.

### Lead Authorization:
The Blueprint is cleared for execution. All flags resolved. The Assistant may proceed.
