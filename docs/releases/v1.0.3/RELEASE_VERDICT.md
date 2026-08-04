# v1.0.3 Release Verdict

**CANDIDATE — NOT YET RELEASED**

This verdict records the state of the `v1.0.3` release-reconciliation track at
the point its evidence dossier was sealed. It is **not** a `PASS` verdict. The
release is not sealed until every pending gate below completes and this verdict
is explicitly promoted by a final release-gate evaluation.

- **Branch:** `fix/v1.0.3-release-reconciliation`
- **Base commit:** `d0a2e7946a2c7ea3c0e39c1670e5105927699ebc` (v1.0.2 seal)
- **Release-candidate commit:** `3b4aa1810b030e25d1819e715774466ee1bc9491`
  (code-complete; the six blocker-class commits land here)
- **Dossier commit:** this commit adds only the four dossier files; it is
  documentation, not part of the release claim, and does not advance the
  candidate commit.

---

## Implementation gates already passed

The following were observed at runtime during the per-commit work and are
recorded honestly in `evidence_manifest.json` with their verification class.
They are **focused** results, not a full-branch CI run.

- **Six frozen reconciliation defects repaired.** The frozen contract suite
  (`backend/tests/test_v103_release_reconciliation.py`, 21 tests) moved from
  19 failures / 2 passes at baseline to 21 passes at the candidate commit.
- **28 / 28 v1.0.3 focused tests pass.** Composed of the 21 frozen contracts
  plus the 7 focused behavioral tests in `test_v103_structured_usage.py`.
- **11 / 11 v1.0.2 regression tests pass.**
- **Provider / cache / cost-focused results** were reported for the individual
  commits (provider 48, cache 32, budget/cost 59, lifecycle 104, gateway 110
  in focused, uncontaminated runs). These are recorded as
  `reported_not_independently_reproduced` where they were not re-run as a
  single batch in this dossier step.
- **Package and README identity at `1.0.3`.** `pyproject.toml` version and the
  README leading identifier agree, verified by the
  `release_identity_is_v1_0_3_everywhere` frozen contract.

---

## Gates still pending

The release **must not** be called `PASS` until these complete:

- **Full branch CI.** The focused suites were run locally; a complete CI run of
  the backend test suite on the candidate commit has not been executed.
- **Confirmatory literature-to-paper E2E.** An end-to-end pipeline run from
  literature search through paper synthesis against a live OpenAI-compatible
  provider has not been executed against the candidate commit.
- **Restart-stability verification.** Durable artifacts (cost ledger,
  checkpoint) have not been exercised across a process restart on the candidate
  commit.
- **Final clean-tree and commit binding.** The tree is clean at dossier seal;
  the candidate commit must be reconfirmed immediately before tagging.
- **Merge and tag.** The branch has not been merged to `master`, and no `v1.0.3`
  tag has been created.

---

## Bounded release claim

`v1.0.3` claims, within the boundaries verified by the focused suites:

1. **Run-isolated cost accounting.** Ledger, summary, and aggregation views are
   scoped per `run_id`; a process-lived `CostTracker` cannot leak one run's
   events into another.
2. **Stage / run attribution.** Every billable `complete_with_usage` and
   `structured_output_with_usage` call across all five concrete providers
   (OpenAI, Anthropic, Gemini, Ollama, LiteLLM) carries `stage` and `run_id`
   into its cost event.
3. **Structured-output accounting.** The gateway schema branch routes through
   the usage-aware boundary so each structured request produces an
   authoritative token receipt (exactly one provider request).
4. **Explicit reconciliation posture.** Persisted cost summaries carry one of
   `partial` (a known unaccounted provider call), `reconciled` (events captured,
   no known gap), or `no_events`.
5. **Honest session finalization.** Session runs are finalized from the
   run-scoped cost summary, not from nonexistent tracker properties.
6. **Release identity.** Package and README identify as `v1.0.3`.

## Explicit non-claims

- **No tool-call accounting claim.** `complete_with_tools` attribution is
  outside the v1.0.3 release claim.
- **No universal live-E2E provider claim.** Only the OpenAI-compatible cloud
  path is live-validated; the other four providers have contract conformance,
  not universal live E2E proof.
- **No human peer-review claim.**
- **No autonomous scientific-validity claim.**
- **No arbitrary-domain generality claim.**

See `known_limitations.md` for the full limitation list.
