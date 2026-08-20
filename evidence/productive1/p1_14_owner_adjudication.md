# Productive-1 owner adjudication (2026-08-20)

## Ruling

The regr-B#2 anomaly is a **real pre-existing product defect**, not a
harness defect and not a Productive-1 targeting defect — and it does
not reopen or rescue Productive-1.

The defect is the repair route's **split authority over promotion**: on
current main, `auto_revise_paper()` promotes the revised paper
immediately when its internal `evaluate_paper_gates()` returns ready;
the API route then separately constructs `PaperSynthesisStage`, runs a
second `_evaluate_paper()` on the already-promoted paper, and persists
that second evaluation — with **no rollback or demotion path** when the
second evaluator blocks. The observed `promoted=true` + final
`blocked` state is exactly that architecture.

Owner-verified structurally on main: two distinct decision points; the
first can mutate canonical `proposal.paper_md`; the second runs
afterward and persists to `paper_meta_json`; no reversal exists.

## Qualification outcome (unchanged)

The frozen result stands: **FAIL — 6/8 overall, 2/4 regression** vs
≥7/8 and ≥3/4 per family. regr-B#2 is NOT invalidated (the
qualification exercised the production cold-repair route through normal
evaluation/freeze/release; a defect in that production route is a
legitimate system-level qualification failure). regr-B#1 independently
supplies the candidate's explicit close condition: one-shot
remediation still produced unsupported numeric output.

## Disposition

- The failed Productive-1 candidate is **not merged**; it and its
  evidence are preserved (this branch).
- The evaluation-consistency defect is **valid successor work if
  separately authorized**. The smallest likely correction: establish
  ONE promotion authority — either defer canonical promotion until the
  full post-repair evaluator passes, or make the already-used pure gate
  evaluation authoritative and eliminate the contradictory second
  decision. That product-semantics change must not be smuggled into
  the closed candidate.
- The targeting change materially improved numeric remediation
  reliability on the supplied record but did not meet the frozen
  delivery threshold: a preserved failed candidate, not a deliverable.
