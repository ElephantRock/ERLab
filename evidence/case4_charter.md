# Case 4 Charter — Freeze Record (C4-0)

- **Frozen at:** 2026-08-18 (C4-0)
- **Product head under test (R0):** `d4e3125786f23c710d794d741e792aab24dd0f06`
- **Status:** charter frozen BEFORE harness implementation; no production change permitted before the C4 harness demonstrates otherwise
- **Companion seals:** `evidence/case4_manifest.json` + `evidence/case4_manifest.sha256` (produced at C4-3)

**Additive clarification (navigation only, does not modify the charter text below):** the
charter's phase identifiers (C4-0 … C4-7) and its run-matrix row identifiers (C4-1 … C4-4)
collide. To keep evidence unambiguous, the four matrix runs are labeled **R1, R2, R3, R4**
in all Case-4 artifacts:

| Charter row | Run label | Frozen input | Expected capability family |
| --- | --- | --- | --- |
| C4-1 | **R1** | Case-2 domain + question | `tabular_calibration_selective_v1` |
| C4-2 | **R2** | Case-3 domain + question | `tabular_robust_regression_v1` |
| C4-3 | **R3** | Case-3 domain + question | `tabular_robust_regression_v1` |
| C4-4 | **R4** | Case-2 domain + question | `tabular_calibration_selective_v1` |

Matrix order is C–R–R–C exactly as the charter table lists its rows (R1 calibration, R2
robust-regression, R3 robust-regression, R4 calibration).

One further additive implementation disclosure, frozen here before launch: the sealed
coordinator enforces a **per-run hang watchdog at 9,500 seconds** (≈ 3× the longest prior
qualifying autonomous run, Case-3E at 3,160.6 s). It exists solely to convert a
non-terminating worker into a preserved `RUN_FAIL(watchdog_hang)` specimen. It is not a
latency criterion: a run that terminates, however slowly, is judged only on its own
results, honoring the charter's "no latency SLA" exclusion.

A second additive implementation disclosure: the charter's "fresh" Class-1 research state
is operationalized exactly as Case 3E's accepted preflight recorded it — a **new DB with
zero runs**. Concretely, the Case-4 preflight archives residue, initializes an empty
schema through the production initializer (`init_db`), and baselines that file; nothing
in the in-process orchestrator path creates tables, so the evidence harness performs this
one initialization itself (Case-4 independent-review finding P0-1, fixed before seal).

A third additive implementation disclosure: the evidence branch pairs its sealed files
with the same `.gitattributes` byte-exact round-trip entries the Q2→main delta already
carries (`-text` on sealed Case-4 artifacts; this repository runs `core.autocrlf=true`,
which broke Case-2 seals once already). The preflight's product-delta gate therefore
allows exactly `evidence/**` plus `.gitattributes` — no other non-evidence change.

A fourth additive implementation disclosure: the "exact product head" gate is enforced as
**exact product bytes at HEAD** — either `HEAD == R0` itself (the Case-3 layout, with
evidence untracked) or an evidence-branch HEAD that descends from R0 and whose entire diff
against R0 is the allowed evidence delta (the sealed-branch layout). Both layouts prove
the product under test is byte-identical to R0; anything else fails closed.

A sixth additive implementation disclosure (2026-08-18, quota adjudication): the first
QUALIFYING launch on R1 exited RUN_FAIL whose root cause was an exhausted shared Z.AI
five-hour quota (HTTP 429 code 1308) — an external operating condition. The owner
additionally adjudicated a second **GENERIC_PRODUCT_DEFECT**: the typed
`GatewayTransportError` lost its identity in post-ideation fail-soft catchalls, letting a
run finalize SUCCEEDED with manufactured fallback artifacts. Under the same frozen path
the product head moved **R1 `2ce7a874` → R2 `7e546263` (PR #39: GatewayTransportError
propagation through those catchalls, so the run terminates FAILED_EXECUTION)** and the
matrix restarts on R2. Launches additionally await the owner's provider-entitlement
ruling on the Z.AI Coding Plan endpoint before any further qualification.

