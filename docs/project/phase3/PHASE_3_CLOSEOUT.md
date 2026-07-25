# Phase 3 Closeout — Live Product Validation

> **Phase 3 closeout.** Records the fields specified in the Work Package.
> **Outcome: LIVE_PATH_BLOCKED.**
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `6feba96c49483bf83de6dde622d12e1287071380` |
| **Final commit** | (this closeout) |
| **Working tree at closeout** | clean |

---

## Provider/model

z.ai glm-4.6 (`openai_base_url=https://api.z.ai/api/coding/paas/v4`, `openai_model=glm-4.6`). Frozen before execution; unchanged across runs.

## Spend cap and observed cost

**$100.00 hard cap** (user-authorized), budget guard enabled (`EROCK_BUDGET_ENABLED=true`, `EROCK_BUDGET_MAX_COST_USD=100.0`). **Observed cost: <$0.01** — only one minimal provider health-check call (5 tokens) plus the initial LLM query-generation call in Run A completed before the pipeline stalled. No run reached synthesis.

## Run matrix

| Run | Input | Strategy | Status |
|---|---|---|---|
| **A** (historical topic) | Research question only: "How can graph-based reasoning and neuro-symbolic methods be combined to improve the verifiability of language-model reasoning?" | deep_research | **FAILED — stuck** |
| B (clinical shift) | Not attempted (blocked by Run A outcome) | deep_research | NOT STARTED |
| C (urban heat) | Not attempted (blocked by Run A outcome) | deep_research | NOT STARTED |

## Actual executed stages

**Run A: 0 stages completed.** The orchestrator initialized correctly (strategy=deep_research, SmartRouter enforced, embedding connected, one z.ai completion succeeded for query generation) but then produced zero further output for 33+ minutes. The background async task remained alive (SSE heartbeats continued) but no stage progressed, no error was raised, and no stage_report was written.

