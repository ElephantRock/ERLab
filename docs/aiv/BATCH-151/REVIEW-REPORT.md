REVIEW REPORT
═══════════════════════════════════════════════════════════

Batch ID:            BATCH-151
Blueprint Version:   1.0
Cycle Mode:          STANDARD
Reviewer:            Craft Agent (AI Reviewer Instance)
Timestamp:           2026-05-11T00:33:00+03:00
Review Cycle:        1
Report ID:           REVIEW-BATCH-151-2026-05-11

═══════════════════════════════════════════════════════════
CHECKLIST RESULTS
═══════════════════════════════════════════════════════════

───────────────────────────────────────────────────────────
CHK-00 · CYCLE MODE VERIFICATION
───────────────────────────────────────────────────────────

PASS — STANDARD cycle is correct.

The batch has 4 tasks (>1), modifies existing source files (TASK-04 modifies 4
files), and declares 5 Hard Boundaries. It does not qualify for Simplified
cycle. The declared STANDARD mode is consistent with actual conditions.

Document count expectation: 3 + (2 × 4) + 1 = 12 documents.
(BLUEPRINT, REVIEW-REPORT, 4×(REPORT + PARTIAL), CERT)

───────────────────────────────────────────────────────────
CHK-01 · BATCH GOAL CLARITY AND DEPLOYABILITY
───────────────────────────────────────────────────────────

PASS — The Batch Goal is a single, clear, deployable outcome:

> "Ship a one-command `docker compose up` deployment that starts the Elephant
> Rock backend (FastAPI), frontend (React/Vite), and SQLite database in
> production-ready configuration, plus add AI-generated honesty labeling to
> all exported proposals."

This is deployable and testable. BAC-01 provides a concrete falsification
(`docker compose up --build` must produce a running system within 120 seconds).

BAC-01 through BAC-07 cover: Docker deployment (BAC-01), test regression
(BAC-02), CHANGELOG (BAC-03), document archival (BAC-04), STATE.md update
(BAC-05), dev workflow warnings (BAC-06), and secrets (BAC-07).

SUB-FLAG 01A (LOW): Batch Goal mentions "SQLite database" but TASK-03 does not
include a SQLite container service. SQLite is file-based and runs inside the
backend container — this is architecturally fine, but the Goal's phrasing
could be read as "starts… SQLite database" as a separate container. Not
blocking, but the Assistant may need clarification.

───────────────────────────────────────────────────────────
CHK-02 · SCOPE BOUNDARIES (MUST DO / MUST NOT DO)
───────────────────────────────────────────────────────────

PASS with FLAGS.

**MUST DO** — 10 items covering both Docker infrastructure (8 items) and AI
honesty badge (2 items). Adequately specific.

**MUST NOT DO** — 5 items. Adequately constraining.

**FLAG-02A (HIGH):** SCOPE item states:
> "MUST NOT add any new Python or npm dependencies (use existing
> `requirements.txt` and `package.json` as-is)"

No `requirements.txt` exists in this project. The project uses `pyproject.toml`
for all Python dependency management. The existing `Dockerfile` correctly uses
`COPY pyproject.toml ./` and `RUN pip install --no-cache-dir --prefix=/install .`.
This reference will mislead the Assistant.

**FLAG-02B (MEDIUM):** SCOPE states exported proposals include "Markdown, PDF,
BibTeX, LaTeX" but HB-04 and TASK-04 only cover "Markdown, LaTeX, BibTeX"
— **PDF is listed in SCOPE but omitted from the Hard Boundary and task scope.**
See CHK-03 and CHK-05 for cascade effects.

**FLAG-02C (MEDIUM):** SCOPE declares `docker-compose.yml` and `nginx.conf` as
files to be provided, but both already exist:

| File | Current State | Blueprint Treatment |
|:-----|:-------------|:-------------------|
| `docker-compose.yml` | EXISTS — PostgreSQL + Redis + app + nginx | Implicitly treated as NEW |
| `Dockerfile` | EXISTS — multi-stage, uses pyproject.toml | Replaced by `Dockerfile.backend` (NEW) |
| `nginx/nginx.conf` | EXISTS — proxies `/api/`, `/health`, WebSocket, SSE | Listed in TASK-02 as `nginx.conf (NEW)` |

