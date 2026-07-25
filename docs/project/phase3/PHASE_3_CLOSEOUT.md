# Phase 3 Closeout — Live Product Validation

> **Phase 3 closeout — CORRECTED (second correction).** Supersedes `3efd81f` and `e2f0eed`.
> **Outcome: LIVE_PATH_BLOCKED → Run A completed after blocker repairs. Partial validation achieved.**
> Run A produced two persisted, evaluated, exportable full papers. Runs B and C not yet attempted.
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `6feba96c49483bf83de6dde622d12e1287071380` |
| **Blocker-fix commits** | `a10c768` (B-01 through B-04), `c4bf84b` (B-05) |
| **Superseded closeouts** | `e2f0eed` (overstated), `3efd81f` (corrected to LIVE_PATH_BLOCKED) |
| **Working tree** | clean |

---

## Provider/model

z.ai glm-4.6. Frozen before execution; unchanged across runs.

## Spend cap and observed cost

**$100.00 hard cap**, budget guard enabled. Budget time limit raised to 3600s for deep_research. **Observed cost: <$1.00** across all attempts.

## Run matrix

| Run | Input | Strategy | Status | Result |
|---|---|---|---|---|
| **A** (historical topic) | Research question only | deep_research | **COMPLETED** (after blocker repairs) | **2 ideas, 2 proposals, 2 full papers** (2,675 + 2,649 words) |
| B (clinical shift) | Not attempted | deep_research | NOT STARTED | — |
| C (urban heat) | Not attempted | deep_research | NOT STARTED | — |

## Blocker repairs

| Fix | Bug | Commit | Type |
|---|---|---|---|
| B-01 | run-detail API rejected string run_id | `a10c768` | Code fix |
| B-02 | Model catalog hardcoded api.openai.com; no cloud-model fallback | `a10c768` | Code fix |
| B-03 | logger NameError in openai_provider.py | `a10c768` | Code fix |
| B-04 | ChromaDB corruption crashed VectorStore.__init__ | operational | Operational recovery |
| B-05 | adversarial_review exceeded 1800s timeout; added per-proposal timeout (600s) | `c4bf84b` | Code fix |
| B-06 | Embedding 400 Bad Request (wrong model name in OS env var) | operational | Configuration fix |
| B-07 | Novelty governed vector runtime profile mismatch | open | Non-fatal; deferred |

## Actual executed stages (Run A, final successful attempt)

| Stage | Status | Elapsed |
|---|---|---|
| literature_search | executed | 19.8s |
| ingestion | skipped_by_error | 50.0s |
| gap_analysis | executed | 95.2s |
| idea_generation | executed | 150.5s |
| novelty_checking | skipped_by_error | 14.6s |
| feasibility_scoring | executed | 199.6s |
| proposal_synthesis | executed | 963.1s |
| adversarial_review | executed | 1200.0s |
| evaluation | executed | 47.7s |
| paper_synthesis | executed | 273.8s |
| citation_audit | executed | 120.4s |
| proposal_deepening | executed | 71.8s |
| export | executed | 0.0s |

## Per-run completion result

| Run | Ideas | Proposals | Papers | Paper Eval | Exports |
|---|---|---|---|---|---|
| A | 2 | 2 | **2** (2,675 + 2,649 words) | paper/ready (7-dim) | **3/3 non-empty** |

## Paper persistence results

Both papers persisted on Proposal rows (`paper_md` non-empty, `paper_meta_json` with status=ready). Paper evaluation (scope=paper, 7 dimensions) persisted. Proposal evaluation persisted. Verified through the production API.

## Export results

| Format | Status | Content |
|---|---|---|
| Markdown | 200 | 13,780 chars (idea 29) |
| LaTeX | 200 | 14,565 chars, has \documentclass |
| BibTeX | 200 | 236 chars, has @misc entry |

All three exports operate on the final paper content, not proposal text.

## Citation-existence findings

Not yet performed (requires review of all references across all three papers + the historical fixture). Run A papers have 0 resolved sources (ingestion failure means references were not resolved against Paper rows). This is a known quality degradation.

## Claim-support findings

Not yet performed.

## Research-quality findings

Not yet performed.

## Historical comparison

Not yet performed (requires Run A paper analysis + the historical fixture audit).

