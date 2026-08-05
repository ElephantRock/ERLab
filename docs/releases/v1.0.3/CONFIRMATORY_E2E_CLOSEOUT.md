# v1.0.3 Confirmatory E2E Closeout

This document records the complete evidence chronology for the two authorized
confirmatory E2E attempts, the post-attempt engineering remediation, and the
final closeout verdict.

## Final candidate

```text
candidate_sha:  a82644014628f3f21cc89763d99aade5e4231993
base_sha:       d0a2e7946a2c7ea3c0e39c1670e5105927699ebc
pr:             #4
ci_run:         31034674404
ci_result:      success
```

## Attempt 1

```text
result:                   FAIL
actual run_id:            run_20260805_045655
paper produced:           no
gaps/ideas/proposals:     0/0/0
recorded cost:            $0.079345
recorded events:          25
independent ERLab defect: blank stage attribution (25/25 events had stage="")
protocol defects:
  - preflight/runtime run-ID mismatch
  - no session-finalization evidence
```

The empty model response is not characterized as a proven external outage.

## Attempt 2

```text
result:                   FAIL
run_id:                   e2e_v103_2nd_20260805_150951
paper produced:           no
gaps/ideas/proposals:     0/0/0
recorded cost:            $0.080325
recorded events:          25
blank recorded stages:    0
run isolation:            validated
ledger reconciliation:    validated for recorded events
session reconciliation:   validated
accounting completeness:  NOT PROVEN
```

### Failure boundary

```text
gap-analysis output-contract failure at the ERLab/provider boundary
```

The provider returned a nonempty response (1730 chars) that did not conform to
the gap-analysis schema. This failure is classified at the ERLab/provider
boundary, not exclusively as provider misbehavior.

### Independent release/protocol defects

```text
1. Confirmatory runner returned exit code 0 for failed product outcome
2. Session storage used the shared configured directory
```

## Post-attempt remediation

```text
21ba004  test(v1.0.3): freeze second confirmatory findings
bf03b15  fix(v1.0.3): enforce confirmatory outcome and isolation
a826440  fix(v1.0.3): enforce gap-analysis output contract
```

### Verified outcomes

```text
first-E2E frozen findings:   19 passed
second-E2E frozen findings:   7 passed
full backend CI:              5003 passed, 0 failed
coverage:                     69.29%
```

```text
repair verification != successful confirmatory acceptance
```

The green regression suite establishes that the observed defects were repaired;
it does not establish that `a826440` can successfully complete the frozen
literature-to-paper workflow against the live provider.

## Final closeout verdict

```text
CANDIDATE — FAILED CONFIRMATORY GATE
NOT RELEASED
```

* Both authorized paid attempts were consumed.
* No further paid attempt was authorized.
* No successful post-repair live E2E exists.
* Paper production, seven-dimensional evaluation, citation-chain resolution,
  exports, restart persistence, and browser/API recovery were not demonstrated
  on the final candidate.
* The candidate cannot be promoted from this evidence package.