A fifth additive implementation disclosure (2026-08-18 adjudication record): the first
matrix launch was **preserved and invalidated** — the sealed harness initialized the
"fresh" database with a cold `init_db()` that created zero tables (model modules never
imported), and R1's orchestrator then ran 62 minutes unpersisted and still returned
SUCCEEDED, which the owner adjudicated as a demonstrated **GENERIC_PRODUCT_DEFECT**
(false success on required persistence failure). Under the charter's
GENERIC_PRODUCT_DEFECT path the product head moved
**R0 `d4e3125` → R1 `2ce7a874` (PR #38: fail closed on initial run-record creation
failure)** and the entire C–R–R–C matrix restarts on R1; nothing from the invalidated
attempt counts toward 4/4. The harness repair loads the model metadata before `init_db()`,
asserts the required tables exist by querying the database file directly, and the controls
now include a mandatory **behavioral cold-initialization control against a real temporary
SQLite database**. Acceptance criteria are unchanged.

---

Everything below the marker is the owner's frozen Case-4 plan text, preserved verbatim.

---BEGIN FROZEN CHARTER TEXT---

## Case 4 — Bounded Serial Operational Repeatability

This should be a **reliability qualification of the existing product**, not another architecture-extension exercise.

The product baseline is clean for that purpose: current `main = d4e3125786f23c710d794d741e792aab24dd0f06`, and the Q2→main delta contains only evidence/archive material plus `.gitattributes`; there is no backend or frontend product change after Q2.

The two most comparable accepted autonomous runs took 3,056.4 seconds for Case 2D and 3,160.6 seconds for Case 3E—about 52 minutes of orchestration each—and both completed the blocked→one-cold-repair→six-gates→freeze/release path with zero interventions.   That makes a four-run qualification matrix roughly a four-hour exercise including remediation and reset overhead.

I would **not** call four runs a statistical estimate of a production reliability rate. Case 4 should prove *bounded repeatability under nominal operating conditions*. High-N reliability, concurrency, and rate estimation belong later.

### Frozen objective

> **Demonstrate that the already-qualified ERLab architecture can repeatedly complete fresh-state autonomous research lifecycles across both existing empirical capability families on one frozen production head, without human continuation, cross-run state contamination, capability-specific lifecycle handling, or release-authority divergence.**

The qualifying claim is therefore narrower and stronger than "it worked again":

> **On a fixed product and fixed operating contract, four serial autonomous runs spanning both qualified capability families completed end-to-end with identical governance semantics and zero operator intervention.**

### R0 and protected scope

Freeze:

`R0 = d4e3125786f23c710d794d741e792aab24dd0f06`

R0 is the product under test. An evidence branch may add only the Case-4 manifest, sealed qualification harness, harness tests/negative controls, preflight records, and run evidence. A pre-launch comparison against R0 must show **no production-code delta**.

Protected machinery remains exactly what Case 3 protected: autonomous design, `ExperimentSpec`, common execution, persistence/hydration, synthesis, cold remediation, the existing six assurance gates, revision preservation, freeze/release, provider-readiness semantics, transport-failure semantics, and orchestrator topology.

Explicitly out of scope: no third capability; no seventh paper gate; no new retry layer; no new circuit breaker; no latency SLA; no model substitution; no scientific-result equality requirement; no capability-specific Case-4 code in production; no deliberate fault injection. Those last items belong in Cases 5–6.

### Run matrix

Use the exact previously qualified inputs, because the purpose is operational repeatability rather than another scientific novelty test.

| Run  | Frozen input             | Expected capability family         | Research state |
| ---- | ------------------------ | ---------------------------------- | -------------- |
| C4-1 | Case-2 domain + question | `tabular_calibration_selective_v1` | fresh          |
| C4-2 | Case-3 domain + question | `tabular_robust_regression_v1`     | fresh          |
| C4-3 | Case-3 domain + question | `tabular_robust_regression_v1`     | fresh          |
| C4-4 | Case-2 domain + question | `tabular_calibration_selective_v1` | fresh          |

I prefer **C–R–R–C** rather than C–R–C–R. It puts both capability families at different temporal positions and also includes an immediate same-family repetition, which gives us both transition and repeated-use coverage in four runs.

Each input remains only:

`domain + research_question + autonomous_experiment_enabled=True`

No explicit experiment spec, dataset choice, method choice, proposal choice, repair choice, or continuation decision is supplied by the operator.

The exact scientific conclusion, paper text, and final hash are **not required to match across runs**. What must repeat is the governed lifecycle. Each run must establish its own `E == F == R == H`.

### Matrix-level zero-intervention rule

