# AIV v5.3 — REVIEW REPORT

**Batch ID:**        BATCH-155
**Blueprint Ver:**   1.0
**Reviewer:**        Craft Agent (AI Reviewer)
**Review Date:**     2026-05-11T04:42 EAT
**Review Cycle:**    1
**Verdict:**         ACCEPT WITH MODIFICATIONS

═══════════════════════════════════════════════════════════

## CHECK RESULTS

### CHK-00: Cycle Mode & Scheduling

| Aspect           | Value      | Assessment |
|:-----------------|:-----------|:-----------|
| Cycle Mode       | STANDARD   | Correct for wiring/integration batch |
| Task Sequencing  | Sequential | Appropriate — TASK-02 depends on TASK-01 output |
| Review SLA       | 30 min     | Standard |
| Execution SLA    | 60 min/task | Reasonable |
| Lead Programmer   | ivory-wolf | Active, verified in STATE.md |

**Result: PASS**

---

### CHK-01: Batch Goal

> "Wire existing PubMed and CrossRef sources into the default search pipeline alongside Semantic Scholar, arXiv, and OpenAlex. Add config settings for PubMed/CrossRef. Wire the existing RelevanceFilter into the literature search stage."

**Verification against codebase:**

| Claim | Codebase Reality | Match? |
|:------|:-----------------|:-------|
| PubMed/CrossRef sources exist | `pubmed_source.py` (173 lines), `crossref_source.py` (173 lines) — fully implemented | **YES** |
| RelevanceFilter exists, not wired | `relevance_filter.py` (110 lines) — `RelevanceFilter` class with `filter()` method, never imported in `search_service.py` | **YES** |
| `SearchService._default_sources()` only has S2/arXiv/OpenAlex | Confirmed — returns 2 or 3 sources depending on S2 API key | **YES** |
| `MultiSourceSearcher` supports N sources | Confirmed — `register()` + `list_sources()` pattern | **YES** |

Goal is specific, achievable, and accurately describes the gap.

**Result: PASS**

---

### CHK-02: Scope Statement

**MUST DO — verified against codebase:**

| Item | Codebase Anchor | Actionable? |
|:-----|:----------------|:------------|
| Add `pubmed_api_key`, `pubmed_enabled`, `crossref_enabled` to Settings | `config.py` — neither field exists | **YES** |
| Update `_default_sources()` to include PubMed/CrossRef | `search_service.py` L139-158 — currently only imports S2/arXiv/OpenAlex | **YES** |
| Wire RelevanceFilter after dedup | `search_service.py` — `search_all()` returns `list[Paper]` after dedup, filter not called | **YES** (but see FLAG-01) |
| Update `source_priority` in `_deduplicate` | `search_service.py` L114 — currently `{"semantic_scholar": 0, "arxiv": 1, "openalex": 2}` | **YES** |

**MUST NOT DO — boundaries verified:**

| Boundary | Rationale | Enforceable? |
|:---------|:----------|:-------------|
| No modifications to source classes | PubMedSource, CrossRefSource are complete and working | **YES** |
| No new DB tables/migrations | Wiring-only batch | **YES** |
| No Paper/SearchResult model changes | Models are shared across pipeline | **YES** |
| PubMed/CrossRef must be toggleable | Config-driven enablement | **YES** |

**Result: FLAG** — FLAG-01 (type mismatch in filter wiring), FLAG-02 (scope claims no new models but TASK-03 creates one)

---

### CHK-03: Hard Boundaries

| HB | Statement | Testable? | Covered by Tests? |
|:---|:----------|:----------|:-------------------|
| HB-01 | 2,551 pre-existing tests pass | `pytest` full suite | Baseline cited, lint command given |
| HB-02 | Individual source failure independent | `asyncio.gather(return_exceptions=True)` confirmed in `search_all()` L69 | TEST-155-02-05 (filter failure), TEST-155-03-02 (unhealthy source) |
| HB-03 | PubMed/CrossRef toggleable, default True | Config field + conditional in `_default_sources()` | TEST-155-01-03, 01-04, 01-05 |
| HB-04 | RelevanceFilter guarantees MIN_PAPERS=5 | `relevance_filter.py` L16: `MIN_PAPERS = 5` confirmed | TEST-155-02-04 |
| HB-05 | No network calls in tests | All tests mock HTTP clients | Test design specifies mocking |

**Result: PASS**

---

### CHK-04: Data Models / Schema

| Claim | Verification | Match? |
|:-----|:-------------|:-------|
| No new data models | Wiring-only batch — confirmed | **YES** |
| `pubmed_source.py` — 173 lines | `wc -l` → 173 lines | **YES** |
| `crossref_source.py` — 173 lines | `wc -l` → 173 lines | **YES** |
| `relevance_filter.py` — 134 lines | `wc -l` → **110 lines** | **NO** (see FLAG-03) |
| `RelevanceFilter` has `MIN_PAPERS=5` | Confirmed at line 16 | **YES** |
| `Paper`, `SearchResult`, `Author` in models.py | Referenced throughout, unchanged | **YES** |

