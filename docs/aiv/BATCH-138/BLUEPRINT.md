BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-138
Blueprint Version:        1.1
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-10
Review SLA:               30 min
Execution SLA per Task:   90 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (T2 depends on T1; T3 depends on T1)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Externalize all hardcoded model name fallbacks, provider default URLs,
and external API base URLs into config.py so that every runtime-tunable
value is env-overridable. After this Batch, no .py file in backend/
(excluding tests, config.py, reference tables, and CLI) contains a
model name or URL that isn't read from settings.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add config.py settings for external API URLs: crossref_api_url,
    openalex_api_url, semantic_scholar_api_url
  - Add config.py setting for default compaction fallback model
    (compaction_fallback_model)
  - Replace hardcoded "gpt-4o" fallback in window_manager.py with
    settings read
  - Replace hardcoded external API URLs in crossref_source.py,
    openalex_source.py, semantic_scholar.py with settings reads
  - Replace hardcoded localhost URLs in function defaults
    (embedding_providers.py, otlp_exporter.py, observability/manager.py,
    pdf_service.py, ollama_provider.py, provider_factory.py) with
    settings reads where the calling orchestrator already has settings

What the code MUST NOT do:
  - Modify MODEL_CONTEXT_SIZES or MODEL_PRICING reference tables
  - Change CLI defaults (setup.py, dev.py, research.py — user-facing)
  - Modify any pipeline logic or data models
  - Remove or alter any existing config.py field defaults
  - Change the runtime behavior when .env is configured identically

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────
  Lint command:  python -m ruff check backend/ && npx tsc --noEmit --project frontend/tsconfig.json

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: All new config.py fields MUST have EROCK_ prefixed env vars
         and sensible defaults matching current hardcoded values.
         Verified by: Settings() initializes without errors and all
         new fields have non-None defaults.

  HB-02: After changes, `pytest --co -q` MUST collect the same test
         count (±0) from the pre-existing suite — no tests broken
         by configuration changes. New tests are additive.

  HB-03: The application MUST still start and /health MUST return 200
         after all changes.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────
