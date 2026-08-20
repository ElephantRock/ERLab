# Productive-1 candidate seal (P1-11)

Frozen 2026-08-20. No product or prompt edits after this point; a later
code change creates a new candidate.

## Candidate identity

- **Branch/commit:** `productive1/repair-targeting` @ `3eb9885`
  (base: main `6f13f80` = R2 `7e546263` + documentation-only erratum).
- **Product delta (exactly two files):**
  - `backend/pipeline/evaluation/paper_remediator.py` —
    `derive_numeric_repair_targets()`: joins the existing numeric-fidelity
    validator's mismatches to their ResultMarkers; full `result_context`.
  - `backend/pipeline/evaluation/revision_directive.py` — optional
    `numeric_repair_targets` / `result_context` fields; prompt renders
    the NUMERIC REPAIR TARGETS block, qualified result context, and the
    preservation rule; bare-map fallback retained.
- **Tests:** `backend/tests/test_evaluation/test_p1_repair_targeting.py`
  (15 deterministic controls, P1-7/P1-8).
- **Fingerprint:** full suite 5,726 passed / 18 failed — failure set
  byte-identical to the frozen P1-0 baseline (empty diff both
  directions); product-file lint rule multiset unchanged vs baseline.
- **No:** DB migrations, new gates, retries, thresholds, provider/model
  policy changes, deterministic post-generation fixer, second LLM call,
  retry-until-pass loop. One repair remains the maximum;
  `EvidenceInvariant.result_map_hash` semantics unchanged; the
  validator remains the authority.

## Provider/model assignment (unchanged from P1-0)

Pipeline LLM qwen3-4b-2507 (local LM Studio); evaluator/repair glm-5.2
via Z.AI Coding Plan endpoint; embedding qwen3-embedding-0.6b.

## Qualification starting states (frozen identities)

| State | Family | Source specimen | Pre-repair preparation |
| --- | --- | --- | --- |
| calib-A | calibration | `evidence/case4_qualifying_runfail_3/r1_specimen.db` (runfail_3; published at case4/evidence-publication 58dc36a) | strip revision ≥1 (its blocked evaluation is authentic) |
| calib-B | calibration | `evidence/case4_qualifying_runfail_2/r1_specimen.db` (runfail_2) | strip revisions ≥1; restore proposal paper to rev0 bytes; recompute blocked evaluation with the production gate evaluator (deterministic pure function) |
| regr-A | robust regression | `evidence/case3a_specimen.db` (Case-3 first attempt; on main) | same as calib-B |
| regr-B | robust regression | 3E-era live DB preserved at `evidence/case4_runtime/preflight_archive/20260818T081540Z/data/elephant_rock.db` | same as calib-B |

Each state: autonomous design `designed`, 2 successful experiment
results, dataset-qualified marker set (calibration 74 markers;
regression 54 markers), rev0 blocked original paper.

## Frozen qualification contract (P1-12/P1-13)

8 trials = the four states × 2 byte-identical restores each; fresh API
process per trial; exactly one cold repair per trial; per trial record:
original/repair paper hashes, directive target set, six-gate outcomes,
revision lineage, and on ready the normal freeze + release + E==F==R==H.
PASS = ≥7/8 overall AND ≥3/4 per capability family AND zero
unsupported-numeric negative-control promotions AND zero operator
edits/continuation decisions AND unchanged assurance semantics AND
ordinary release identity on every successful trial.
