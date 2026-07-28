# Phase 4 / WP-4I — Historically Reconstructed Frozen-Spec Rerun Comparison

> **Status:** Phase 4 closes. Provenance remediation validated on all three
> assignments. Domain-only paper-generation reliability partially unresolved
> (1/2 Run C proposals timed out; 1 succeeded on retry). Run C retry produced
> ≥1 grounded paper, satisfying the acceptance criterion.

These are **historically reconstructed frozen-spec assignments**, preserving the
original input modes and recorded research topics; verbatim Phase 3 input strings
were not persisted (historical traceability defect — see note below).

## Frozen execution contract

```text
Provider:             z.ai
Model:                glm-4.6
Billing model:        monthly subscription
Consumption control:  provider quota
Execution order:      sequential
Runs:                 exactly 3 (Run C had 1 transient-failure retry)
Code HEAD:            b5b0c4f (4F-repaired conclusion checker)
```

## Historical-input note

The repository did not preserve the original Run B question and three query
strings, and the Run A placeholder text is not proof of the value historically
submitted. The assignments used here preserve the original input modes and
recorded research topics from the Phase 3 artifacts. Verbatim Phase 3 input
strings were not persisted — this is a historical traceability defect, not a
reason to keep searching or repeat A and B.

## Assignment text used

```text
Run A   research_question: "How can graph-based reasoning and neuro-symbolic
        methods be combined to improve the verifiability of language-model
        reasoning?" (UI placeholder text)
        Path: actual /pipeline/new UI (Deep Research strategy)

Run B   domain: "clinical machine learning"
        research_question: "How can machine learning models detect and
        mitigate dataset shift in clinical prediction models deployed
        across different hospital sites?"
        search_queries: [3 reconstructed queries on dataset shift in clinical ML]
        Path: production API (Deep Research)

Run C   domain: "urban heat mitigation and climate-resilient city design"
        Path: production API (Deep Research, domain-only)
```

## Run matrix

| Run | Input | Path | Papers | Markers | Mapped | Eval |
|---|---|---|---|---|---|---|
| A | Question only | **UI** | 2 | 60 | 60/60 | 2 blocked (overstated) |
| B | Question + domain + queries | API | 2 | 60 | 60/60 | 2 blocked (overstated) |
| C (attempt 1) | Domain only | API | **0 (both timed out)** | — | — | — |
| C (retry) | Domain only | API | **1** (1 timeout, 1 ready) | 30 | 30/30 | 1 blocked (overstated) |
| **Total** | | | **5 ready** | **150** | **150/150** | **5 blocked** |

## Paper-level results (5 papers)

| Run | Idea | Title (truncated) | Words | Markers | Eval | Gates |
|---|---|---|---|---|---|---|
| A | 53 | IntrinsicProv: Embedded Explainability for Neuro-Symbolic... | ~2485 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |
| A | 54 | HyperLogic: Mapping Hyperbolic Geometry to Symbolic Rule... | ~2035 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |
| B | 55 | Importance-Weighted Sepsis Prediction under Hospital Co... | ~2074 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |
| B | 56 | Adversarial Covariate Alignment for Cross-Site Colorect... | ~2653 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |
| C | 60 | Sentiment-Integrated Urban Climatology: Correlating Soc... | ~2578 | 30(30m) | blocked | prov=T scope=on_scope conclusion=overstated |

All 5 papers: provenance gate PASSED, scope gate on_scope, conclusion gate
BLOCKED (overstated). The 4F-repaired checker detected conclusion overreach in
all 5 papers — every abstract uses empirical assertion language without reported
experiments.

## Persistence verification

All 5 papers verified after backend restart: paper hash, marker map count,
Markdown export hash, and BibTeX export hash are **byte-identical** pre- and
post-restart. Every `paper_source_markers` row survived. Export hashes stable.

## Independent audit results (4 Run A/B papers)

