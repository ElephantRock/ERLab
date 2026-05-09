BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-140
Blueprint Version:        1.1
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-10
Review SLA:               30 min
Execution SLA per Task:   90 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (T2 depends on T1)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Add an EROCK_ENV toggle (development/production) that shifts
security defaults. In production mode: CORS defaults to empty
(same-origin only), JWT secret must be non-default, debug is
forced off. Developer experience is preserved via the default
EROCK_ENV=development which keeps current permissive behavior.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add config.py field: `env` (str, "development" | "production",
    default "development")
  - Add a property or validation that computes effective CORS origins:
    when env=production AND cors_origins=["*"], override to [] (empty)
  - Add a property that forces debug=False when env=production
    (effective_debug property: returns False if is_production, else settings.debug)
  - When env=production and debug=True in env, log a warning that debug is forced off
  - Add a startup ERROR (not just warning) when env=production AND
    jwt_secret is the default value — the app MUST log the error
    and refuse to start (sys.exit(1) or raise)
  - Update the CORS middleware in app.py to read from settings
    instead of hardcoded ["*"]
  - Update .env.example with EROCK_ENV field

What the code MUST NOT do:
  - Change any pipeline logic or data models
  - Break backward compatibility for users who don't set EROCK_ENV
    (default is "development" — same behavior as today)
  - Remove any existing config.py fields
  - Introduce new dependencies

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m ruff check backend/ && npx tsc --noEmit --project frontend/tsconfig.json

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: When EROCK_ENV=development (default), the application MUST
         behave identically to its current behavior: CORS allows all
         origins, no JWT enforcement, debug mode respected.
         Verified by: running with EROCK_ENV unset produces same
         middleware config as current code.

  HB-02: When EROCK_ENV=production AND jwt_secret is default, the
         application MUST refuse to start with a clear error message.
         Verified by: setting EROCK_ENV=production with default JWT
         and confirming startup raises an exception.

  HB-03: When EROCK_ENV=production, CORS middleware MUST use the
         configured cors_origins (which defaults to [] if not
         explicitly set). No wildcard in production unless explicitly
         configured.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
No data model changes. Existing modules referenced:

  Module:   backend.config.Settings
  Fields:   cors_origins: list[str] = ["*"]  (line 96)
            auth_enabled: bool = False  (line 90)
            jwt_secret: str = "dev-secret-change-in-production"  (line 91)
            debug: bool = False  (line 20)
  Source:   backend/config.py (verified 2026-05-10)

  Module:   backend.api.app
  CORS middleware: allow_origins=["*"]  (line 26, hardcoded)
  startup() function: line 234 (has JWT warning from BATCH-137)
  Source:   backend/api/app.py (verified)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AUTH-01: EROCK_ENV is the SOLE toggle for security posture.
           All production-mode behaviors derive from it.

  AUTH-02: In production mode, security is opt-OUT (strict defaults).
           In development mode, security is opt-IN (permissive defaults).

  AUTH-03: The startup error for default JWT in production is a
           HARD BLOCK — not a warning. The app must not serve requests.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: BATCH-137 (startup warning infrastructure)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-10 (BATCH-139 Close)
  Batches since update:    0
  Reconciliation audit:    [x] N/A (< 5 batches)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,470 collected tests
  Expected delta (all Tasks):      +8 new tests
  Expected total at Batch close:   2,478

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-140/TASK-01 — Add EROCK_ENV toggle and CORS hardening
  Priority:          Critical
  Description:       Add the `env` field to config.py with a property
                     that computes effective security settings. Update
                     CORS middleware in app.py to read from settings.
                     Add a `is_production` property.
  Files in scope:
    - backend/config.py (add `env` field, `is_production` property, `effective_cors_origins` property, `effective_debug` property)
    - backend/api/app.py (CORS middleware reads settings, startup production check)
    - .env.example (add EROCK_ENV field)
    - backend/tests/test_pipeline/test_batch140_env_toggle.py (new)
  Depends on:        None

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-140-01-01   | unit     | Default env is "development"               | Breaking backward compat                    | Change default to "production"                         | Settings(_env_file=None).env == "development" |
    | TEST-140-01-02   | unit     | is_production is False by default          | All users treated as production             | Remove is_production property                          | Settings(_env_file=None).is_production == False |
    | TEST-140-01-03   | unit     | effective_cors_origins returns ["*"] in dev mode | CORS blocks legitimate requests in dev | Change effective_cors_origins to always return []      | Settings(_env_file=None).effective_cors_origins == ["*"] |
    | TEST-140-01-04   | unit     | effective_cors_origins returns [] in production when cors_origins=["*"] | Wildcard CORS in production | Change production override to keep ["*"] | Production mode + default cors_origins → effective_cors_origins == [] |
    | TEST-140-01-05   | unit     | effective_cors_origins returns configured value in production | Explicit CORS config ignored in production | Remove the passthrough logic | Production mode + cors_origins=["https://example.com"] → ["https://example.com"] |
    | TEST-140-01-06   | unit     | effective_debug returns False in production | Debug mode leaks info in production | Remove the effective_debug property | Production mode + debug=True → effective_debug == False |
    | TEST-140-01-07   | unit     | effective_debug returns settings.debug in development | Debug forced off in dev | Remove the effective_debug property | Development mode + debug=True → effective_debug == True |

  Acceptance Criteria:
    AC-01-01: config.py has `env` field defaulting to "development"
    AC-01-02: `is_production` property returns True when env="production"
    AC-01-03: `effective_cors_origins` returns ["*"] in dev mode (HB-01)
    AC-01-04: `effective_cors_origins` returns [] in prod mode with default cors
    AC-01-05: CORS middleware in app.py reads settings.effective_cors_origins
    AC-01-06: effective_debug returns False in production regardless of debug setting
    AC-01-07: .env.example has EROCK_ENV documentation

  Traceability:
    AC-01-01 → TEST-140-01-01
    AC-01-02 → TEST-140-01-02
    AC-01-03 → TEST-140-01-03
    AC-01-04 → TEST-140-01-04
    AC-01-05 → TEST-140-01-05
    AC-01-05 → TEST-140-01-05
    AC-01-06 → TEST-140-01-06, TEST-140-01-07
    AC-01-07 → TEST-140-01-01 (EROCK_ENV field present)

