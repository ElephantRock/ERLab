# Phase 3 Closeout — Live Product Validation

> **Phase 3 closeout.** Records the fields specified in the Work Package.
> **Outcome: QUALITY_REMEDIATION_REQUIRED.**
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `6feba96c49483bf83de6dde622d12e1287071380` |
| **Final commit** | (this closeout + blocker fixes at `a10c768`) |
| **Working tree at closeout** | clean |

---

## Provider/model

z.ai glm-4.6 (`openai_base_url=https://api.z.ai/api/coding/paas/v4`, `openai_model=glm-4.6`). Frozen before execution; unchanged across runs.

## Spend cap and observed cost

**$100.00 hard cap** (user-authorized), budget guard enabled. **Observed cost: <$0.50** (multiple LLM calls across 5 run attempts; none reached full synthesis). Budget guard time limit raised to 1800s for deep_research runs (default 600s was too short).

## Run matrix

| Run | Input | Strategy | Status | Result |
|---|---|---|---|---|
| **A** (historical topic) | Research question only | deep_research | **PARTIAL** (5 attempts) | 2 ideas, 2 proposals, **0 papers** (adversarial_review timeout blocked paper_synthesis) |
| B (clinical shift) | Not attempted | deep_research | NOT STARTED | Blocked by Run A adversarial_review finding |
| C (urban heat) | Not attempted | deep_research | NOT STARTED | Blocked by Run A adversarial_review finding |

## Blocker repairs (code changes)

Four fixes were required to unblock the live pipeline (commit `a10c768`):

1. **B-01: run-detail API rejected string run_id (422).** Fixed: accept str, resolve via numeric-then-string lookup.
2. **B-02: model catalog used hardcoded api.openai.com instead of configured z.ai base_url.** Fixed: use `settings.openai_base_url` + cloud-model fallback when `/v1/models` returns 404.
3. **B-03: `logger` NameError in openai_provider.py structured-output path.** Fixed: added `import logging` + `logger = logging.getLogger(__name__)`.
4. **B-04: ChromaDB corruption crashed VectorStore.__init__.** Fixed operationally (fresh DB; no code change).

## Actual executed stages (Run A, retry 5 — the furthest attempt)

| Stage | Status | Elapsed |
|---|---|---|
| literature_search | executed | 24.9s |
| ingestion | skipped_by_error (embedding 400) | 48.2s |
| gap_analysis | executed | 94.5s |
| gap_reflection | executed | 0.0s |
| idea_generation | executed | ~200s |
| idea_reflection | executed | 0.0s |
| novelty_checking | executed (degenerate — governed vector runtime not configured) | 0.0s |
| feasibility_scoring | executed | ~144s |
| mechanical_metrics | executed | 0.0s |
| proposal_synthesis | executed | ~360s |
| adversarial_review | **TIMED OUT (1800s × 4 retries)** | >1800s |
| evaluation → export | **not reached** | — |

## Per-run completion result

| Run | Ideas | Proposals | Paper | Evaluation | Exports |
|---|---|---|---|---|---|
| A | 2 | 2 (965 + 2499 chars) | **0** (blocked) | absent | none |

## Paper persistence results

No paper produced. The pipeline reached `proposal_synthesis` (2 proposals persisted) but the `adversarial_review` stage repeatedly exceeded its 1800s timeout with glm-4.6, blocking `paper_synthesis`.

## Citation-existence findings

Not applicable — no papers produced.

## Claim-support findings

Not applicable — no papers produced.

## Research-quality findings

Not applicable — no papers produced. The 2 generated proposals are short (965, 2499 chars) — likely stub-level given multiple stages executed in 0.0s (degenerate output from failed LLM calls or empty inputs).

## Historical comparison

Not applicable — Run A did not produce a paper to compare against the historical fixture.

## User effort

| Metric | Run A |
|---|---|
| Required inputs | 1 (research question via POST /api/v1/pipeline/run) |
| Manual actions | Multiple: 5 retry attempts, env var fixes, ChromaDB reset, backend restarts |
| Failures requiring intervention | 4 code blockers + 1 stage timeout + embedding failures |
| Elapsed to first completed paper | **Never** |
| Could user understand failures without logs | **No** — pipeline shows "running" indefinitely during timeouts; no progress visible |

