# Phase 3 Closeout — Live Product Validation

> **Phase 3 closeout.**
> **Outcome: QUALITY_REMEDIATION_REQUIRED.**
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `6feba96c49483bf83de6dde622d12e1287071380` |
| **Final commit** | (this closeout) |
| **Code-fix commits** | `a10c768`, `c4bf84b`, `eddd0a9`, `c3283c1`, `9d747fb`, `5e09c47` |
| **Working tree** | clean |

---

## Provider/model

z.ai glm-4.6. Frozen before execution; unchanged across runs.

## Spend cap and observed cost

**$100.00 hard cap.** Observed cost: <$2.00 across all runs.

## Run matrix

| Run | Input | Path | Papers |
|---|---|---|---|
| A (API) | Question only | Production API | 2 ready (2675 + 2649 words) |
| A (UI) | Question only | **UI `/pipeline/new`** | 1 ready (2334 words), 1 failed |
| B | Question + domain + queries | Production API | 2 ready (2807 + 2475 words) |
| C | Domain only | Production API | 1 ready (2534 words), 1 failed |
| **Total** | | | **6 ready, 2 explicitly failed** |

## Per-run completion result

All three frozen assignments completed end-to-end through the production orchestration path. Run A was also submitted through the actual UI. 6 papers persisted, evaluated, exported.

## Paper persistence results

All 6 ready papers verified after backend restart: paper_md non-empty, paper_eval scope=paper status=ready, proposal_eval scope=proposal distinct. Export hashes stable across double-fetch. 2 failed papers: paper_md=None, meta_status=failed, export returns 404. No false-ready artifacts.

## Export results

6/6 ready papers: Markdown/LaTeX/BibTeX all non-empty and stable.

## Citation-existence findings

**Live papers (6):** 0 resolvable references. All contain [SOURCE-N] markers (10–83 per paper) but no bibliography, reference list, or source identity data. BibTeX exports contain only self-citations. The missing source data is consistent with and likely downstream of the ingestion failure, but the exact data path was not traced.

**Historical fixture (10 references independently verified):**
- 3 verified (refs 1–3: Besta, Wei, Yao — clean matches)
- 4 verified_with_metadata_difference (refs 4,5,8,9 — real papers, wrong year/author/venue)
- 3 not_found (refs 6,7,10 — probable fabrications or unverified citations)

## Claim-support findings

**Live papers (6):** All cited claims classified source_unavailable. No source identity is recoverable for any [SOURCE-N] marker. Central claims are not independently substantiated by recoverable source evidence. Claim support is not independently auditable.

**Historical fixture (12 claims):**
- 3 supported (accurate background claims citing verified refs)
- 2 partially supported (real papers with metadata errors)
- 2 unsupported (claims resting on probable fabrications)
- 5 source_unavailable (internal novelty claims without citation support)
- 0 central claims supported

## Research-quality findings (10-dimension matrix)

| Paper | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 | Scope |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 29 LogicBench | PART | PASS | PART | PART | PART | PART | UNAV | PASS | FAIL | FAIL | partially_on |
| 30 Counterfactual Aud. | PART | PASS | PART | PART | PART | PART | UNAV | PASS | FAIL | FAIL | on_scope |
| 39 Q-Sym | PART | PASS | PART | PART | PART | PART | UNAV | PASS | FAIL | FAIL | **off_scope** |
| 35 MC-DA | PART | PASS | PART | PART | PART | PART | UNAV | PASS | PART | FAIL | on_scope |
| 36 TopoGAN | PART | PASS | PART | PART | PART | PART | UNAV | PASS | PART | FAIL | on_scope |
| 37 KG-for-UHI | PART | PASS | PART | PART | PART | PART | UNAV | PASS | PART | FAIL | on_scope |

Cross-cutting: all 6 papers are design+projection (no empirical results). Strongest dimensions: D2 (scope consistency) and D8 (limitations) — PASS all. Weakest: D10 references (6 FAIL), D9 conclusions (3 FAIL, 3 PARTIAL), D7 contradiction (6 UNAVAILABLE).

Scope drift: idea 39 (Q-Sym) drifted from neuro-symbolic verifiability to quantization/compression. Automated evaluation did not detect the drift.

## Automated-versus-independent comparison

**Systemic false-confidence pattern.** All 6 papers have automated paper evaluation = "ready" with positive dimension scores. The independent review found:
- 6/6 FAIL on references usable — automated eval did not detect missing bibliography
- 3/6 FAIL on conclusions — automated eval did not detect overreaching claims
- 1/6 off_scope — automated eval did not detect scope drift
- 6/6 source_unavailable on all cited claims — automated eval has no provenance check
- 6/6 no empirical results — automated eval passed design+projection papers as validated

## Historical comparison

Current papers have richer persistence, evaluation visibility, and export capabilities than the historical fixture (which lost everything when deleted). However, the historical fixture had a better bibliography (10 entries, 3 clean) compared to current papers (0 bibliography entries). Neither output is a quality gold standard.