No data model changes. Existing modules referenced:

  Module:   backend.config.Settings
  New fields to add:
    crossref_api_url: str = "https://api.crossref.org"
    openalex_api_url: str = "https://api.openalex.org"
    semantic_scholar_api_url: str = "https://api.semanticscholar.org/graph/v1"
    compaction_fallback_model: str = "gpt-4o"
  Source:   backend/config.py (verified 2026-05-10)

  Module:   backend.pipeline.compaction.window_manager
  Lines 47, 97: model = model_name or getattr(self._provider, "default_model", "gpt-4o")
  Source:   backend/pipeline/compaction/window_manager.py (verified)

  Module:   backend.pipeline.literature.crossref_source
  Line 17:  API_BASE = "https://api.crossref.org"
  Source:   backend/pipeline/literature/crossref_source.py (verified)

  Module:   backend.pipeline.literature.openalex_source
  Line 12:  API_BASE = "https://api.openalex.org"
  Source:   backend/pipeline/literature/openalex_source.py (verified)

  Module:   backend.pipeline.literature.semantic_scholar
  Line 14:  API_BASE = "https://api.semanticscholar.org/graph/v1"
  Source:   backend/pipeline/literature/semantic_scholar.py (verified)

  Module:   backend.pipeline.ingestion.pdf_service
  Line 23:  s1_parser_url: str = "http://localhost:8000"
  Source:   backend/pipeline/ingestion/pdf_service.py (verified)

  Module:   backend.pipeline.observability.otlp_exporter
  Line 31:  endpoint: str = "http://localhost:4317"
  Source:   backend/pipeline/observability/otlp_exporter.py (verified)

  Module:   backend.pipeline.observability.manager
  Line 66:  otlp_endpoint: str = "http://localhost:4317"
  Source:   backend/pipeline/observability/manager.py (verified)

  Module:   backend.providers.provider_factory
  Line 306: base_url=getattr(settings, "ollama_base_url", "http://localhost:11434")
  Source:   backend/providers/provider_factory.py (verified)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────
  AUTH-01: config.py is the SOLE location for default URL/model values.
           All other modules read from settings or accept constructor
           params that default to settings reads.

  AUTH-02: Reference data tables (MODEL_CONTEXT_SIZES, MODEL_PRICING)
           are NOT configuration. They are static reference data and
           must not be externalized.

  AUTH-03: CLI modules (setup.py, dev.py, research.py) use their own
           defaults for user-facing prompts. These are NOT in scope.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────
  Depends on: BATCH-137 (credential hygiene completed — .env untracked,
              config.py lmstudio_base_url default fixed)

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────
  State file exists:       [x] YES
  Last Updated:            2026-05-10 (BATCH-137 Close)
  Batches since update:    0
  Reconciliation audit:    [x] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,429 collected tests
                             (BATCH-137 close: 2,416 + 13 new)
  Expected delta (all Tasks):      +8 new tests
  Expected total at Batch close:   2,437

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-138/TASK-01 — Externalize API URLs in config.py
  Priority:          High
  Description:       Add new settings fields for external API base URLs
                     (CrossRef, OpenAlex, Semantic Scholar). Wire them into
                     the literature source modules. Also wire existing
                     s1_parser_url setting into pdf_service.py.
  Files in scope:
    - backend/config.py (add 3 new fields: crossref, openalex, semantic_scholar URLs)
    - backend/pipeline/literature/crossref_source.py (read API_BASE from settings)
    - backend/pipeline/literature/openalex_source.py (read API_BASE from settings)
    - backend/pipeline/literature/semantic_scholar.py (read API_BASE from settings)
    - backend/pipeline/ingestion/pdf_service.py (read default from existing settings.s1_parser_url)
  Depends on:        None

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-138-01-01   | unit     | Config has crossref_api_url with correct default | External API URL not configurable | Remove field from config.py | Settings().crossref_api_url == "https://api.crossref.org" |
    | TEST-138-01-02   | unit     | Config has openalex_api_url with correct default | External API URL not configurable | Remove field from config.py | Settings().openalex_api_url == "https://api.openalex.org" |
    | TEST-138-01-03   | unit     | Config has semantic_scholar_api_url with correct default | External API URL not configurable | Remove field from config.py | Settings().semantic_scholar_api_url == "https://api.semanticscholar.org/graph/v1" |
    | TEST-138-01-04   | unit     | Literature sources read URL from settings | Source module uses hardcoded URL instead of settings | Hardcode the URL back in the source module | CrossRef source initializes with settings value, not a string literal |

  Acceptance Criteria:
    AC-01-01: config.py has crossref_api_url, openalex_api_url,
              semantic_scholar_api_url, s1_parser_url_default fields
    AC-01-02: All new fields have EROCK_ prefixed env var names (automatic via pydantic-settings)
    AC-01-03: Literature source modules read URLs from settings, not string literals
    AC-01-04: Application starts successfully after changes

  Traceability:
    AC-01-01 → TEST-138-01-01, TEST-138-01-02, TEST-138-01-03
    AC-01-02 → TEST-138-01-01, TEST-138-01-02, TEST-138-01-03
    AC-01-03 → TEST-138-01-04
    AC-01-04 → all tests (smoke)