## Blockers

| ID | Description | Status |
|---|---|---|
| B-01 | run-detail API rejects string run_id | **FIXED** (`a10c768`) |
| B-02 | model catalog uses wrong URL | **FIXED** (`a10c768`) |
| B-03 | logger NameError in openai_provider | **FIXED** (`a10c768`) |
| B-04 | ChromaDB corruption | **FIXED** (operational reset) |
| B-05 | **adversarial_review exceeds 1800s timeout with glm-4.6** | **OPEN** — stage times out and retries 4×, blocking paper_synthesis for 2+ hours |
| B-06 | **ingestion embedding 400 Bad Request** | **OPEN** — certain batch requests rejected by LM Studio; ingestion fails, literature not embedded |
| B-07 | **novelty_checking requires governed vector runtime** | **OPEN** — fresh ChromaDB lacks the governed runtime; novelty runs degenerate |

## Improvements

| ID | Description |
|---|---|
| I-01 | The orchestrator's background task needs a watchdog: a run producing no stage progress for N minutes should fail explicitly, not hang indefinitely |
| I-02 | Pipeline structlog output doesn't reach uvicorn stdout — pipeline progress is invisible during execution |
| I-03 | Semantic Scholar excluded (no API key) — limits literature coverage |
| I-04 | The embedding model name auto-correction picks listed-but-unloaded models from LM Studio's /models endpoint |

## Product-readiness outcome

### **QUALITY_REMEDIATION_REQUIRED**

The live workflow partially works — literature search, gap analysis, idea generation, and proposal synthesis all execute through the production orchestration path with live z.ai glm-4.6 calls. **But the pipeline cannot reliably complete to a full paper** because:

1. The adversarial_review stage repeatedly exceeds its timeout (B-05), blocking paper_synthesis.
2. Ingestion fails (B-06), so literature is not embedded into the vector store.
3. Novelty checking runs degenerate (B-07) without a governed vector runtime.

These are operational reliability defects, not architectural failures. The controlled integration paths (Phases 1-2) remain valid. The live path requires hardening before it can produce reviewable papers.

**This proceeds to Phase 4 with quality/reliability defects as the priority.**

## Controlled integration results

Not re-run (Phase 3 code changes were blocker fixes only, verified against architecture + ranking suites). Phase 1 and Phase 2 controlled integrations remain valid from their respective phases.

## Architecture result

**41 passed, 0 failed** (after blocker fixes).

## Ranking result

**253 passed, 3 skipped** (after blocker fixes). No P1E artifact changed.

## Frontend result

Not re-run (Phase 3 made no frontend changes). Phase 2 baseline holds.

## Full backend baseline

Not re-run. Phase 3 changed 4 backend files (blocker fixes); architecture + ranking suites pass (294/294). A full-selector run would confirm the 136 baseline failures are unchanged, but the spec allows preserving the baseline when changes are bounded and verified against focused suites.

## Production-code changes

**4 files** (blocker fixes, commit `a10c768`): `backend/api/routes/pipeline.py` (B-01), `backend/providers/model_manager.py` (B-02), `backend/providers/catalog.py` (B-02), `backend/providers/openai_provider.py` (B-03). No P1E artifacts, no retrieval architecture, no frontend.

## Known limitations

1. **No paper was produced in any live run.** The pipeline reaches proposal_synthesis but adversarial_review blocks paper_synthesis.
2. **Runs B and C were not attempted** because the adversarial_review timeout applies to all deep_research runs.
3. **No citation, claim-support, or research-quality evidence** was produced (requires completed papers).
4. **The 2 proposals generated are short** (965, 2499 chars) — likely stubs from degenerate stages.
5. **Multiple stages executed in 0.0s** — indicating empty/degenerate inputs from earlier stage failures cascading forward.

## P1E artifacts changed = 0

## Retrieval architecture changed = 0

## Working tree status

**clean** at closeout.

---

*End of Phase 3. Outcome: QUALITY_REMEDIATION_REQUIRED. The live pipeline partially works but cannot reliably produce a full paper. Three open blockers (adversarial_review timeout, ingestion embedding failure, novelty vector runtime) are the Phase 4 priority.*
