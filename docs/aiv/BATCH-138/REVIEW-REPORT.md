# BLUEPRINT REVIEW REPORT

| Field            | Value                          |
|:-----------------|:-------------------------------|
| **Batch ID**     | BATCH-138                      |
| **Reviewer**     | lean-flint (Blueprint Reviewer)|
| **Date**         | 2026-05-10                     |
| **Version**      | 1.0                            |
| **Verdict**      | CONDITIONAL PASS (3 Flags)     |
| **Severity**     | MEDIUM                         |

═══════════════════════════════════════════════════════════

## STRUCTURAL LAYER (CHK-00 – CHK-12)

---

**CHK-00 — Batch ID present and correctly formatted**
**PASS** — `BATCH-138` present, matches naming convention.

---

**CHK-01 — Lead Programmer assigned**
**PASS** — `ivory-wolf` assigned.

---

**CHK-02 — Cycle Mode declared**
**PASS** — `STANDARD` declared.

---

**CHK-03 — Batch Goal is a single atomic objective**
**PASS** — Single objective: externalize hardcoded model name fallbacks, provider default URLs, and external API base URLs into config.py. Cohesive and well-bounded.

---

**CHK-04 — Scope Statement present with MUST / MUST-NOT**
**PASS** — Both sections present. MUST section enumerates 6 concrete actions. MUST-NOT section lists 5 explicit exclusions. Boundaries are clear and testable.

---

**CHK-05 — Hard Boundaries present and falsifiable**
**PASS** — Three hard boundaries (HB-01 through HB-03) each include verification method: Settings() initializes without errors, pytest --co -q same count, /health returns 200.

---

**CHK-06 — Lint Command present**
**PASS** — `python -m ruff check backend/ && npx tsc --noEmit --project frontend/tsconfig.json`.

---

**CHK-07 — Authority Rules declared**
**PASS** — AUTH-01 through AUTH-03 clearly designate config.py as sole authority, reference tables as out-of-scope, and CLI modules as excluded.

---

**CHK-08 — Dependency Map declared**
**PASS** — Explicitly depends on BATCH-137 (credential hygiene). Dependency is single-entry and traceable.

---

**CHK-09 — Task Sequencing valid**
**PASS** — Sequential: T2 depends on T1; T3 depends on T1. No circular dependencies.

---

**CHK-10 — Data Model / Schema section present**
**PASS** — Lists all new config.py fields with types, defaults, and source file references. Each module entry includes exact line numbers and current hardcoded values.

---

**CHK-11 — Test Baseline present and reconciled**
**PASS** — 2,429 collected tests. Explicitly reconciled: 2,416 pre-existing + 13 new (BATCH-137). Matches STATE.md test baseline.

---

**CHK-12 — STATE.md Status present**
**PASS** — Confirmed: state file exists, last updated 2026-05-10 (BATCH-137 Close), 0 batches since update, reconciliation audit N/A (<5 batches).

═══════════════════════════════════════════════════════════

## TASK-LEVEL LAYER (CHK-13 – CHK-18)

---

**CHK-13 — Each Task has Priority, Description, Files in scope**
**PASS** — All three tasks (T1, T2, T3) have Priority, Description, and Files in scope sections.

---

**CHK-14 — Each Task has Required Tests with full table**
**PASS** — All three tasks include test tables with Test ID, Type, Behavior Verified, Failure Mode, Falsified By, and Pass Criteria columns. 8 tests total across 3 tasks.

---

**CHK-15 — Test count reconciles with expected delta**
**PASS** — Blueprint claims +8 new tests (4 in T1, 2 in T2, 2 in T3). Expected total at Batch close: 2,437 = 2,429 + 8. Arithmetic is correct.

---

**CHK-16 — Acceptance Criteria per Task are falsifiable**
**PASS** — Each task has 3-4 ACs that reference specific file contents, field names, or test outcomes. All are falsifiable.

---

**CHK-17 — Traceability matrix per Task maps ACs to Tests**
**PASS** — Each task includes explicit AC → TEST mappings. No orphaned ACs or tests.

---

**CHK-18 — Batch-Level Acceptance Criteria present**
**PASS** — BAC-01 through BAC-04 cover env var prefixes (HB-01), test count regression (HB-02), CHANGELOG update, and document archiving.

═══════════════════════════════════════════════════════════

## INVESTIGATIVE LAYER (CHK-19 – CHK-24)

---

**CHK-19 — Data Model section matches live config.py**
**FLAG** — Blueprint proposes adding `s1_parser_url_default: str = "http://localhost:8000"` as a new field, but config.py already contains `s1_parser_url: str = "http://localhost:8000"` at line 102. Adding a second field with a different name (`s1_parser_url_default` vs. `s1_parser_url`) creates a duplicate that will confuse consumers about which field to read. The existing `s1_parser_url` field is already the correct one — TASK-01 should wire pdf_service.py to read from `settings.s1_parser_url`, not introduce a new field.

---

