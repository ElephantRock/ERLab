# v1.0.3 Release Verdict

**CANDIDATE — FAILED CONFIRMATORY GATE**

- **Branch:** `fix/v1.0.3-release-reconciliation`
- **Base commit:** `d0a2e7946a2c7ea3c0e39c1670e5105927699ebc` (v1.0.2 seal)
- **Final candidate commit:** `a82644014628f3f21cc89763d99aade5e4231993`
- **PR:** #4 (open, draft, unmerged)
- **CI run:** 31034674404 — all 4 jobs success
- **Closeout document:** `CONFIRMATORY_E2E_CLOSEOUT.md`

---

## What was validated

The following were observed at runtime during per-commit work and in the
final CI run at `a826440`:

- **Six frozen reconciliation defects repaired** and verified by the
  21-test frozen contract suite (`test_v103_release_reconciliation.py`).
- **Gateway stage/run context propagation** verified by the 19-test
  first-E2E findings suite (`test_v103_e2e_findings.py`).
- **Terminal outcome enforcement, session isolation, and gap-output
  contract** verified by the 7-test second-E2E findings suite
  (`test_v103_second_e2e_findings.py`).
- **Full backend CI green:** 5003 passed, 34 skipped, 117 deselected,
  3 xfailed, 0 failed, coverage 69.29%.
- **Package and README identity at `1.0.3`.**
- **Run isolation, ledger reconciliation, and session reconciliation**
  validated for recorded events during the second confirmatory attempt.
- **Stage attribution** validated (0/25 blank stages) during the second
  confirmatory attempt.

## What failed

- **Both confirmatory E2E attempts failed to produce a paper** (0 gaps,
  0 ideas, 0 proposals on each attempt).
- **Attempt 1** exposed blank stage attribution (25/25 events had
  `stage=""`) — repaired by Commit 11.
- **Attempt 1** exposed preflight/runtime run-ID mismatch and missing
  session-finalization — repaired by Commits 12-14.
- **Attempt 2** exposed a gap-analysis output-contract failure: a nonempty
  provider response that did not conform to the gap schema was silently
  accepted or normalized instead of producing an explicit contract failure
  — repaired by Commit 15.
- **Attempt 2** exposed two independent release/protocol defects:
  the runner returned exit code 0 for a failed product outcome, and
  session storage used the shared configured directory — repaired by
  Commit 14.

## What remains unproven

- **No successful live literature-to-paper completion** on the final
  candidate `a826440`. Both paid attempts were consumed.
- **No final-candidate paper/evaluation/citation/export persistence
  evidence.**
- **Accounting completeness** for the historical second attempt remains
  not proven (no request-to-ledger correlation was performed).
- **Live behavior of the repaired gap-output contract** remains
  unverified (the repair is hermetic-test-verified only).
- **Restart persistence** was not demonstrated on the final candidate.
- **Browser/API retrieval** was not demonstrated on the final candidate.

---

## Bounded release claim

`v1.0.3` claims, within the boundaries verified by the focused and CI suites:

1. **Run-isolated cost accounting.**
2. **Stage / run attribution** across all five concrete providers.
3. **Structured-output accounting** via the usage-aware gateway boundary.
4. **Explicit reconciliation posture** (`partial`/`reconciled`/`no_events`).
5. **Honest session finalization** from the run-scoped summary.
6. **Gap-analysis output-contract enforcement** (nonempty schema-incompatible
   output raises a typed error rather than silently normalizing).
7. **Release identity** at `1.0.3`.

These claims are bounded to hermetic and CI verification. No successful live
literature-to-paper E2E exists on the final candidate.

## Explicit non-claims

- **No tool-call accounting claim.**
- **No universal live-E2E provider claim.**
- **No successful confirmatory paper-production claim.**
- **No human peer-review claim.**
- **No autonomous scientific-validity claim.**
- **No arbitrary-domain generality claim.**

See `known_limitations.md` and `CONFIRMATORY_E2E_CLOSEOUT.md` for the full
evidence record.
