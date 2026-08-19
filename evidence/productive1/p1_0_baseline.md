# Productive-1 implementation baseline (P1-0)

Frozen 2026-08-20. No code changes occur in this step; acceptance
criteria freeze here.

## Baseline facts

- **Product SHA:** `6f13f809010fcf6a373bf063c224420aa4231b42` (= main;
  R2 `7e5462637bff4ea83a4141e6149ea04c049e80b8` + the documentation-only
  Case-3 erratum PR #41; no product delta after R2).
- **Working branch:** `productive1/repair-targeting` (from main).
- **Full-suite failure fingerprint (frozen):** 5,711 passed / 18 failed /
  36 skipped / 1 xfailed — failure set byte-identical to the R2-era
  environmental baseline (empty diff vs the prior frozen set; known
  local-environment failures: docker sandbox, phase5/phase8 controlled
  proofs, batch28 auth, fresh-process recovery).
- **Provider/model configuration (unchanged):** pipeline LLM
  qwen3-4b-2507 via local LM Studio (100.64.0.2:1234); embedding
  qwen3-embedding-0.6b (1024-dim, /v1); evaluator/repair glm-5.2 via
  Z.AI Coding Plan endpoint; `EROCK_BUDGET_ENABLED=false` as previously
  reported.
- **Case-4 blocked specimen identity:** the final consumed attempt's
  specimen, published at
  `evidence/case4_qualifying_runfail_3/` on `case4/evidence-publication`
  (snapshot `762627b`, precision note `58dc36a`); local evidence branch
  commit `2a0cca1`; SQLite specimen 1,642,496 bytes; blocked repaired
  paper = paper_revisions revision 1 (39,460 chars); original = revision
  0 (30,469 chars); 74 dataset-qualified markers across two experiment
  results.

## Frozen Productive-1 qualification contract (per the owner plan)

- **Delta scope:** only `paper_remediator.py` and
  `revision_directive.py` change, plus one test module under
  `backend/tests/test_evaluation/`; no DB migrations, no new gates, no
  new retries, no changed thresholds, no provider/model policy, no
  deterministic post-generation fixer, no second LLM call, no retry-
  until-pass loop; validator remains the authority; one repair remains
  the maximum; `EvidenceInvariant.result_map_hash` semantics unchanged.
- **Qualification (P1-12):** 8 trials = 4 blocked starting states
  (2 calibration, 2 robust-regression) × 2 byte-identical restores each;
  fresh API process per trial; exactly one cold repair per trial;
  record original/repair hashes, directive/target set, gate outcomes,
  revision lineage, and on ready the normal freeze/release/E==F==R==H.
- **PASS criterion (P1-13):** ≥7/8 overall AND ≥3/4 per capability
  family AND zero negative-control promotions AND zero operator
  edits/continuation decisions AND unchanged assurance semantics AND
  ordinary release identity on every successful trial.

## Diagnostic tranche obligations (before any product patch)

P1-1 discrepancy record; P1-2 unchanged-implementation baseline of the
one-shot path on byte-identical state (stop with no patch if the frozen
criterion is already met); stop condition: persisted value wrong or
validator false positive ⇒ do not patch remediation.