The SCOPE should explicitly state these files are being **replaced/simplified**
(from PostgreSQL+Redis to SQLite single-container). Without this declaration,
the Assistant may not realize the existing Docker infrastructure needs to be
dismantled, and the Lead cannot verify whether removing Redis/Postgres services
counts as "modifying existing… core business logic" (which is a MUST NOT).

**FLAG-02D (LOW):** MUST DO item says "docker-compose.yml MUST expose port 3000
(frontend) and 8000 (backend API)." The existing `docker-compose.yml` exposes
port 8080 (nginx). The Blueprint is changing the architecture from
(app+nginx+frontend) to (backend+frontend), which is fine, but worth noting as
a deliberate change.

───────────────────────────────────────────────────────────
CHK-03 · HARD BOUNDARY FALSIFIABILITY
───────────────────────────────────────────────────────────

PASS with 1 FLAG.

| HB | Falsifiable? | Assessment |
|:---|:------------|:-----------|
| HB-01 | YES — `pytest` run produces count | Test count verified at 2,480 per STATE.md and `pytest --co`. ✅ |
| HB-02 | YES — `grep -r` for secret patterns | Clear and testable. ✅ |
| HB-03 | YES — `docker compose up` + timer + container exit codes | Specific time bound (120s) and exit code check. ✅ |
| HB-04 | PARTIAL — see flag below | Missing PDF from enumeration. ⚠️ |
| HB-05 | YES — Run dev commands and check stderr for warnings | Testable. ✅ |

**FLAG-03A (MEDIUM):** HB-04 says:
> "The AI honesty badge MUST be present in every exported proposal format
> (Markdown, LaTeX, BibTeX export metadata). If any format lacks the badge,
> the boundary is violated."

PDF is listed in the SCOPE MUST-DO ("All exported proposals (Markdown, **PDF**,
BibTeX, LaTeX) MUST include an AI-generated honesty badge") but is **absent from
HB-04**. This means HB-04 is falsifiable for 3 of 4 declared formats — a scope
coverage gap that makes the boundary incomplete.

**Resolution:** Either add PDF to HB-04 (and TASK-04) or remove PDF from the
SCOPE statement.

HB-03's 120-second SLA is ambitious for a first-time `docker compose up --build`
(which must build two images from scratch including `pip install` from
pyproject.toml). Consider whether the SLA applies only to warm builds or also
cold builds.

───────────────────────────────────────────────────────────
CHK-04 · DATA MODEL ACCURACY
───────────────────────────────────────────────────────────

PASS with 2 FLAGS.

**Verified module references (file system confirmed):**

| Blueprint Reference | Exists? | Verified Path |
|:--------------------|:--------|:-------------|
| `backend.pipeline.synthesis.proposal_synthesizer.ProposalSynthesizer` | ✅ YES | Correct |
| `backend.pipeline.synthesis.fast_synthesizer.FastSynthesizer` | ✅ YES | Correct |
| `backend.api.routes.export.py` | ✅ YES | Correct (two files: `export.py` + `exports.py`) |
| `backend.pipeline.export.bibtex_exporter.py` | ✅ YES | Correct |
| `backend.pipeline.export.md_to_latex.py` | ✅ YES | Correct |
| `backend.pipeline.constants.py` | ❌ NO | Correctly marked (NEW) |
| `backend/config.py` (Lint command) | ✅ YES | Correct |

**FLAG-04A (MEDIUM):** Data Models section says:
> `backend.api.routes.export.py` — exports proposals to Markdown/PDF

The actual file header reads: *"Export API routes: download proposals as
Markdown or **BibTeX**."* PDF export is handled by a **different file**
(`exports.py`). This stale description will mislead the Assistant about which
file to modify for badge injection in PDF exports.

**FLAG-04B (LOW):** The Verified Module Map in STATE.md does not include entries
for `backend.pipeline.synthesis` or `backend.pipeline.export` — these modules
exist in the codebase but are unlisted. The Blueprint's references are accurate
against the filesystem, but future Blueprints would benefit from STATE.md
including these entries.

───────────────────────────────────────────────────────────
CHK-05 · TASK COHERENCE, INDEPENDENCE, COMPLETENESS
───────────────────────────────────────────────────────────

PASS with 3 FLAGS.

