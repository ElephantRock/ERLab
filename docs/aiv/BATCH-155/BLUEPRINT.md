BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-155
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (TASK-01→TASK-02→TASK-03)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────

Wire existing PubMed and CrossRef sources into the default search
pipeline alongside Semantic Scholar, arXiv, and OpenAlex. Add config
settings for PubMed/CrossRef. Wire the existing RelevanceFilter into
the literature search stage. Result: 5 concurrent search sources
with embedding-based relevance filtering.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────

What the code MUST do:
  - Add `pubmed_api_key` and `pubmed_enabled` settings to config.py
  - Add `crossref_enabled` setting to config.py (already has crossref_api_url)
  - Update `SearchService._default_sources()` to include:
    (a) PubMedSource (when pubmed_enabled=True, default True)
    (b) CrossRefSource (when crossref_enabled=True, default True)
    (c) SemanticScholarSource (already included when API key present)
    (d) ArxivSource (already included)
    (e) OpenAlexSource (already included)
  - Wire the existing RelevanceFilter into the literature search stage
    (`backend/pipeline/literature/search_service.py`) so that after
    deduplication, papers are scored by relevance and low-scoring ones
    are filtered out
  - Update the MultiSourceSearcher integration to use all 5 sources
    when configured

What the code MUST NOT do:
  - MUST NOT modify existing source implementations (PubMedSource, CrossRefSource,
    SemanticScholarSource, ArxivSource, OpenAlexSource classes)
  - MUST NOT break existing search behavior when new sources fail
    (each source fails independently)
  - MUST NOT add new database tables or migrations
  - MUST NOT change the Paper or SearchResult models
  - MUST NOT make PubMed/CrossRef required — they must be toggleable

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────

  Backend:  python -c "from backend.config import get_settings; print('OK')"
  Tests:    python -m pytest backend/tests/test_pipeline/test_batch155_search_expansion.py -v -p no:asyncio

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: All 2,551 pre-existing tests MUST pass after Batch close.
  HB-02: Individual source failure MUST NOT prevent other sources from
         returning results (already guaranteed by asyncio.gather + return_exceptions).
  HB-03: PubMed and CrossRef MUST be toggleable via config (enabled/disabled).
         Default: enabled=True for both.
  HB-04: Relevance filter MUST have a guaranteed minimum paper count
         (already implemented as MIN_PAPERS=5 in relevance_filter.py).
  HB-05: No network calls in tests. All new tests must mock HTTP clients.

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

No new data models. This batch wires existing modules together.

Existing modules referenced:
  - `backend/config.py` — Settings class (add pubmed_api_key, pubmed_enabled, crossref_enabled)
  - `backend/pipeline/literature/search_service.py` — SearchService (modify _default_sources)
  - `backend/pipeline/literature/multi_source.py` — MultiSourceSearcher (already supports N sources)
  - `backend/pipeline/literature/pubmed_source.py` — PubMedSource (exists, 173 lines, fully implemented)
  - `backend/pipeline/literature/crossref_source.py` — CrossRefSource (exists, 173 lines, fully implemented)
  - `backend/pipeline/literature/semantic_scholar.py` — SemanticScholarSource (exists, 176 lines)
  - `backend/pipeline/literature/relevance_filter.py` — RelevanceFilter (exists, 134 lines, not wired)
  - `backend/pipeline/literature/models.py` — Paper, SearchResult, Author

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────

  A-01: Source priority for deduplication: semantic_scholar > pubmed >
        openalex > crossref > arxiv (S2 has richest metadata).
  A-02: Relevance filter runs AFTER deduplication, not before.
        This avoids filtering duplicates that would be merged anyway.
  A-03: New config fields use EROCK_ prefix in .env.example
        (pubmed_api_key, pubmed_enabled, crossref_enabled).

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────

  Depends on:
    - BATCH-137 (config externalization) — lazy import pattern
    - Existing PubMedSource, CrossRefSource, RelevanceFilter (all pre-built)

  Blocks:
    - BATCH-163 (Semantic Scholar Novelty) — needs all sources available

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────

  State file exists:       [X] YES
  Last Updated:            2026-05-11 (BATCH-154 Close)
  Batches since update:    0
  Reconciliation audit:    [X] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline at Blueprint issuance:  2,551 existing tests
  Expected delta (all Tasks):      +16 new tests
  Expected total at Batch close:   2,567

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-155/TASK-01
  Priority:          Critical
  Description:       Add PubMed and CrossRef config settings and wire them
                     into SearchService._default_sources(). Must:
                     (a) Add `pubmed_api_key: str | None = None` to Settings
                     (b) Add `pubmed_enabled: bool = True` to Settings
                     (c) Add `crossref_enabled: bool = True` to Settings
                     (d) Update `_default_sources()` to conditionally add PubMedSource
                         and CrossRefSource
                     (e) Update source_priority in _deduplicate to include all 5 sources
                     (f) Update `.env.example` with new fields
  Files in scope:
    - backend/config.py (MODIFY — 3 new settings fields)
    - backend/pipeline/literature/search_service.py (MODIFY — _default_sources + source_priority)
    - .env.example (MODIFY — new fields)
  Depends on:        None
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-155-01-01   | unit   | Settings has pubmed_enabled field        | Config missing, startup crash | Access settings.pubmed_enabled | Field exists, default True |
    | TEST-155-01-02   | unit   | Settings has crossref_enabled field      | Config missing | Access settings.crossref_enabled | Field exists, default True |
    | TEST-155-01-03   | unit   | _default_sources includes PubMed when enabled | PubMed not searched | Mock pubmed_enabled=True | PubMedSource in source list |
    | TEST-155-01-04   | unit   | _default_sources excludes PubMed when disabled | Wasted API calls | Mock pubmed_enabled=False | PubMedSource NOT in source list |
    | TEST-155-01-05   | unit   | _default_sources includes CrossRef when enabled | CrossRef not searched | Mock crossref_enabled=True | CrossRefSource in source list |
    | TEST-155-01-06   | unit   | Dedup priority includes all 5 sources    | Wrong source preferred in merge | Check priority dict | All 5 source names in priority dict |
  Acceptance Criteria:
    AC-01-01: PubMed toggleable via pubmed_enabled (HB-03)
    AC-01-02: CrossRef toggleable via crossref_enabled (HB-03)
    AC-01-03: _default_sources returns up to 5 sources
  Traceability:
    AC-01-01 → TEST-155-01-03, TEST-155-01-04
    AC-01-02 → TEST-155-01-05
    AC-01-03 → TEST-155-01-06

