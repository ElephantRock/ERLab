# Phase 9 / 9A — Fixture Availability Audit

> **Status:** The exact original blocked paper bytes are NOT recoverable.
> Phase 9 proceeds with controlled synthetic fixtures (9E) and isolated
> live remediation cases (9G) created from the accepted Phase 8 papers
> with deliberate alignment defects injected.

## What was checked

```text
git history (data/ is gitignored — never committed)
DB backups (none exist)
DB snapshots (backend/data/elephant_rock.db — does not contain proposals 52/57/59)
Phase 8 review docs (contain excerpts, not full paper bytes)
paper_recovery.py (overwrites in place — no prior-version storage)
/tmp hash capture files (ephemeral, not persisted)
```

## What is available

The three Phase 8 papers (proposals 52, 57, 59) currently hold the **corrected**
versions from 8R.7:

```text
p52 (Iris):      hash=55cc6ef93ae5750e8c366df7... words=2048 eval=ready
p57 (Wine):      hash=c5147869a94d836f66b0940c... words=2616 eval=ready
p59 (Concrete):  hash=204b32857253eff62df5c18b... words=1639 eval=ready
```

The original blocked versions (quantum-solver Iris, multimodal Wine, PINN
Concrete) were overwritten by `resume_empirical_paper()` during 8R.7 and are
not recoverable in byte-exact form.

## Resolution

Per correction #1: "If an exact original cannot be recovered, record that
fixture as unavailable rather than manufacturing it."

Per correction #2: "Create isolated remediation cases using exact original
blocked paper + references to the existing frozen ExperimentResult."

Phase 9 proceeds by:

1. **9E controlled tests:** Use synthetic paper fixtures with known alignment
   defects (quantum abstracts, PINN attributions) that exercise the
   claim_alignment gate. These are deterministic and don't require the
   original bytes.

2. **9G live validation:** Create isolated test proposals with deliberately
   injected alignment defects (e.g., take the accepted Wine paper's method
   and results, but swap the abstract for an unrelated quantum narrative).
   The auto-remediation must correct the abstract while preserving all
   evidence identities. These are new proposals, not mutations of the sealed
   Phase 8 proposals.

This approach respects both corrections: no manufactured "originals" claimed
as exact, and no mutation of the sealed Phase 8 artifacts.
