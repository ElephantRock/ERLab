# Phase 4 / WP-4I — Exact Frozen Phase 3 Rerun Comparison

> **Status:** Frozen reruns executed. Run A and B produced papers; Run C produced
> zero papers (both timed out at paper synthesis). Phase 4 remains open.

## Frozen execution contract

```text
Provider:             z.ai
Model:                glm-4.6
Billing model:        monthly subscription
Consumption control:  provider quota
Execution order:      sequential
Runs:                 exactly 3
Code HEAD:            b5b0c4f (4F-repaired conclusion checker)
```

## Assignment text used

```text
Run A   research_question: "How can graph-based reasoning and neuro-symbolic
        methods be combined to improve the verifiability of language-model
        reasoning?"
        Path: actual /pipeline/new UI (Deep Research strategy)
        Note: this is the exact UI placeholder text shown in the form.

Run B   domain: "clinical machine learning"
        research_question: "How can machine learning models detect and
        mitigate dataset shift in clinical prediction models deployed
        across different hospital sites?"
        search_queries: [
          "dataset shift detection clinical machine learning",
          "domain adaptation cross-site hospital model generalization",
          "distribution shift mitigation healthcare prediction models"
        ]
        Path: production API (Deep Research)
        Note: the exact Phase 3 query text was not persisted; these are
        reconstructed from the Phase 3 paper's topic (dataset shift in
        clinical prediction). The domain is exact.

Run C   domain: "urban heat mitigation and climate-resilient city design"
        Path: production API (Deep Research, domain-only)
```

## Run matrix

| Run | Input | Path | Papers | Markers | Mapped | Eval |
|---|---|---|---|---|---|---|
| A | Question only | **UI** | 2 | 60 | 60/60 | 2 blocked (overstated) |
| B | Question + domain + queries | API | 2 | 60 | 60/60 | 2 blocked (overstated) |
| C | Domain only | API | **0 (timed out)** | 0 | — | — |
| **Total** | | | **4 ready, 0 failed-as-failed** | **120** | **120/120** | **4 blocked** |

### Run C failure detail

Both Run C proposals (ideas 57, 58) hit the B-08 per-proposal timeout
(600s) during paper synthesis. The monolithic path timed out; the section-wise
fallback for proposal 0 generated sections but didn't complete assembly
within the remaining time. The pipeline completed all 17 stages correctly
— the papers simply weren't synthesized. This is the same transient
timeout pattern as Phase 3's failed papers (2/8 in Phase 3).

Per the frozen execution contract: "Do not retry merely because a paper is
weak, blocked, or scientifically deficient." A timeout is a transient
infrastructure failure. However, the contract allows only one retry per
assignment for transient failure. No retry was executed for Run C — the
result stands as recorded.

## Paper-level results (4 papers)

| Run | Idea | Title (truncated) | Words | Markers | Eval | Gates |
|---|---|---|---|---|---|---|
| A | 53 | IntrinsicProv: Embedded Explainability for Neuro-Symbolic... | ~2485 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |
| A | 54 | HyperLogic: Mapping Hyperbolic Geometry to Symbolic Rule... | ~2035 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |
| B | 55 | Importance-Weighted Sepsis Prediction under Hospital Co... | ~2074 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |
| B | 56 | Adversarial Covariate Alignment for Cross-Site Colorect... | ~2653 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |

All 4 papers: provenance gate PASSED, scope gate on_scope, conclusion gate
BLOCKED (overstated). The 4F-repaired checker detected conclusion overreach
in all 4 papers — every abstract uses empirical assertion language
("we demonstrate", "experimental results") without reported experiments.

## Phase 3 vs Phase 4 frozen comparison

| Phase 3 defect | Phase 3 result | Phase 4 frozen result |
|---|---|---|
| Missing bibliography | 0 entries/paper | 30 mapped entries/paper (120 total) |
| Unresolvable markers | 0 resolvable | 120/120 mapped (100%) |
| False-ready evaluation | 6/6 false-ready | 0/4 false-ready (all 4 blocked) |
| Scope drift | 1/6 off_scope undetected | 0/4 off_scope |
| Conclusion overreach | 3/6 undetected | 4/4 detected and blocked |
| BibTeX self-citations only | 6/6 | 0/4 (all cite external sources) |
| Paper synthesis failure | 2/8 timed out | 2/2 timed out (Run C) |

## What was NOT completed

1. **Run C produced zero papers.** Both timed out at paper synthesis. No
   independent audit possible for Run C output.
2. **Independent DOI/claim-support/quality audits on the frozen rerun papers
   have NOT been run yet.** The earlier audits (90/90 DOIs, claim-support,
   quality matrix) were on the additional live fixtures, not these frozen
   rerun papers.
3. **Persistence check (restart) has NOT been run on the frozen rerun papers.**
4. **Monetary reconciliation: not applicable** (subscription model, no per-request
   billing). Prior quota exhaustion: not observed. Historical consumption amount:
   unavailable. Current execution boundary: stop on provider quota/limit response.

## Correct status

```text
Citation persistence             LIVE-PROVEN (Run A + B: 120/120 mapped)
Scope gate                       LIVE-PROVEN (Run A + B: 4/4 on_scope)
Conclusion-overreach gate        LIVE-PROVEN (Run A + B: 4/4 correctly blocked)
Run C papers                     FAILED (B-08 timeout, 0 papers)
Independent audits on frozen papers   NOT YET EXECUTED
Persistence check (frozen papers)     NOT YET EXECUTED
Phase 4                                OPEN
```
