# Phase 6 / 6B — B-08 Paper-Synthesis Timeout Trace

> The first demonstrated paper-synthesis reliability boundary is identified
> with timings and call evidence.

## B-08 boundary

```text
PER_PROPOSAL_TIMEOUT = 600 seconds (stages.py:1865)
asyncio.wait_for timeout wraps _synthesize_paper_for_proposal (stages.py:1965-1973)
The timeout wraps the ENTIRE per-proposal workflow: both monolithic and
section-wise paths, plus the if/else selection between them.
```

## Identified failure modes

### Primary: Mode 5 — Completed sections discarded on timeout

The section-wise synthesizer (`section_wise_synthesizer.py:138-167`) has:
- no try/except around the section generation loop (lines 142-161)
- no partial-result assembly when asyncio.TimeoutError cancels the coroutine
- `_assemble_paper` (line 164) and `return SectionWiseResult(...)` (line 167)
  only run after ALL 7 sections complete

When the outer 600s `asyncio.wait_for` raises `TimeoutError`, the in-progress
`sections` list is destroyed with the stack frame. Proposal 1 had **5 finished
sections** (Abstract through Discussion + Future Work) totaling real words and
citations — all discarded.

### Contributing: Mode 3 — Structured-output retries consume the budget

The log is dominated by:
```
structured_output: json_schema returned NNNN chars but failed all parse attempts
```
Each section costs 1-3 sequential provider round-trips. "Related Work" needed
3 attempts and ended in `prose fallback, 0 words` — a fully wasted third call.
With 7 sections + 1 outline call, that is ~15-20 sequential POST calls per
proposal against z.ai. Each returns 200 OK but with JSON that fails parsing.

### Contributing: Mode 6 — Oversized input forces section-wise path

Estimated input tokens: 12,990 (proposal 0) / 13,653 (proposal 1).
`available_output` is negative, so the monolithic path is skipped entirely
and the slower section-wise path is selected. Each section's prompt stays
large because the full literature context is included per section.

## Modes ruled out

| Mode | Applies? | Evidence |
|---|---|---|
| 1. Single provider call > 600s | NO | Every HTTP call returned 200 OK promptly; 600s accumulated across many calls |
| 2. Valid response, parse/assembly failed | PARTIAL | Contributing factor (schema failures), but terminal failure is timeout, not parse |
| 4. Monolithic left insufficient time | NO | Monolithic was never invoked; section-wise selected up front |
| 7. Timeout wrapped whole workflow | NO | Correctly bounded per-proposal at 600s, not around the stage |

## Timing evidence from Phase 5 live run

```text
Proposal 0 (run_2718873e9191):
  Section-wise selected: available_output = -6027 < minimum 2000
  Outline generated: 1119 chars
  Abstract: completed (132 words, 0 citations, 1 retry)
  Introduction: completed
  Related Work: 3 attempts → prose fallback, 0 words (wasted call)
  Proposed Method: completed (202 words, 7 citations)
  Evaluation Plan: completed (148 words, 2 citations)
  Discussion: in progress when timeout fired
  → Paper synthesis timed out after 600s (non-fatal, B-08)
  → All 4-5 completed sections discarded

Proposal 1 (run_2718873e9191):
  Section-wise selected: available_output = -6690 < minimum 2000
  Outline generated: 33 chars
  Sections completed: Abstract through Discussion and Future Work (5+ of 7)
  → Paper synthesis timed out after 600s (non-fatal, B-08)
  → All completed sections discarded

Stage total: 1,200,007ms (exactly 2 × PER_PROPOSAL_TIMEOUT)
```

## Minimal fix locations

The smallest demonstrated repair (Branch D from the Phase 6 spec):

1. **Add try/except around the section loop** in
   `section_wise_synthesizer.py:142-161` that assembles whatever sections
   exist so far when asyncio.TimeoutError is raised.

2. **Optionally: per-section timeout** so partial work survives the outer
   timeout. This gives `_assemble_paper` a chance to run with the sections
   that completed.

This is Mode 5 (Branch D) — persist completed sections as they finish, so a
timeout returns partial results instead of discarding everything.

---

*Trace complete. The repair target is: section-wise partial-result preservation.*
