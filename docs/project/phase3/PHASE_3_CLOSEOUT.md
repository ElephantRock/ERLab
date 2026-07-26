# Phase 3 Closeout — Live Product Validation (interim)

> **Phase 3 is NOT complete.** Run A completed with papers; Run B failed 4 times with 4 different failure modes.
> **Outcome: LIVE_PATH_BLOCKED.**
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `6feba96c49483bf83de6dde622d12e1287071380` |
| **Current HEAD** | `9d747fbcb4e10cc8f9ed4f981bfcf06f93b88449` |
| **Code-fix commits** | `a10c768`, `c4bf84b`, `eddd0a9`, `c3283c1`, `9d747fb` |
| **Working tree** | clean |

---

## Run matrix

| Run | Input | Attempts | Final status | Result |
|---|---|---|---|---|
| **A** (historical topic) | Question only | 5 (after 4 blocker repairs) | **COMPLETED** | 2 papers (2675 + 2649 words), evaluated, exported |
| **B** (clinical shift) | Question + domain + queries | 4 | **FAILED** | 0 papers (4 different failure modes) |
| C (urban heat) | Domain only | 0 | NOT STARTED | Blocked |

## Run B failure modes (4 attempts, 4 distinct failures)

| Attempt | Run ID | Failure | Root cause |
|---|---|---|---|
| 1 | run_6fb7057c88d4 | paper_synthesis section-wise timeout (>90 min) | Section-wise path exceeds stage timeout (B-08, fixed) |
| 2 | run_2a00c7cdfdc1 | paper_synthesis NameError | B-08 method extraction import bug (fixed in c3283c1) |
| 3 | run_b403492a56a1 | gap_analysis 0 gaps (LLM returned 180 papers, LLM call OK, but parsed to 0 gaps) | Parsing boundary undiagnosed (B-09 diagnostic logging added) |
| 4 | run_f18e8ccdd2f2 | literature_search 0 papers (PubMed EFetch 429 on all batches) | **External API rate-limiting** — not a product defect |

Attempt 4 is a different class of failure: PubMed returned 429 (Too Many Requests) on all EFetch calls after successful ESearch. The pipeline correctly halted when no papers were found. Crossref and arXiv responses arrived after the halt. This is external API rate-limiting, not a product defect.

## Code changes made

| Commit | Fix | Type |
|---|---|---|
| `a10c768` | B-01 run-detail string run_id; B-02 model catalog URL + cloud fallback; B-03 logger NameError; B-04 ChromaDB reset | Code fix |
| `c4bf84b` | B-05 adversarial_review per-proposal timeout (600s) | Code fix |
| `eddd0a9` | B-08 paper_synthesis per-proposal timeout (600s) | Code fix |
| `c3283c1` | B-08 import fix in extracted method | Code fix |
| `9d747fb` | B-09 gap analysis diagnostic logging | Code fix (logging only) |

## Post-code verification (after all fixes)

| Check | Result |
|---|---|
| Focused gap + synthesis + adversarial tests | 18 passed |
| Phase 1 + Phase 2 controlled integrations | 4 passed |
| Architecture seals | 41 passed, 0 failed |
| Ranking suite | 253 passed, 3 skipped |
| Frontend | 988 tests, build clean, budgets hold |
| Full backend selector | 138 failed, 4636 passed, 47 skipped |
| Node-ID diff vs Phase 2 baseline | 2 new (B-09 caplog test-isolation artifacts), 0 removed |
| Phase-3 production-code-attributable failures | 0 |

## Open issues

| ID | Description | Status |
|---|---|---|
| B-06 | Ingestion embedding failures → no resolved references | OPEN |
| B-07 | Novelty governed vector runtime mismatch | OPEN (non-fatal) |
| B-09 | gap_analysis diagnostic logging added; root cause of attempt-3 empty gaps still unknown (would need a live LLM response to diagnose) | DIAGNOSTIC ONLY |
| B-10 | **External API rate-limiting (PubMed 429) prevents literature retrieval** — not a product defect but an operational reliability concern | EXTERNAL |

## Product-readiness outcome

### **LIVE_PATH_BLOCKED**

Run A validates live paper generation for one topic. Run B cannot complete due to external API rate-limiting (attempt 4) and an unresolved gap-analysis boundary (attempt 3). The pipeline cannot reliably complete across different research topics with the current external service configuration.

## P1E artifacts changed = 0

## Retrieval architecture changed = 0

## Working tree status

**clean** at closeout.

---

*Phase 3 is NOT complete. 1/3 runs completed. Run B stopped after 4 attempts per contract.*