**Task coherence (one concern per task):**
- TASK-01: Backend Dockerfile + entrypoint + health — one concern ✅
- TASK-02: Frontend Dockerfile + Nginx — one concern ✅
- TASK-03: Docker Compose orchestration — one concern ✅
- TASK-04: AI honesty badge across export formats — one concern ✅

**Task independence:**
- TASK-01, TASK-02, TASK-04 are independently executable ✅
- TASK-03 depends on TASK-01 + TASK-02 ✅

**FLAG-05A (HIGH):** TASK-01 description contains **three errors** that will
cause execution failure:

> "(a) Stage 1: Install Python deps from **requirements.txt**"

No `requirements.txt` exists. The project uses `pyproject.toml`. The existing
`Dockerfile` correctly uses `COPY pyproject.toml ./` and `RUN pip install .`.
The Assistant following this instruction verbatim will produce a broken
Dockerfile.

> "(d) Health check: GET **/api/v1/health** returns 200"

The actual health endpoint is at **`/health`** (defined in `backend/api/app.py`
line 312: `@app.get("/health")`). No `/api/v1/health` route exists. The
existing `Dockerfile` and `docker-compose.yml` also reference this wrong path
— this is a pre-existing bug the Blueprint is perpetuating.

> "Files in scope: `backend/api/routes/health.py` (NEW — health check endpoint
> if not exists)"

The `/health` endpoint already exists in `backend/api/app.py`. Creating a
separate `health.py` route module is unnecessary unless the intent is to
refactor the endpoint out of `app.py`. If so, this should be explicit.

**FLAG-05B (MEDIUM):** Task Sequencing declares "Mixed (TASK-01 first, then
TASK-02/03/04 parallel)" but TASK-03 depends on both TASK-01 **and** TASK-02.
If TASK-02 and TASK-03 run in parallel, TASK-03 will start before
`Dockerfile.frontend` exists. Correct sequencing:

```
TASK-01 (backend Dockerfile) ──┐
                                ├──► TASK-03 (compose) ──► (done)
TASK-02 (frontend Dockerfile) ─┘

TASK-04 (badge) ──────────────────────────────────────────► (done, fully parallel)
```

The Blueprint should say: "TASK-01 and TASK-02 parallel, then TASK-03. TASK-04
parallel with all."

**FLAG-05C (MEDIUM):** TASK-02 lists `nginx.conf (NEW)` but the file already
exists at `nginx/nginx.conf` with a complete production configuration including
WebSocket proxying, SSE proxying, security headers, and gzip. The Blueprint
must clarify:
- Is the Assistant creating a NEW `nginx.conf` in the project root (different
  path from the existing `nginx/nginx.conf`)?
- Or replacing `nginx/nginx.conf` with a simpler version?

The existing config references `upstream backend { server app:8000; }` which
uses the service name from the current docker-compose.yml. The new config must
use whatever service name the new docker-compose.yml defines.

**File reality summary for all tasks:**

| File | Blueprint Says | Actual State | Issue? |
|:-----|:--------------|:------------|:-------|
| `Dockerfile.backend` | NEW | Does not exist | ✅ Correct |
| `backend/api/routes/health.py` | NEW (conditional) | `/health` exists in `app.py` | ⚠️ Unnecessary |
| `docker-entrypoint.sh` | NEW | Does not exist | ✅ Correct |
| `Dockerfile.frontend` | NEW | Does not exist | ✅ Correct |
| `nginx.conf` | NEW | `nginx/nginx.conf` EXISTS | ⚠️ Path conflict |
| `docker-compose.yml` | NEW | EXISTS (Postgres+Redis) | ⚠️ Must replace |
| `.env.docker` | NEW | Does not exist | ✅ Correct |
| `backend/pipeline/constants.py` | NEW | Does not exist | ✅ Correct |
| `proposal_synthesizer.py` | MODIFY | Exists | ✅ Correct |
| `fast_synthesizer.py` | MODIFY | Exists | ✅ Correct |
| `bibtex_exporter.py` | MODIFY | Exists | ✅ Correct |
| `md_to_latex.py` | MODIFY | Exists | ✅ Correct |

───────────────────────────────────────────────────────────
CHK-06 · TEST COVERAGE (6-COLUMN TABLES, T1–T6 COMPLIANCE)
───────────────────────────────────────────────────────────

