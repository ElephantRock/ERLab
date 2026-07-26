# Phase 3 Closeout — Live Product Validation (interim)

> **Phase 3 is NOT complete.** Runs A and B completed with papers; Run C not attempted.
> **Outcome: LIVE_PATH_BLOCKED** (Run C + quality audits remain).
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `6feba96c49483bf83de6dde622d12e1287071380` |
| **Current HEAD** | `5e09c47dbe128b10c4a3bd6573930c469119f330` |
| **Code-fix commits** | `a10c768`, `c4bf84b`, `eddd0a9`, `c3283c1`, `9d747fb`, `5e09c47` |
| **Working tree** | clean |

---

## Run matrix

| Run | Input | Status | Result |
|---|---|---|---|
| **A** (historical topic) | Question only | **COMPLETED** | 2 papers (2675 + 2649 words), evaluated, exported |
| **B** (clinical shift) | Question + domain + queries | **COMPLETED** (attempt 5) | 2 papers (2807 + 2475 words), evaluated, exported |
| C (urban heat) | Domain only | NOT STARTED | — |

## Run B completion (attempt 5, after B-10 fix)

All 17 stages executed end-to-end. B-10 fix (premature source aggregation) allowed literature search to find 196 unique papers from 237 total. B-05 fix (adversarial_review timeout) bounded the stage to 1200s. B-08 fix (paper_synthesis timeout) allowed section-wise synthesis to complete in 644s.

### Papers produced
| Paper | Title | Words | Chars | Paper eval | Proposal eval |
|---|---|---|---|---|---|
| 1 | Multi-View Contrastive Domain Adaptation for Cross-Site Clin... | 2807 | 15009 | paper/ready (7-dim) | present |
| 2 | Topology-Preserving Synthetic Data for Non-Stationary Clinic... | 2475 | 14690 | paper/ready (7-dim) | present |

### Exports verified
| Format | Status | Size |
|---|---|---|
| Markdown | 200 | 15010 chars |
| LaTeX | 200 | 16148 chars |
| BibTeX | 200 | 237 chars |

### Trust & Sources
Paper evaluation (scope=paper) and proposal evaluation (scope=proposal) distinct. 0 resolved sources (ingestion failure persists).

## Code changes (all blocker repairs)

| Commit | Fix |
|---|---|
| `a10c768` | B-01 run-detail string run_id; B-02 model catalog URL; B-03 logger NameError; B-04 ChromaDB reset |
| `c4bf84b` | B-05 adversarial_review per-proposal timeout |
| `eddd0a9` | B-08 paper_synthesis per-proposal timeout |
| `c3283c1` | B-08 import fix |
| `9d747fb` | B-09 gap analysis diagnostic logging |
| `5e09c47` | B-10 premature source aggregation (PubMed partial→failed + gather return_exceptions=True) |

## What was validated

Two production-API-started live runs (A + B) each produced two persisted, paper-evaluated, exportable full papers through z.ai glm-4.6. All three export formats return non-empty paper content. Paper evaluation (scope=paper, 7-dim) and proposal evaluation (scope=proposal) are both distinct.

## What was NOT validated

- Run C not attempted.
- UI-started run not proven.
- Ingestion failed on every run → 0 resolved sources in Trust & Sources.
- Citation-existence, claim-support, and research-quality audits not performed.
- Historical comparison not performed.

## Open issues

| ID | Description | Status |
|---|---|---|
| B-06 | Ingestion embedding failures → no resolved references | OPEN |
| B-07 | Novelty governed vector runtime mismatch | OPEN (non-fatal) |
| B-09 | Gap analysis diagnostic logging added; attempt-3 root cause unknown | DIAGNOSTIC ONLY |

## Product-readiness outcome

**LIVE_PATH_BLOCKED** (Run C + quality audits remain). Runs A and B validate that the live pipeline can produce full papers across different research topics.

## P1E artifacts changed = 0 | Retrieval architecture changed = 0 | Working tree: clean

---

*Phase 3 is NOT complete. 2/3 runs completed (A + B). Run C + quality audits remain.*
