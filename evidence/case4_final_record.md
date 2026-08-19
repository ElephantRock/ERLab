# Case 4 Final Record — DID NOT QUALIFY

Recorded 2026-08-19 per the owner's closeout ruling. Case 4 (bounded
serial operational repeatability) is closed as **not qualified**: the
single consumed qualifying attempt on the corrected checker ended in a
genuine `RUN_FAIL(assurance_remediation)` — the one authorized cold
repair produced a substantive paper that failed `numeric_fidelity` and
correctly did not promote. No further Case-4 relaunch is permitted under
this contract; successor work (for example, improving single-pass
remediation reliability) requires a new explicitly authorized objective.

## The defining attempt (consumed, final)

Launch 2026-08-19 19:11:42Z under seal v8 (`b9fe4391…`), product head
R2 (`7e5462637bff4ea83a4141e6149ea04c049e80b8`), Coding Plan operating
state. Preflight 14/14. R1 (frozen Case-2 input,
`tabular_calibration_selective_v1`): orchestrator SUCCEEDED (~51 min);
design `designed`; capability correct; 2/2 experiments through the common
executor; 74 markers; initial paper `blocked`; the single authorized cold
repair ran — HTTP 200, revised paper substantive (provenance pass, scope
pass, conclusion support pass, experiment alignment pass, method fidelity
pass) — but **`numeric_fidelity` failed**, promotion correctly refused,
final evaluation `blocked`, release correctly not invoked, `E == F == R
== H` therefore not established. Zero operator interventions. Zero quota
or transport errors. Specimen: `evidence/case4_qualifying_runfail_3/`
(commit `2a0cca1`).

## Attempt ledger (complete)

| # | Launch (UTC) | Binding | Outcome | Classification |
| --- | --- | --- | --- | --- |
| 0 | 2026-08-18 04:09 | v3 / R0 | preflight environmental stop (embedding URL missing `/v1`) | pre-boundary; nothing consumed |
| 1 | 2026-08-18 08:15 | v4 / R0 | worker ran 62 min against a 0-byte schema-less DB; orchestrator SUCCEEDED unpersisted | INVALID_ATTEMPT — harness cold-init defect; preserved and invalidated (`evidence/case4_invalidated_launch1/`, `4f2e068`) |
| 2 | 2026-08-18 11:07 | v4 / R0 | matrix refused in 16 s, zero workers | INVALID_ATTEMPT — evidence packaging; preserved (`evidence/case4_invalidated_launch2/`) |
| 3 | 2026-08-18 12:01 | v4→v5 era / R1 | RUN_FAIL; root cause external quota exhaustion (429 code 1308) mid-run | qualifying RUN_FAIL; adjudicated second GENERIC_PRODUCT_DEFECT → R2 (`evidence/case4_qualifying_runfail_1/`, `1b1f7d1`) |
| 4 | 2026-08-18 22:53 | v7 / R2 | product lifecycle fully healthy through freeze; checker falsely failed at the freeze milestone | INVALID_ATTEMPT — harness/checker defect; preserved and invalidated (`evidence/case4_qualifying_runfail_2/`, `d1a7a0a`; adjudication in `evidence/case4_runfail2_adjudication.md`) |
| 5 | 2026-08-19 19:11 | v8 / R2 | genuine output-quality failure at the remediation boundary | **CONSUMED — RUN_FAIL(assurance_remediation), final** (`evidence/case4_qualifying_runfail_3/`, `2a0cca1`) |

## Durable product outcomes (merged to main, independent of qualification)

- **R1** `2ce7a874…` (PR #38): fail closed on initial run-record creation
  failure — a required `create_run_record()` returning `None` now
  terminalizes `FAILED_EXECUTION` at `persistence_initialization` before
  any research stage executes.
- **R2** `7e546263…` (PRs #39/#40): `GatewayTransportError` propagates
  through 19 post-ideation fail-soft catchalls so provider death
  terminates `FAILED_EXECUTION` instead of manufacturing fallback
  artifacts (found from the quota specimen's 207-character stub paper).
- Both corrections: two independent review rounds each, full CI green,
  zero newly-failing tests.

## Harness seal lineage

v1 `33c8feb5` (initial) → v2/v3 (pre-launch gate/schema reseals) → v4
`3c1bb420` (cold-init repair: models import + table assertion +
behavioral control) → v5 `5d8a85ce` (R2 rebind) → v6 `5c784a56`
(general-API operating state; abandoned — no balance) → v7 `7f9ab8bb`
(Coding Plan rebind per owner ruling) → **v8 `b9fe4391`** (checker fact
ordering/availability repair; controls 32/32). The failed checkers and
specimens of every attempt are preserved unchanged in git history and
the directories above.

## Publication note

The local evidence branch (`case4/reliability-qualification`) carries two
merge commits (the R1 and R2 product merges), which this repository's
linear-history rule rejects on push. Rewriting that history would break
the commit SHAs cited throughout this record and the manifest, so the
evidence lineage is published as a byte-exact linear snapshot branch
(`case4/evidence-publication`, cut from `main`): every sealed file —
charter, harness, manifest, seals, controls, adjudications, specimens,
and this record — appears there with identical bytes, verifiable against
the SHA-256 seals recorded in the manifest. The commit SHAs cited above
remain the local lineage's historical labels.

## What Case 4 established despite non-qualification

Across six launches the product's governance machinery behaved
correctly at every boundary it reached: typed terminal outcomes, the
six-gate assurance boundary (it is what stopped the unqualified paper),
bounded single-repair policy, freeze/release authority gating, and —
after the two merged corrections — persistence and transport failure
identity. The unmet link is single-pass remediation reliability: the
repair synthesis did not reliably reproduce the experiment's numbers
verbatim, and the frozen contract allows exactly one repair. That is
successor work, not a Case-4 continuation.
