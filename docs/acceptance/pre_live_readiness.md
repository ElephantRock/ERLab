# Pre-live readiness verdict

> Phase A7 — closing the implementation phase (A0–A7) of the live-paper
> acceptance program.

This report states whether the acceptance framework is technically ready
for **one budget-capped live attempt** (Phase B). A live attempt requires
separate authorization and is not part of this implementation scope.

---

## Verdict

```
NOT READY FOR A LIVE ATTEMPT
```

The acceptance *framework* (Milestone A) is proven hermetically. The
*live-attempt prerequisites* are not all met. The honest verdict is NOT
READY, not "mostly ready."

---

## What is proven (Milestone A — acceptance mode works hermetically)

| Item | Status | Evidence |
| --- | --- | --- |
| Runner audit (A0) | ✅ | `docs/acceptance/live_paper_runner_audit.md` |
| Typed acceptance contract (A1) | ✅ | `backend/acceptance/live_paper_contract.py` + 25 tests |
| Manifest-driven acceptance mode (A2) | ✅ | `backend/acceptance/runner.py` + 11 tests |
| Verdict layer + 12 hard gates (A3/A4) | ✅ | `backend/acceptance/live_paper_verdict.py` + 20 tests |
| Hermetic rehearsal (A6) | ✅ | `test_hermetic_rehearsal.py` + 16 tests |
| Network interdiction | ✅ | socket-connect-not-invoked + provider-has-no-client assertions |
| PASS decision is trustworthy | ✅ | complete synthetic result → PASS, all gates green |
| FAIL decisions are trustworthy | ✅ | 11 negative controls, each yields the expected FAIL gate |
| Evidence bundle + hashing | ✅ | required files written, hashes generated last |
| Execution stays on the production orchestrator | ✅ | no second orchestration path introduced |
| Hard cost-ceiling mechanism EXISTS | ✅ | `budget_guard.py` + `autonomy/budget.py` support pre-call `max_cost_usd` |

**Total: 72 acceptance tests pass; ruff clean on all new files.**

---

## What blocks a live attempt (gaps against the pre-live gate)

The plan's pre-live gate (§13) requires all of these to be true. The
items still missing:

| Pre-live requirement | Status | Gap |
| --- | --- | --- |
| Acceptance rehearsal passes | ✅ met | — |
| All negative controls pass | ✅ met | — |
| Network interdiction verified | ✅ met (framework level) | — |
| Exact code SHA frozen | ✅ mechanism | live attempt must freeze the actual SHA at attempt time |
| Working tree clean | ✅ mechanism | enforced at preflight |
| **Frozen corpus frozen and hashed** | ❌ **NOT MET** | Phase A5 not done — no real corpus manifest exists yet |
| **Provider/model frozen** | ⚠️ declared in case, not verified live | the case names `zai`/`glm-4.6`; live credential verification is a Phase B preflight step |
| **Hard cost cap demonstrably enforced** | ⚠️ mechanism exists, not yet wired end-to-end in a rehearsal | `budget_guard` can enforce, but the rehearsal did not exercise a live provider call to prove refusal-at-ceiling |
| Restart proof passes | ⚠️ deferred in rehearsal case | `require_restart_recovery=False` in the hermetic case; fresh-process DB recovery not yet proven |
| Artifact directory absent | ✅ mechanism | enforced at preflight |
| One-attempt policy documented | ✅ | this report + the case manifest |
| **Human reviewer identified** | ❌ **NOT MET** | no human reviewer named for the live attempt |

---

## Why the verdict is NOT READY

Two hard blockers and two incomplete items:

1. **No frozen real corpus (Phase A5).** A live attempt must not use live
   search for the first proof, and the frozen-corpus input mode — the
   production ingestion adapter plus a hashed corpus manifest of 12–20 real
   papers with verified DOIs/arXiv IDs — does not yet exist. This is the
   largest remaining work item and requires real paper curation, not just
   code.

2. **Hard cost-cap enforcement is not yet demonstrated end-to-end.** The
   `budget_guard`/`autonomy/budget` mechanism can refuse a call at the
   ceiling, but no rehearsal has driven a provider call to the ceiling to
   prove refusal. Wiring the manifest budget through the guard and proving
   refusal is a prerequisite.

3. **Fresh-process restart recovery is deferred.** The hermetic rehearsal
   disabled `require_restart_recovery`. The gate logic exists and is tested
   for pass/fail classification, but actual fresh-instance DB reload of the
   paper/evaluation/citation artifacts has not been performed.

4. **No human reviewer identified** for the live attempt.

---

## What this branch establishes (precise conclusion)

> The live-paper acceptance **framework** is complete and proven
> hermetically: a typed case contract, a manifest-driven runner mode that
> stays on the production orchestrator, a 12-gate verdict layer, an
> immutable evidence bundle, and a network-free rehearsal that makes
> trustworthy PASS/FAIL decisions.

It does **not** establish:

> ERLab can complete a live provider-driven gap-to-paper workflow. That
> requires Phase A5 (frozen corpus), cost-cap enforcement rehearsal,
> restart-recovery proof, and a separately authorized Phase B live attempt.

---

## Next authorized engineering step

The next implementation work that does NOT require live authorization:

```
A5  frozen real corpus (production ingestion adapter + hashed manifest)
    + wire the manifest budget through budget_guard and prove refusal
    + perform fresh-process restart recovery proof
    + re-run the hermetic rehearsal with those gates enabled
```

After A5 + the two incomplete items close, this report should be updated
to either:

```
READY FOR ONE BUDGET-CAPPED LIVE ATTEMPT
```

or remain:

```
NOT READY
```

No paid provider call, PR retargeting, ready-for-review transition,
merge, tag, or release belongs in the current scope.