PASS with 1 FLAG.

**6-column table compliance:** All tests across all 4 tasks have complete
6-column tables (Test ID, Type, Behavior Verified, Failure Mode, Falsified By,
Pass Criteria). ✅

**T1 — Falsifiability:** Every test has a specific "Falsified By" column with
a concrete code change that would break the test. ✅

**T2 — Error path / boundary coverage:**

| Task | Happy Path | Error Path | Boundary | Gap? |
|:-----|:----------|:----------|:--------|:-----|
| TASK-01 | TEST-01/02/03/04 | Implicit (build fail) | Non-root user | Missing: migration failure scenario |
| TASK-02 | TEST-01/02/03/04 | Build fail | MIME types | Adequate |
| TASK-03 | TEST-01-05 | Valid compose | Volume, depends_on | Adequate |
| TASK-04 | TEST-01-06 | None explicit | Consistency test (06) | Missing: empty badge, export failure |

TASK-01 lacks an error-path test for "Alembic migration fails" — the
entrypoint runs migrations before uvicorn, but no test verifies behavior when
`alembic upgrade head` fails.

TASK-04 has no error-path test. TEST-04-06 is a consistency test, not an
error test. Missing scenarios: what if the synthesizer returns empty output?
What if the constant is accidentally set to empty string?

**T5 — Traceability:** Every AC maps to at least one test. Every test maps to
at least one AC. No unmapped tests or uncovered ACs. ✅

**T6 — Mandatory falsification (Critical/High tasks):**

| Task | Priority | T6 Coverage |
|:-----|:--------|:-----------|
| TASK-01 | Critical | All 4 tests have "Falsified By" ✅ |
| TASK-02 | Critical | All 4 tests have "Falsified By" ✅ |
| TASK-03 | Critical | All 5 tests have "Falsified By" ✅ |
| TASK-04 | High | All 6 tests have "Falsified By" ✅ |

**FLAG-06A (MEDIUM):** TASK-04 declares 4 export format targets:
(a) ProposalSynthesizer, (b) FastSynthesizer, (c) BibTeX, (d) LaTeX.
But the SCOPE lists **PDF** as a required format. There is no test for PDF
export badge compliance. Either:
- Add TEST-151-04-07 for PDF export, or
- Remove PDF from the SCOPE statement

Additionally, the existing `markdown_exporter.py` at
`backend/pipeline/export/markdown_exporter.py` is not listed in TASK-04's
files-in-scope, yet Markdown export is one of the 4 target formats. If the
badge is appended at the synthesizer level (before export), the Markdown
exporter may not need modification — but this should be explicitly stated.

**Test count verification:**
- TASK-01: 4 tests
- TASK-02: 4 tests
- TASK-03: 5 tests
- TASK-04: 6 tests
- Total new: 19 tests (Blueprint says +16) — **count mismatch**

**FLAG-06B (LOW):** Blueprint declares "+16 new tests" in the Test Baseline
section, but the actual test tables contain 19 tests (4+4+5+6). The expected
total should be 2,480 + 19 = 2,499, not 2,496.

───────────────────────────────────────────────────────────
CHK-07 · CONSISTENCY WITH STATE.md AND EXISTING CODEBASE
───────────────────────────────────────────────────────────

PASS with 3 FLAGS.

**STATE.md cross-reference:**

| Check | Result |
|:------|:-------|
| Test baseline (2,480) matches STATE.md | ✅ Confirmed via `pytest --co` |
| STATE.md last updated 2026-05-10 (BATCH-140) | ✅ Current |
| 0 batches since update | ✅ No reconciliation audit needed |
| DEC-007 (.env.example as sole template) | ✅ Blueprint follows this for `.env.docker` |
| DEC-008 (config.py sole default location) | ✅ Docker reads same config |
| DEC-009 (EROCK_ENV production mode) | ✅ Referenced in Dependency Map |
| No carry-forward obligations | ✅ STATE.md shows none |

**FLAG-07A (HIGH):** The Blueprint is silent on the existing Docker
infrastructure. The codebase currently has:

```
Dockerfile              ← Multi-stage, installs from pyproject.toml, uses Postgres
docker-compose.yml      ← 5 services: postgres, redis, app, frontend, nginx
nginx/nginx.conf        ← Full config with WebSocket, SSE, security headers
```

