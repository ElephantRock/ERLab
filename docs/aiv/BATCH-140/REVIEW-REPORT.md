# BLUEPRINT REVIEW REPORT

═══════════════════════════════════════════════════════════

**Batch ID:**              BATCH-140
**Blueprint Version:**     1.0
**Reviewer:**              plain-lotus (AIV v5.3 Advisory)
**Date Reviewed:**         2026-05-10T01:49 UTC+3
**Investigative Layer:**   STATE.md, backend/config.py, backend/api/app.py
**Verdict:**               ⚠️ CONDITIONAL PASS
**Total Flags:**           3 (2 MEDIUM · 1 LOW)

═══════════════════════════════════════════════════════════

## CHECKLIST RESULTS

| Check  | Area                              | Verdict | Notes                                                      |
|:-------|:----------------------------------|:--------|:-----------------------------------------------------------|
| CHK-00 | Blueprint completeness            | ✅ PASS | All 13 required sections present                           |
| CHK-01 | Batch goal clarity                | ✅ PASS | Single-paragraph goal; unambiguous                         |
| CHK-02 | Scope statement (must / must not) | ✅ PASS | Both sections present and specific                         |
| CHK-03 | Lint command specified            | ✅ PASS | `ruff` + `tsc` command provided                            |
| CHK-04 | Hard boundaries defined           | ✅ PASS | HB-01 · HB-02 · HB-03 — all with verification methods     |
| CHK-05 | Data models referenced            | ✅ PASS | Existing fields cited with line numbers; no model changes  |
| CHK-06 | Authority rules defined           | ✅ PASS | AUTH-01 · AUTH-02 · AUTH-03                                |
| CHK-07 | Dependency map                    | ✅ PASS | BATCH-137 listed; verified present in STATE.md             |
| CHK-08 | STATE.md status                   | ✅ PASS | Updated 2026-05-10 (BATCH-139); 0 batches since update    |
| CHK-09 | Test baseline                     | ✅ PASS | 2,470 — matches STATE.md line 1 of TEST BASELINE section  |
| CHK-10 | Task list present                 | ✅ PASS | 2 tasks with priorities                                    |
| CHK-11 | Task descriptions                 | ✅ PASS | Clear, actionable descriptions                             |
| CHK-12 | Files in scope                    | ✅ PASS | TASK-01: 4 files · TASK-02: 2 files — all verified extant  |
| CHK-13 | Task dependencies                 | ✅ PASS | T2→T1 declared; sequencing header confirms "Sequential"    |
| CHK-14 | Required tests table              | ✅ PASS | 6-column tables present for both tasks                     |
| CHK-15 | Test ID uniqueness                | ✅ PASS | TEST-140-01-{01..05} · TEST-140-02-{01..03} — unique      |
| CHK-16 | Failure modes specified           | ✅ PASS | Every test row has a failure mode                          |
| CHK-17 | Falsification criteria            | ✅ PASS | Every test row has a "Falsified By" column                 |
| CHK-18 | Pass criteria                     | ✅ PASS | Explicit assertions for each test                          |
| CHK-19 | AC traceability                   | ⚠️ FLAG | See **F-03** — AC-01-06 traceability is "implicit"        |
| CHK-20 | Batch-level ACs                   | ✅ PASS | BAC-01 · BAC-02 · BAC-03 · BAC-04                         |
| CHK-21 | Internal consistency              | ⚠️ FLAG | See **F-02** — JWT check condition ambiguous              |
| CHK-22 | Scope alignment                   | ⚠️ FLAG | See **F-01** — debug-forcing in scope but absent from tasks|
| CHK-23 | Code consistency with STATE.md   | ✅ PASS | References DEC-007 / DEC-008 correctly; verified in code   |
| CHK-24 | Lint command validity             | ✅ PASS | Standard `ruff` + `tsc` — both tools verified in repo      |

**Score:** 21 PASS · 2 MEDIUM FLAG · 1 LOW FLAG

═══════════════════════════════════════════════════════════

## FLAG DETAIL

### F-01 · MEDIUM · CHK-22 — Scope–Test Gap: Debug Forcing in Production

**What the Scope Statement says (verbatim):**

> "Add a property that forces debug=False when env=production"

**What TASK-01 actually delivers:**

| Deliverable                    | In Scope | In Task Desc | In ACs | In Tests |
|:-------------------------------|:--------:|:------------:|:------:|:--------:|
| `env` field                    | ✅       | ✅           | ✅     | ✅       |
| `is_production` property       | ✅       | ✅           | ✅     | ✅       |
| `effective_cors_origins` prop  | ✅       | ✅           | ✅     | ✅       |
| Debug-forcing property         | ✅       | ❌           | ❌     | ❌       |