**Result: FLAG** — FLAG-03 (line count inaccuracy for relevance_filter.py)

---

### CHK-05: Tasks

#### TASK-01: Config + _default_sources

| Aspect | Assessment |
|:-------|:-----------|
| Priority | Critical — correct |
| Scope | 3 files modified (config.py, search_service.py, .env.example) |
| Config fields | `pubmed_api_key: str | None = None`, `pubmed_enabled: bool = True`, `crossref_enabled: bool = True` — types match Pydantic pattern |
| Tests | 6 tests covering toggle, inclusion, exclusion, priority — comprehensive |
| Traceability | AC-01-01 through AC-01-03 all map to specific tests |

**Gap identified:** Blueprint does not explicitly specify how `settings.pubmed_api_key` flows to `PubMedSource(api_key=...)`. The `_default_sources()` method must import PubMedSource and pass the key. This is implied by "(d) conditionally add PubMedSource" but not spelled out. (FLAG-04)

**Result: PASS with note**

#### TASK-02: Wire RelevanceFilter

| Aspect | Assessment |
|:-------|:-----------|
| Priority | Critical — correct |
| Scope | 1 file (search_service.py) |
| Filter integration | After deduplication — per A-02 |
| Graceful degradation | Skip when no embedding provider — testable |
| Tests | 5 tests covering order, skip, reduce, minimum, failure — comprehensive |

**Critical gap identified:** `SearchService._deduplicate()` returns `list[Paper]`, but `RelevanceFilter.filter()` expects `list[SearchResult]` as its first parameter. After deduplication, the `SearchResult` wrapper (with `relevance_score`, `source` fields) is lost. The blueprint simultaneously requires:
1. Filter runs AFTER dedup (Authority Rule A-02)
2. Do NOT modify RelevanceFilter (TASK-02 constraint)
3. Wire filter into search pipeline (TASK-02 goal)

These three constraints are **mutually irreconcilable** without a conversion step the blueprint never mentions. The Lead must either:
- (a) Modify `_deduplicate()` to return `list[SearchResult]` instead of `list[Paper]` (breaking change to return type), OR
- (b) Wrap deduplicated `Paper` objects back into `SearchResult` before filtering, OR
- (c) Modify `RelevanceFilter.filter()` to also accept `list[Paper]` (violates TASK-02 constraint)

Option (b) is the cleanest path but requires a conversion function the blueprint doesn't specify. (FLAG-01 — **HIGH**)

**Result: FLAG** — FLAG-01 (type mismatch, architectural gap)

#### TASK-03: Health Check + MultiSourceSearcher

| Aspect | Assessment |
|:-------|:-----------|
| Priority | High — acceptable |
| Scope | 2 files (search_service.py, multi_source.py) |
| New class | `SearchSourceHealth` with `check_all()` |

**Inconsistencies identified:**

1. **Scope contradiction**: Batch scope states "No new data models. This batch wires existing modules together." But TASK-03 creates a new `SearchSourceHealth` class. This is a new code artifact not mentioned in the Data Models section. (FLAG-02)

2. **File collision**: Both TASK-02 and TASK-03 modify `search_service.py`. TASK-03 lists dependency on TASK-01 only, not TASK-02. Sequential execution mitigates this, but the dependency graph is incomplete. (FLAG-06)

3. **Overlap with TASK-01**: TASK-03 sub-task (c) says "Wire into SearchService as health_check() method" and TEST-155-03-03 verifies "MultiSourceSearcher uses all configured sources." But the actual source wiring happens in TASK-01's `_default_sources()`. TEST-155-03-03 is really testing TASK-01's output, not TASK-03's health check.

**Result: FLAG** — FLAG-02 (scope contradiction), FLAG-06 (dependency gap)

---

### CHK-06: Tests

| Metric | Value | Assessment |
|:-------|:------|:-----------|
| Total new tests | 16 (6+5+5) | Reasonable for wiring batch |
| Test naming | `TEST-155-{task}-{seq}` | Consistent with AIV convention |
| Each test has failure mode | Yes | Good |
| Each test has falsification method | Yes | Good |
| Each test has pass criteria | Yes | Good |
| Lint command | Valid (`from backend.config import get_settings`) | Correct |
| Test command | `-p no:asyncio` | Consistent with GOTCHA-001 |

**Concerns:**
- TEST-155-03-05 ("Mock one source with 10s delay") risks flakiness if the delay is real. Must mock `asyncio.sleep` or use a short timeout. Blueprint should specify.
- No integration test verifying end-to-end: 5 sources → dedup → filter → output. All tests are unit-level.

