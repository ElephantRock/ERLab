BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-137
Blueprint Version:        1.1
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-09
Review SLA:               30 min
Execution SLA per Task:   90 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (T2 depends on T1; T3 depends on T2)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Remove all secrets from git history, add startup guards that emit
prominent warnings when insecure defaults are detected (default JWT
secret, missing API keys), and ensure .env.example is the only
environment template tracked in the repository.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Remove .env from git tracking (git rm --cached)
  - Verify .gitignore enforcement for .env
  - Update .env.example with all security-relevant configuration fields
    (currently 12 fields — must expand to cover jwt_secret, all API keys,
    lmstudio_base_url, lmstudio_model, cors, database_url, auth_enabled)
  - Add a startup check in app.py that warns when JWT secret is the default
    "dev-secret-change-in-production" AND auth_enabled=True
  - Add a startup check that warns when no LLM API key is configured AND
    lmstudio_enabled=False
  - Replace all hardcoded non-localhost IP addresses in backend/pipeline/
    and backend/providers/ with settings reads or empty defaults

What the code MUST NOT do:
  - Modify any pipeline logic, model routing, or data models
  - Change the runtime behavior of any existing feature
  - Remove or alter any existing configuration field defaults
  - Introduce new dependencies

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m ruff check backend/api/ backend/providers/ backend/config.py && npx tsc --noEmit --project frontend/tsconfig.json

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: .env MUST NOT be tracked by git after this Batch. Verified by
         `git ls-files .env` returning empty.

  HB-02: .env.example MUST NOT contain any real API key, token, or
         password. Every value must be a placeholder like "your-key-here"
         or an empty string. Verified by grep for hex strings longer
         than 20 chars.

  HB-03: The application MUST still start successfully with only
         .env.example copied to .env (using placeholder values).
         Startup warnings are acceptable; crashes are not.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