The historical fixture's reference defects (3 probable fabrications, 4 metadata errors) are independent evidence of AI-hallucinated bibliography patterns. The current papers' complete absence of bibliography is a different but equally severe citation-integrity failure.

## User effort

| Metric | Result |
|---|---|
| Required inputs | 1 per run (research question or domain) |
| Manual actions after submission | 0 (pipeline completes autonomously) |
| Elapsed to completed paper | ~55–60 minutes per run |
| Could user understand failures | Partially — UI shows stage progress; failures visible but ingestion/novelty failures not prominent |

## Blockers / Improvements / Ideas

### Blockers
| ID | Description |
|---|---|
| Missing bibliography | Papers contain [SOURCE-N] markers but no bibliography or reference list — severe citation-integrity failure |
| Ingestion failure (B-06) | Embedding failures prevent literature indexing → no resolved references |
| Overreaching conclusions | 3/6 papers claim demonstration without empirical evidence |
| Automated eval false confidence | Evaluator reports "ready" on papers with missing provenance and scope drift |

### Improvements
| ID | Description |
|---|---|
| Scope drift detection | Automated evaluator should check paper topic against frozen input |
| Provenance propagation | Trace the reference data path from ingestion → paper synthesis to identify where source identity is lost |
| Empirical validation | Papers should be labeled as "design+projection" not "ready" when no results exist |
| Novelty governed runtime (B-07) | Restore governed vector runtime for novelty checking |
| Gap analysis diagnostics (B-09) | Root cause of intermittent empty gaps still unknown |

### Ideas
None recorded.

## Product-readiness outcome

### **QUALITY_REMEDIATION_REQUIRED**

The live workflow completes reliably: three frozen assignments produced six persisted, evaluated, exportable full papers through z.ai glm-4.6, including one through the actual UI. The pipeline's persistence, evaluation, and export infrastructure works end-to-end after blocker repairs.

However, citation integrity is materially deficient:
- Papers contain citation markers but no bibliography or resolvable references
- No cited claim can be independently assessed for source support
- The automated evaluator reports positive results on papers with missing provenance
- One paper drifted off-scope without detection
- Three papers claim demonstration without empirical evidence

These are quality-remediation defects, not architectural blockers. The pipeline produces output; the output requires remediation before it can be trusted as a research product.

This proceeds to Phase 4 with quality defects as the priority:
1. Restore ingestion and reference propagation (B-06 and the missing-bibliography defect)
2. Add provenance checking to the automated evaluator
3. Address scope-drift detection
4. Address conclusion-overreach detection

## Controlled integration results

**4 passed** (Phase 1 + Phase 2 controlled integrations).

## Architecture result

**41 passed, 0 failed.**

## Ranking result

**253 passed, 3 skipped.**

## Frontend result

**988 tests, build clean, budgets hold.**

## Full backend selector

**138 failed, 4643 passed, 47 skipped.** 2 new vs Phase 2 baseline = B-09 caplog test-isolation artifacts (not production defects).

## Production-code changes

6 files across 6 commits: pipeline.py, model_manager.py, catalog.py, openai_provider.py, stages.py (2 changes), gap_analyzer.py, pubmed_source.py, search_service.py. Plus 4 focused test files.

## Known limitations

1. **No bibliography in any live paper** — the primary quality defect
2. **Ingestion failure persists** — literature not indexed → no resolved sources
3. **All papers are design+projection** — no empirical results
4. **Automated evaluator gives false confidence** — reports "ready" on papers lacking provenance
5. **Scope drift occurred** (1/6 papers) without automated detection
6. **B-09 gap-analysis root cause unknown** — intermittent empty gaps

## P1E artifacts changed = 0

## Retrieval architecture changed = 0

## Working tree status

**clean** at closeout.

---

## Phase 3 completion criteria

| Criterion | Status |
|---|---|
| provider/model and spend cap frozen | ✅ |
| three specified live assignments attempted | ✅ all three completed |
| at least Run A used the actual UI | ✅ |
| all runs used the production orchestration path | ✅ |
| live configuration and executed stages recorded | ✅ |
| completed papers persistence-checked | ✅ 6/6 ready, 2/2 failed preserved |
| Markdown/LaTeX/BibTeX exports content-checked | ✅ all non-empty and stable |
| references independently checked | ✅ 0 live + 10 historical audited |
| central claims reviewed | ✅ all classified |
| historical/current compared | ✅ without treating either as truth |
| automated/independent compared | ✅ false confidence identified |
| user effort recorded | ✅ |
| Blockers/Improvements/Ideas classified | ✅ |
| product-readiness outcome assigned | ✅ QUALITY_REMEDIATION_REQUIRED |
| no aggregate score | ✅ |
| no prompt/retrieval tuning | ✅ |
| controlled integrations pass | ✅ |
| architecture/ranking/frontend pass | ✅ |
| full backend state reported honestly | ✅ |
| P1E artifacts changed = 0 | ✅ |
| retrieval architecture changed = 0 | ✅ |
| working tree clean | ✅ |

---

*End of Phase 3. Outcome: QUALITY_REMEDIATION_REQUIRED.*
