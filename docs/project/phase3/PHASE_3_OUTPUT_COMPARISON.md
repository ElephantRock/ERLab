# Phase 3 Output Comparison + Automated-vs-Independent + Historical Comparison

> No aggregate score computed. All comparisons are non-averaged.

---

## 1. Historical Output Comparison

### Workflow comparison

| Dimension | Historical GoT×NSR | Current Run A (UI, idea 39) | Current Run A (API, ideas 29/30) |
|---|---|---|---|
| Input path | Unknown (pipeline-generated, 2026-05) | UI `/pipeline/new` form | Production API `POST /pipeline/run` |
| Manual actions | Unknown | 0 after submission | 0 after submission |
| Completion behavior | Completed with paper | Completed (1 paper ready, 1 failed) | Completed (2 papers ready) |
| Persistence | No persistence survived (deleted in Phase 0) | Persisted on Proposal row, reloadable | Persisted on Proposal row, reloadable |
| Evaluation visibility | None survived | Paper eval (scope=paper, 7-dim), proposal eval | Same |
| Trust & Sources | Not available | 0 resolved sources | 0 resolved sources |
| Export formats | Unknown | Markdown/LaTeX/BibTeX (non-empty) | Same |
| Provenance availability | None (deleted) | Run artifacts in data/runs/ + DB | Same |

### Artifact structure comparison

| Dimension | Historical GoT×NSR | Current papers (avg) |
|---|---|---|
| Word count | 4,347 | 2,334–2,807 |
| Section inventory | 8 sections + appendix | 7–9 sections |
| Abstract | Yes (~200 words) | Yes (~150–250 words) |
| Methodology description | Detailed (3 studies described) | Formal problem definition + loss function |
| Gap claims | 17 gaps across 3 studies | 1–3 gaps per paper |
| Proposal/contribution count | 6 proposals | 1 proposal per paper |
| Citation-marker style | `[N]` numbered references | `[SOURCE-N]` positional markers |
| Bibliography | 10-entry numbered bibliography | **NONE** |
| Limitations | Yes (4 specific limitations) | Yes (material and specific) |
| Empirical results | None (survey/gap-analysis paper) | None (design+projection papers) |

### Independently reviewed quality comparison

| Dimension | Historical fixture | Current Run A papers |
|---|---|---|
| Scope adherence | On-scope (GoT×NSR topic) | 2 partially-on-scope (29, 30), 1 off-scope (39) |
| Reference existence | 3/10 verified, 4/10 verified-with-errors, 3/10 not-found | 0/0 verifiable (no bibliography) |
| Metadata accuracy | 4/10 have metadata errors | N/A (no references) |
| Claim support | 3 supported, 2 partially, 2 unsupported, 5 unavailable | All source_unavailable |
| Central-claim substantiation | 0/5 central claims supported | 0/2 central claims supported |
| Novelty qualification | Partially qualified (hedged but unverifiable) | Partially qualified (same) |
| Conclusion support | Weak (claims of demonstration without empirical evidence) | 2 FAIL, 1 PARTIAL for overreaching conclusions |

---

## 2. Automated-vs-Independent Comparison

For every current paper, placing automated and independent findings side by side:

### Idea 29 (LogicBench)

| Aspect | Automated finding | Independent finding | Interpretation |
|---|---|---|---|
| Paper evaluation | ready, 7-dim (novelty=0.7) | D9=FAIL (claims demonstration without evidence) | **False confidence**: automated eval passed; conclusion overreaches |
| Proposal evaluation | present | N/A (not independently assessed) | — |
| Citation audit | 0 sources | 0 bibliography, markers unresolvable | Consistent failure |
| Claim support | N/A | source_unavailable (all claims) | Not independently substantiated |
| References usable | N/A | FAIL | Citations demonstrably unusable |

### Idea 30 (Symbolic Counterfactual Auditing)

| Aspect | Automated finding | Independent finding | Interpretation |
|---|---|---|---|
| Paper evaluation | ready, 7-dim | D9=FAIL | **False confidence** |
| Claim support | N/A | source_unavailable | Not independently substantiated |
| References | N/A | FAIL | Unusable |

### Idea 39 (Q-Sym — OFF SCOPE)

| Aspect | Automated finding | Independent finding | Interpretation |
|---|---|---|---|
| Paper evaluation | ready, 7-dim | D9=FAIL + off_scope | **False confidence + scope drift undetected** |
| Claim support | N/A | source_unavailable | Not independently substantiated |
| References | N/A | FAIL | Unusable |
| Scope | N/A | off_scope (quantization, not verifiability) | **Automated eval did not detect scope drift** |

### Idea 35 (MC-DA)

| Aspect | Automated finding | Independent finding | Interpretation |
|---|---|---|---|
| Paper evaluation | ready, 7-dim | D9=PARTIAL, scope=on_scope | Softer — hedged conclusions |
| Claim support | N/A | source_unavailable | Not independently substantiated |
| References | N/A | FAIL | Unusable |

### Idea 36 (TopoGAN)

| Aspect | Automated finding | Independent finding | Interpretation |
|---|---|---|---|
| Paper evaluation | ready, 7-dim | D9=PARTIAL, scope=on_scope | Softer |
| Claim support | N/A | source_unavailable | Not independently substantiated |
| References | N/A | FAIL | Unusable |

### Idea 37 (KG-for-UHI-LCA)

| Aspect | Automated finding | Independent finding | Interpretation |
|---|---|---|---|
| Paper evaluation | ready, 7-dim | D9=PARTIAL, scope=on_scope (title concern unfounded) | Softer |
| Claim support | N/A | source_unavailable | Not independently substantiated |
| References | N/A | FAIL | Unusable |

### False-confidence summary

**All 6 papers have automated paper evaluation = "ready" with positive dimension scores.** The independent review found:
- **6/6 FAIL on references usable** — automated eval did not detect missing bibliography
- **3/6 FAIL on conclusions** — automated eval did not detect overreaching claims
- **1/6 off_scope** — automated eval did not detect scope drift
- **6/6 source_unavailable on all cited claims** — automated eval has no provenance check
- **6/6 no empirical results** — automated eval passed design+projection papers as if validated

This is a systemic false-confidence pattern: the automated evaluator reports positive results for papers that lack verifiable provenance, contain overreaching conclusions, and in one case answer the wrong question.

---

## 3. Defect Ledger

| ID | Description | Severity | Blocks |
|---|---|---|---|
| B-06 | Ingestion embedding failure → no resolved references | Severe | Citation integrity, source review |
| B-07 | Novelty governed vector runtime mismatch | Moderate | Novelty checking (non-fatal) |
| B-09 | Gap analysis empty-output boundary (diagnostic only) | Moderate | Gap quality (intermittent) |
| Missing bibliography | Papers contain [SOURCE-N] markers but no bibliography | Severe | Citation usability |
| Overreaching conclusions | 3/6 papers claim demonstration without evidence | Material | Scientific validity |
| Scope drift | 1/6 papers (Q-Sym) answers wrong question | Material | Product reliability |
| No empirical results | All 6 papers are design+projection only | Material | Research validity |
| Automated eval false confidence | Evaluator reports "ready" on papers with missing provenance | Severe | Trust in automated checks |

---

*End of output comparison. No aggregate scores computed.*