No data model changes in this Batch. Existing modules referenced:

  Module:   backend.config.Settings (pydantic-settings BaseSettings)
  Fields:   jwt_secret: str = "dev-secret-change-in-production"
            auth_enabled: bool = False
            default_provider: str = "openai"
            anthropic_api_key: str | None = None
            openai_api_key: str | None = None
            lmstudio_enabled: bool = False
            lmstudio_base_url: str = "http://100.64.0.1:1234/v1"
            lmstudio_model: str = "qwen/qwen3-4b-2507"
  Source:   backend/config.py lines 27-75 (verified 2026-05-09)

  Module:   backend.api.app
  Function: startup() — @app.on_event("startup"), line 234
  Source:   backend/api/app.py (verified 2026-05-09)

  Module:   backend.providers.provider_factory
  Line 173: base_url=getattr(settings, "lmstudio_base_url", "http://100.64.0.1:1234")
  Line 159: base_url=settings.ollama_base_url (no hardcoded fallback)
  Line 306: embedding cache _wrap_cached() uses settings.ollama_base_url
  Source:   backend/providers/provider_factory.py (verified 2026-05-09)

  Module:   backend.pipeline.knowledge.embedding_providers
  Line 120: base_url: str = "http://localhost:11434"
  Line 289: base_url=base_url or "http://localhost:11434"
  Source:   backend/pipeline/knowledge/embedding_providers.py (verified 2026-05-09)

  Module:   backend.pipeline.ingestion.pdf_service
  Line 23:  s1_parser_url: str = "http://localhost:8000"
  Source:   backend/pipeline/ingestion/pdf_service.py (verified 2026-05-09)

  Module:   backend.pipeline.observability.otlp_exporter
  Line 31:  endpoint: str = "http://localhost:4317"
  Source:   backend/pipeline/observability/otlp_exporter.py (verified 2026-05-09)

  Module:   backend.pipeline.observability.manager
  Line 66:  otlp_endpoint: str = "http://localhost:4317"
  Source:   backend/pipeline/observability/manager.py (verified 2026-05-09)

  Module:   backend.providers.ollama_provider
  Line 14:  base_url: str = "http://localhost:11434"
  Source:   backend/providers/ollama_provider.py (verified 2026-05-09)

  File:     .env.example — 12 EROCK_ fields, 924 bytes (verified; will expand to ~30)
  File:     .gitignore — has .env on line 7 (verified)
  File:     .env — tracked by git despite .gitignore (verified: `git ls-files .env` returns ".env")

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AUTH-01: .env is the sole source of runtime secrets. .env.example is the
           sole template. No other file may contain real credentials.

  AUTH-02: The startup() function is the sole place where security warnings
           are emitted. No middleware or route handler should duplicate this.

  AUTH-03: Warnings are non-blocking. The application must never refuse to
           start — only warn loudly.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  No prior Batch dependencies. Standalone hardening Batch.

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-07
  Batches since update:    16 (B121-B136)
  Reconciliation audit:    [x] PERFORMED — all Phase 9 module entries
                           verified present during Blueprint authoring.
                           No stale entries found.

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,416 collected tests
                             (live pytest --co -q on 2026-05-09;
                              STATE.md stale at 2,361 — B121-B136 delta
                              of 55 tests not yet recorded in STATE.md)
  Expected delta (all Tasks):      +10 new tests
  Expected total at Batch close:   2,426

  STATE.md reconciliation note:
    STATE.md last updated 2026-05-07 (BATCH-120 close, count 2,292).
    Phase 9 summary claims 2,361 after B121-B129. B130-B136 added 55 more.
    Live collection confirms 2,416. STATE.md will be updated at Batch Close
    to reflect the true current count.

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-137/TASK-01 — Remove .env from git + update .env.example
  Priority:          Critical
  Description:       Untrack .env from git, verify .gitignore enforcement,
                     and update .env.example to document all security-relevant
                     configuration fields with placeholder values.
  Files in scope:
    - .env.example (expand with all security-relevant settings)
    - .env (git rm --cached only — no content changes)
  Depends on:        None

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-137-01-01   | unit     | .env is not tracked by git                 | .env content leaks to anyone who clones     | `git ls-files .env` returns a path                     | assert subprocess.run(["git","ls-files",".env"]).stdout.strip() == "" |
    | TEST-137-01-02   | unit     | .env.example contains no real credentials  | API key or secret committed to template      | Add a real-looking 40-char hex key to .env.example     | grep -cP '[0-9a-f]{20,}' .env.example returns 0 |
    | TEST-137-01-03   | unit     | .env.example documents JWT_SECRET field    | New users don't know to change the secret    | Remove EROCK_JWT_SECRET line from .env.example         | "EROCK_JWT_SECRET" in open(".env.example").read() |
    | TEST-137-01-04   | unit     | .env.example documents LMSTUDIO fields     | Hardcoded IP leaks developer topology        | Remove EROCK_LMSTUDIO_BASE_URL from .env.example       | "EROCK_LMSTUDIO_BASE_URL" in open(".env.example").read() |

  Acceptance Criteria:
    AC-01-01: `git ls-files .env` returns empty (HB-01)
    AC-01-02: .env.example has zero hex strings >20 chars (HB-02)
    AC-01-03: .env.example documents jwt_secret, all api keys,
              lmstudio_base_url, lmstudio_model, cors, auth_enabled, database_url
    AC-01-04: .gitignore contains .env entry

  Traceability:
    AC-01-01 → TEST-137-01-01
    AC-01-02 → TEST-137-01-02
    AC-01-03 → TEST-137-01-03, TEST-137-01-04
    AC-01-04 → TEST-137-01-01

TASK-02: BATCH-137/TASK-02 — Startup security warnings
  Priority:          High
  Description:       Add startup checks in app.py startup() function that
                     emit prominent logging.WARNING when insecure defaults
                     are detected. Warnings must not block startup.
  Files in scope:
    - backend/api/app.py (startup() function only)
    - backend/tests/test_pipeline/test_batch137_startup_warnings.py (new)
  Depends on:        TASK-01

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-137-02-01   | unit     | Startup warns when JWT secret is default AND auth_enabled=True | App silently runs with forgeable JWT in production | Remove the warning check from startup() | assert "JWT secret" in captured_warnings |
    | TEST-137-02-02   | unit     | Startup does NOT warn when JWT secret is custom AND auth_enabled=True | False positives alarm correctly-configured users | Set jwt_secret to a custom value, add a spurious check | assert "JWT secret" NOT in captured_warnings |
    | TEST-137-02-03   | unit     | Startup warns when no LLM API key configured | Pipeline fails at first LLM call with cryptic error | Remove the warning check from startup() | assert "no LLM API key" in captured_warnings |
    | TEST-137-02-04   | unit     | Startup does NOT warn when LM Studio enabled and no cloud key | False positive for local-only setups | Set lmstudio_enabled=True, add a check that still warns | assert "no LLM API key" NOT in captured_warnings |

  Acceptance Criteria:
    AC-02-01: When auth_enabled=True + default JWT secret → WARNING logged
    AC-02-02: When auth_enabled=False → no JWT warning regardless of secret
    AC-02-03: When all API keys None + lmstudio_enabled=False → WARNING logged
    AC-02-04: When lmstudio_enabled=True → no API key warning
    AC-02-05: Application starts successfully in all cases (no exceptions)

  Traceability:
    AC-02-01 → TEST-137-02-01
    AC-02-02 → TEST-137-02-02
    AC-02-03 → TEST-137-02-03
    AC-02-04 → TEST-137-02-04
    AC-02-05 → all tests