**CHK-20 — Line references in Blueprint match live source files**
**PASS** — All 8 line references verified against live source:

| Blueprint Claim | Actual Line | Content | Match |
|:---|:---|:---|:---|
| window_manager.py L47, L97 | L47, L97 | `"gpt-4o"` fallback | ✓ |
| crossref_source.py L17 | L17 | `API_BASE = "https://api.crossref.org"` | ✓ |
| openalex_source.py L12 | L12 | `API_BASE = "https://api.openalex.org"` | ✓ |
| semantic_scholar.py L14 | L14 | `API_BASE = "https://api.semanticscholar.org/graph/v1"` | ✓ |
| pdf_service.py L23 | L23 | `s1_parser_url: str = "http://localhost:8000"` | ✓ |
| otlp_exporter.py L31 | L31 | `endpoint: str = "http://localhost:4317"` | ✓ |
| manager.py L66 | L66 | `otlp_endpoint: str = "http://localhost:4317"` | ✓ |
| provider_factory.py L306 | L306 | `getattr(settings, "ollama_base_url", "http://localhost:11434")` | ✓ |

---

**CHK-21 — MUST-NOT scope respected (no overlap with excluded items)**
**FLAG** — The BATCH GOAL Scope Statement ("What the code MUST do") lists `embedding_providers.py` and `ollama_provider.py` as targets for localhost URL replacement, but neither file appears in any Task's "Files in scope" section. TASK-03's Files-in-scope lists only `otlp_exporter.py`, `manager.py`, `provider_factory.py`, and the test file. The Batch Goal promises work on 2 additional files that no Task covers, creating a scope gap — the Batch Goal cannot be fully achieved without tasks for these files.

---

**CHK-22 — Hard Boundaries can be verified as stated**
**FLAG** — TASK-03's TEST-138-03-02 pass criterion states: `provider_factory.py has no string containing "http://" in getattr calls`. However, after TASK-03's changes, the embedding provider creation in `_wrap_cached()` at line 306 currently reads `getattr(settings, "ollama_base_url", "http://localhost:11434")`. If the task replaces this with a direct `settings.ollama_base_url` read, the test passes. But there is **no corresponding config.py field addition** in TASK-03's Data Model section for an `ollama_base_url` default — because `ollama_base_url` already exists at line 26 of config.py. The test is technically achievable, but the Data Model section does not acknowledge that the fix reuses an existing field rather than adding a new one, making the Data Model section incomplete for TASK-03.

---

**CHK-23 — Authority Rules consistent with Task scope**
**PASS** — AUTH-01 (config.py is sole authority) is consistent: all tasks read from settings. AUTH-02 (reference tables excluded) is respected: no tasks touch MODEL_CONTEXT_SIZES or MODEL_PRICING. AUTH-03 (CLI modules excluded) is respected: no tasks touch setup.py, dev.py, or research.py.

---

**CHK-24 — Dependency Map and STATE.md reconcile**
**PASS** — BATCH-137 dependency declared. STATE.md last updated at BATCH-137 Close (2026-05-10). 0 batches since update. No outstanding carry-forward obligations from STATE.md. Observability endpoint config (`observability_otlp_endpoint`) already exists in config.py at line 168, which TASK-03 should leverage rather than adding a new field.

═══════════════════════════════════════════════════════════

## FLAG SUMMARY

| # | Check | Severity | Issue |
|:--|:------|:---------|:------|
| 1 | CHK-19 | MEDIUM | `s1_parser_url_default` proposed as a new field but `s1_parser_url` already exists in config.py (line 102). Duplicate field will confuse consumers. |
| 2 | CHK-21 | LOW | Batch Goal names `embedding_providers.py` and `ollama_provider.py` as targets, but no Task includes them in Files-in-scope. |
| 3 | CHK-22 | LOW | TASK-03 Data Model section does not list any new config.py field, yet the task implies reuse of `ollama_base_url` and `observability_otlp_endpoint` — this should be explicitly stated. |

═══════════════════════════════════════════════════════════

## REVIEWER RECOMMENDATION

**CONDITIONAL PASS — 3 Flags (1 MEDIUM, 2 LOW)**

The Blueprint is structurally sound and well-organized. The MEDIUM flag (CHK-19) should be resolved before execution to avoid introducing a redundant config field. The two LOW flags (CHK-21, CHK-22) are documentation gaps that do not block execution but should be corrected for audit completeness.

**Required before execution:**
- Replace `s1_parser_url_default` with `s1_parser_url` in the Data Model section and wire TASK-01 to read the existing field.

**Recommended before execution:**
- Either add tasks/files-in-scope for `embedding_providers.py` and `ollama_provider.py`, or remove them from the Batch Goal MUST section.
- Add a note to TASK-03's Data Model section stating it reuses existing `ollama_base_url` and `observability_otlp_endpoint` fields rather than adding new ones.

═══════════════════════════════════════════════════════════

## LEAD RESPONSE

[Pending]

═══════════════════════════════════════════════════════════
