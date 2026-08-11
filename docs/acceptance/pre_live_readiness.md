# Pre-live readiness verdict

> Updated after closing the budget-refusal and fresh-process recovery
> blockers. The verdict remains NOT READY because corpus, human-review,
> and live-preflight prerequisites are still open.

This report states whether the acceptance framework is technically ready
for **one budget-capped live attempt** (Phase B). A live attempt requires
separate authorization and is not part of this implementation scope.

---

## Verdict

```
NOT READY FOR A LIVE ATTEMPT
```

Two of the previous blockers are now closed. The remaining blockers are
the frozen corpus, the human reviewer, and the live provider preflight.
The honest verdict is still NOT READY — engineering controls passing does
not by itself authorize a paid run.

---

## What is now proven (Milestone A — acceptance framework v0 + safety controls)

| Item | Status | Evidence |
| --- | --- | --- |
| Runner audit (A0) | ✅ | `docs/acceptance/live_paper_runner_audit.md` |
| Typed acceptance contract (A1) | ✅ | `live_paper_contract.py` + 25 tests |
| Manifest-driven acceptance mode (A2) | ✅ | `runner.py` + 11 tests |
| Verdict layer + 12 hard gates (A3/A4) | ✅ | `live_paper_verdict.py` + 20 tests |
| Hermetic rehearsal (A6) | ✅ | `test_hermetic_rehearsal.py` + 16 tests |
| **Hard pre-call budget refusal** (NEW) | ✅ | `budget_authority.py` + `gateway.py` wiring + 24 tests |
| **Fresh-process restart recovery** (NEW) | ✅ | `recovery.py` + subprocess test + 4 tests |
| **Integrated rehearsal w/ budget + restart** (NEW) | ✅ | `test_integrated_rehearsal.py` + 13 tests |
| Network interdiction | ✅ | socket-not-invoked + provider-has-no-client |
| Execution stays on the production orchestrator | ✅ | no second orchestration path |

**Total: 113 acceptance tests pass; ruff clean on all new files.**

### Budget refusal — closed

The hard cost authority is wired into `LLMGateway.call()`, the single
chokepoint covering every billable call. A refused call raises
`BudgetExceededError` (a `PromptTooLargeError` subclass) so the
`GatewayProvider` re-raises rather than falling back to the billed inner
provider. The decision accounts for committed + reserved + projected
maximum, preventing overshoot. Proven via the real gateway boundary with
a provider spy: a denied call leaves call/usage/token/cost counts
unchanged.

### Fresh-process recovery — closed

A child process (real `subprocess.run`) imports ERLab afresh, connects to
the isolated SQLite DB with a new engine, and loads the run through
production read APIs (`get_run_by_uuid`, `load_gaps`, `crud`). The paper,
evaluation, and source map come from `proposals.paper_md` /
`paper_meta_json` — not from an in-memory handoff. Negative control: the
child exits nonzero when the paper is absent.

---

## What still blocks a live attempt

| Pre-live requirement | Status | Gap |
| --- | --- | --- |
| Acceptance rehearsal passes | ✅ met | — |
| All negative controls pass | ✅ met | — |
| Network interdiction verified | ✅ met | — |
| Exact code SHA frozen | ✅ mechanism | live attempt freezes the SHA at attempt time |
| Working tree clean | ✅ mechanism | enforced at preflight |
| Hard cost cap demonstrably enforced | ✅ met | gateway refuses at the ceiling |
| Restart proof passes | ✅ met | fresh-process subprocess recovery |
| **Frozen corpus frozen and hashed** | ❌ **NOT MET** | Phase A5 not done — no real corpus manifest |
| Provider/model frozen | ⚠️ declared in case, not verified live | live credential verification is a Phase B preflight |
| Artifact directory absent | ✅ mechanism | enforced at preflight |
| One-attempt policy documented | ✅ | this report + the case manifest |
| **Human reviewer identified** | ❌ **NOT MET** | no human reviewer named |

---

## Why the verdict is still NOT READY

1. **No frozen real corpus (Phase A5).** A live attempt must not use live
   search for the first proof, and the frozen-corpus input mode — the
   production ingestion adapter plus a hashed corpus manifest of 12–20 real
   papers with verified DOIs/arXiv IDs — does not yet exist. This is the
   largest remaining work item and requires real paper curation.

2. **No human reviewer identified** for the live attempt.

3. **Live provider/model preflight not performed.** The case declares the
   provider/model; verifying live credentials is a Phase B preflight step.

---

## What this branch establishes (precise conclusion)

> The live-paper acceptance **framework** is complete and proven
> hermetically, including the two safety controls a paid run depends on:
> hard pre-call budget refusal (no overshoot, no bypass) and fresh-process
> artifact recovery through production persistence.

It does **not** establish:

> ERLab can complete a live provider-driven gap-to-paper workflow. That
> requires the frozen real corpus, a human reviewer, and a separately
> authorized Phase B live attempt.

---

## Next authorized engineering step

```
A5  frozen real corpus (production ingestion adapter + hashed manifest
    of 12-20 real papers with verified DOIs/arXiv IDs)
```

After A5 + a named human reviewer, this report should be re-evaluated for
either:

```
READY FOR ONE BUDGET-CAPPED LIVE ATTEMPT
```

or remain:

```
NOT READY
```

No paid provider call, PR retargeting, ready-for-review transition,
merge, tag, or release belongs in the current scope.