TASK-02: BATCH-138/TASK-02 — Externalize compaction fallback model
  Priority:          Medium
  Description:       Replace hardcoded "gpt-4o" fallback in window_manager.py
                     with a settings read. Add compaction_fallback_model to config.py.
  Files in scope:
    - backend/config.py (add compaction_fallback_model field)
    - backend/pipeline/compaction/window_manager.py (replace "gpt-4o" with settings read)
    - backend/tests/test_pipeline/test_batch138_compaction.py (new)
  Depends on:        TASK-01 (config.py changes)

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-138-02-01   | unit     | Config has compaction_fallback_model field | Compaction fallback model not configurable | Remove field from config.py | Settings().compaction_fallback_model == "gpt-4o" |
    | TEST-138-02-02   | unit     | Window manager reads fallback from settings | Hardcoded fallback used | Hardcode "gpt-3.5-turbo" in window_manager | WindowManager uses settings.compaction_fallback_model when no model specified |

  Acceptance Criteria:
    AC-02-01: config.py has compaction_fallback_model with default "gpt-4o"
    AC-02-02: window_manager.py reads fallback from settings, not hardcoded string
    AC-02-03: Existing compaction tests still pass

  Traceability:
    AC-02-01 → TEST-138-02-01
    AC-02-02 → TEST-138-02-02
    AC-02-03 → existing test suite (HB-02)

TASK-03: BATCH-138/TASK-03 — Clean up remaining localhost URL defaults
  Priority:          Low
  Description:       Replace remaining hardcoded localhost URLs in function
                     default parameters with settings reads. These are already
                     called from contexts where settings is available, so the
                     change is mechanical. Reuses existing config fields:
                     ollama_base_url, observability_otlp_endpoint, s1_parser_url
                     — no new config fields needed for this Task.
  Files in scope:
    - backend/pipeline/observability/otlp_exporter.py (read default from settings)
    - backend/pipeline/observability/manager.py (read default from settings)
    - backend/providers/provider_factory.py (clean up getattr fallback for ollama)
    - backend/pipeline/knowledge/embedding_providers.py (read default from settings)
    - backend/providers/ollama_provider.py (read default from settings)
    - backend/tests/test_pipeline/test_batch138_url_defaults.py (new)
  Depends on:        TASK-01 (config.py changes)

  Required Tests:
    | Test ID          | Type     | Behavior Verified                          | Failure Mode                                | Falsified By                                           | Pass Criteria                                         |
    |:-----------------|:---------|:-------------------------------------------|:--------------------------------------------|:-------------------------------------------------------|:------------------------------------------------------|
    | TEST-138-03-01   | unit     | OTLP exporter reads endpoint from settings | Hardcoded localhost used in production | Hardcode a different URL | OTLPExporter.__init__ receives settings value |
    | TEST-138-03-02   | unit     | No getattr URL fallbacks in provider_factory | Provider factory still has hardcoded fallback | Add back getattr with hardcoded URL | provider_factory.py has no string containing "http://" in getattr calls |

  Acceptance Criteria:
    AC-03-01: otlp_exporter and manager read URL from settings, not hardcoded defaults
    AC-03-02: provider_factory.py has no getattr fallbacks with hardcoded URLs
    AC-03-03: All existing tests pass

  Traceability:
    AC-03-01 → TEST-138-03-01
    AC-03-02 → TEST-138-03-02
    AC-03-03 → existing test suite (HB-02)

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: All new config.py fields have EROCK_ env var names and sensible defaults (HB-01)
  BAC-02: No regression in existing test count (HB-02)
  BAC-03: CHANGELOG.md updated with BATCH-138 entry.
  BAC-04: All documents archived under /docs/aiv/BATCH-138/.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────
Reviewer Report ID:       REVIEW-BATCH-138-2026-05-10
Review Cycle:             1
Lead Decision:            [x] ACCEPT WITH MODIFICATIONS

All 3 flags acted on:
  CHK-19 (MEDIUM) → Fixed: Removed s1_parser_url_default (duplicate).
    T1 now uses existing config.py field s1_parser_url (line 102).
    Blueprint updated: new fields count changed from 5 to 3.
  CHK-21 (LOW) → Fixed: Added embedding_providers.py and
    ollama_provider.py to T3 Files-in-scope so Batch Goal
    and Task scope are aligned.
  CHK-22 (LOW) → Fixed: T3 description now explicitly states
    it reuses existing ollama_base_url, observability_otlp_endpoint,
    and s1_parser_url fields — no new config fields for T3.

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-10 00:50

═══════════════════════════════════════════════════════════