TASK-02: BATCH-140/TASK-02 — Production JWT enforcement
  Priority:          High
  Description:       Add a startup check that raises a fatal error when
                     env="production" and jwt_secret is the default value.
                     This check fires REGARDLESS of auth_enabled — even if
                     auth is disabled, a default JWT secret in production is
                     a security risk because auth_enabled can be flipped on
                     without changing the secret.
                     Update the existing BATCH-137 JWT warning to only
                     fire in development mode (in production, it's an error).
  Files in scope:
    - backend/api/app.py (startup() production JWT check)
    - backend/tests/test_pipeline/test_batch140_prod_jwt.py (new)
  Depends on:        TASK-01 (needs is_production property)

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-140-02-01   | unit     | Production + default JWT raises error      | App starts with forgeable tokens            | Remove the production check from startup()             | startup() raises Exception containing "JWT secret" |
    | TEST-140-02-02   | unit     | Production + custom JWT starts fine        | Legitimate config blocked                   | Change check to always raise                          | startup() completes without exception |
    | TEST-140-02-03   | unit     | Development + default JWT only warns       | Dev mode blocked (breaking change)          | Change warning to error                              | startup() completes, warning logged (no exception) |

  Acceptance Criteria:
    AC-02-01: Production + default JWT → startup raises exception (HB-02)
    AC-02-02: Production + custom JWT → startup succeeds
    AC-02-03: Development + default JWT → startup warns but succeeds (HB-01)

  Traceability:
    AC-02-01 → TEST-140-02-01
    AC-02-02 → TEST-140-02-02
    AC-02-03 → TEST-140-02-03

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: EROCK_ENV=development produces identical behavior to pre-BATCH-140 (HB-01)
  BAC-02: EROCK_ENV=production enforces strict security defaults (HB-02, HB-03)
  BAC-03: CHANGELOG.md updated with BATCH-140 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-140/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-140-2026-05-10
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

All 3 flags acted on:
  F-01 (MEDIUM) → Fixed: Added `effective_debug` property to config.py.
    Added TEST-140-01-06 and TEST-140-01-07. Added AC-01-06.
    T1 now includes effective_debug in config.py scope.
  F-02 (MEDIUM) → Fixed: Production JWT check fires REGARDLESS of
    auth_enabled. Reason: auth_enabled can be flipped on without
    changing the secret, making the default secret a latent risk.
    T2 description updated to make this explicit.
  F-03 (LOW) → Fixed: AC-01-07 now maps to TEST-140-01-01 explicitly
    (EROCK_ENV field present in config).

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-10 01:55

═══════════════════════════════════════════════════════════