The TASK-01 description lists only three additions (`env`, `is_production`, `effective_cors_origins`). No acceptance criterion, no test row, and no pass criterion covers the debug-forcing behavior. If this requirement is intentional, the tasks must be augmented. If it was aspirational, the Scope Statement must be narrowed to match the tasks.

**Remediation:** Either (a) add an `effective_debug` property to TASK-01 with TEST-140-01-06, or (b) remove the debug-forcing bullet from the Scope Statement.

---

### F-02 · MEDIUM · CHK-21 — JWT Production Check: `auth_enabled` Condition Ambiguous

**Blueprint text (Scope Statement):**

> "Add a startup ERROR (not just warning) when env=production AND jwt_secret is the default value"

**Existing code (app.py line 257):**

```python
if settings.auth_enabled and settings.jwt_secret == "dev-secret-change-in-production":
    _log.warning(...)
```

The existing BATCH-137 warning is **conditional on `auth_enabled=True`**. The BATCH-140 scope and HB-02 do not mention `auth_enabled` at all. Two interpretations are possible:

| Interpretation           | Behavior                                            | Risk                                        |
|:-------------------------|:----------------------------------------------------|:--------------------------------------------|
| **Unconditional**        | Production + default JWT → always block             | Blocks apps that intentionally run without auth |
| **Conditional**          | Production + `auth_enabled=True` + default JWT → block | App silently runs with insecure secret if auth is later enabled |

Neither interpretation is obviously wrong, but the blueprint must resolve this ambiguity before execution because it directly affects the test pass criteria (TEST-140-02-01 · TEST-140-02-02) and the startup code path.

**Remediation:** Add an explicit AUTH rule or scope clarifier: either "the production JWT check is unconditional" or "the production JWT check only fires when `auth_enabled=True`."

---

### F-03 · LOW · CHK-19 — AC-01-06 Has No Direct Test

**Traceability table says:**

> AC-01-06 → TEST-140-01-01 (implicit)

AC-01-06 requires `.env.example` to contain an `EROCK_ENV` field. TEST-140-01-01 verifies that `Settings(_env_file=None).env == "development"`. These verify different things:

- **TEST-140-01-01** verifies the config default (a runtime property).
- **AC-01-06** verifies a file content change (a documentation artifact).

The .env.example update is typically verified by visual inspection, which is acceptable, but labeling it as "implicit" traceability to a runtime test is misleading. The test does not actually verify that the file was updated.

**Remediation:** Either (a) add a trivial file-content test for .env.example, or (b) change the traceability cell to "manual verification" and remove the false link to TEST-140-01-01.

═══════════════════════════════════════════════════════════

## INVESTIGATIVE LAYER NOTES

Source files were read and cross-referenced against the blueprint claims:

| Claim in Blueprint                              | Verified | Evidence                                              |
|:------------------------------------------------|:--------:|:------------------------------------------------------|
| `cors_origins: list[str] = ["*"]` in config.py  | ✅       | Line 96 area — field present with stated default      |
| CORS middleware hardcoded `allow_origins=["*"]`  | ✅       | app.py `CORSMiddleware` init — hardcoded wildcard     |
| BATCH-137 JWT warning in startup()               | ✅       | app.py line 257 — gated by `auth_enabled`             |
| `jwt_secret` default is `"dev-secret-change-in-production"` | ✅ | config.py line 91                              |
| `.env.example` exists                           | ✅       | Confirmed present at project root                     |
| No existing `env` field in config.py            | ✅       | grep for `env:` — no matches                         |
| STATE.md test baseline = 2,470                  | ✅       | "Last verified count: 2,470" in TEST BASELINE section |
| Test delta 5 + 3 = 8                            | ✅       | Arithmetic confirmed                                  |
| Expected total 2,478                            | ✅       | 2,470 + 8 = 2,478                                    |

All verifiable claims confirmed. No discrepancies found between the investigative layer and the blueprint.

═══════════════════════════════════════════════════════════

## VERDICT

┌──────────────────────────────────────────────────────┐
│  ⚠️  CONDITIONAL PASS                                │
│                                                       │
│  Resolve F-01 and F-02 before execution.              │
│  F-03 is advisory and may be addressed at Lead        │
│  Programmer discretion.                               │
│                                                       │
│  Flags: 2 MEDIUM · 1 LOW                              │
│  Blocking: F-01, F-02                                 │
│  Advisory: F-03                                       │
└──────────────────────────────────────────────────────┘

**Lead Programmer response required in:** LEAD RESPONSE TO REVIEW REPORT section of BLUEPRINT.md

═══════════════════════════════════════════════════════════