**Result: PASS with notes**

---

### CHK-07: Consistency

| Check | Result |
|:------|:-------|
| STATE.md test baseline matches blueprint (2,551) | **PASS** — verified |
| DEC-007 (EROCK_ prefix) followed for new env vars | **PASS** — `.env.example` uses EROCK_ prefix |
| DEC-008 (config externalization) pattern followed | **PASS** — new fields in Settings class |
| Authority Rules non-contradictory | **FLAG** — A-02 conflicts with TASK-02 constraint (FLAG-01) |
| Dependency map accurate | **FLAG** — BATCH-163 dependency noted, but TASK-03 internal dependency incomplete (FLAG-06) |
| Source priority change documented | **FLAG** — arxiv drops from priority 1→4, no impact analysis (FLAG-05) |

---

## FLAG SUMMARY

| Flag | Severity | Area | Description | Resolution |
|:-----|:---------|:-----|:------------|:-----------|
| **FLAG-01** | **HIGH** | TASK-02 / Architecture | `_deduplicate()` returns `list[Paper]` but `RelevanceFilter.filter()` expects `list[SearchResult]`. Blueprint requires filter after dedup (A-02) AND no RelevanceFilter modification (TASK-02e). These constraints are irreconcilable without an undocumented conversion step. | Lead must: (a) add explicit conversion from `list[Paper]` → `list[SearchResult]` before filter call, or (b) modify `_deduplicate()` return type to `list[SearchResult]`. Document chosen approach in TASK-02 description. |
| **FLAG-02** | MEDIUM | Scope / TASK-03 | Scope states "No new data models" but TASK-03 creates `SearchSourceHealth` class. Data Models section omits it. | Add `SearchSourceHealth` to Data Models section, or revise scope statement to "No new database models." |
| **FLAG-03** | LOW | Data Models | `relevance_filter.py` stated as 134 lines, actual count is **110 lines**. | Correct line count in blueprint. |
| **FLAG-04** | LOW | TASK-01 | `PubMedSource(api_key=...)` wiring not explicitly specified. `settings.pubmed_api_key` must flow to constructor but TASK-01 only says "conditionally add PubMedSource." | Add explicit sub-step: "pass `settings.pubmed_api_key` to `PubMedSource(api_key=...)`." |
| **FLAG-05** | LOW | TASK-01 / A-01 | Source priority change reorders arxiv from rank 1 → 4. Current code: `{s2:0, arxiv:1, openalex:2}`. Proposed: `{s2:0, pubmed:1, openalex:2, crossref:3, arxiv:4}`. No impact analysis. | Add note to TASK-01 explaining that arxiv preference drops because PubMed and CrossRef provide richer metadata. |
| **FLAG-06** | LOW | TASK-03 / Dependencies | TASK-02 and TASK-03 both modify `search_service.py`. TASK-03 depends only on TASK-01, not TASK-02. Sequential execution mitigates, but dependency graph is incomplete. | Add TASK-02 as explicit dependency of TASK-03. |

---

## VERDICT

### **ACCEPT WITH MODIFICATIONS**

**Rationale:** The batch goal is clear, achievable, and accurately scoped. All referenced modules exist and are production-ready. The test plan is well-structured with proper traceability. Hard boundaries are testable and map to actual codebase constraints.

**However**, FLAG-01 represents a genuine architectural gap that cannot be resolved without modifying the blueprint. The `list[Paper]` vs `list[SearchResult]` type mismatch between `_deduplicate()` output and `RelevanceFilter.filter()` input is not addressed, and the three constraints (filter-after-dedup, don't-modify-filter, wire-filter) are mutually irreconcilable as written. The Lead **must** address FLAG-01 before execution.

FLAG-02 through FLAG-06 are lower severity and can be resolved as documentation corrections during Lead Response.

**Required modifications before execution:**
1. Resolve FLAG-01: Choose and document Paper→SearchResult conversion strategy
2. Resolve FLAG-02: Update scope or data models section
3. Resolve FLAG-03–FLAG-06: Documentation corrections

═══════════════════════════════════════════════════════════

## LEAD RESPONSE SECTION

*To be completed by ivory-wolf after review.*

**Reviewer Report ID:** RR-155-1
**Review Cycle:** 1
**Lead Decision:** [ ] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

If ACCEPT WITH MODIFICATIONS — list each Reviewer flag acted on:
  FLAG-01 → Action taken:
  FLAG-02 → Action taken:
  FLAG-03 → Action taken:
  FLAG-04 → Action taken:
  FLAG-05 → Action taken:
  FLAG-06 → Action taken:

Blueprint Version after response:
Lead Sign:                ivory-wolf + YYYY-MM-DD HH:MM

═══════════════════════════════════════════════════════════
