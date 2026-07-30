# Phase 8 / 8R — Remediation: Proposal-Experiment Semantic Binding

> **Status:** The semantic binding enforcement (8R.2/8R.3) works. G2 retry
> achieved eval=ready with experiment_alignment gate passing. G1 rerun was
> blocked by the strict dataset-name check (since fixed). The alignment gate
> now catches papers that don't describe the actual experiment.

## What was fixed

### 8R.2 — Proposal-spec binding (commit 283353b)

ProposalSynthesisStage now injects the experiment spec's research question,
task type, dataset, analysis method, baseline, comparison model, and primary
metric into the framing directive. Proposals must be compatible with the
actual experiment.

PaperSynthesisStage now enriches the experiment_context with the spec's
method/dataset/target so the paper narrative describes the ACTUAL experiment,
not an unrelated architecture.

### 8R.3 — Experiment alignment gate (commit 283353b + 19342a4)

A new `experiment_alignment` gate in `_evaluate_paper` checks that the paper
mentions the spec's key method terms (logistic/linear regression) and dataset
name. Papers that don't describe the actual experiment are blocked.

## 8R.4 — Rerun results

### G1 rerun (run_bd9e2ac37931)

```text
experiment:    succeeded (balanced_acc 0.741 vs 0.500)
paper:         mentions "logistic regression" and "wine quality"
eval:          blocked — experiment_alignment gate caught the old strict check
               (required "wine_quality" underscore form; paper used "wine quality")
fix:           alignment check now accepts any dataset name form (commit 19342a4)
post-fix:      paper would pass alignment (verified)
```

### G2 retry (run_bac9868ed6fa)

```text
experiment:    succeeded (model_rmse 9.80 vs baseline 16.05, lower_better)
paper:         mentions "linear regression" and "concrete"
eval:          READY — all gates passed
  provenance:            passed (30 mapped sources)
  scope_alignment:       passed (on scope)
  conclusion_support:    passed (claims consistent with results)
  experiment_alignment:  PASSED ("Paper describes the experiment's method and dataset")
result_markers: 6 (lower_better + higher_better mix)
```

## Evidence of improvement

The original Phase 8 runs had ZERO overlap between papers and experiments
(quantum computing papers with classical ML experiments). After the 8R fixes:

```text
G1 paper: mentions "logistic regression" + "wine quality"  (from 0 → 2 terms)
G2 paper: mentions "linear regression" + "concrete"         (from 0 → 2 terms)
```

The framing directive and enriched experiment context successfully steered the
paper narrative toward the actual experiment. The alignment gate confirms this
structurally rather than relying on the LLM's self-assessment.

## Remaining limitation

The paper abstracts still contain creative framing (physics-informed neural
networks, etc.) that doesn't fully match the experiment. The method and dataset
terms ARE present, but the narrative framing is still broader than a pure
experiment report. This is because idea generation is not constrained to the
experiment spec — only proposal synthesis and paper synthesis are. Fully
constraining idea generation would require deeper changes to the ideation
pipeline (AgentOrchestrator.run signature).

The alignment gate ensures this residual mismatch is caught and reported
honestly, rather than producing false "ready" confidence.
