# Phase 4 / WP-4I — Live Remediation Validation (additional live runs)

> **Status:** Phase 4 provenance path live-demonstrated. Final acceptance remains
> pending exact frozen reruns, comprehensive independent audits, final code
> verification, and spend reconciliation.
>
> These six papers are **additional Phase 4 live fixtures**, NOT the required
> frozen Phase 3-versus-Phase 4 comparison reruns. The original Phase 3
> assignments (graph-based reasoning/neuro-symbolic; dataset-shift in clinical
> ML; urban heat/climate-resilient cities) were not used — equivalent topics
> were substituted because the original input text was not recoverable from
> the Phase 3 artifacts. The frozen comparison requires rerunning the exact
> original assignments under new explicit spend authorization.

## Authorization (frozen before execution)

| Field | Value |
|---|---|
| Provider | z.ai |
| Model | glm-4.6 |
| Hard total spend cap | $10.00 |
| Run A path | Actual `/pipeline/new` UI |
| Run B path | Production API (`POST /api/v1/pipeline/run`) |
| Run C path | Production API |
| Commit at execution | `95ac345` (Phase 4 + gap-analysis fix) |

## Live run matrix

| Run | Input | Path | Papers | Markers | Mapped | Eval |
|---|---|---|---|---|---|---|
| A | Question only (neuro-symbolic verifiability) | **UI `/pipeline/new`** | 2 ready | 60 | 60/60 | 1 ready, 1 blocked |
| B | Question + domain + queries (clinical ML) | API | 2 ready | 60 | 60/60 | 2 ready |
| C | Domain only (clinical ML) | API | 2 ready | 60 | 60/60 | 2 ready |
| **Total** | | | **6 ready** | **180** | **180/180** | **5 ready, 1 blocked** |

All assignments used equivalent inputs matching the Phase 3 shapes. The original
Phase 3 question/queries text was not persisted and is not recoverable (see
`PHASE_4_RUN_MANIFEST.json`); these are documented as equivalents.

## Live blockers encountered and repaired

### Blocker 1: gap_analysis bare-gap-object parser discard

Three consecutive pre-fix runs (A×2, B) failed at `gap_analysis` with 0 gaps.
Root cause (revealed by the 4G logging fix): glm-4.6 returned a single bare gap
object (a dict with gap-shaped keys) instead of the requested JSON array.
`gap_analyzer.py:119` kept the dict as-is, then `result.get("gaps", [])` returned
`[]` because the dict had no `"gaps"` key. The generated gap was silently
discarded.

This was the Phase 3 "B-09 intermittent empty gaps, root cause unknown" defect —
now root-caused and fixed (commit `95ac345`, parser robustness, prompt unchanged).

### Blocker 2: budget_max_seconds=600 (10 min) too short for deep_research

Three post-fix runs halted after `idea_generation` (cumulative elapsed 611s >
600s budget). The `budget_max_seconds` default of 600s is far too short for
`deep_research` (~25-30 min). Fixed by restarting the backend with
`EROCK_BUDGET_MAX_SECONDS=5400` (90 min). This is a configuration correction,
not a code change.

## Persistence results (post-restart verification)

All 6 papers verified after backend restart: paper hash, marker map count,
Markdown export hash, and BibTeX export hash are **byte-identical** pre- and
post-restart. Every `paper_source_markers` row survived. Export hashes stable.

## Independent citation audit (Run C, idea 47 — sample of 10/30 sources)

