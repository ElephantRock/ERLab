# Phase A0 — Existing runner audit

> Requirement-to-implementation matrix for `run_e2e_pipeline.py` against the
> live-paper acceptance program.

This audit was performed **before** any code changes, on branch
`acceptance/live-paper-proof` at `581c2a2...` (PR #5 head). Its purpose is
to confirm that execution remains on the existing runner/orchestrator path
and to classify the exact delta the acceptance program must close.

The runner under audit is `run_e2e_pipeline.py` (463 lines, repo root). It
is a *confirmatory* runner, not an acceptance runner: it verifies a terminal
paper exists but does not classify a PASS/FAIL/INCONCLUSIVE verdict against
typed gates.

---

## 1. Existing controls to preserve

Every requirement in the plan's "Existing controls to preserve" table is
already implemented by the runner. Execution stays on this path.

| Requirement | Existing mechanism | Location | Status |
| --- | --- | --- | --- |
| Run identity | `ConfirmatoryConfig.run_id` | `run_e2e_pipeline.py:55-68` | **already satisfied** |
| Session identity | `ConfirmatoryConfig.session_id` | `run_e2e_pipeline.py:58` | **already satisfied** |
| Identifier safety | `validate_preflight()` — blank + unsafe-char regex | `:71-84` | **already satisfied** |
| Isolated session directory | `derive_attempt_session_dir()` — `<base>/confirmatory/<run_id>` | `:87-108` | **already satisfied** |
| No directory reuse | existing-directory rejection before execution | `:257-260` | **already satisfied** |
| Durable run reservation | `RunService.create_run(run_id_override=...)` | `:283-289` | **already satisfied** |
| Production execution | `PipelineOrchestrator(strategy="deep_research")` | `:302-303` | **already satisfied** |
| Result/run binding | `result.run_id == config.run_id` | `:338-344` | **already satisfied** |
| Session record uniqueness | exactly-one-matching-run-record check | `:354-365` | **already satisfied** |
| Cost reconciliation | cost-tracker summary vs session record (tokens + cost) | `:350-385` | **already satisfied** |
| Completed paper requirement | `validate_terminal_outcome()` — nonblank `paper_markdown` | `:149-219` | **already satisfied** (weakest form) |
| Failure exit | `sys.exit(1)` on PreflightError / TerminalOutcomeError / RuntimeError / Exception | `:446-459` | **already satisfied** |

**Conclusion:** the runner is a sound execution spine. The acceptance layer
**adds** controls around it; it does not replace the spine.

---

## 2. Missing or insufficient controls — the acceptance delta

Each item is classified as:
- **requires extension** — can be built on the existing runner without a new orchestration path
- **blocked pending design** — needs investigation before implementation
- **not applicable** — out of scope for the hermetic-rehearsal phase (A0–A7)

### 2.1 Exact code-origin verification — **requires extension**

The runner reads no Git state. It hardcodes `FROZEN_DOMAIN` and `FROZEN_PARAMS`
but never verifies the repository HEAD or working-tree cleanliness. Two source
trees could execute under the same case.

**Delta:** acceptance preflight must record `git rev-parse HEAD`, require
`HEAD == expected_code_sha`, require `git diff --quiet`, and record runner +
backend import paths plus a dependency snapshot hash. No runner restructuring
needed — a preflight hook.

### 2.2 Typed acceptance manifest — **requires extension**

`ConfirmatoryConfig` carries only `run_id`, `session_id`, `domain`. All other
parameters are module-level constants (`FROZEN_PARAMS`, provider/model
hardcoded in the docstring as "z.ai (glm-4.6)"). There is no typed artifact
class, no corpus mode, no budget, no execution policy, no gates.

**Delta:** add `LivePaperAcceptanceCase` (Pydantic) loaded from a JSON
manifest. The runner gains `--acceptance-case <path>`. The old
confirmatory interface remains supported.

### 2.3 Explicit `PipelineOutcome` acceptance — **requires extension**

`validate_terminal_outcome()` rejects an explicit *failed* status string but
does **not** check the typed `PipelineOutcome` enum added in PR #5
(`result.py`). A run that exits normally with `outcome=NO_RESEARCH_GAP` or
`outcome=FAILED_OUTPUT_CONTRACT` is not caught as a failure here — it would
only be caught downstream if no paper was produced, which is a weaker check.

**Delta:** acceptance gate 3 must require
`result.outcome == PipelineOutcome.SUCCEEDED` and `terminal_stage is None`.

### 2.4 Mandatory stage-report validation — **requires extension**

The runner never inspects `result.stage_report`. A stage that silently
disappears (skipped by strategy without declaration) is invisible to the
current verdict.

**Delta:** acceptance gate 4 must validate every mandatory stage in the
`deep_research` strategy recorded an `executed` (or declared-permit) status,
with no silent skips.

### 2.5 Final-paper evaluation validation — **requires extension**

The runner checks `paper_markdown` is nonblank. It does **not** check the
seven-dimensional paper evaluation, its scope (`paper` vs `proposal`), or
whether any evaluation gate is blocking.

**Delta:** acceptance gate 7 must require all seven dimensions present,
score-bounded, with justification, scope=`paper`, and no blocking gate.

### 2.6 Citation/source-map validation — **requires extension**

No citation-audit or source-map check exists in the runner.

**Delta:** acceptance gate 8 must require the citation audit executed,
every marker mapped, no fabricated/out-of-range sources.

### 2.7 Export validation — **requires extension**

Export runs as a stage but the runner does not verify the export file exists
or contains the paper.

**Delta:** acceptance gate 10 must require the export file exists, contains
the paper text, and preserves citation markers.

### 2.8 Cost ceiling enforcement (not merely reconciliation) — **requires extension**

The runner *reconciles* cost after execution (line 350-385) but does not
*enforce* a ceiling. If the run overshoots, it fails reconciliation only if
the session record disagrees — not if a hard cap was breached.

**Capability check:** enforcement IS possible. `budget_guard.py:99-108`
checks `max_cost_usd` and `autonomy/budget.py:104` checks
`total_cost_usd >= max_cost_usd`. The gateway/cost layer can refuse the next
call.

**Delta:** acceptance preflight must wire the manifest's
`maximum_cost_usd` into the budget guard and prove a call is refused at the
ceiling. **Not blocked** — the mechanism exists.

### 2.9 Frozen-corpus integrity — **requires extension**

There is no corpus mode. The runner always runs live search
(`deep_research`). A frozen real corpus must enter through a production
ingestion boundary without injecting gaps/ideas.

**Delta:** add a small production corpus adapter (input adapter, not a new
harness) plus a corpus manifest with per-document and aggregate hashes.
Phase A5.

### 2.10 Fresh-process database restart recovery — **requires extension**

The runner verifies results in-memory within one process. It does not shut
down persistence and reload from a fresh instance.

**Capability check:** `RunService` is DB-backed (`create_run`, `mark_run`),
so reload-by-run-id is feasible. Proposal metadata (paper/evaluation/source
map) is persisted by `PipelinePersistence.persist_proposals`.

**Delta:** acceptance gate 11 must, after execution, construct **new**
persistence/RunService instances, load the run by ID, and recover the paper,
evaluation, citation audit, source map, and export location. **Not blocked.**

### 2.11 Complete artifact collection and hashing — **requires extension**

The runner prints a summary dict; it writes no evidence bundle and no hashes.

**Delta:** acceptance mode writes the full evidence bundle (§11 of the plan)
and hashes it last.

### 2.12 PASS/FAIL/INCONCLUSIVE classification — **requires extension**

The runner has a binary outcome: a non-exception path prints a summary; any
exception exits 1. There is no verdict enum, no INCONCLUSIVE distinction, no
machine-readable gate result.

**Delta:** the verdict layer (Phase A3) classifies the result. Exit codes:
0 PASS / 1 FAIL / 2 INCONCLUSIVE / 3 INVALID_CASE.

### 2.13 Human paper-readability review — **not applicable (A0–A7)**

A human review step is procedural, not code. The acceptance framework emits
a `human_review.md` template; the review itself is out of the hermetic
implementation scope. Recorded for completeness.

### 2.14 Safe redaction of credentials and provider payloads — **requires extension**

The runner's summary is credential-free, but no general redaction rule is
enforced on an evidence bundle.

**Delta:** evidence writers must redact secrets and avoid raw provider
responses unless explicitly safe.

---

## 3. Cross-cutting findings

### 3.1 Execution path is unchanged
The acceptance layer calls the same `PipelineOrchestrator(strategy="deep_research")`
via the same `orchestrator.run(...)`. It only adds preflight, post-run
classification, and evidence. **No second orchestration path is introduced**
— the central stop condition holds.

### 3.2 Cost ceiling: not blocked
`budget_guard.py` and `autonomy/budget.py` both support a hard `max_cost_usd`
check before a call proceeds. Acceptance mode must wire the manifest budget
through this guard. No design blocker.

### 3.3 Restart recovery: not blocked
Persistence is relational (RunService) and proposal metadata is persisted.
Fresh-instance reload is implementable without restructuring.

### 3.4 The runner is the spine, not the verdict
`validate_terminal_outcome()` is a coarse gate (nonblank paper). The verdict
layer must layer the 12 typed gates on top of — not inside — the runner.

---

## 4. Phase exit gate

Every acceptance requirement is classified. No item is left ambiguous, and
none requires a new orchestration harness:

```text
already satisfied:     12  (the spine — preserved as-is)
requires extension:    12  (the acceptance delta, on the existing runner)
blocked pending design: 0
not applicable:         1  (human review — procedural, A0–A7 out of scope)
```

**Implementation may begin.** Execution remains on the existing runner and
orchestrator path.
