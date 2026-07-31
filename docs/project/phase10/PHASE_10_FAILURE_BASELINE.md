# Phase 10 / 10A — Phase 9 Failure Baseline

> Two exact, hash-verified Phase 9 failed-remediation cases are frozen.

## Frozen fixtures

### Iris (proposal 61)

```text
source_proposal_id:     61
experiment_result_id:   11
spec_id:                phase5-pilot-v1
paper_sha256:           63578edbfff722f393c3f3c0...
paper_length:           81 chars
fixture:                backend/tests/fixtures/phase10/iris/original_paper.md
```

The paper is a deliberately-constructed quantum-solver abstract linked to
the Iris logistic-regression experiment. This is the Phase 9 isolated test
case. The Phase 9 whole-paper revision failed to remove the quantum framing.

### Wine (proposal 62)

```text
source_proposal_id:     62
experiment_result_id:   19
spec_id:                phase8-g1-wine
paper_sha256:           63578edbfff722f393c3f3c0...
paper_length:           81 chars
fixture:                backend/tests/fixtures/phase10/wine/original_paper.md
```

The paper is a deliberately-constructed quantum-solver abstract linked to
the Wine Quality logistic-regression experiment. Same failure pattern as Iris.

## Phase 9 revision-1 status

The Phase 9 revision-1 attempts were not preserved in the PaperRevision table.
They were ephemeral outputs from the 9G live remediation runs, deleted during
test cleanup between iterations. The original blocked papers (revision 0
equivalents) are still the canonical `paper_md` on proposals 61 and 62,
which is correct — the failed revisions were never promoted.

Phase 10 will create new isolated proposals referencing these exact originals.

## Hash verification

```text
iris:  sha256(fixture) == sha256(proposal.paper_md)  ✓
wine:  sha256(fixture) == sha256(proposal.paper_md)  ✓
```

## Concrete reference case

Concrete (Phase 9 proposal 63) was successfully remediated and promoted.
It is the positive Phase 9 reference and is NOT rerun in Phase 10.