TASK-03: BATCH-137/TASK-03 — Remove hardcoded IP fallbacks
  Priority:          High
  Description:       Replace hardcoded non-localhost IP addresses used as
                     fallback defaults with settings reads. config.py defaults
                     may use "localhost" (environment-neutral) or empty string.
                     NOTE: T1 documents lmstudio_base_url in .env.example; this
                     Task changes the config.py default value. T1 must document the
                     field generically (not the specific default) so T3's default
                     change doesn't invalidate T1's deliverable.
  Files in scope:
    - backend/config.py (change lmstudio_base_url default from "http://100.64.0.1:1234/v1" to "http://localhost:1234/v1")
    - backend/providers/provider_factory.py (remove "http://100.64.0.1:1234" getattr fallback)
    - backend/providers/ollama_provider.py (keep localhost default — acceptable)
    - backend/pipeline/knowledge/embedding_providers.py (keep localhost default — acceptable)
    - backend/pipeline/ingestion/pdf_service.py (keep localhost default — acceptable)
    - backend/pipeline/observability/otlp_exporter.py (keep localhost default — acceptable)
    - backend/pipeline/observability/manager.py (keep localhost default — acceptable)
    - backend/pipeline/orchestrator.py (keep localhost default — acceptable via settings)
    - backend/tests/test_pipeline/test_batch137_no_hardcoded_ips.py (new)
  Depends on:        TASK-02

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-137-03-01   | unit     | No hardcoded non-localhost IPs in backend code | Developer topology leaks to production | Add "100.64.0.1" to any file in scope                  | Grep with regex `(100\.64\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})` in backend/pipeline/ and backend/providers/ non-test .py files returns 0 matches |
    | TEST-137-03-02   | unit     | provider_factory reads LMSTUDIO_BASE_URL from settings | Factory uses developer's IP | Set settings.lmstudio_base_url to empty string         | Provider init receives base_url from settings, not a hardcoded string |
    | TEST-137-03-03   | unit     | config.py lmstudio_base_url default is localhost or empty | Production connects to developer's machine | Change default back to "http://100.64.0.1:1234/v1"     | Settings().lmstudio_base_url does not contain "100.64" |

  Acceptance Criteria:
    AC-03-01: No file in backend/pipeline/ or backend/providers/ (excluding tests)
              contains a hardcoded non-localhost IP address (100.64.x.x, 192.168.x.x, 10.x.x.x)
    AC-03-02: config.py lmstudio_base_url default is "http://localhost:1234/v1" or ""
    AC-03-03: provider_factory.py getattr fallbacks use settings, not hardcoded IPs
    AC-03-04: Application starts and health check passes after changes

  Traceability:
    AC-03-01 → TEST-137-03-01
    AC-03-02 → TEST-137-03-03
    AC-03-03 → TEST-137-03-02
    AC-03-04 → TEST-137-03-01 (integration)

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: `git ls-files .env` returns empty AND .gitignore contains .env
  BAC-02: .env.example contains zero real credentials AND documents all
          security-relevant settings
  BAC-03: CHANGELOG.md updated with BATCH-137 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-137/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-137-2026-05-10
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

All 7 flags acted on:
  CHK-13 (LOW) → Acknowledged. LM Studio + unreachable server edge case is
    out of scope for this Batch (not a config issue — it's a runtime
    connectivity issue). The startup warning only checks key presence,
    not server reachability. Deferred to a future hardening Batch.
  CHK-14 (MEDIUM) → Fixed: Test baseline section now includes live
    pytest --co confirmation (2,416) and explains the STATE.md gap.
  CHK-17 (HIGH) → Fixed: Batch Goal changed from "refuse to run" to
    "emit prominent warnings when insecure defaults are detected."
    Now consistent with AUTH-03 and HB-03.
  CHK-19 (HIGH) → Fixed: .env.example count corrected (12, not 23).
    provider_factory.py line references corrected (173, 159, 306).
    app.py startup() line corrected (234, not ~245).
  CHK-22 (MEDIUM) → Fixed: T3 description now includes explicit NOTE
    about T1/T3 coupling and the documentation strategy.
  CHK-23 (LOW) → Fixed: TEST-137-03-01 now specifies exact regex:
    `(100\.64\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})`
  CHK-24 (HIGH) → Fixed: Test baseline section now includes live
    count verification and STATE.md reconciliation note explaining
    the B121-B136 gap.

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-09 21:17

═══════════════════════════════════════════════════════════
