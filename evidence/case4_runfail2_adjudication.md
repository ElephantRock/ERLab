# Case 4 — runfail_2 adjudication: consumption, defect ownership, and the repair basis

Recorded 2026-08-19 per the owner's repair plan, from the preserved
specimen at commit `d1a7a0ae5c9b802a0355e97862adeffd13f307b1`
(`evidence/case4_qualifying_runfail_2/` + the sealed harness bytes of
seal v7, harness sha `95296aa7…`). No code was changed during
reconstruction.

## Failure chronology (all facts from artifacts; UTC, 2026-08-18)

1. 22:53:09 — sealed preflight 14/14 PASS; R1 worker launched (matrix
   zero-intervention boundary).
2. STEP1 — production Q2 provider readiness OK.
3. STEP2 — orchestrator SUCCEEDED (run_id `run_20260818_225311`-era;
   worker total 3,275.7 s).
4. STEP3-6 — design `designed`; capability `tabular_calibration_selective_v1`
   (correct for the frozen Case-2 input); 2 specs with complete ids;
   4 method_facts persisted pre-remediation.
5. 23:43:48 — STEP5: experiments 2/2 succeeded; 74 markers; initial
   paper evaluation **blocked**.
6. 23:43:49 — STEP8: fresh API process started (continuation from
   persisted state).
7. 23:43:54 — sealed policy: blocked → single cold repair invoked.
8. 23:47:43 — repair: HTTP 200, **promoted: true**, eval `ready`;
   final evaluation `ready`; all six gates PASS (incl.
   `conclusion_support: supported_by_paper`, `method_fidelity: true`).
9. 23:47:43 — freeze invoked; response `state='frozen'`,
   `release_eligible=True` (preserved verbatim in the failure message's
   own repr); the specimen DB contains the freeze-created revision
   (id 3, revision_number 2, `source='release'`, eval ready) — the
   freeze completed server-side.
10. 23:47:43 — checker: with `facts["phase"]="freeze"`,
    `first_failure` evaluates every check up to and including `freeze`.
    `CHECK_ORDER` places `revisions` (index 11) before `freeze`
    (index 12), and the worker collects revision facts only AFTER the
    freeze block — so `facts["revisions_preserved"]` still held its
    default `False` and `first_failure` spuriously returned
    `"revisions"` inside the freeze branch.
11. 23:47:43 — worker FAIL (`failure_type='revisions'` carrying the
    freeze branch's message text — the mismatch is the defect's
    signature). **Release was never invoked**; `verification` is null;
    no release bytes exist.
12. Coordinator archived the specimen; matrix exited
    `RUN_FAIL(persistence)`; `operator_interventions == 0`.

## Defect ownership: HARNESS/CHECKER DEFECT (proven)

The required findings, each verified against the specimen:

- **The needed facts existed before freeze.** The specimen DB holds the
  pre-freeze revision history (id 1 rev 0 `blocked`/`pipeline`; id 2
  rev 1 `ready`/`auto_remediation`) — queryable at any moment before
  the freeze call.
- **Product behavior did not destroy them.** Post-freeze rows are
  exactly the pre-freeze rows plus the freeze-created revision
  (id 3 rev 2 `ready`/`release`); numbering is contiguous 0..2.
- **The checker deferred fact collection until after freeze.** The
  `revisions` check requires the frozen revision id (obtainable only
  from the freeze response) and the post-freeze row set — a strictly
  post-freeze data dependency — yet `CHECK_ORDER` placed it before
  `freeze`, and the worker's milestone sequence asserted freeze before
  collecting rows. The check could never have passed at the position
  it was evaluated.
- **The release path was never reached because the checker terminated
  first.** Release/E==F==R==H never executed (artifact fact, step 11).

Classification: **HARNESS/CHECKER DEFECT.** The product satisfied every
contract item it was permitted to execute (items 1–11; item 12's
release authority untested solely because the checker stopped the run).

## Attempt-consumption adjudication (frozen rules, recorded verbatim)

- Charter (frozen owner text): *"A failed matrix gets **no automatic
  second attempt**. Harness exits, evidence is preserved, then the
  failure is adjudicated."* — no automatic retry occurred; this
  document is that adjudication, under the owner's 2026-08-19 repair
  plan.
- Charter failure taxonomy, INVALID_ATTEMPT: *"the qualification itself
  violated its frozen conditions: wrong product head, unsealed/changed
  harness, non-fresh initial research state, forbidden
  product/configuration change, or human decision/action after matrix
  launch."*
- Owner precedent, attempt 1 (harness cold-init defect, boundary
  crossed, R1 ran 62 min unpersisted): *"the attempt is **preserved and
  invalidated**, not consumed"* — the qualification's own instrument
  failed; the run was not run under the qualified operating contract.
- Owner precedent, launch 2 (evidence packaging): *"It does not count
  toward or against the 4/4 matrix."*

Application without new policy: the instrument that failed here is the
sealed checker itself, in the same class as the prior harness-instrument
defects the owner ruled INVALID_ATTEMPT. The product lifecycle did not
fail; the run cannot be *promoted* either, because the checker
terminated before release and the four-authority equality were ever
tested.

**Ruling: INVALID_ATTEMPT (harness/checker defect) — the attempt is
preserved and invalidated, not consumed, and does not count toward or
against the 4/4 matrix.** Relaunch proceeds under the owner's standing
2026-08-19 authorization if the Coding Plan window condition holds at
launch time.

## Consequence for the run record

The recorded matrix verdict `RUN_FAIL(persistence)` stands in the
preserved specimen unchanged; this adjudication reclassifies its
meaning for the qualification ledger. The prior specimen cannot
substitute for the missing release authority (owner's acceptance rule).