TASK-02: BATCH-155/TASK-02
  Priority:          Critical
  Description:       Wire RelevanceFilter into SearchService. After
                     deduplication, papers pass through embedding-based
                     relevance scoring. Must:
                     (a) Add optional `relevance_filter` parameter to SearchService
                     (b) In `search_all()`, after deduplication, run relevance filter
                     (c) If no embedding provider is available, skip filter gracefully
                     (d) Log filter statistics (X before → Y after)
                     (e) Do NOT modify the RelevanceFilter class itself
  Files in scope:
    - backend/pipeline/literature/search_service.py (MODIFY — filter integration)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-155-02-01   | unit   | RelevanceFilter called after dedup       | Filter runs before dedup (wasted work) | Mock filter, check call order | Dedup called first, then filter |
    | TEST-155-02-02   | unit   | Filter skipped when no embedding provider | Filter crashes without provider | Create SearchService without filter | Returns all papers, no crash |
    | TEST-155-02-03   | unit   | Filter reduces paper count               | Irrelevant papers pass through | Mock filter to return 2 of 10 | 2 papers returned |
    | TEST-155-02-04   | unit   | Filter guarantees minimum papers (HB-04) | Too few papers returned | Mock all scores below threshold | At least 5 papers returned |
    | TEST-155-02-05   | unit   | Filter failure doesn't block search      | Pipeline crashes on filter error | Mock filter to raise Exception | Returns unfiltered results, no crash |
  Acceptance Criteria:
    AC-02-01: RelevanceFilter integrated after deduplication (A-02)
    AC-02-02: Graceful degradation when no embedding provider (HB-05 compliant)
    AC-02-03: Minimum paper count guaranteed (HB-04)
  Traceability:
    AC-02-01 → TEST-155-02-01
    AC-02-02 → TEST-155-02-02, TEST-155-02-05
    AC-02-03 → TEST-155-02-03, TEST-155-02-04

TASK-03: BATCH-155/TASK-03
  Priority:          High
  Description:       Wire MultiSourceSearcher to use all 5 sources
                     and update tests. Also add a search source health
                     check method that tests each source's connectivity.
                     Must:
                     (a) Create a `SearchSourceHealth` class with `check_all()` method
                     (b) For each registered source, try a simple search and report status
                     (c) Return dict of source_name → {"healthy": bool, "latency_ms": float}
                     (d) Wire into SearchService as `health_check()` method
  Files in scope:
    - backend/pipeline/literature/search_service.py (MODIFY — add health_check)
    - backend/pipeline/literature/multi_source.py (MODIFY — use all sources from settings)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-155-03-01   | unit   | health_check returns dict for all sources | Missing source in health report | Mock 5 sources, call health_check | Dict has 5 entries |
    | TEST-155-03-02   | unit   | Failed source marked unhealthy           | False positive health status | Mock source to raise on search | healthy=False for failed source |
    | TEST-155-03-03   | unit   | MultiSourceSearcher uses all configured sources | Only 2 sources used | Configure 5, check list_sources() | list_sources() returns 5 names |
    | TEST-155-03-04   | unit   | Health check latency measured            | No latency data | Run health_check | latency_ms > 0 for each source |
    | TEST-155-03-05   | unit   | Individual source timeout doesn't block others | One slow source blocks all | Mock one source with 10s delay | Other sources still report |
  Acceptance Criteria:
    AC-03-01: health_check works for all 5 sources
    AC-03-02: Failed sources reported as unhealthy
    AC-03-03: MultiSourceSearcher uses all configured sources
  Traceability:
    AC-03-01 → TEST-155-03-01
    AC-03-02 → TEST-155-03-02
    AC-03-03 → TEST-155-03-03

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: SearchService wires 5 sources (S2, arXiv, OpenAlex, PubMed, CrossRef).
  BAC-02: RelevanceFilter integrated into search pipeline.
  BAC-03: All 2,551 pre-existing tests pass (HB-01).
  BAC-04: CHANGELOG.md updated with BATCH-155 entry.
  BAC-05: All documents archived under /docs/aiv/BATCH-155/.
  BAC-06: STATE.md updated with test count, DEC-013 (5-source search).

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

[Completed by Lead after Phase I-B.]

Reviewer Report ID:       REVIEW-BATCH-155-2026-05-11
Review Cycle:             1 (§4.5 Fallback — Reviewer stalled)
Lead Decision:            [X] ACCEPT WITH MODIFICATIONS

  FLAG-01 → ACTION: CrossRefSource(mailto=settings.openalex_email or "") wired correctly.
  FLAG-02 → ACKNOWLEDGED: Fields grouped with existing search settings in .env.example.

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-11 04:46

═══════════════════════════════════════════════════════════
