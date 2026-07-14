# Phase 1 Entry Criteria

> **Purpose:** define exactly what evidence is required before Phase 1 (IA +
> shell + mobile sheet) begins. Phase 1 is gated by Q1, Q5, Q6 — starting it
> before those resolve risks hardening the wrong workflow.
>
> **Use:** check each criterion. Phase 1 starts when all are met OR their
> safe-default is explicitly accepted in writing. "Explicitly accepted"
> means a dated decision log entry, not silence.

## The gating questions (recap)

Per `decision_rules.md`:

| Question | Gates | Why it gates |
|---|---|---|
| **Q1** primary user (researcher vs manager) | Phase 1, Phase 2 | Determines whether READ or TRIAGE is the center — the IA's organizing principle |
| **Q5** governance frequency (daily vs rare) | Phase 1 | Determines whether GOVERN is a primary nav group |
| **Q6** comparison (side-by-side vs serial) | Phase 1, Phase 3 | May add a whole new primary surface (COMPARE) to the IA |

Q2, Q3, Q4 gate Phase 2 / Phase 4 only — they do **not** block Phase 1.

## Entry criteria — all must be met

### 1. Q1 resolved OR safe default explicitly accepted
- **Resolved:** evidence-backed verdict (confirmed/revised/refuted) in the
  evidence-matrix synthesis, per `interview_protocol.md` flip thresholds.
- **OR safe default accepted:** "individual researcher, READ is center"
  (`decision_rules.md` Q1 safe default), with a written decision-log entry
  acknowledging it's provisional and naming the follow-up trigger (e.g.
  "revisit if interview 4+ contradicts").

### 2. Q5 resolved OR safe default explicitly accepted
- **Resolved:** verdict on governance frequency.
- **OR safe default accepted:** "governance is daily, GOVERN stays primary
  nav" (`decision_rules.md` Q5 safe default), written decision-log entry.

### 3. Q6 resolved OR comparison deferred by written decision
- **Resolved:** verdict on side-by-side vs serial.
- **OR deferred:** "build serial-first; comparison is a Phase 3.5 add-on if
  Q6 later flips" — explicitly written down. This is the safe default, but
  because Q6 can add a whole new surface, the deferral must be a conscious
  decision, not an omission. If deferred, Phase 1 IA must *not* preclude a
  later COMPARE entry (leave structural room).

### 4. Route reachability fix plan approved
- `route_reachability_fix_plan.md` reviewed and the INV-1 fix (`/knowledge`
  desktop nav home) either done or scheduled as the first Phase 1 task.
- The invariant/gated split understood by whoever leads Phase 1.

### 5. No new contract warnings beyond baseline
- The Phase 0 lint baseline (194 warnings, per `phase_0_lint_baseline.md`)
  has not grown. Run `npx eslint . 2>&1 | tail -2` and confirm the count is
  ≤ 194. (Preferably < 194 if any validation-independent migration has
  happened.)
- If the count grew, either reduce it back or document why in the decision
  log (with a `// LINT-EXCEPTION` per the warning-budget policy).

### 6. PRODUCT.md v1 amendment proposal drafted
- After validation synthesis, `PRODUCT.md` is either:
  - **Reaffirmed as-is** (all `[H]` removed or marked confirmed), or
  - **Amended** with the validated revisions, and the `[H]` markers on
    resolved questions removed.
- The amendment doesn't have to be *final*, but it must exist as a written
  artifact so Phase 1 builds against a stated target, not a moving one.

### 7. INTERFACE_CONTRACT.md amendment drafted (if PRODUCT.md changed)
- If any validation answer revised a load-bearing assumption, the matching
  contract section is amended. Specifically:
  - Q1 revised → §5 (IA), §6 (ScoreReport) re-derived.
  - Q5 revised → §5 (IA: GOVERN demoted).
  - Q6 revised → new §7 (Compare surface) + §5 (IA: COMPARE entry).
- If PRODUCT.md was reaffirmed, no contract amendment needed.

## Non-blocking but recommended

These strengthen Phase 1 but don't gate it:

- **At least 3 interviews completed** (the minimum for saturation per
  `interview_protocol.md`). If only 1–2 are done, the safe defaults carry
  more weight and should be the explicit path, not "resolved."
- **The parallel-safe audits reviewed** (status indicators, score shapes,
  migration candidates) — so Phase 1 can reference the compliance inventory
  and the known debt.
- **A Phase 1 owner named** — someone whose accountability is the coherence
  of the IA, not feature delivery. (Per the root-cause analysis: the
  frontend's incoherence traces to being everyone's second job.)

## Decision log format

Every "safe default accepted" or "deferred" entry should be:

```text
[YYYY-MM-DD] Phase 1 entry: <criterion>
  Decision: <resolved | safe-default-accepted | deferred>
  Evidence: <synthesis ref | "n/a — provisional">
  Trigger to revisit: <what would change this>
  Decided by: <name>
```

Stored in `docs/product_validation/decision_log.md` (create on first entry).

## What "Phase 1 started" means

Once all 7 criteria are met, Phase 1 scope (per `INTERFACE_CONTRACT.md §9`)
is:
- App-shell + sidebar retype (loop-derived IA per the validated Q1/Q5/Q6).
- Mobile sheet (INV-2 fix — every route reachable).
- Route reachability CI check (orphan prevention).
- `/knowledge` nav home (INV-1, if not already done).
- Adoption of `useResource` + `<DataView>` in the shell itself (the first
  real consumers of the Phase 0 primitives).

Phase 1 is **not**: reading-surface retype (Phase 2), triage migration
(Phase 3), or the lint flip (Phase 5).

## The one-sentence summary

Phase 1 starts when the IA-shaping questions have answers (evidence-backed
or explicitly-deferred) AND the ratchet hasn't slipped — not before.