| SOURCE | Title | DOI | Crossref-verified |
|---|---|---|---|
| 1 | Physics-informed machine learning | 10.1038/s42254-021-00314-5 | ✅ verified |
| 2 | Machine Learning: Algorithms, Real-World Applications... | 10.1007/s42979-021-00592-x | (not individually re-checked) |
| 3 | A survey on deep learning in medical image analysis | 10.1016/j.media.2017.07.005 | ✅ verified |
| 4 | Computed Tomography: Principles, Design, Artifacts... | 10.1117/3.2197756 | (not individually re-checked) |
| 5 | Current Applications and Future Impact of ML in Radiology | 10.1148/radiol.2018171820 | (not individually re-checked) |
| 6 | Automated Machine Learning | 10.1007/978-3-030-05318-5 | (not individually re-checked) |
| 7 | Deep EHR: A Survey of Recent Advances... | 10.1109/jbhi.2017.2767063 | ✅ verified |
| 8 | Natural products in drug discovery | 10.1038/s41573-020-00114-z | ✅ verified |
| 9 | Review of deep learning: concepts, CNN architectures... | 10.1186/s40537-021-00444-8 | (not individually re-checked) |
| 10 | Deep learning in histopathology | 10.1038/s41591-021-01343-4 | ✅ verified |

25/90 unique DOIs independently verified via Crossref API (100% match, 0 not-found,
0 metadata mismatches). The remaining 65 unique DOIs have not been individually
re-checked. All 90 carry real titles from Crossref/PubMed/OpenAlex retrieval
(provenance continuity), but existence has been independently verified for only
the 25 sampled DOIs, not all 90.

## Claim-support audit (≥12 relationships)

Each of the 6 papers contains 30 `[SOURCE-N]` markers, all mapped to real
`Paper` rows. The claim-support audit examines whether cited claims trace to
the mapped sources. With 180 total marker→source mappings across 6 papers, the
claim-support relationships are auditable for the first time (Phase 3 had 0
auditable relationships). A focused audit of Run A idea 51 (5 claims × their
mapped sources) is in `runs/run_a/idea_51_paper.md`.

## Phase 3 vs Phase 4 comparison

| Phase 3 defect | Phase 3 result | Phase 4 result |
|---|---|---|
| **Missing bibliography** | 6/6 papers: 0 bibliography entries | 6/6 papers: 30 mapped sources each (180 total) |
| **Unresolvable markers** | 6/6 papers: 0 resolvable references | 6/6 papers: 180/180 mapped (100%) |
| **False-ready evaluation** | 6/6 papers: automated eval=ready despite 0 provenance | 5/6 eval=ready (provenance verified); 1/6 eval=blocked (overreach detected) |
| **Scope drift** | 1/6 off_scope (Q-Sym), undetected | 0/6 off_scope; all 6 classified on_scope |
| **Conclusion overreach** | 3/6 overstated, undetected | 1/6 overstated → **blocked** (Run A idea 52) |
| **BibTeX only self-citations** | 6/6: only `@misc` self-entries | 6/6: 30 `@article` external entries each |
| **Trust & Sources wrong list** | derived from hallucinated references_json | consumes the persisted marker map (180 entries) |
| **Persistence** | not checked after restart | all hashes byte-identical after restart |

## What the evaluation gate caught (Run A idea 52)

Paper: *Formal Verification Wrapper for Neuro-Symbolic Agents in Safety-Critical
Systems*. The paper has full provenance (30/30 markers mapped) and is on-scope.
But its conclusion claims demonstration without empirical results:

```
paper artifact: ready (13,462 chars, persisted)
paper evaluation: blocked
reason: conclusion_support=overstated
  "Conclusion uses empirical/causal claim language (claims demonstration)
   but the paper reports no empirical results."
```

In Phase 3, this paper would have been `eval=ready` (the false-confidence
defect). The 4F conclusion-overreach detector caught it. The paper artifact
remains accessible — the gate blocked the evaluation, not the generation.

## Known limitations

1. **Equivalent assignments, not original Phase 3 text** — the original
   question/queries were not persisted. Inputs match the Phase 3 shapes and
   recoverable domains.
2. **5/10 DOI sample verified** — not all 180 sources were individually
   re-checked against Crossref (budget/time). The 5 checked were 100% accurate.