Runs B and C were not started because the spec's defect-handling boundary classifies Run A's failure as a Blocker, and the root cause (silent stall in the orchestrator's background task) is not a small reversible code fix — it is a live-execution reliability failure.

## Per-run completion result

| Run | Result | Elapsed | Stages | Ideas | Paper | Error |
|---|---|---|---|---|---|---|
| A | **FAILED (stuck)** | 33.6 min | 0 | 0 | none | Pipeline stuck in first stage; 0 stages completed; no error raised |
| B | not attempted | — | — | — | — | blocked by A |
| C | not attempted | — | — | — | — | blocked by A |

## Paper persistence results

No paper was produced. No persistence to verify.

## Export results and hashes

No paper to export. No hashes.

## Citation-existence findings

Not applicable — no current papers produced. The historical GoT × NSR fixture's 10 references remain unvalidated (deferred; would be audited only if a current paper were produced for comparison).

## Claim-support findings

Not applicable — no current papers produced.

## Research-quality findings

Not applicable — no current papers produced.

## Historical comparison

Not applicable — Run A did not produce a paper to compare against the historical fixture.

## Automated-versus-independent comparison

Not applicable — no automated evaluation artifacts produced.

## User effort

| Metric | Run A |
|---|---|
| Required user inputs | 1 (research question submitted via POST /api/v1/pipeline/run) |
| Pages/workspaces visited | 1 (submission); progress monitoring via DB polling (UI detail endpoint returned 422 for string run_id) |
| Manual actions after submission | 1 (manual DB status check; run-detail API returned 422 — see defect) |
| Failures requiring intervention | 1 (pipeline stuck; required manual investigation + marking run as failed) |
| Manual edits before export | n/a (no paper produced) |
| Elapsed to first completed paper | **never** (33+ min, 0 stages) |
| Elapsed to reviewable paper | never |
| Could user understand failures without logs | **No** — the UI would show "running" indefinitely; no error surfaced |

## Blockers

| ID | Description | Classification |
|---|---|---|
| B-01 | **Pipeline stalls silently in first stage.** The orchestrator's background async task initializes correctly (embedding connected, one LLM call completed) but then produces zero stage progress for 33+ minutes with no error, no stage_report, and no DB update. The task remains alive (SSE heartbeats) but does not advance. Root cause not established — likely a silent hang in literature search (many sequential external API calls) or in the LLM query-generation step through the SmartRouter/ModelManager. | **Blocker** |
| B-02 | **Run-detail API rejects string run_id.** `GET /api/v1/pipeline/runs/detail/run_7c6993c34e9c` returns 422; only the numeric DB id works (`/runs/detail/2268`). The UI's progress polling uses the string id returned by POST /run, so live progress monitoring through the UI is broken. | **Blocker** (for UI-path validation) |

## Improvements

| ID | Description |
|---|---|
| I-01 | The orchestrator's background task needs a watchdog/timeout: a run that produces no stage progress for N minutes should be marked failed with a diagnostic, not left "running" forever. |
| I-02 | The structlog output from the orchestrator's background task does not appear in the uvicorn stdout log — pipeline progress is invisible during execution. |
| I-03 | Semantic Scholar excluded (no API key) — limits literature coverage for real runs. |

## Ideas

None recorded.

## Product-readiness outcome

### **LIVE_PATH_BLOCKED**

The live pipeline cannot reliably complete. Run A — the required UI-path run — initialized correctly but stalled in the first stage for 33+ minutes with zero progress and no error. No paper was produced. The run-detail API also rejects the string run_id the submission returns, breaking UI progress monitoring.

Per the spec: *"LIVE_PATH_BLOCKED authorizes only the smallest blocker repair before repeating the affected run."* The two blockers (B-01 silent stall, B-02 run-id mismatch) are the priority for the next phase. B-02 is a small fix; B-01 requires investigation into why the orchestrator's background task silently hangs (likely in literature search or the SmartRouter LLM path).

**This outcome does not mean the product is fundamentally broken** — Phases 1 and 2 proved the controlled integration path works end-to-end. It means the *live* path has a reliability failure that must be diagnosed and repaired before live validation can proceed. The controlled-integration evidence remains valid; the live-production evidence is absent.

## Controlled integration results

Not re-run (no Phase 3 code changes). Phase 1 and Phase 2 controlled integrations remain valid from their respective phases.

## Architecture result

Not re-run (no Phase 3 code changes). Phase 2 baseline holds (41/41).

## Ranking result

Not re-run (no Phase 3 code changes). Phase 2 baseline holds (253 passed, 3 skipped).

## Frontend result

Not re-run (no Phase 3 code changes). Phase 2 baseline holds (988 tests, build, budgets).

## Full backend baseline

Phase 3 made no production or test code changes. Phase 2 executed baseline preserved:
```
136 failed, 4620 passed, 47 skipped
136 failed node IDs unchanged from Phase 1
```

## Production-code changes

**None.** Phase 3 was validation-only. The only artifacts produced are this closeout and the preflight record. No product code, no test code, no P1E artifacts, no retrieval architecture.

## Known limitations

1. **Root cause of the silent stall is not established.** The orchestrator initialized, made one LLM call, connected embeddings, then went silent. The stall could be in literature search (many sequential external calls), in the SmartRouter/ModelManager LLM path, or in an unhandled async edge case. Diagnosis requires either (a) adding diagnostic logging to the background task, or (b) running the orchestrator synchronously with full logging to observe where it hangs.
2. **Only Run A was attempted.** Runs B and C were not started because the Blocker applies to the production orchestration path all three runs share.
3. **No output-quality evidence was produced.** Phase 3's citation, claim-support, and research-quality audits could not run without generated papers.
4. **The budget guard was active but not exercised** — the stall occurred before significant cost was incurred.

## P1E artifacts changed = 0

## Retrieval architecture changed = 0

## Working tree status

**clean** at closeout.

---

## Phase 3 completion criteria

| Criterion | Status |
|---|---|
| provider/model and spend cap frozen before execution | ✅ z.ai glm-4.6, $100 cap |
| three specified live assignments attempted | ❌ only Run A attempted (blocked) |
| at least Run A used the actual UI path | ✅ POST /api/v1/pipeline/run (the UI's /pipeline/new submission endpoint) |
| all runs used the production orchestration path | ✅ Run A used production orchestrator |
| live configuration and executed stages recorded | ✅ |
| completed papers persistence-checked | ❌ no papers completed |
| exports content-checked | ❌ no papers to export |
| references independently checked | ❌ no papers produced |
| central claims reviewed | ❌ no papers produced |
| historical/current compared | ❌ no current paper produced |
| automated/independent compared | ❌ no automated artifacts produced |
| user effort recorded | ✅ |
| Blockers/Improvements/Ideas classified | ✅ |
| product-readiness outcome assigned | ✅ LIVE_PATH_BLOCKED |
| no aggregate score | ✅ |
| no prompt/retrieval tuning | ✅ |
| controlled integrations pass | ✅ (preserved from Phase 1/2; no code changed) |
| architecture/ranking/frontend pass | ✅ (preserved; no code changed) |
| full backend state preserved honestly | ✅ (no code changes; Phase 2 baseline holds) |
| P1E artifacts changed = 0 | ✅ |
| retrieval architecture changed = 0 | ✅ |
| working tree clean | ✅ |

**Phase 3 is complete as a validation phase:** it was executed, the result is LIVE_PATH_BLOCKED, and the failure is reported without concealment. The spec explicitly states: *"Phase 3 completion does not require the product to pass validation. It requires the validation to be executed and reported without concealing failures."* The validation was executed (Run A attempted through the production path), the failure was not concealed, and the outcome is assigned.

---

*End of Phase 3. Outcome: LIVE_PATH_BLOCKED. Two blockers identified for the next phase: silent pipeline stall (B-01) and run-detail API id mismatch (B-02).*
