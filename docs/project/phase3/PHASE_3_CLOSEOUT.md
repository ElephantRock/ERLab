# Phase 3 Closeout — Live Product Validation (interim)

> **Phase 3 is NOT complete.** 1 of 3 live runs completed; Run B is blocked.
> **Outcome: LIVE_PATH_BLOCKED.**
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `6feba96c49483bf83de6dde622d12e1287071380` |
| **Current HEAD** | `6d29fd161376236c6cce9e2138aa4b1409679582` |
| **Blocker-fix commits** | `a10c768` (B-01–B-04), `c4bf84b` (B-05) |
| **Superseded closeouts** | `e2f0eed`, `3efd81f` |
| **Working tree** | clean |

---

## Run matrix

| Run | Input | Status | Result |
|---|---|---|---|
| **A** (historical topic) | Question only | **COMPLETED** | 2 ideas, 2 proposals, **2 full papers** (2675 + 2649 words). Paper evaluation (scope=paper, 7-dim). Exports (MD/LaTeX/BibTeX) non-empty. |
| **B** (clinical shift) | Question + domain + queries | **BLOCKED** | 2 ideas, 2 proposals. Paper synthesis stuck in section-wise timeout (>90 min). 0 papers. |
| C (urban heat) | Domain only | NOT STARTED | Blocked by Run B finding. |

## Run A detailed results

**Run A completed end-to-end** through the production orchestration path with z.ai glm-4.6. This is the first live full-paper generation in the project.

### Stage execution
| Stage | Status | Elapsed |
|---|---|---|
| literature_search | executed | 19.8s |
| ingestion | skipped_by_error (embedding) | 50.0s |
| gap_analysis | executed | 95.2s |
| idea_generation | executed | 150.5s |
| novelty_checking | skipped_by_error (governed runtime) | 14.6s |
| feasibility_scoring | executed | 199.6s |
| proposal_synthesis | executed | 963.1s |
| adversarial_review | executed (bounded by B-05 fix) | 1200.0s |
| evaluation | executed | 47.7s |
| paper_synthesis | executed | 273.8s |
| citation_audit | executed | 120.4s |
| proposal_deepening | executed | 71.8s |
| export | executed | 0.0s |

### Papers produced
| Paper | Title | Words | Chars | Paper eval | Proposal eval |
|---|---|---|---|---|---|
| 1 | LogicBench: A Benchmark for Neuro-Symbolic Consistency... | 2675 | 13771 | paper/ready (7-dim) | present |
| 2 | Symbolic Counterfactual Auditing for Faithful NS... | 2649 | 15692 | paper/ready (7-dim) | present |

### Exports verified
| Format | Status | Size | Content |
|---|---|---|---|
| Markdown | 200 | 13780 chars | paper content |
| LaTeX | 200 | 14565 chars | has \documentclass |
| BibTeX | 200 | 236 chars | has @misc entry |

### Trust & Sources
Paper evaluation (scope=paper) and proposal evaluation (scope=proposal) are distinct. 0 resolved sources (ingestion failure means no reference resolution). Human review: not_started.

## Run B blocking issue

Run B's proposals are longer than Run A's (4392 chars vs 1840–2448 chars), which triggers **section-wise paper synthesis** instead of the monolithic path. Section-wise synthesis makes 7+ sequential LLM calls per proposal. With glm-4.6's latency, this exceeds the 1800s stage timeout. The log shows:
- Proposal 0: section-wise completed (995 words, 6/7 sections) within one timeout window
- Proposal 1: section-wise stuck on "available output=6" (model output budget exhausted), timing out repeatedly

This is a new blocker (B-08): **paper_synthesis section-wise path times out when proposals are long enough to exhaust the model's output budget.** The monolithic path (used by Run A) completes in ~273s; the section-wise path (triggered by Run B) cannot complete within 1800s.

## Open blockers

| ID | Description | Status |
|---|---|---|
| B-06 | Ingestion embedding failures → no resolved references | OPEN (quality degradation) |
| B-07 | Novelty governed vector runtime mismatch | OPEN (non-fatal) |
| **B-08** | **Paper synthesis section-wise path times out with long proposals** | **OPEN (path blocker for Runs B and C)** |

## What was validated

- **The core product claim works live** (Run A): research question → literature search → gap analysis → idea generation → proposal synthesis → adversarial review → evaluation → **paper synthesis** → citation audit → export.
- **Paper persistence works live**: both papers persisted on Proposal rows, retrievable through the API, with paper evaluation (scope=paper) and proposal evaluation (scope=proposal) both distinct.
- **Exports work live**: all three formats return non-empty paper content.
- **Trust & Sources works live**: the review payload loads with distinct evaluation scopes.
- **The adversarial_review B-05 fix works**: the stage completed within 1200s instead of exceeding 1800s.

## What was NOT validated

- Runs B and C (blocked by B-08).
- Citation-existence audit (not executable without resolved references).
- Claim-support audit.
- Research-quality review.
- Historical comparison (requires Run A paper audit + historical fixture audit).
- User effort across multiple runs.
- The freeze rule held (no tuning between runs).

## Product-readiness outcome

### **LIVE_PATH_BLOCKED**

Run A validates the core product claim against a live provider. Run B reveals that paper synthesis cannot reliably complete when the section-wise path is triggered by longer proposals. This is a path blocker for Runs B and C.

## Cost

<$1.00 total across all attempts.

## P1E artifacts changed = 0

## Retrieval architecture changed = 0

## Production code changes

5 files (commits `a10c768`, `c4bf84b`): pipeline.py, model_manager.py, catalog.py, openai_provider.py, stages.py + test_phase3_live_blockers.py.

## Next work

B-08 must be diagnosed and repaired (same approach as B-05: determine if section-wise synthesis is mandatory or fail-open, then bound it) before repeating Run B. Runs B and C, citation audits, claim-support review, and output comparison begin only after the section-wise path is repaired.

---

*Phase 3 is NOT complete. 1/3 runs completed. 2/3 blocked by B-08 (paper synthesis section-wise timeout).*