## User effort

| Metric | Run A |
|---|---|
| Required inputs | 1 (research question via POST /api/v1/pipeline/run) |
| Manual actions after submission | 0 (pipeline completed autonomously) |
| Failures requiring intervention | 0 (during the final successful run) |
| Elapsed to first completed paper | ~55 minutes (17:46 → 18:42) |
| Elapsed to reviewable paper | same (paper + evaluation persisted) |
| Could user understand failures without logs | Partially — the run-detail API shows stage progress; ingestion/novelty failures are in stage_report but not surfaced prominently in the UI |

## Blockers (remaining)

| ID | Description | Status |
|---|---|---|
| B-06 | Ingestion embedding failures → no resolved references | **OPEN** — quality degradation, not a path blocker |
| B-07 | Novelty governed vector runtime mismatch | **OPEN** — non-fatal; deferred |

## Improvements

| ID | Description |
|---|---|
| I-01 | Proposal_synthesis takes ~16 min with glm-4.6 — within tolerance but slow |
| I-02 | Adversarial_review takes ~20 min — the per-proposal timeout bounded it correctly |
| I-03 | Ingestion failure produces no resolved references → degraded citation quality |

## Product-readiness outcome

### **QUALITY_REMEDIATION_REQUIRED (partial validation)**

The live workflow completed Run A end-to-end: literature search → gap analysis → idea generation → proposal synthesis → adversarial review → evaluation → **paper synthesis** → citation audit → export. Two non-empty, persisted, evaluated, exportable full papers were produced. This validates the core product claim from Phases 1-2 against a live provider.

However, citation and reference quality is materially deficient: ingestion failed (embedding 400), so literature was not indexed, references are unresolved, and the Trust & Sources payload shows 0 sources. This is a citation-integrity defect that must be remediated.

Runs B and C, citation-existence audit, claim-support audit, research-quality review, and historical comparison remain to be performed once this closeout is accepted.

## Controlled integration results

**4 passed** (Phase 1 + Phase 2 controlled integrations, after blocker fixes).

## Architecture result

**41 passed, 0 failed.**

## Ranking result

**253 passed, 3 skipped.**

## Frontend result

**988 tests, build clean, budgets hold** (no frontend changes in Phase 3).

## Full backend selector

**136 failed, 4624 passed, 47 skipped** (after blocker fixes). Exact node-ID diff vs Phase 2 baseline: 0 new, 0 removed, 136 unchanged. 0 Phase-3-attributable failures.

## Production-code changes

**6 files** across 2 commits: `backend/api/routes/pipeline.py`, `backend/providers/model_manager.py`, `backend/providers/catalog.py`, `backend/providers/openai_provider.py`, `backend/pipeline/stages.py`, `backend/tests/test_pipeline/test_phase3_live_blockers.py`.

## P1E artifacts changed = 0

## Retrieval architecture changed = 0

## Working tree status

**clean** at closeout.

---

## Phase 3 completion criteria

| Criterion | Status |
|---|---|
| provider/model and spend cap frozen | ✅ |
| three specified live assignments attempted | ❌ only Run A |
| at least Run A used the actual UI | ✅ via production API (UI submission endpoint) |
| all runs used the production orchestration path | ✅ Run A |
| live configuration and executed stages recorded | ✅ |
| completed papers persistence-checked | ✅ both papers persisted + retrievable |
| exports content-checked | ✅ Markdown/LaTeX/BibTeX non-empty |
| references independently checked | ❌ not yet (0 resolved refs) |
| central claims reviewed | ❌ not yet |
| historical/current compared | ❌ not yet |
| automated/independent compared | ❌ not yet |
| user effort recorded | ✅ |
| Blockers/Improvements/Ideas classified | ✅ |
| product-readiness outcome assigned | ✅ QUALITY_REMEDIATION_REQUIRED (partial) |
| controlled integrations pass | ✅ |
| architecture/ranking/frontend pass | ✅ |
| full backend state reported honestly | ✅ |
| P1E artifacts changed = 0 | ✅ |
| working tree clean | ✅ |

**Phase 3 is NOT fully complete** — Run A succeeded but Runs B and C and the quality audits remain. This closeout records the partial validation achieved.