3. **Budget cost not precisely tracked** — the cost API returned
   SERVICE_UNAVAILABLE. Estimated spend well under $10 (Phase 3's 3-run suite
   was <$2; this run had similar volume plus failed pre-fix attempts).
4. **adversarial_review structured_output parse failures** — glm-4.6's JSON
   schema responses failed parsing in the adversarial review stage. These are
   non-fatal (HB-03) and did not block the pipeline, but indicate a provider
   compatibility issue outside Phase 4 scope.
5. **Run A idea 52 is scientifically weak** — it claims demonstration without
   results, which is why the gate blocked it. This is a legitimate Phase 4
   finding, not a defect.

## P1E artifacts changed = 0

## Retrieval ranking architecture changed = 0

## Working tree status

Clean at closeout.

---

---

## Post-code verification (at HEAD b0b88a4, includes gap-analysis fix 95ac345)

After the 4I production-code change (commit `95ac345`, gap-analysis bare-gap-object
recovery), the full verification suite was re-run:

```
Canonical backend selector:  4831 passed, 0 failed, 47 skipped, exit 0
Architecture:                41 passed, 0 failed
Ranking:                     253 passed, 3 skipped
Controlled integrations:     14 passed (P1 + P2 + P4)
Frontend typecheck:          PASS (exit 0)
Frontend tests:              988 passed
Frontend build:              PASS (exit 0)
Frontend lint:               0 errors
Frontend budgets:            all hold (TS, API, lint)
```

The gap-analysis production fix did not regress any suite. The +1 vs the 4G
baseline (4830→4831) is the new `test_bare_gap_object_without_wrapper_is_recovered`
regression test from commit `95ac345`.

## Comprehensive citation audit (all 180 markers across 6 papers)

```
Total markers:               180
Mapped:                      180/180 (100%)
Unmapped:                    0
Missing DOI:                 0
Missing title:               0
Missing authors:             10  (metadata gaps from original providers)
Missing year:                30  (metadata gaps from original providers)
Duplicate DOIs within paper: 0
Unique DOIs across all papers: 90  (each appears in 2 papers — same source corpus
                                    per run's two ideas; canonical identity retained)
DOI existence independently verified (Crossref API):
  25/90 unique DOIs sampled (stratified), 100% match, 0 not-found, 0 mismatch.
  Remaining 65 DOIs: provenance continuity established (mapped to Paper rows with
  real metadata from Crossref/PubMed/OpenAlex), but existence not independently
  re-verified via Crossref.
```

## Claim-support audit (sample: Run C idea 47)

```
Sentences containing [SOURCE-N] citations:  9
Required minimum:                           12 (or all where fewer exist)
Auditable claim-source relationships:       9 (the ceiling for this paper)
```

All 9 claim-source relationships point to mapped sources with real DOIs. The
paper has 30 mapped markers but only 9 sentences contain distinct claim-source
attributions — many markers appear in context/lists rather than supporting
specific claims. This is a legitimate finding about the paper's citation
density, not a Phase 4 defect.

## Correct status

```
4A–4H                                    COMPLETE
4G                                       COMPLETE
4I live provenance path                  SUBSTANTIALLY VALIDATED
4I frozen comparison (exact Phase 3)     NOT EXECUTED
Independent citation audit               PARTIAL — 25/90 DOIs verified, all 180 mapped
Independent claim audit                  PARTIAL — 9 relationships in 1/6 papers
Post-code verification at b0b88a4        COMPLETE — 0 failures
Spend-cap compliance                     UNVERIFIED — cost API unavailable
Phase 4                                  OPEN
```

The six papers are recorded as **additional Phase 4 live fixtures**, not as
satisfaction of the frozen Phase 3-versus-Phase 4 comparison criterion.

---

*End of WP-4I follow-up. Phase 4 provenance path live-demonstrated; final
acceptance pending exact frozen reruns, comprehensive audits, and spend
reconciliation.*
