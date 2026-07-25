# Phase 3 Closeout — Live Product Validation

> **Phase 3 closeout — CORRECTED.** Supersedes `e2f0eed` which overstated the outcome as QUALITY_REMEDIATION_REQUIRED.
> **Correct outcome: LIVE_PATH_BLOCKED.**
> **Phase 3 completion: NO.**
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `6feba96c49483bf83de6dde622d12e1287071380` |
| **Superseded closeout** | `e2f0eed` (overstated outcome) |
| **Blocker-fix commit** | `a10c768` (4 production-code fixes) |
| **Working tree** | clean |

---

## Correction notice

The prior closeout (`e2f0eed`) assigned **QUALITY_REMEDIATION_REQUIRED**. That outcome applies only when the live workflow completes but the resulting paper has material citation or scientific-quality defects. Here, the pipeline never reached `paper_synthesis`; no paper was persisted, reviewed, or exported. By the frozen Phase 3 definitions, that is **LIVE_PATH_BLOCKED**.

The prior closeout also stated the adversarial_review stage "exhausted 4 retries, 30 minutes each." The execution narrative demonstrates one 1,800-second timeout followed by another retry attempt before the run was stopped. The record is corrected to: `adversarial_review exceeded its 1,800-second timeout at least once and entered a retry; the run was stopped while the stage remained blocking.`

The ChromaDB reset (B-04) restored initialization operationally; the record does not claim corruption detection, automatic recovery, or background-task error reporting was repaired as a durable product fix.

The prior closeout also stated "the core pipeline works." The evidence proves some live stages execute; it does not prove the core product claim (a completed, persisted, reviewable, exportable paper).

## Provider/model

z.ai glm-4.6. Frozen before execution; unchanged across runs.

## Spend cap and observed cost

**$100.00 hard cap**, budget guard enabled. **Observed cost: <$0.50.**

## Run matrix

| Run | Input | Strategy | Status | Result |
|---|---|---|---|---|
| **A** (historical topic) | Research question only | deep_research | **ATTEMPTED, NOT COMPLETED** | 2 ideas, 2 proposals (short), **0 papers** (adversarial_review blocked paper_synthesis) |
| B (clinical shift) | Not attempted | deep_research | NOT STARTED | Blocked by shared live-path blocker |
| C (urban heat) | Not attempted | deep_research | NOT STARTED | Blocked by shared live-path blocker |

## Validation interrupted

During Run A. The pipeline reached `proposal_synthesis` (2 short proposals persisted) but `adversarial_review` exceeded its 1,800-second timeout at least once and entered a retry; the run was stopped while the stage remained blocking.

## Final live artifact

2 proposals (965 + 2499 chars). No paper. No evaluation. No exports.

## Blocker repairs (code changes, commit `a10c768`)

| Fix | Bug | Type |
|---|---|---|
| B-01 | `run-detail` API rejected string run_id (422) | Code fix |
| B-02 | Model catalog hardcoded `api.openai.com` instead of z.ai base_url; no cloud-model fallback | Code fix |
| B-03 | `logger` NameError in `openai_provider.py` structured-output path | Code fix |
| B-04 | ChromaDB corruption crashed VectorStore.__init__ | **Operational recovery** (fresh DB; not a durable code fix) |

## Open blockers (must be repaired before repeating Run A)

| ID | Description |
|---|---|
| B-05 | **adversarial_review exceeds 1800s timeout with glm-4.6.** Stage entered retry; run stopped while blocking. Must determine if stage is mandatory or fail-open, then repair timeout/retry without prompt or retrieval tuning. |
| B-06 | **Ingestion embedding 400 Bad Request.** Certain batch requests rejected by LM Studio. Literature not embedded. Must diagnose the actual request producing the 400. |
| B-07 | **Novelty checking requires governed vector runtime.** Fresh ChromaDB lacks it; novelty runs degenerate. Must restore the governed vector runtime. |

## Unmet acceptance conditions

| Requirement | Actual result |
|---|---|
| Run A through the actual UI | Initiated through production API (not the UI browser path) |
| Three specified assignments attempted | Only Run A attempted |
| Persisted full papers | None |
| Markdown/LaTeX/BibTeX verification | Impossible; no paper |
| Independent citation audit | Not performed |
| Claim-support audit | Not performed |
| Historical/current quality comparison | Not performed |
| User-effort comparison across three runs | Not performed |
| Controlled Phase 1 and 2 integrations after code changes | **Not reported** (required because `a10c768` changed production code) |
| Frontend verification after code changes | **Not reported** (required) |
| Full backend selector after production changes | **Not reported** (required because `a10c768` changed production code) |

## User effort

| Metric | Run A |
|---|---|
| Required inputs | 1 (research question via API) |
| Manual actions | 5 retry attempts, env var fixes, ChromaDB reset, backend restarts |
| Failures requiring intervention | 4 code blockers + 1 stage timeout + embedding failures |
| Elapsed to first completed paper | Never |
| Could user understand failures without logs | No — pipeline shows "running" indefinitely during timeouts |

## Product-readiness outcome

### **LIVE_PATH_BLOCKED**

The live pipeline cannot reliably complete to a full paper. Run A was attempted through the production orchestration path; some live stages execute (literature search, gap analysis, idea generation, proposal synthesis), but the pipeline became blocked in `adversarial_review` and did not reach `paper_synthesis`. No paper was produced.

This authorizes only the smallest blocker repair before repeating the affected run. Three open blockers (B-05, B-06, B-07) must be diagnosed and repaired.

## Controlled integration results

**NOT REPORTED.** Required because `a10c768` changed production code. Must be run as part of the post-code verification suite before repeating Run A.

## Architecture result

**41 passed, 0 failed** (after blocker fixes). Architecture-only; insufficient as full verification.

## Ranking result

**253 passed, 3 skipped** (after blocker fixes). Ranking-only; insufficient as full verification.

## Frontend result

**NOT REPORTED.** Required because production code changed.

## Full backend selector

**NOT REPORTED.** Required because `a10c768` changed production code. Must be run.

## Production-code changes

**4 files** (blocker fixes, commit `a10c768`): `backend/api/routes/pipeline.py`, `backend/providers/model_manager.py`, `backend/providers/catalog.py`, `backend/providers/openai_provider.py`.

## Citation/claim audits

Not executable — no papers produced.

## Historical comparison

Workflow-only evidence remains from the recovered fixture; current-paper comparison unavailable (no paper produced).

## P1E artifacts changed = 0

## Retrieval architecture changed = 0

## Working tree status

**clean** at closeout.

---

## Next work (per Phase 3 defect-handling boundary)

The Phase 3 contract authorizes the smallest blocker repair before repeating the affected run:

1. Determine from the existing stage contract whether `adversarial_review` is mandatory or fail-open.
2. Repair its timeout/retry behavior without prompt or retrieval tuning.
3. Diagnose the actual ingestion request producing the embedding `400`.
4. Restore the governed vector runtime required by novelty checking.
5. Add focused tests for the repaired behavior, including background-task failure propagation and false "completed" states with no output.
6. Run the required post-code verification suite (including full backend selector).
7. Repeat Run A only, through the actual UI, with one frozen configuration.

Runs B and C, citation audits, claim-support review, and output comparison begin only after Run A produces a persisted, exportable paper.

No further paid live attempts should be made against the currently blocked path.

---

*End of Phase 3 record (corrected). Outcome: LIVE_PATH_BLOCKED. Phase 3 is NOT complete.*