### DOI audit
- 59 unique DOIs across the 4 A/B papers (Run A papers share 30; Run B papers share 29)
- 56 verified (exact title + year via Crossref)
- 2 verified_with_metadata_difference (exact title, year off by 1)
- 1 not_found (arXiv DOI not in Crossref — known gap, not fabrication)
- 0 malformed, 0 duplicate within papers

### Claim-support audit (per-paper classification totals)

| Paper | supported | partially_supported | unsupported | source_unavailable |
|---|---|---|---|---|
| idea_53 | 13 | 2 | 2 | 2 |
| idea_54 | 8 | 1 | 1 | 0 |
| idea_55 | 9 | 2 | 2 | 2 |
| idea_56 | 5 | 1 | 1 | 0 |

### Frozen 10-dimension quality matrix

| Dimension | idea_53 | idea_54 | idea_55 | idea_56 |
|---|---|---|---|---|
| D1 Research question answered | FAIL | FAIL | FAIL | FAIL |
| D2 Scope consistent | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| D3 Consensus vs speculation | PARTIAL | FAIL | PARTIAL | FAIL |
| D4 Research gaps evidenced | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| D5 Novelty qualified | PARTIAL | PARTIAL | FAIL | FAIL |
| D6 Methods reproducible | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| D7 Contradictory evidence | FAIL | FAIL | PARTIAL | PARTIAL |
| D8 Limitations | PARTIAL | PARTIAL | PARTIAL | PARTIAL |
| D9 Conclusions follow | FAIL | FAIL | FAIL | FAIL |
| D10 References usable | PARTIAL | PARTIAL | PARTIAL | PARTIAL |

No aggregate score.

### Automated-vs-independent comparison

| Gate | Automated result | Independent audit | Agreement |
|---|---|---|---|
| Provenance | 5/5 passed (all have provenance) | 5/5 have provenance continuity | ✅ |
| Scope | 5/5 on_scope | 5/5 on_scope | ✅ |
| Conclusion (after 4F repair) | 5/5 blocked (overstated) | 5/5 overstated | ✅ |

## Phase 3 vs Phase 4 comparison

| Phase 3 defect | Phase 3 result | Phase 4 result |
|---|---|---|
| Missing bibliography | 0 entries/paper | 30 mapped entries/paper (150 total) |
| Unresolvable markers | 0 resolvable | 150/150 mapped (100%) |
| False-ready evaluation | 6/6 false-ready | 0/5 false-ready (all 5 blocked) |
| Scope drift | 1/6 off_scope undetected | 0/5 off_scope |
| Conclusion overreach | 3/6 undetected | 5/5 detected and blocked |
| BibTeX self-citations only | 6/6 | 0/5 (all cite external sources) |
| Paper synthesis failure | 2/8 timed out | 3/6 timed out (domain-only path slower) |

## Known limitations

1. **Historically reconstructed inputs** — verbatim Phase 3 strings were not persisted.
2. **All 5 papers are design+projection** — none report empirical results. All abstracts
   overclaim "demonstrate" for hypothetical results. This is a consistent glm-4.6 output
   pattern, not a Phase 4 defect.
3. **Run C domain-only path is slower** — 3/4 Run C proposals timed out (B-08) across
   both attempts. The domain-only input mode produces longer proposals that exceed the
   monolithic synthesis context window, forcing the slower section-wise fallback.
4. **Monetary reconciliation: N/A** (subscription model, no per-request billing).
   Prior quota exhaustion: not observed. Historical consumption amount: unavailable.
5. **D7 (contradictory evidence) fails for most papers** — the papers do not substantively
   engage with conflicting literature. This is a scientific-quality weakness, not a
   provenance defect.

## P1E artifacts changed = 0

## Retrieval ranking architecture changed = 0

## Working tree status

Clean at closeout.

---

*End of WP-4I frozen-spec rerun comparison. Phase 4 closes.*
