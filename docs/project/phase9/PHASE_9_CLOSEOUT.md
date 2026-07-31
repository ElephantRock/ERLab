# Phase 9 — Unattended Semantic Remediation: Closeout

> **Phase 9 acceptance: NOT MET.**
>
> ERLab implemented and validated a bounded, evidence-constrained automatic
> paper-remediation mechanism. It successfully corrected and promoted one of
> three isolated live cases and correctly retained the other two as blocked
> without rerunning experiments or mutating sealed artifacts. Phase 9 acceptance
> was not met because unattended single-pass remediation did not produce
> gate-passing papers for all three cases, and the exact original Phase 8
> blocked papers were unavailable for historical replay.

## Phase record

```text
Phases 0–8    CLOSED — acceptance met

Phase 9       CLOSED — acceptance not met
Outcome        REMEDIATION_MECHANISM_PROVEN
               SINGLE-PASS_RELIABILITY_INSUFFICIENT
```

## What was built and verified

```text
9A  Fixture availability audit               COMPLETE (originals not byte-recoverable)
9B  Revision directive + evidence invariants COMPLETE
9C  Pure paper gate evaluator                COMPLETE (no side effects)
9D  PaperRevision table + migration 035      COMPLETE (verified on existing + fresh DB)
9E  Constrained one-attempt remediation      COMPLETE
9F  Controlled proof (16 tests)              COMPLETE
9G  Three isolated live remediation cases    COMPLETE (1 promoted, 2 honestly blocked)
9H  Closeout corrections                     COMPLETE
```

## Architecture

```text
paper with semantic blocker
→ pure gate evaluation (no side effects)
→ eligible_for_remediation check
→ revision 0 stored unconditionally (original preserved)
→ atomic revision 1 claim (UNIQUE constraint, idempotent)
→ evidence hash verification
→ constrained revision (original paper as mandatory input)
→ invariant verification (no invented markers)
→ pure gate re-evaluation
→ promote if ready, else persist blocked
```

## 9G Live remediation results

```text
Case        Original        Revised          Promoted    Eval
Concrete    quantum PINN    linear regress.  YES         ready
Iris        quantum VQLS    still quantum    NO          blocked
Wine        quantum GNN     still quantum    NO          blocked
```

The Concrete case fully succeeded. The Iris and Wine cases were honestly
blocked — the LLM (glm-4.6) did not fully remove the quantum framing in one
revision pass. The system correctly refused to promote these blocked revisions.

## Supported claim

> ERLab can automatically attempt one evidence-constrained semantic revision,
> preserve its audit history, promote a corrected paper only when all gates
> pass, and otherwise retain an explicit blocked outcome without rerunning
> the experiment.

It cannot yet claim reliable single-pass correction across all cases.

## Acceptance failures

```text
Three automatic revisions produced                YES (3 attempted)
All three corrected papers pass internal gates     NO (1 of 3)
Exact original Phase 8 papers available            NO (overwritten, not recoverable)
External review of Phase 9 outputs                 NOT PERFORMED
```

## Closeout corrections

### Revision-row count

Initial report stated 3 PaperRevision rows (revision 1 only). Root cause:
revision 0 storage was placed after the revision 1 idempotency check, so
when revision 1 existed from a prior run, revision 0 was never stored.

**Fix:** Moved revision 0 storage before the idempotency check. Revision 0
is now stored unconditionally. Verified: revision 0 correctly persisted with
original paper hash and parent_revision_id=None.

### Fresh Alembic verification

`Base.metadata.create_all()` was insufficient evidence. Verified actual
`alembic upgrade head` on an empty database:

```text
EROCK_DATABASE_URL="sqlite:///tmp/test_alembic2.db" python -m alembic upgrade head
→ All 35 migrations applied successfully
→ paper_revisions table created with 17 columns
→ Alembic version: 035
→ UNIQUE constraint present (sqlite_autoindex_paper_revisions_1)
```

## Verification

```text
Controlled proof tests:     16 passed
Phase 5-9 total tests:      82 passed
Canonical backend:          4,973 passed, 0 failed
Frontend:                   988 passed, 0 failed
Sealed Phase 8 papers:      unchanged (verified)
Migration 035 fresh DB:     PASS (alembic upgrade head on empty DB)
Working tree:               clean
```