This is important enough to freeze explicitly:

**Operator intervention budget = 0 from matrix-harness launch until the matrix harness exits with its final verdict.**

That means no checking C4-1 and deciding whether to launch C4-2. The sealed harness itself must drive the entire matrix.

After each accepted run, it automatically preserves the run specimen, resets only the preregistered **Class-1 research state**, verifies that the next state is fresh, and starts the next run. Class-2 operating state—model certification, assignments, provider configuration, governed datasets and capability registrations—remains preserved.

If any run fails, the matrix should **fail fast and exit**. Do not spend another hour collecting runs that cannot restore the frozen 4/4 acceptance condition.

### Fresh-state boundary

Every run should execute in a fresh process, not by repeatedly calling `PipelineOrchestrator.run()` in one long-lived Python interpreter.

The evidence harness can remain one sealed file, for example `launch_case4.py`, with coordinator and worker modes. The coordinator spawns itself as a worker subprocess for each matrix entry. That gives each run fresh Python/module state while avoiding a second harness abstraction.

Before each worker starts, the coordinator must verify fresh research state. The Case-3 state taxonomy already treated the database, Chroma/index state, checkpoints, runs and knowledge indexes as disposable/recreated research state while preserving certification/assignment/provider/dataset state.

Completed runtime state should be **archived, not deleted**. At minimum preserve each SQLite specimen, worker log, result record, and released bytes; record SHA-256s of any large local-only specimen directories.

### Per-run acceptance contract

Every C4 run must satisfy all of the following. These freeze before implementation begins.

1. Required-provider production readiness passes against the **configured** endpoint before research execution.
2. Orchestrator terminal outcome is `SUCCEEDED`.
3. Autonomous design status is `designed`.
4. The capability selected from the frozen input is the expected qualified capability family.
5. Every designed experiment compiles through the existing common `ExperimentSpec` contract and every expected `ExperimentResult` succeeds through the common executor.
6. `method_facts` and autonomous-design state are durably persisted before paper remediation.
7. A persisted paper evaluation exists. `ready` proceeds directly; `blocked` invokes the existing production cold-repair route **exactly once**; any other/missing state fails.
8. Continuation occurs from persisted state through a fresh API process—no live in-memory research object is authoritative.
9. Final evaluation is `ready` and the **same six gates only** pass: provenance, scope alignment, conclusion support, experiment alignment, numeric fidelity, method fidelity.
10. Failed/blocked and repaired revision states remain preserved.
11. Freeze succeeds and produces a release-eligible frozen revision.
12. `E == F == R == H`, and release bytes equal the frozen/current paper bytes.
13. `operator_interventions == 0`.
14. The run specimen is archived before the next run begins, and the next run's research state is demonstrably fresh.

Case 2D already established the exact continuation semantics we want to reuse—blocked paper, one automated cold repair, frozen revision, four-authority equality and zero intervention.  Case 3E strengthened that path with required orchestrator success, explicit capability checking and the Q2 fail-closed provider spine.

### Matrix acceptance

**PASS requires 4/4 accepted runs.**

Additionally, all four must use the same R0 product bytes, same sealed harness, same governed operating-state configuration, and no human decision between matrix launch and final verdict.

There is **no partial qualification** such as 3/4. There is also no cross-run requirement that papers, experimental values, scientific conclusions, repair occurrence, or release hashes be identical. A run that begins `ready` and needs no repair is as valid as a run that legitimately enters `blocked` and receives its one preregistered repair.

What we are testing is lifecycle reliability, not output determinism.

### Failure taxonomy

Use four top-level outcomes:

**PASS** — all four runs satisfy the contract.

**RUN_FAIL** — a launched run fails under the frozen nominal contract. Preserve the precise subtype: provider availability/transport, orchestration, autonomous design, experiment execution, persistence, synthesis, assurance/remediation, freeze, or release identity. A correctly typed provider failure is better than false success, but it still means the Case-4 4/4 success criterion was not achieved.

**GENERIC_PRODUCT_DEFECT** — evidence demonstrates a capability-independent product bug. Preserve the complete matrix specimen, make only the smallest generic correction, freeze a new product head `R1`, and restart the **entire matrix from C4-1**. Runs from different product heads cannot be combined into 4/4.