The Blueprint proposes replacing this with:

```
Dockerfile.backend      ← NEW (replaces Dockerfile?)
Dockerfile.frontend     ← NEW
docker-compose.yml      ← REPLACE (2 services: backend, frontend; SQLite only)
nginx.conf              ← NEW (replaces nginx/nginx.conf?)
```

But it never explicitly states: "The existing Dockerfile, docker-compose.yml,
and nginx/nginx.conf are replaced by this batch." Without this declaration:
- The Assistant won't know whether to delete or rename the old files
- The Lead can't verify whether removing PostgreSQL/Redis services conflicts
  with SCOPE's "MUST NOT modify existing pipeline stages, orchestrator, or
  core business logic" (removing DB services could affect other services that
  reference them)
- TEST-151-01-02 (`docker build -f Dockerfile.backend .`) may conflict with
  the existing `docker build -f Dockerfile .`

**FLAG-07B (MEDIUM):** The existing `Dockerfile` (currently functional) will
remain in the repo unless explicitly removed or renamed. After BATCH-151,
running `docker compose up` would use the new `docker-compose.yml` but the old
`Dockerfile` would still exist, creating ambiguity. The Blueprint should declare
what happens to:
- `Dockerfile` (old) — rename to `Dockerfile.legacy`? Delete?
- `docker-compose.prod.yml` — still needed?
- `nginx/` directory — kept for legacy or removed?

**FLAG-07C (LOW):** The existing `docker-compose.yml` healthcheck uses:
```
test: ["CMD", "python", "-c", "import urllib.request;
       urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
```
This references `/api/v1/health` which does not exist (actual endpoint is
`/health`). The Blueprint's TASK-03 TEST-151-03-04 perpetuates this wrong path.
Both the old and new healthchecks will fail unless corrected to `/health`.

═══════════════════════════════════════════════════════════
SUMMARY
═══════════════════════════════════════════════════════════

Total Flags:       11
  HIGH:            3 (FLAG-02A, FLAG-05A, FLAG-07A)
  MEDIUM:          5 (FLAG-02B, FLAG-02C, FLAG-03A, FLAG-04A, FLAG-05B, FLAG-05C, FLAG-06A, FLAG-07B)
  LOW:             3 (FLAG-01A, FLAG-02D, FLAG-04B, FLAG-05C-note, FLAG-06B, FLAG-07C)

Wait — recounting distinct flags:

| # | Flag | Severity | Summary |
|:--|:-----|:---------|:--------|
| 1 | FLAG-02A | HIGH | `requirements.txt` referenced but project uses `pyproject.toml` |
| 2 | FLAG-05A | HIGH | TASK-01 has 3 factual errors: wrong dep file, wrong health path, unnecessary new file |
| 3 | FLAG-07A | HIGH | Blueprint silent on replacing existing Docker infrastructure |
| 4 | FLAG-02B | MEDIUM | PDF in SCOPE but missing from HB-04 and TASK-04 |
| 5 | FLAG-02C | MEDIUM | Files marked NEW that already exist (docker-compose.yml, nginx.conf) |
| 6 | FLAG-03A | MEDIUM | HB-04 incomplete — missing PDF format from SCOPE |
| 7 | FLAG-04A | MEDIUM | Data model description of export.py is stale (says PDF, actual file says BibTeX) |
| 8 | FLAG-05B | MEDIUM | Task sequencing contradicts declared dependencies |
| 9 | FLAG-05C | MEDIUM | nginx.conf path ambiguity — new root-level vs existing nginx/nginx.conf |
| 10 | FLAG-06A | MEDIUM | No test for PDF badge compliance; test count says +16 but tables show +19 |
| 11 | FLAG-07B | MEDIUM | Old Dockerfile/Compose will create ambiguity after Batch |
| 12 | FLAG-01A | LOW | Goal phrasing could imply SQLite as separate container |
| 13 | FLAG-02D | LOW | Port change from 8080 to 3000 implicit |
| 14 | FLAG-04B | LOW | STATE.md missing entries for synthesis/export modules |
| 15 | FLAG-06B | LOW | Test count mismatch (+16 declared, +19 in tables) |
| 16 | FLAG-07C | LOW | Pre-existing healthcheck path bug perpetuated |