**INVALID_ATTEMPT** — the qualification itself violated its frozen conditions: wrong product head, unsealed/changed harness, non-fresh initial research state, forbidden product/configuration change, or human decision/action after matrix launch.

A failed matrix gets **no automatic second attempt**. Harness exits, evidence is preserved, then the failure is adjudicated. This avoids repeating the Case-2C / first-Case-3 timing mistake in a larger form.

### Preflight

Case 4 should deliberately simplify the Case-3E preflight.

Keep hard gates for exact product head, clean tracked product tree, sealed manifest/harness, required provider readiness through production configuration, model certification/assignment identity, embedding availability, evaluator availability, governed capability/dataset registration, and fresh Class-1 state.

Do **not** carry Case-3E's 8× structured-response battery or long-form throughput probe forward as Case-4 hard gates. Those were diagnostic controls introduced around the 3C/3D uncertainty; Case 4 should test normal production readiness rather than screening the model repeatedly before every real run. Case-3E's preflight shows those diagnostics separately from the Q2 readiness gate.  They can be recorded diagnostically if useful, but should not decide qualification eligibility.

### Harness verification before sealing

The qualification harness itself is load-bearing, so test it *before* launch. This is justified by the prior harness defects; it is not a new production test framework.

Before sealing, bounded synthetic negative controls should prove that the harness fails closed on: orchestrator non-success, missing design, wrong capability, unsuccessful experiment count, missing evaluation, repair failure/second-repair attempt, E/F/R/H mismatch, and non-fresh next-run state.

Also prove the positive branches: ready-without-repair and blocked→one-repair.

Once review and those checks are complete, seal the harness. **No acceptance criterion or harness behavior changes after seal.**

### Execution phases

1. **C4-0 — Freeze the reliability charter.** Record R0, exact two frozen inputs, C–R–R–C matrix, scope exclusions, failure taxonomy, 4/4 rule and zero-intervention boundary.
2. **C4-1 — Build the evidence-only matrix harness.** One sealed `launch_case4.py`; no production changes. Reuse the established Case-3 continuation logic, parameterized only at the evidence layer.
3. **C4-2 — Harness qualification.** Run the bounded positive/negative controls, review the harness, resolve findings, then freeze its exact bytes.
4. **C4-3 — Seal.** Produce `case4_manifest.json` + SHA, harness SHA, exact R0/product-tree proof and input records.
5. **C4-4 — One preflight.** Establish healthy nominal operating conditions and fresh initial research state. Once the matrix launches, hands off.
6. **C4-5 — Execute C–R–R–C.** Coordinator automatically runs, continues, archives, resets and decides. Fail fast on first nonqualifying run.
7. **C4-6 — Independent verification.** Recompute each run's persisted design/experiment/revision/gate/release facts, all four authority hashes, specimen hashes, state-isolation checks and intervention ledger.
8. **C4-7 — Closeout.** If 4/4, commit the evidence package and qualify Case 4. If not, commit/preserve the failure specimen and stop for adjudication.

### Evidence package

The committed package should contain the frozen manifest/seal, sealed harness/seal, preflight, matrix-level result, four per-run result records, four run logs, four exact release copies, and one acceptance/verification record.

Preserve each SQLite database and any large runtime archives byte-exact locally, with hashes recorded in the evidence. Commit those binaries only if their size and contents make that sensible; their Git inclusion should **not** become a new acceptance gate.

The matrix result should include timings, provider/transport failure counts, retry diagnostics, repair path, revision sequence and selected capability/specs for every run. Those are **diagnostics**, not new thresholds.

### What Case 4 will and will not prove

If this passes, the defensible claim becomes:

> **The same governed autonomous research architecture repeatedly completed nominal end-to-end operation across both qualified empirical capability families, through fresh process and research-state boundaries, with zero operator intervention and exact release authority on every run.**

It will **not** establish "99% reliability," tolerance of intentional outages, concurrency safety, or sustained-load behavior.

That gives the remaining reliability roadmap clean boundaries:

**Case 5:** deliberate fault/recovery qualification—startup outage, mid-run transport loss, restart/resume, persisted typed failure and recovery semantics.

**Case 6:** sustained/load qualification—larger run count, concurrency/resource pressure, cross-run isolation under load, and any reliability-rate statement we actually want to support.

This is the Case-4 plan I would freeze. No production change is justified before the C4 harness demonstrates otherwise.

---END FROZEN CHARTER TEXT---