Severity:         **HIGH** — 3 high-severity flags that will cause execution
                  failure if not addressed.

Recommendation:   **RECOMMEND REVISION**

The three HIGH flags are blocking:

1. **FLAG-02A/FLAG-05A (merged):** The Assistant will produce a broken
   Dockerfile that references a non-existent `requirements.txt`. The correct
   pattern is already in the existing `Dockerfile`: `COPY pyproject.toml ./`
   and `RUN pip install .`. TASK-01 description must be updated.

2. **FLAG-05A (health path):** The health check endpoint is at `/health`, not
   `/api/v1/health`. TASK-01 TEST-151-01-01 and TASK-03 TEST-151-03-04 must
   use the correct path. The existing `/health` endpoint in `app.py` returns
   `{"status": "ok", "version": "0.1.0"}` — this satisfies TASK-01's pass
   criteria of `json["status"] == "ok"`.

3. **FLAG-07A (infrastructure replacement):** The Blueprint must explicitly
   declare that the existing Docker infrastructure (Dockerfile, docker-compose.yml,
   nginx/nginx.conf) is being replaced/simplified, and specify what happens to
   the old files. Without this, the Assistant cannot safely proceed.

═══════════════════════════════════════════════════════════
RECOMMENDED LEAD ACTIONS
═══════════════════════════════════════════════════════════

For each HIGH flag, the recommended minimum correction:

| Flag | Action |
|:-----|:-------|
| FLAG-02A + FLAG-05A | Change all references from `requirements.txt` to `pyproject.toml`. Update TASK-01(a) to: "Stage 1: Install Python deps from pyproject.toml via `pip install .`" |
| FLAG-05A (health) | Change all references from `/api/v1/health` to `/health`. Remove `backend/api/routes/health.py` from TASK-01 files-in-scope (endpoint already exists in `app.py`). Update TEST-151-01-01 pass criteria to reference `/health`. |
| FLAG-07A | Add explicit SCOPE statement: "The existing `Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml`, and `nginx/` directory are replaced. The old `Dockerfile` is renamed to `Dockerfile.legacy`." |

For MEDIUM flags — resolve or explicitly defer in Lead Response:

| Flag | Action |
|:-----|:-------|
| FLAG-02B + FLAG-03A + FLAG-06A | Decide: either add PDF to HB-04 + TASK-04 with a test, or remove PDF from SCOPE. Must be internally consistent. |
| FLAG-02C + FLAG-05C + FLAG-07B | Declare file replacement strategy explicitly. Specify new file paths (root-level vs `nginx/` subdirectory). |
| FLAG-04A | Correct Data Models description of export.py to match actual file: "exports proposals as Markdown or BibTeX". |
| FLAG-05B | Correct task sequencing to: "TASK-01 and TASK-02 parallel → TASK-03 → (TASK-04 fully parallel)". |

═══════════════════════════════════════════════════════════
AUDIT TRAIL
═══════════════════════════════════════════════════════════

Files read during this review:
  - /docs/aiv/BATCH-151/BLUEPRINT.md (full)
  - /AIV_FRAMEWORK_v5.3.md (§4.1–4.3, §3.1, §13)
  - /docs/aiv/STATE.md (full)
  - /backend/api/app.py (health endpoint at line 312, route mounting)
  - /backend/api/routes/status.py (full — platform status routes)
  - /Dockerfile (existing — pyproject.toml based)
  - /docker-compose.yml (existing — PostgreSQL + Redis)
  - /nginx/nginx.conf (existing — production config)
  - /pyproject.toml (dependency management)
  - /backend/pipeline/synthesis/proposal_synthesizer.py (verified exists)
  - /backend/pipeline/synthesis/fast_synthesizer.py (verified exists)
  - /backend/pipeline/export/bibtex_exporter.py (header verified)
  - /backend/pipeline/export/md_to_latex.py (header verified)
  - /backend/api/routes/export.py (header — "Markdown or BibTeX")
  - /backend/api/routes/exports.py (header — "PDF export and bulk ZIP")
  - /.env.example (21 EROCK_ variables verified)

Investigative layer: FULLY PERFORMED (filesystem accessible).

═══════════════════════════════════════════════════════════
END REVIEW REPORT
═══════════════════════════════════════════════════════════
